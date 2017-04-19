import os
import tempfile
import unittest
import uuid

from tornado_aws import client

from . import utils


class BaseTestCase(unittest.TestCase):

    CLIENT = client.AWSClient

    def get_client(self, *args, **kwargs):
        return self.CLIENT(*args, **kwargs)


class ClientConfigTestCase(BaseTestCase):

    def setUp(self):
        super(ClientConfigTestCase, self).setUp()
        os.environ.pop('AWS_CONFIG_FILE', None)
        os.environ.pop('AWS_SHARED_CREDENTIALS_FILE', None)
        os.environ.pop('AWS_DEFAULT_PROFILE', None)



    def test_passed_in_values(self):
        region = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        obj = self.get_client('dynamodb', region=region,
                              access_key=access_key, secret_key=secret_key)
        self.assertEqual(obj._region, region)

    def test_with_valid_config_default_profile(self):
        cfg = {
            'default': {
                'region': uuid.uuid4().hex
            }
        }

        creds = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as config_handle:
            config_handle.write(utils.build_ini(cfg))
            config_handle.flush()
            os.environ['AWS_CONFIG_FILE'] = config_handle.name
            with tempfile.NamedTemporaryFile() as handle:
                handle.write(utils.build_ini(creds))
                handle.flush()
                os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
                obj = self.get_client('dynamodb')
                self.assertEqual(cfg['default']['region'], obj._region)

    def test_with_valid_config_specified_profile(self):
        cfg = {
            'default': {
                'region': uuid.uuid4().hex
            },
            'profile custom': {
                'region': uuid.uuid4().hex
            }
        }

        creds = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            },
            'custom': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as config_handle:
            config_handle.write(utils.build_ini(cfg))
            config_handle.flush()
            os.environ['AWS_CONFIG_FILE'] = config_handle.name
            os.environ['AWS_DEFAULT_PROFILE'] = 'custom'
            with tempfile.NamedTemporaryFile() as handle:
                handle.write(utils.build_ini(creds))
                handle.flush()
                os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
                obj = self.get_client('dynamodb')
                self.assertEqual(cfg['profile custom']['region'], obj._region)



class AsyncClientConfigTestCase(ClientConfigTestCase):

    CLIENT = client.AsyncAWSClient
