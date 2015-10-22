"""
The :py:class:`AWSClient` and :py:class:`AsyncAWSClient` implement low-level
AWS clients. The clients provide only the mechanism for submitted signed HTTP
requests to the AWS APIs and are generally meant to be used by service specific
client API implementations.

"""
import datetime
import hashlib
import hmac
import logging
try:
    from urllib import parse as _urlparse
except ImportError:
    import urlparse as _urlparse

from tornado import httpclient

from tornado_aws import config

LOGGER = logging.getLogger(__name__)

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
    CONNECT_TIMEOUT = 10
    REQUEST_TIMEOUT = 30
    SCHEME = 'https'

    def __init__(self, service, profile=None, region=None,
                 access_key=None, secret_key=None, endpoint=None):
        self._service = service
        self._profile = profile
        self._region, self._access_key, self._secret_key = \
            self._get_config(region, access_key, secret_key)
        self._endpoint_url = self._endpoint(endpoint)
        self._host = self._hostname(self._endpoint_url)

    def fetch(self, method, path='/', query_args=None, headers=None, body=b'',
              raise_error=False):
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
        :rtype: :py:class:`tornado.httpclient.HTTPResponse`

        """
        signed_headers, signed_url = \
            self._signed_request(method, path, query_args or {}, dict(headers),
                                 body)
        request = httpclient.HTTPRequest(signed_url, method,
                                         signed_headers, body,
                                         connect_timeout=self.CONNECT_TIMEOUT,
                                         request_timeout=self.REQUEST_TIMEOUT)
        adapter = self._get_client_adapter()
        response = adapter.fetch(request, raise_error=raise_error)
        adapter.close()
        return response

    def _auth_header(self, amz_date, date_stamp, request_hash, signed_headers):
        """Return the Authorization string header value

        :param str amz_date: The x-amz-date header value
        :param str date_stamp: The signing date_stamp
        :param str request_hash: The SHA-256 request hash
        :param str signed_headers: A semicolon delimited list of header keys
        :rtype: str

        """
        scope, signature = self._signature(amz_date, date_stamp, request_hash)
        return _HEADER_FORMAT.format(self.ALGORITHM, self._access_key, scope,
                                     signed_headers, signature)

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

    def _get_config(self, region, access_key, secret_key):
        """Get the negotiated configuration, preferring values that were passed
        in to the client and using any values returned from the file based
        configuration where values are missing.

        :param str region: The AWS region
        :param str access_key: Access key that was passed in to the constructor
        :param str secret_key: Secret key that was passed in to the constructor
        :rtype: str, str, str
        :return: region, access_key, secret_key

        """
        if not region or not access_key or not secret_key:
            _region, _access_key, _secret_key = config.get(self._profile)
            return (region or _region,
                    access_key or _access_key,
                    secret_key or _secret_key)
        return region, access_key, secret_key

    def _get_client_adapter(self):
        """Return a HTTP client

        :rtype: :py:class:`tornado.httpclient.HTTPClient`

        """
        return httpclient.HTTPClient()

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
            'Content-Length': len(body),
            'Date': amz_date,
            'Host': self._host,
            'X-Amz-Content-sha256': payload_hash
        })

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
        key = 'AWS4{0}'.format(self._secret_key)
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
    def __init__(self, service, profile=None, region=None, access_key=None,
                 secret_key=None, endpoint=None, max_clients=100):
        super(AsyncAWSClient, self).__init__(service, profile, region,
                                             access_key, secret_key, endpoint)
        self._max_clients = max_clients

    def _get_client_adapter(self):
        """Return an asynchronous HTTP client adapter

        :rtype: :py:class:`tornado.httpclient.AsyncHTTPClient`

        """
        return httpclient.AsyncHTTPClient(max_clients=self._max_clients)
