"""
AWS Credentials Loader

"""
try:
    import configparser
except ImportError:  # pragma: no cover
    import ConfigParser as configparser
import json
import logging
from os import path
import os

from tornado import concurrent, httpclient, ioloop

from tornado_aws import exceptions

LOGGER = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = '~/.aws/credentials'
DEFAULT_REGION = 'us-east-1'
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
        except (httpclient.HTTPError,
                OSError) as error:
            LOGGER.error('Error fetching from EC2 Instance Metadata (%s)',
                         error)
            raise exceptions.ConfigNotFound(path=file_path)

    if profile not in config and 'default' not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)
    return (config.get(profile, {}).get('region') or
            config.get('default', {}).get('region') or
            DEFAULT_REGION)


def _parse_file(file_path):
    """Parse the specified configuration file, returning a nested dict
    of key/value pairs by section.

    :param str file_path: The path of the file to read.
    :rtype: dict

    """
    file_path = path.abspath(path.expanduser(path.expandvars(file_path)))
    LOGGER.debug('Reading file: %s', file_path)
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
    url = INSTANCE_ENDPOINT.format(REGION_PATH)
    client = httpclient.HTTPClient(force_instance=True)
    response = client.fetch(url,
                            connect_timeout=HTTP_TIMEOUT,
                            request_timeout=HTTP_TIMEOUT)
    data = json.loads(response.body.decode('utf-8'))
    client.close()
    return data['region']


class Authorization(object):
    """Object used to hold configuration information."""

    def __init__(self, profile, access_key=None, secret_key=None, client=None):
        """Create a new instance of the ``_AuthConfig`` class.

        :param str profile: The configuration profile to use
        :param str access_key: Optional configured access key
        :param str secret_key: Optional configured secret key
        :param client: The HTTP client to use for EC2 API
        :type client: tornado.httpclient.HTTPClient or
            tornado.httpclient.AsyncHTTPClient

        """
        self._client = client
        self._profile = profile

        (self._access_key,
         self._secret_key) = self._resolve_credentials(access_key, secret_key)
        self._security_token = None
        self._expiration = None
        self._local_credentials = bool(self._access_key)

        async = isinstance(client, httpclient.AsyncHTTPClient)
        self._ioloop = ioloop.IOLoop.current() if async else None

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
        """Returns True if the client needs to fetch remote credentials.

        :rtype: bool

        """
        if self._local_credentials:
            return False
        return not self._access_key

    def refresh(self):
        """Load dynamic credentials from the AWS Instance Metadata and user
        data HTTP API.

        :raises: tornado_aws.exceptions.NoCredentialsError

        """
        LOGGER.debug('Refreshing EC2 IAM Credentials')
        async = isinstance(self._client, httpclient.AsyncHTTPClient)
        future = concurrent.TracebackFuture() if async else None
        try:
            result = self._fetch_credentials(async)
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
        except (httpclient.HTTPError,
                OSError) as error:
            LOGGER.error('Error Fetching Credentials: %s', error)
            raise exceptions.NoCredentialsError()
        return future

    def reset(self):
        """Reset the security credentials.

        :raises: tornado_aws.exceptions.LocalCredentialsError()

        """
        if self.local_credentials:
            raise exceptions.LocalCredentialsError()
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

    def _fetch_credentials(self, async):
        """Fetch credential information from the local EC2 Metadata and user
        data API.

        :param bool async: Perform async fetch
        :rtype: dict

        """
        if async:
            return self._fetch_credentials_async()
        role = self._get_role()
        credentials = self._get_instance_credentials(role)
        return credentials

    def _fetch_credentials_async(self):
        """Return the credentials from the EC2 Instance Metadata and user data
        API using an Async adapter.

        :return: :class:`~concurrent.TracebackFuture`

        """
        future = concurrent.TracebackFuture()

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

    def _get_instance_credentials(self, role):
        """Attempt to get temporary credentials for the specified role from the
        EC2 Instance Metadata and user data API

        :param tornado.httpclient.HTTPClient client: The http client to use
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

        :rtype: :class:`~tornado.concurrent.TracebackFuture`
        :raises: tornado.httpclient.HTTPError

        """
        future = concurrent.TracebackFuture()

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

        :param tornado.httpclient.HTTPClient client: The HTTP client
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

        :rtype: :class:`~tornado.concurrent.TracebackFuture`
        :raises: tornado.httpclient.HTTPError

        """
        future = concurrent.TracebackFuture()

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

    def _resolve_credentials(self, access_key, secret_key):
        """Try and load the credentials file from disk checking first to see
        if a path is specified in the ``AWS_SHARED_CREDENTIALS_FILE``
        environment variable and if not, falling back to ``~/.aws/credentials``

        :return: access_key, secret_key
        :rtype: str, str
        :raises: ConfigNotFound
        :raises: ConfigParserError

        """
        access_key = os.getenv('AWS_ACCESS_KEY_ID', access_key)
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', secret_key)
        if access_key and secret_key:
            return access_key, secret_key

        file_path = os.getenv('AWS_SHARED_CREDENTIALS_FILE',
                              DEFAULT_CREDENTIALS_PATH)

        try:
            config = _parse_file(file_path)
        except exceptions.ConfigNotFound:
            return None, None

        if self._profile not in config:
            raise exceptions.NoProfileError(path=file_path,
                                            profile=self._profile)

        values = []
        for key in ['aws_access_key_id', 'aws_secret_access_key']:
            values.append(config[self._profile].get(key) or
                          config.get('default', {}).get(key))
        if not all(values):
            return None, None
        return values[0], values[1]
