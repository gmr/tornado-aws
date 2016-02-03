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
            value = config.get_region('default')
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
            value = config.get_region('foo')
            self.assertEqual(expectation['foo']['region'], value)

    @unittest.skipIf(os.environ.get('TRAVIS') == 'true',
                     'Skipping this test on Travis CI.')
    def test_raises_for_missing_file(self):
        os.environ['AWS_CONFIG_FILE'] = uuid.uuid4().hex
        self.assertRaises(exceptions.ConfigNotFound, config.get_region,
                          'default')
