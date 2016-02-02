import os
import tempfile
import unittest
import uuid

from tornado_aws import config
from tornado_aws import exceptions

from . import utils


class ParseConfigFileTestCase(unittest.TestCase):

    def test_parsing_file(self):
        expectation = {
            'section a': {
                'key-1': uuid.uuid4().hex,
                'key-2': uuid.uuid4().hex
            },
            'section b': {
                'key-a': uuid.uuid4().hex,
                'key-b': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            value = config._parse_file(handle.name)
            self.assertDictEqual(expectation, value)

    def test_bad_config_file(self):
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(b'foo: bar\n')
            handle.flush()
            self.assertRaises(exceptions.ConfigParserError,
                              config._parse_file,
                              handle.name)


class GetRegionTestCase(unittest.TestCase):

    def test_parsing_file(self):
        expectation = {
            'default': {
                'region': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            value = config._get_region('default')
            self.assertEqual(expectation['default']['region'], value)

    def test_non_default_value(self):
        expectation = {
            'default': {
                'region': uuid.uuid4().hex
            },
            'foo': {
                'region': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            value = config._get_region('foo')
            self.assertEqual(expectation['foo']['region'], value)

    def test_raises_for_bad_profile(self):
        expectation = {
            'default': {
                'region': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            self.assertRaises(exceptions.NoProfileError,
                              config._get_region, 'foo')

    @unittest.skipIf(os.environ.get('TRAVIS') == 'true',
                     'Skipping this test on Travis CI.')
    def test_raises_for_missing_file(self):
        os.environ['AWS_CONFIG_FILE'] = uuid.uuid4().hex
        self.assertRaises(exceptions.ConfigNotFound, config._get_region,
                          'default')


class GetCredentialsTestCase(unittest.TestCase):

    def test_parsing_file(self):
        expectation = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
            access_key, secret_key = config._get_credentials('default')
            self.assertEqual(expectation['default']['aws_access_key_id'],
                             access_key)
            self.assertEqual(expectation['default']['aws_secret_access_key'],
                             secret_key)

    def test_non_default_value(self):
        expectation = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            },
            'foo': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
            access_key, secret_key = config._get_credentials('foo')
            self.assertEqual(expectation['foo']['aws_access_key_id'],
                             access_key)
            self.assertEqual(expectation['foo']['aws_secret_access_key'],
                             secret_key)

    def test_raises_for_bad_profile(self):
        expectation = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
            self.assertRaises(exceptions.NoProfileError,
                              config._get_credentials, 'foo')

    def test_missing_profile_value(self):
        expectation = {
            'foo': {
                'bar': uuid.uuid4().hex,
                'foo': uuid.uuid4().hex
            }
        }
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
            self.assertRaises(exceptions.NoCredentialsError,
                              config._get_credentials, 'foo')

    @unittest.skipIf(os.environ.get('TRAVIS') == 'true',
                     'Skipping this test on Travis CI.')
    def test_raises_for_missing_file(self):
        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = uuid.uuid4().hex
        self.assertRaises(exceptions.ConfigNotFound, config._get_credentials,
                          'default')


class GetTestCase(unittest.TestCase):

    def test_with_valid_config(self):
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

                region, access_key, secret_key = config.get()

        self.assertEqual(cfg['default']['region'], region)
        self.assertEqual(creds['default']['aws_access_key_id'], access_key)
        self.assertEqual(creds['default']['aws_secret_access_key'], secret_key)

    def test_with_valid_config_non_default_profile(self):
        cfg = {
            'foo': {
                'region': uuid.uuid4().hex
            }
        }

        creds = {
            'foo': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex
            }
        }

        os.environ['AWS_DEFAULT_PROFILE'] = 'foo'
        with tempfile.NamedTemporaryFile() as config_handle:
            config_handle.write(utils.build_ini(cfg))
            config_handle.flush()
            os.environ['AWS_CONFIG_FILE'] = config_handle.name

            with tempfile.NamedTemporaryFile() as handle:
                handle.write(utils.build_ini(creds))
                handle.flush()
                os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name

                region, access_key, secret_key = config.get()

        self.assertEqual(cfg['foo']['region'], region)
        self.assertEqual(creds['foo']['aws_access_key_id'], access_key)
        self.assertEqual(creds['foo']['aws_secret_access_key'], secret_key)

    def test_with_valid_config_specified_profile(self):
        cfg = {
            'foo': {
                'region': uuid.uuid4().hex
            }
        }

        creds = {
            'foo': {
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

                region, access_key, secret_key = config.get('foo')

        self.assertEqual(cfg['foo']['region'], region)
        self.assertEqual(creds['foo']['aws_access_key_id'], access_key)
        self.assertEqual(creds['foo']['aws_secret_access_key'], secret_key)
