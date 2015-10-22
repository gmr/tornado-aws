"""
The AWS ...

"""
import hashlib
import hmac
import logging
import time
from email import utils

from tornado import gen
from tornado import httpclient

from tornado_aws import config

LOGGER = logging.getLogger(__name__)

ALGORITHM = 'AWS4-HMAC-SHA256'


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
    :py:class:`AWSClient` instance or by setting the ``AWS_DEFAULT_PROFILE``
    environment variable. If neither are set, ``default`` will be used.

    The AWS region can be specified when creating a new instance or

    :param str service: The service for the API calls
    :param str profile: Specify the configuration profile name
    :param str region: The AWS region to make requests to
    :param str access_key: The access key
    :param str secret_key: The secret access key

    """
    CONNECT_TIMEOUT = 10
    REQUEST_TIMEOUT = 30

    def __init__(self, service, profile=None, region=None,
                 access_key=None, secret_key=None):
        self._adapter = self._get_client_adapter()
        self._service = service
        self._profile = profile
        self._region, self._access_key, self._secret_key = \
            self._get_config(region, access_key, secret_key)

    def fetch(self, method, uri, headers, body=None, raise_error=None):
        """Executes a request, returning an
        :py:class:`HTTPResponse <tornado.httpclient.HTTPResponse>`.

        If an error occurs during the fetch, we raise an
        :py:class:`HTTPError <tornado.httpclient.HTTPError>` unless the
        ``raise_error`` keyword argument is set to ``False``.

        :param str method: HTTP request method
        :param str uri: The request URL
        :param dict headers: Request headers
        :param str body: The request body
        :rtype: :py:class:`tornado.httpclient.HTTPResponse`
        :raises: :py:class:`tornado.httpclient.HTTPError`

        """
        request = httpclient.HTTPRequest(uri, method, headers, body)
        return self._adapter.fetch(request, raise_error=raise_error)

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
    def _rfc822_date():
        """Returns the current time in UTC as a RFC-822 formatted timestamp

        :rtype: str

        """
        return utils.formatdate(time.time(), usegmt=True)


class AsyncAWSClient(AWSClient):
    """Implement an asynchronous low level AWS client that performs the request
    signing required for AWS API requests.


    The keyword argument ``max_clients`` determines the maximum number of
    simultaneous :py:meth:`fetch() <AsyncAWSWait.fetch>` operations that can
    execute in parallel on each :py:class:`IOLoop <tornado.ioloop.IOLoop>`.

    :param str service: The service for the API calls
    :param str profile: Specify the configuration profile name
    :param str region: The AWS region to make requests to
    :param str access_key: The access key
    :param str secret_key: The secret access key
    :param int max_clients: Max simultaneous HTTP requests (Default: ``100``)

    """
    def __init__(self, service, profile=None, region=None, access_key=None,
                 secret_key=None, max_clients=100):
        self._max_clients = max_clients
        super(AsyncAWSClient, self).__init__(service, profile, region,
                                             access_key, secret_key)

    @gen.coroutine
    def fetch(self, method, uri, headers, body=None, raise_error=None):
        """Executes a request, returning an
        :py:class:`HTTPResponse <tornado.httpclient.HTTPResponse>`.

        If an error occurs during the fetch, we raise an
        :py:class:`HTTPError <tornado.httpclient.HTTPError>` unless the
        ``raise_error`` keyword argument is set to ``False``.

        :param str method: HTTP request method
        :param str uri: The request URL
        :param dict headers: Request headers
        :param str body: The request body
        :rtype: :py:class:`tornado.httpclient.HTTPResponse`
        :raises: :py:class:`tornado.httpclient.HTTPError`

        """
        request = httpclient.HTTPRequest(uri, method, headers, body)
        response = yield self._adapter.fetch(request, raise_error=raise_error)
        raise gen.Return(response)

    def _get_client_adapter(self):
        """Return an asynchronous HTTP client adapter

        :rtype: :py:class:`tornado.httpclient.AsyncHTTPClient`

        """
        return httpclient.AsyncHTTPClient(max_clients=self._max_clients)
