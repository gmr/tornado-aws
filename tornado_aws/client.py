"""

"""
import hashlib
import hmac
import logging
import time
from email import utils

from tornado import httpclient

from tornado_aws import config

LOGGER = logging.getLogger(__name__)

ALGORITHM = 'AWS4-HMAC-SHA256'


class AWSClient(object):
    """Implement a low level AWS client that performs the request signing
    required for AWS API requests.

    :py:class:`AWSClient`` uses the same configuration method and environment
    variables as the AWS CLI. For configuration information visit the "Getting
    Set Up" section of the `AWS Command Line Interface user guide
    <http://docs.aws.amazon.com/cli/latest/userguide/>`_

    When creating the :py:class`AWSClient` instance you need to specify the
    ``service`` that you will be interacting with. This value is used when
    signing the request headers and must match the service values as specified
    in the `AWS General Reference documentation
    <http://docs.aws.amazon.com/general/latest/gr/Welcome.html>`_.


    The AWS configuration profile can be set when creating the
    :py:class:`AWSClient` instance or by setting the ``AWS_DEFAULT_PROFILE``
    environment variable. If neither are set, ``default`` will be used.

    The AWS region can be specified when creating a new instance or



     ``It will load configuration from ``~/.aws/config`` and
    ``~/.aws/credentials`` if the paths are not set in ``AWS_CONFIG_FILE`` and
    ``AWS_SHARED_CREDENTIALS_FILE`` environment files. The ``default`` profile
    will be used if the  is not set.

    .. _docs:

    :param str service: The service for the API calls
    :param str profile: Specify the configuration profile name
    :param str region:
    :param str access_key:
    :param str secret_key:

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



    def fetch(self, method, uri, headers, body=None):



        pass

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

        :rtype: tornado.httpclient.HTTPClient

        """
        return httpclient.HTTPClient()

    @staticmethod
    def _rfc822_date():
        """Returns the current time in UTC as a RFC-822 formatted timestamp

        :rtype: str

        """
        return utils.formatdate(time.time(), usegmt=True)



class AsyncAWSClient(AWSClient):
    """

    """
    def __init__(self, service, profile=None, region=None, access_key=None,
                 secret_key=None, max_clients=100):
        self._max_clients = max_clients
        super(AsyncAWSClient, self).__init__(service, profile, region,
                                             access_key, secret_key)

    def _get_client_adapter(self):
        """Return an asynchronous HTTP client adapter

        :rtype: tornado.httpclient.AsyncHTTPClient

        """
        return httpclient.AsyncHTTPClient(max_clients=self._max_clients)
