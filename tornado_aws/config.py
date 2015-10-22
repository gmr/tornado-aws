"""
AWS Credentials Loader

"""
try:
    import configparser
except ImportError:  # pragma: no cover
    import ConfigParser as configparser
import logging
from os import path
import os

from tornado_aws import exceptions

LOGGER = logging.getLogger(__name__)

DEFAULT_REGION = 'us-east-1'


def get(profile=None):
    """Return the credentials from the configured ~/.aws/credentials file
    following the behavior implemented by awscli and botocore.

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
    config = _parse_file(file_path)
    if profile not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)
    values = []
    for key in ['aws_access_key_id', 'aws_secret_access_key']:
        values.append(config[profile].get(key) or
                      config.get('default', {}).get(key))
    if not all(values):
        raise exceptions.NoCredentialsError
    return values[0], values[1]


def _get_region(profile):
    """Return the region

    :param str profile: The configuration profile to use
    :return: str

    """
    file_path = os.getenv('AWS_CONFIG_FILE', '~/.aws/config')
    config = _parse_file(file_path)
    if profile not in config:
        raise exceptions.NoProfileError(path=file_path, profile=profile)
    return (config[profile].get('region') or
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
