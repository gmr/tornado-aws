"""
AWS Credentials Loader

"""
import configparser
import http.client
import json
import logging
import os
from os import path
import socket

from tornado import concurrent, httpclient, ioloop
try:
    from tornado import curl_httpclient
except ImportError:  # pragma: no cover
    curl_httpclient = httpclient
    curl_httpclient.CurlAsyncHTTPClient = httpclient.AsyncHTTPClient

from tornado_aws import exceptions

LOGGER = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = '~/.aws/credentials'
DEFAULT_REGION = 'us-east-1'
INSTANCE_HOST = '169.254.169.254'
INSTANCE_ENDPOINT = 'http://169.254.169.254/latest/{}'
INSTANCE_ROLE_PATH = '/meta-data/iam/security-credentials/'
INSTANCE_CREDENTIALS_PATH = '/meta-data/iam/security-credentials/{}'
REGION_PATH = '/dynamic/instance-identity/document'

HTTP_TIMEOUT = 0.25


def get_region(profile):
    """Return the credentials from the configured ~/.aws/credentials file
    following a similar behavior implemented by awscli and botocore.

    :param str profile: Use the optional profile for getting settings
    :return: region
    :rtype: str
    :raises: exceptions.ConfigNotFound

    """
    region = os.getenv('AWS_DEFAULT_REGION', None)
    if region:
        return region

    file_path = os.getenv('AWS_CONFIG_FILE', '~/.aws/config')
    try:
        config = _parse_file(file_path)
    except exceptions.ConfigNotFound:
        try:
            return _request_region_from_instance()
        except (socket.error, socket.timeout, OSError) as error:
            LOGGER.error('Error fetching from EC2 Instance Metadata (%s)',
                         error)
            raise exceptions.ConfigNotFound(path=file_path)

    key = 'profile {0}'.format(profile)
    if key not in config and 'default' not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)
    return config.get(
        key, {}).get('region') or config.get(
            'default', {}).get('region') or DEFAULT_REGION


def _is_async_client(client):
    """Returns ``True`` if the client that is passed in is asynchronous.

    :param client: The HTTP client to use for EC2 API
    :type client: tornado.httpclient.HTTPClient or
        tornado.httpclient.AsyncHTTPClient or
        tornado.curl_httpclient.CurlAsyncHTTPClient
    :rtype: bool

    """
    return isinstance(client, (httpclient.AsyncHTTPClient,
                               curl_httpclient.CurlAsyncHTTPClient))


def _parse_file(file_path):
    """Parse the specified configuration file, returning a nested dict
    of key/value pairs by section.

    :param str file_path: The path of the file to read.
    :rtype: dict

    """
    file_path = path.abspath(path.expanduser(path.expandvars(file_path)))
    LOGGER.debug('Attempting to load credentials from %s', file_path)
    if not path.exists(file_path):
        raise exceptions.ConfigNotFound(path=file_path)

    parser = configparser.RawConfigParser()
    try:
        parser.read(file_path)
    except configparser.Error as error:
        LOGGER.error('Error reading file: %s', error)
        raise exceptions.ConfigParserError(path=file_path)

    config = {}
    for section in parser.sections():
        config[section] = {}
        for option in parser.options(section):
            config[section][option] = parser.get(section, option)
    return config


def _request_region_from_instance():
    """Attempt to get the region from the instance metadata

    :rtype: str

    """
    conn = http.client.HTTPConnection(INSTANCE_HOST, timeout=3)
    conn.request('GET', INSTANCE_ENDPOINT.format(REGION_PATH),
                 headers={'Accept': 'application/json'})
    response = conn.getresponse()
    return json.loads(response.read().decode('utf-8'))['region']


class Authorization(object):
    """Object used to hold configuration information."""

    def __init__(self, profile, access_key=None, secret_key=None,
                 security_token=None, client=None):
        """Create a new instance of the ``_AuthConfig`` class.

        :param str profile: The configuration profile to use
        :param str access_key: Optional configured access key
        :param str secret_key: Optional configured secret key
        :param str security_token: Optional configured security token
        :param client: The HTTP client to use for EC2 API
        :type client: tornado.httpclient.HTTPClient or
            tornado.httpclient.AsyncHTTPClient

        """
        self._client = client
        self._profile = profile
        self._local_credentials = False
        self._access_key = None
        self._secret_key = None
        self._security_token = None
        self._expiration = None
        self._resolve_credentials(access_key, secret_key, security_token)
        self._is_async = _is_async_client(client)
        LOGGER.info('Authorization for async client: %s', self._is_async)
        self._ioloop = ioloop.IOLoop.current() if self._is_async else None

    @property
    def access_key(self):
        """Return the current access key.

        :rtype: str or None

        """
        return self._access_key

    @property
    def local_credentials(self):
        """Indicates if the credentials are loaded dynamically or if they
        are statically set upon initialization

        :rtype: bool

        """
        return self._local_credentials

    @property
    def secret_key(self):
        """Return the current secret key.

        :rtype: str or None

        """
        return self._secret_key

    @property
    def security_token(self):
        """Return the current security token value.

        :rtype: str or None

        """
        return self._security_token

    def needs_credentials(self):
        """Returns True if the client needs fetch/refresh credentials

        :rtype: bool

        """
        return not self._access_key or not self._secret_key

    def refresh(self):
        """Load dynamic credentials from the AWS Instance Metadata and user
        data HTTP API.

        :raises: tornado_aws.exceptions.NoCredentialsError

        """
        future = concurrent.Future() if self._is_async else None

        # Refresh config file credentials
        if self._local_credentials:
            future.set_result(self._resolve_credentials())
            return future

        LOGGER.debug('Refreshing EC2 IAM Credentials')
        try:
            result = self._fetch_credentials()
            if concurrent.is_future(result):

                def on_complete(response):
                    exception = response.exception()
                    if exception:
                        if isinstance(exception, httpclient.HTTPError) and \
                                exception.code == 599:
                            future.set_exception(
                                exceptions.NoCredentialsError())
                        else:
                            future.set_exception(exception)
                        return
                    self._assign_credentials(response.result())
                    future.set_result(True)

                self._ioloop.add_future(result, on_complete)
            else:
                self._assign_credentials(result)
        except (httpclient.HTTPError, OSError) as error:
            LOGGER.error('Error Fetching Credentials: %s', error)
            raise exceptions.NoCredentialsError
        return future

    def reset(self):
        """Reset the security credentials.

        :raises: tornado_aws.exceptions.LocalCredentialsError()

        """
        self._access_key = None
        self._secret_key = None
        self._expiration = None
        self._security_token = None

    def _assign_credentials(self, data):
        """Assign the values returned by the EC2 Metadata and user data API to
        the internal credentials attributes.

        :param dict data: The data returned by the EC2 api

        """
        self._access_key = data['AccessKeyId']
        self._secret_key = data['SecretAccessKey']
        self._expiration = data['Expiration']
        self._security_token = data['Token']

    def _fetch_credentials(self):
        """Fetch credential information from the local EC2 Metadata and user
        data API.

        :rtype: dict

        """
        if self._is_async:
            return self._fetch_credentials_async()
        role = self._get_role()
        credentials = self._get_instance_credentials(role)
        return credentials

    def _fetch_credentials_async(self):
        """Return the credentials from the EC2 Instance Metadata and user data
        API using an Async adapter.

        :return: :class:`~concurrent.Future`

        """
        future = concurrent.Future()

        def on_credentials(response):
            if not self._future_exception(response, future):
                result = response.result()
                future.set_result(result)

        def on_role(response):
            if not self._future_exception(response, future):
                req = self._get_instance_credentials_async(response.result())
                self._ioloop.add_future(req, on_credentials)

        request = self._get_role_async()
        self._ioloop.add_future(request, on_role)
        return future

    @staticmethod
    def _future_exception(inner, outer):
        exception = inner.exception()
        if exception:
            outer.set_exception(exception)
        return bool(exception)

    def _get_config_value(self, config, key):
        """Return the config value for the key, if it exists, checking both
        the current profile and the default profile.

        :param dict config: The config to use
        :param str key: The key to get the value for
        :rtype: str

        """
        return config[self._profile].get(
            key, config.get('default', {}).get(key))

    def _get_instance_credentials(self, role):
        """Attempt to get temporary credentials for the specified role from the
        EC2 Instance Metadata and user data API

        :param str role: The role to get temporary credentials for

        :rtype: dict
        :raises: tornado.httpclient.HTTPError

        """
        url_path = INSTANCE_CREDENTIALS_PATH.format(role)
        response = self._client.fetch(INSTANCE_ENDPOINT.format(url_path),
                                      connect_timeout=HTTP_TIMEOUT,
                                      request_timeout=HTTP_TIMEOUT)
        return json.loads(response.body.decode('utf-8'))

    def _get_instance_credentials_async(self, role):
        """Attempt to get temporary credentials for the specified role from the
        EC2 Instance Metadata and user data API

        :param str role: The role to get temporary credentials for

        :rtype: :class:`~tornado.concurrent.Future`
        :raises: tornado.httpclient.HTTPError

        """
        future = concurrent.Future()

        def on_response(response):
            if not self._future_exception(response, future):
                body = response.result().body
                future.set_result(json.loads(body.decode('utf-8')))

        url_path = INSTANCE_CREDENTIALS_PATH.format(role)
        result = self._client.fetch(INSTANCE_ENDPOINT.format(url_path),
                                    connect_timeout=HTTP_TIMEOUT,
                                    request_timeout=HTTP_TIMEOUT)
        self._ioloop.add_future(result, on_response)
        return future

    def _get_role(self):
        """Fetch the IAM role from the ECS Metadata and user data API

        :rtype: str
        :raises: tornado.httpclient.HTTPError

        """
        url = INSTANCE_ENDPOINT.format(INSTANCE_ROLE_PATH)
        response = self._client.fetch(url,
                                      connect_timeout=HTTP_TIMEOUT,
                                      request_timeout=HTTP_TIMEOUT)
        return response.body.decode('utf-8')

    def _get_role_async(self):
        """Fetch the IAM role from the ECS Metadata and user data API

        :rtype: :class:`~tornado.concurrent.Future`
        :raises: tornado.httpclient.HTTPError

        """
        future = concurrent.Future()

        def on_response(response):
            if not self._future_exception(response, future):
                role = response.result()
                future.set_result(role.body.decode('utf-8'))

        url = INSTANCE_ENDPOINT.format(INSTANCE_ROLE_PATH)
        request = self._client.fetch(url,
                                     connect_timeout=HTTP_TIMEOUT,
                                     request_timeout=HTTP_TIMEOUT)
        self._ioloop.add_future(request, on_response)
        return future

    def _resolve_credentials(self, access_key=None, secret_key=None,
                             security_token=None):
        """Try and load the credentials file from disk checking first to see
        if a path is specified in the ``AWS_SHARED_CREDENTIALS_FILE``
        environment variable and if not, falling back to ``~/.aws/credentials``

        :param str access_key: An optional access key value
        :param str secret_key: An optional security key value
        :param str security_token: An optional security token value
        :return: access_key, secret_key, security_token
        :rtype: str, str

        """
        self._local_credentials = False
        self._access_key = os.getenv('AWS_ACCESS_KEY_ID', access_key)
        self._secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', secret_key)
        self._security_token = os.getenv(
            'AWS_SECURITY_TOKEN', os.getenv(
                'AWS_SESSION_TOKEN', security_token))
        if self._access_key and self._secret_key:
            self._local_credentials = True
            return True
        return self._resolve_config_file_credentials()

    def _resolve_config_file_credentials(self):
        """Attempt to load credentials via configuration file, looking to
        the AWS_SHARED_CREDENTIALS_FILE environment variable for the path
        or defaulting to `'~/.aws/credentials`. This allows for instances
        where the credentials file is mounted or managed by an external
        system and can change while the application is running.

        :raises: ConfigNotFound
        :raises: ConfigParserError
        :return: access_key, secret_key, security_token
        :rtype: str, str, str

        """
        file_path = os.getenv(
            'AWS_SHARED_CREDENTIALS_FILE', DEFAULT_CREDENTIALS_PATH)
        try:
            config = _parse_file(file_path)
        except exceptions.ConfigNotFound:
            return False

        if self._profile not in config:
            raise exceptions.NoProfileError(
                path=file_path, profile=self._profile)

        self._access_key = self._get_config_value(config, 'aws_access_key_id')
        self._secret_key = self._get_config_value(
            config, 'aws_secret_access_key')
        self._security_token = self._get_config_value(
            config, 'aws_security_token') or self._get_config_value(
                config, 'aws_session_token')
        self._expiration = self._get_config_value(config, 'aws_access_key_id')
        self._local_credentials = \
            self._access_key is not None and self._secret_key is not None
        return self._local_credentials
