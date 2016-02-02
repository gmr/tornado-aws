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

from tornado import httpclient

from tornado_aws import exceptions

LOGGER = logging.getLogger(__name__)

DEFAULT_REGION = 'us-east-1'
INSTANCE_ENDPOINT = 'http://169.254.169.254/latest/{}'
INSTANCE_ROLE_PATH = '/meta-data/iam/security-credentials/'
INSTANCE_CREDENTIALS_PATH = '/meta-data/iam/security-credentials/{}'
REGION_PATH = '/dynamic/instance-identity/document'

HTTP_TIMEOUT = 0.5


def get(profile=None):
    """Return the credentials from the configured ~/.aws/credentials file
    following the behavior implemented by awscli and botocore.

    :param str profile: Use the optional profile for getting settings
    :return: region, access_key, secret_key
    :rtype: str(), str(), str()

    """
    if not profile:
        profile = os.getenv('AWS_DEFAULT_PROFILE', 'default')

    region = _get_region(profile)
    access_key, secret_key = _get_credentials(profile)
    return region, access_key, secret_key


def _get_credentials(profile):
    """Try and load the credentials file from disk checking first to see if a
    path is specified in the ``AWS_SHARED_CREDENTIALS_FILE`` environment
    variable and if not, falling back to ``~/.aws/credentials``

    :param str profile: The configuration profile to use
    :return: access_key, secret_key
    :rtype: str, str
    :raises: ConfigNotFound
    :raises: ConfigParserError
    :raises: NoCredentialsError

    """
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    if access_key and secret_key:
        return access_key, secret_key

    file_path = os.getenv('AWS_SHARED_CREDENTIALS_FILE', '~/.aws/credentials')
    try:
        config = _parse_file(file_path)
    except exceptions.ConfigNotFound:
        try:
            return _get_credentials_from_instance()
        except (httpclient.HTTPError,
                OSError) as error:
            LOGGER.error('Error fetching from EC2 Instance Metadata (%s)',
                         error)
            raise exceptions.ConfigNotFound(path=file_path)

    if profile not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)

    values = []
    for key in ['aws_access_key_id', 'aws_secret_access_key']:
        values.append(config[profile].get(key) or
                      config.get('default', {}).get(key))
    if not all(values):
        raise exceptions.NoCredentialsError
    return values[0], values[1]


def _get_credentials_from_instance():
    """Attempt to fetch the security credentials from an EC2 instance

    :rtype: tuple

    """
    client = httpclient.HTTPClient()
    url = INSTANCE_ENDPOINT.format(INSTANCE_ROLE_PATH)
    response = client.fetch(url,
                            connect_timeout=HTTP_TIMEOUT,
                            request_timeout=HTTP_TIMEOUT)
    role = response.body.decode('utf-8')
    path = INSTANCE_CREDENTIALS_PATH.format(role)
    url = INSTANCE_ENDPOINT.format(path)
    response = client.fetch(url,
                            connect_timeout=HTTP_TIMEOUT,
                            request_timeout=HTTP_TIMEOUT)
    data = json.loads(response.body.decode('utf-8'))
    client.close()
    return data.get('AccessKeyId'), data.get('SecretAccessKey')


def _get_region(profile):
    """Return the region

    :param str profile: The configuration profile to use
    :return: str

    """
    file_path = os.getenv('AWS_CONFIG_FILE', '~/.aws/config')
    try:
        config = _parse_file(file_path)
    except exceptions.ConfigNotFound:
        try:
            return _get_region_from_instance()
        except (httpclient.HTTPError,
                OSError) as error:
            LOGGER.error('Error fetching from EC2 Instance Metadata (%s)',
                         error)
            raise exceptions.ConfigNotFound(path=file_path)

    if profile not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)
    return (config[profile].get('region') or
            config.get('default', {}).get('region') or
            DEFAULT_REGION)


def _get_region_from_instance():
    """Attempt to get the region from the instance metadata

    :rtype: str

    """
    url = INSTANCE_ENDPOINT.format(REGION_PATH)
    client = httpclient.HTTPClient()
    response = client.fetch(url,
                            connect_timeout=HTTP_TIMEOUT,
                            request_timeout=HTTP_TIMEOUT)
    data = json.loads(response.body.decode('utf-8'))
    client.close()
    return data['region']


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
