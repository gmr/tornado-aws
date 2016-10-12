"""
The :py:class:`AWSClient` and :py:class:`AsyncAWSClient` implement low-level
AWS clients. The clients provide only the mechanism for submitted signed HTTP
requests to the AWS APIs and are generally meant to be used by service specific
client API implementations.

"""
import datetime
import hashlib
import hmac
import json
import logging
import os
try:
    from urllib import parse as _urlparse
except ImportError:
    import urlparse as _urlparse

from tornado import concurrent, httpclient, ioloop

from tornado_aws import config, exceptions

LOGGER = logging.getLogger(__name__)

MIME_AWZ_JSON = 'application/x-amz-json-1.0'

_REFRESH_EXCEPTIONS = [
    'com.amazon.coral.service#InvalidSignatureException',
    'com.amazon.coral.service#UnrecognizedClientException',
    'com.amazon.coral.service#ExpiredTokenException'
]

_HEADER_FORMAT = '{0} Credential={1}/{2}, SignedHeaders={3}, Signature={4}'


class AWSClient(object):
    """Implement a low level AWS client that performs the request signing
    required for AWS API requests.

    ``AWSClient`` uses the same configuration method and environment
    variables as the AWS CLI. For configuration information visit the "Getting
    Set Up" section of the `AWS Command Line Interface user guide
    <http://docs.aws.amazon.com/cli/latest/userguide/>`_.

    When creating the ``AWSClient`` instance you need to specify the
    ``service`` that you will be interacting with. This value is used when
    signing the request headers and must match the service values as specified
    in the `AWS General Reference documentation
    <http://docs.aws.amazon.com/general/latest/gr/Welcome.html>`_.

    The AWS configuration profile can be set when creating the
    ``AWSClient`` instance or by setting the ``AWS_DEFAULT_PROFILE``
    environment variable. If neither are set, ``default`` will be used.

    The AWS region is set by reading in configuration or by the
    ``AWS_DEFAULT_REGION`` environment variable. If neither or set, it will
    attempt to be set by invoking the EC2 Instance Metadata and user data API,
    if available.

    The AWS access key can be set when creating a new instance. If it's not
    passed in when creating the ``AWSClient``, the client will attempt to
    get the key from the ``AWS_ACCESS_KEY_ID`` environment variable. If that is
    not set, it will attempt to get the key from the AWS CLI credentials file.
    The path to the credentials file can be overridden in the
    ``AWS_SHARED_CREDENTIALS_FILE`` environment variable. Note that a value
    set in ``AWS_ACCESS_KEY_ID`` will only be used if there is an accompanying
    value in ``AWS_SECRET_ACCESS_KEY`` environment variable.

    Like the access key, the secret key can be set when creating a new client
    instance. The configuration logic matches the access key with the exception
    of the environment variable. The secret key can set in the
    ``AWS_SECRET_ACCESS_KEY`` environment variable.

    If there is no local configuration or credentials, the client will attempt
    to load the information from the EC2 instance meta-data API, if it is
    available.

    The ``endpoint`` argument is primarily used for testing and allows for
    the use of a specified base URL value instead of the auto-construction of
    a URL using the service and region variables.

    :param str service: The service for the API calls
    :param str profile: Specify the configuration profile name
    :param str region: The AWS region to make requests to
    :param str access_key: The access key
    :param str secret_key: The secret access key
    :param str endpoint: Override the base endpoint URL
    :raises: :py:class:`tornado_aws.exceptions.ConfigNotFound`
    :raises: :py:class:`tornado_aws.exceptions.ConfigParserError`
    :raises: :py:class:`tornado_aws.exceptions.NoCredentialsError`
    :raises: :py:class:`tornado_aws.exceptions.NoProfileError`

    """
    ALGORITHM = 'AWS4-HMAC-SHA256'
    ASYNC = False
    CONNECT_TIMEOUT = 10
    REQUEST_TIMEOUT = 30
    SCHEME = 'https'

    def __init__(self, service, profile=None, region=None,
                 access_key=None, secret_key=None, endpoint=None):
        self._service = service
        self._profile = profile or os.getenv('AWS_DEFAULT_PROFILE', 'default')
        self._region = region or config.get_region(profile)
        self._client = self._get_client_adapter()
        self._auth_config = config.Authorization(self._profile, access_key,
                                                 secret_key, self._client)
        self._endpoint_url = self._endpoint(endpoint)
        self._host = self._hostname(self._endpoint_url)

    def fetch(self, method, path='/', query_args=None, headers=None, body=b'',
              _recursed=False):
        """Executes a request, returning an
        :py:class:`HTTPResponse <tornado.httpclient.HTTPResponse>`.

        If an error occurs during the fetch, we raise an
        :py:class:`HTTPError <tornado.httpclient.HTTPError>` unless the
        ``raise_error`` keyword argument is set to ``False``.

        :param str method: HTTP request method
        :param str path: The request path
        :param dict query_args: Request query arguments
        :param dict headers: Request headers
        :param bytes body: The request body
        :rtype: :class:`~tornado.httpclient.HTTPResponse`
        :raises: :class:`~tornado.httpclient.HTTPError`
        :raises: :class:`~tornado_aws.exceptions.NoCredentialsError`
        :raises: :class:`~tornado_aws.exceptions.AWSError`

        """
        if self._auth_config.needs_credentials():
            self._auth_config.refresh()

        request = self._create_request(method, path, query_args, headers, body)

        try:
            result = self._client.fetch(request, raise_error=True)
            return result
        except httpclient.HTTPError as error:
            awz_error = self._awz_error(error)
            if awz_error:
                if self._credentials_error(awz_error):
                    if not self._auth_config.local_credentials:
                        if not _recursed:
                            self._auth_config.refresh()
                            return self.fetch(method, path, query_args,
                                              headers, body, True)
                        else:
                            self._auth_config.reset()

                raise exceptions.AWSError(type=awz_error['__type'],
                                          message=awz_error['message'])
            raise

    def _auth_header(self, amz_date, date_stamp, request_hash, signed_headers):
        """Return the Authorization string header value

        :param str amz_date: The x-amz-date header value
        :param str date_stamp: The signing date_stamp
        :param str request_hash: The SHA-256 request hash
        :param str signed_headers: A semicolon delimited list of header keys
        :rtype: str

        """
        scope, signature = self._signature(amz_date, date_stamp, request_hash)
        return _HEADER_FORMAT.format(self.ALGORITHM,
                                     self._auth_config.access_key,
                                     scope,
                                     signed_headers, signature)

    @staticmethod
    def _awz_error(error):
        """Returns the AWZ error parsed out of the HTTPError that was raised.

        :param tornado.httpclient.HTTPError error: The error that was raised
        :rtype: dict|None

        """
        if not isinstance(error, httpclient.HTTPError):
            return
        if error.code == 400:
            payload = json.loads(error.response.body.decode('utf-8'))
            if isinstance(payload, dict) and '__type' in payload:
                return payload

    def _create_request(self, method, path='/', query_args=None, headers=None,
                        body=b''):
        """Create the HTTPRequest instance that will be used to make the AWS
        API request.

        :param str method: HTTP request method
        :param str path: The request path
        :param dict query_args: Request query arguments
        :param dict headers: Request headers
        :param bytes body: The request body
        :rtype: tornado.httpclient.HTTPClient

        """
        if headers is None:
            headers = {}
        (signed_headers,
         signed_url) = self._signed_request(method, path, query_args or {},
                                            dict(headers), body or b'')

        return httpclient.HTTPRequest(signed_url, method,
                                      signed_headers, body,
                                      connect_timeout=self.CONNECT_TIMEOUT,
                                      request_timeout=self.REQUEST_TIMEOUT)

    def _endpoint(self, endpoint):
        """Return the user specified endpoint or dynamically create the
        endpoint from the service and region.

        :rtype: str

        """
        if endpoint:
            return endpoint
        return '{}://{}.{}.amazonaws.com'.format(self.SCHEME,
                                                 self._service,
                                                 self._region)

    @staticmethod
    def _get_client_adapter():
        """Return a HTTP client

        :rtype: :py:class:`tornado.httpclient.HTTPClient`

        """
        return httpclient.HTTPClient(force_instance=True)

    @staticmethod
    def _hostname(url):
        """Parse the url returning a named tuple with the parts of the
        the parsed URL

        :param str url: The URL to parse
        :return: str

        """
        return _urlparse.urlparse(url).netloc

    @staticmethod
    def _quote(value):
        """Return the percent encoded value, ensuring there are no skipped
        characters.

        :param str value: The value to quote
        :rtype: str

        """
        return _urlparse.quote(value, safe='').replace('%7E', '~')

    def _credentials_error(self, error):
        """Returns ``True`` if the the error is related to authentication
        errors that could be remedied by loading from ECS metadata and user
        data API.

        :param dict error: The AWZ error response
        :rtype: bool

        """
        if self._auth_config.local_credentials:
            return False
        return error['__type'] in _REFRESH_EXCEPTIONS

    @staticmethod
    def _sign(key, msg):
        """Sign the msg with the key

        :param bytes key: The signing key
        :param bytes msg: The value to sign
        :return: bytes

        """
        return hmac.new(key, msg, hashlib.sha256).digest()

    def _signed_request(self, method, path, query_args, headers, body):
        """Create the request signature headers and return updated headers
         for the request.

        :param str method: HTTP request method
        :param str path: The request path
        :param dict query_args: Query string args
        :param dict headers: Request headers
        :param bytes body: The request body
        :rtype: dict

        """
        if isinstance(body, str):
            body = body.encode('utf-8')

        query_string = self._query_string(query_args)

        timestamp = datetime.datetime.utcnow()
        amz_date = timestamp.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = timestamp.strftime('%Y%m%d')

        payload_hash = hashlib.sha256(body).hexdigest()

        headers.update({
            'Content-Length': str(len(body)),
            'Date': amz_date,
            'Host': self._host,
            'X-Amz-Content-sha256': payload_hash
        })

        # Temporary auth security token
        if self._auth_config.security_token:
            headers['X-Amz-Security-Token'] = self._auth_config.security_token

        signed_headers, headers_string = self._signed_headers(headers)

        request = '\n'.join([method, path, query_string, headers_string,
                             signed_headers, payload_hash])
        request_hash = hashlib.sha256(request.encode('utf-8')).hexdigest()

        headers['Authorization'] = self._auth_header(amz_date, date_stamp,
                                                     request_hash,
                                                     signed_headers)

        return headers, '{0}{1}?{2}'.format(self._endpoint_url, path,
                                            query_string)

    def _query_string(self, query_args):
        """Return the sorted query string from the query args dict

        :param dict query_args: The dict of query arguments
        :rtype: str

        """
        return '&'.join(['{0}={1}'.format(self._quote(k),
                                          self._quote(query_args[k]))
                         for k in sorted(query_args.keys())])

    def _signature(self, amz_date, date_stamp, request_hash):
        """Return the request scope and signature

        :param str date_stamp: The signing date stamp
        :param str amz_date: The x-amz-date header value
        :param str request_hash: The canonical request signature hash
        :rtype: str, str

        """
        scope = '/'.join([date_stamp, self._region, self._service,
                          'aws4_request'])
        to_sign = '\n'.join([self.ALGORITHM, amz_date, scope, request_hash])
        signing_key = self._signing_key(date_stamp)
        return scope, hmac.new(signing_key, to_sign.encode('utf-8'),
                               hashlib.sha256).hexdigest()

    @staticmethod
    def _signed_headers(headers):
        """Create and return the canonical headers string and the signed
        headers list.

        Canonical header names must be trimmed and lowercase, and sorted in
        ASCII order.

        The signed headers lists the headers in the canonical_headers list,
        delimited with ";" and in alpha order.

        :param dict headers: The request headers
        :rtype: str, str

        """
        tmp = dict([(key.lower(), value) for key, value in headers.items()])
        signed_headers = ';'.join([k.lower() for k in sorted(tmp.keys())])
        headers_string = '\n'.join(['{0}:{1}'.format(k, tmp[k])
                                    for k in sorted(tmp.keys())]) + '\n'
        return signed_headers, headers_string

    def _signing_key(self, date_stamp):
        """Create the signature key for the request.

        :param str date_stamp: Date in %Y%m%d format for signing
        :rtype: bytes

        """
        key = 'AWS4{0}'.format(self._auth_config.secret_key)
        date = self._sign(key.encode('utf-8'), date_stamp.encode('utf-8'))
        region = self._sign(date, self._region.encode('utf-8'))
        service = self._sign(region, self._service.encode('utf-8'))
        return self._sign(service, b'aws4_request')


class AsyncAWSClient(AWSClient):
    """Implement a low level AWS client that performs the request signing
    required for AWS API requests.

    ``AWSClient`` uses the same configuration method and environment
    variables as the AWS CLI. For configuration information visit the "Getting
    Set Up" section of the `AWS Command Line Interface user guide
    <http://docs.aws.amazon.com/cli/latest/userguide/>`_.

    When creating the ``AWSClient`` instance you need to specify the
    ``service`` that you will be interacting with. This value is used when
    signing the request headers and must match the service values as specified
    in the `AWS General Reference documentation
    <http://docs.aws.amazon.com/general/latest/gr/Welcome.html>`_.

    The AWS configuration profile can be set when creating the
    ``AWSClient`` instance or by setting the ``AWS_DEFAULT_PROFILE``
    environment variable. If neither are set, ``default`` will be used.

    The AWS access key can be set when creating a new instance. If it's not
    passed in when creating the ``AWSClient``, the client will attempt to
    get the key from the ``AWS_ACCESS_KEY_ID`` environment variable. If that is
    not set, it will attempt to get the key from the AWS CLI credentials file.
    The path to the credentials file can be overridden in the
    ``AWS_SHARED_CREDENTIALS_FILE`` environment variable. Note that a value
    set in ``AWS_ACCESS_KEY_ID`` will only be used if there is an accompanying
    value in ``AWS_SECRET_ACCESS_KEY`` environment variable.

    Like the access key, the secret key can be set when creating a new client
    instance. The configuration logic matches the access key with the exception
    of the environment variable. The secret key can set in the
    ``AWS_SECRET_ACCESS_KEY`` environment variable.

    The ``endpoint`` argument is primarily used for testing and allows for
    the use of a specified base URL value instead of the auto-construction of
    a URL using the service and region variables.

    ``max_clients`` allows for the specification of the maximum number if
    concurrent asynchronous HTTP requests that the client will perform.

    :param str service: The service for the API calls
    :param str profile: Specify the configuration profile name
    :param str region: The AWS region to make requests to
    :param str access_key: The access key
    :param str secret_key: The secret access key
    :param str endpoint: Override the base endpoint URL
    :param int max_clients: Max simultaneous HTTP requests (Default: ``100``)
    :raises: :py:class:`tornado_aws.exceptions.ConfigNotFound`
    :raises: :py:class:`tornado_aws.exceptions.ConfigParserError`
    :raises: :py:class:`tornado_aws.exceptions.NoCredentialsError`
    :raises: :py:class:`tornado_aws.exceptions.NoProfileError`

    """
    ASYNC = True

    def __init__(self, service, profile=None, region=None, access_key=None,
                 secret_key=None, endpoint=None, max_clients=100):
        self._ioloop = ioloop.IOLoop.current()
        self._max_clients = max_clients
        super(AsyncAWSClient, self).__init__(service, profile, region,
                                             access_key, secret_key, endpoint)

    def _get_client_adapter(self):
        """Return an asynchronous HTTP client adapter

        :rtype: :py:class:`tornado.httpclient.AsyncHTTPClient`

        """
        return httpclient.AsyncHTTPClient(max_clients=self._max_clients,
                                          force_instance=True)

    def fetch(self, method, path='/', query_args=None, headers=None, body=b'',
              _recursed=False):
        """Executes a request, returning an
        :py:class:`HTTPResponse <tornado.httpclient.HTTPResponse>`.

        If an error occurs during the fetch, we raise an
        :py:class:`HTTPError <tornado.httpclient.HTTPError>` unless the
        ``raise_error`` keyword argument is set to ``False``.

        :param str method: HTTP request method
        :param str path: The request path
        :param dict query_args: Request query arguments
        :param dict headers: Request headers
        :param bytes body: The request body
        :rtype: :class:`~tornado.httpclient.HTTPResponse`
        :raises: :class:`~tornado.httpclient.HTTPError`
        :raises: :class:`~tornado_aws.exceptions.AWSError`
        :raises: :class:`~tornado_aws.exceptions.NoCredentialsError`

        """
        future = concurrent.TracebackFuture()

        def on_response(response):
            exception = response.exception()
            if exception:
                awz_error = self._awz_error(exception)
                if awz_error:
                    if self._credentials_error(awz_error):
                        self._auth_config.reset()
                        if not self._auth_config.local_credentials:
                            if not _recursed:

                                def on_retry(retry):
                                    if not self._future_exception(retry,
                                                                  future):
                                        future.set_result(retry.result())

                                request = self.fetch(method, path, query_args,
                                                     headers, body, True)
                                self._ioloop.add_future(request, on_retry)
                                return
                    msg = aws_error.get('message', aws_error.get('Message'))
                    if not msg:
                        LOGGER.debug('awz_error without message: %r',
                                     awz_error)
                    exception = exceptions.AWSError(
                        type=awz_error['__type'], message=msg)
                future.set_exception(exception)
            else:
                future.set_result(response.result())

        def perform_request():
            request = self._create_request(method, path, query_args, headers,
                                           body)
            api_future = self._client.fetch(request, raise_error=True)
            self._ioloop.add_future(api_future, on_response)

        def on_refreshed(response):
            if not self._future_exception(response, future):
                perform_request()

        if self._auth_config.needs_credentials():
            request_future = self._auth_config.refresh()
            self._ioloop.add_future(request_future, on_refreshed)
        else:
            perform_request()

        return future

    @staticmethod
    def _future_exception(inner, outer):
        exception = inner.exception()
        if exception:
            outer.set_exception(exception)
        return bool(exception)
