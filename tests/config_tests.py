import datetime
import logging
import os
import tempfile
import unittest
import uuid

import mock
from tornado import concurrent, httpclient, testing

from tornado_aws import config, exceptions
from . import utils

LOGGER = logging.getLogger(__name__)


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
        expectation = {'default': {'region': uuid.uuid4().hex}}
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            value = config.get_region('default')
            self.assertEqual(expectation['default']['region'], value)

    def test_non_default_value(self):
        expectation = {
            'default': {'region': uuid.uuid4().hex},
            'profile foo': {'region': uuid.uuid4().hex}}
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(expectation))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            value = config.get_region('foo')
            self.assertEqual(expectation['profile foo']['region'], value)

    def test_missing_profile_value(self):
        ini_values = {'profile foo': {'region': uuid.uuid4().hex}}
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(ini_values))
            handle.flush()
            os.environ['AWS_CONFIG_FILE'] = handle.name
            with self.assertRaises(exceptions.NoProfileError):
                config.get_region('testing')

    def test_raises_for_missing_file(self):
        os.environ['AWS_CONFIG_FILE'] = uuid.uuid4().hex
        with mock.patch(
                'tornado_aws.config._request_region_from_instance') as region:
            region.side_effect = OSError
            with self.assertRaises(exceptions.ConfigNotFound):
                config.get_region('default')


class CredentialsManagementTestCase(unittest.TestCase):
    def test_assignment_and_reset(self):
        obj = config.Authorization('default', client=httpclient.HTTPClient())
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        expiration = datetime.datetime.now().isoformat()
        obj._assign_credentials({
            'AccessKeyId': access_key,
            'SecretAccessKey': secret_key,
            'Expiration': expiration,
            'Token': token
        })
        self.assertEqual(obj.access_key, access_key)
        self.assertEqual(obj.secret_key, secret_key)
        self.assertEqual(obj._expiration, expiration)
        self.assertEqual(obj.security_token, token)
        obj.reset()
        self.assertIsNone(obj.access_key)
        self.assertIsNone(obj.secret_key)
        self.assertIsNone(obj._expiration)
        self.assertIsNone(obj.security_token)


class ResolvCredentialsTestCase(unittest.TestCase):
    def test_error_case(self):
        ini_values = {'default': {'region': uuid.uuid4().hex}}
        with tempfile.NamedTemporaryFile() as handle:
            handle.write(utils.build_ini(ini_values))
            handle.flush()
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
            with self.assertRaises(exceptions.NoProfileError):
                config.Authorization('foo', client=httpclient.HTTPClient())


"""
class RequestRegionTestCase(utils.AsyncHTTPTestCase):

    @concurrent.run_on_executor
    def make_request(self, expectation):
        url = self.get_url('/latest{}?region=%s' % expectation)
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            return config._request_region_from_instance()

    @testing.gen_test
    def test_sync_request(self):
        expectation = str(uuid.uuid4().hex)
        value = yield self.make_request(expectation)
        self.assertEqual(value, expectation)
"""


class GetRoleTestCase(utils.AsyncHTTPTestCase):

    @concurrent.run_on_executor
    def make_request(self, expectation):
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/?role=%s' %
            expectation)
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default',
                                       client=httpclient.HTTPClient())
            return obj._get_role()

    @testing.gen_test
    def test_sync_request(self):
        expectation = str(uuid.uuid4().hex)
        value = yield self.make_request(expectation)
        self.assertEqual(value, expectation)

    @testing.gen_test
    def test_async_request(self):
        expectation = str(uuid.uuid4().hex)
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/?role=%s' %
            expectation)
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default',
                                       client=httpclient.AsyncHTTPClient())
            value = yield obj._get_role_async()
            self.assertEqual(value, expectation)

    @testing.gen_test
    def test_async_request_error(self):
        client = httpclient.AsyncHTTPClient()
        expectation = str(uuid.uuid4().hex)
        url = self.get_url('/latest/meta-data/iam/'
                           'security-credentials/?role={}'.format(expectation))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj._client, 'fetch') as fetch:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(599))
                fetch.return_value = future
                with self.assertRaises(httpclient.HTTPError):
                    yield obj._get_role_async()


class GetInstanceCredentialsTestCase(utils.AsyncHTTPTestCase):

    @concurrent.run_on_executor
    def make_request(self, role, access_key, secret_key, token):
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization(
                'default', client=httpclient.HTTPClient())
            return obj._get_instance_credentials(role)

    @testing.gen_test
    def test_sync_request(self):
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        value = yield self.make_request(role, access_key, secret_key, token)
        self.assertEqual(value['AccessKeyId'], access_key)
        self.assertEqual(value['SecretAccessKey'], secret_key)
        self.assertEqual(value['Token'], token)

    @testing.gen_test
    def test_async_request(self):
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default',
                                       client=httpclient.AsyncHTTPClient())
            value = yield obj._get_instance_credentials_async(role)
            self.assertEqual(value['AccessKeyId'], access_key)
            self.assertEqual(value['SecretAccessKey'], secret_key)
            self.assertEqual(value['Token'], token)

    @testing.gen_test
    def test_async_request_error(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj._client, 'fetch') as fetch:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(599))
                fetch.return_value = future
                with self.assertRaises(httpclient.HTTPError):
                    yield obj._get_instance_credentials_async(role)


class FetchCredentialsTestCase(utils.AsyncHTTPTestCase):

    @concurrent.run_on_executor
    def make_request(self, role, access_key, secret_key, token):
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization(
                'default', client=httpclient.HTTPClient())
            with mock.patch.object(obj, '_get_role') as get_role:
                get_role.return_value = role
            return obj._fetch_credentials()

    @testing.gen_test
    def test_sync_request(self):
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        value = yield self.make_request(role, access_key, secret_key, token)
        self.assertEqual(value['AccessKeyId'], access_key)
        self.assertEqual(value['SecretAccessKey'], secret_key)
        self.assertEqual(value['Token'], token)

    @testing.gen_test
    def test_async_request(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj, '_get_role_async') as get_role:
                role_future = concurrent.Future()
                role_future.set_result(role)
                get_role.return_value = role_future
                value = yield obj._fetch_credentials()
                self.assertEqual(value['AccessKeyId'], access_key)
                self.assertEqual(value['SecretAccessKey'], secret_key)
                self.assertEqual(value['Token'], token)

    @testing.gen_test
    def test_async_role_error(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj, '_get_role_async') as get_role:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(599))
                get_role.return_value = future
                with self.assertRaises(httpclient.HTTPError):
                    yield obj._fetch_credentials_async()

    @testing.gen_test
    def test_async_creds_error(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(
                    obj, '_get_instance_credentials_async') as get_creds:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(599))
                get_creds.return_value = future
                with self.assertRaises(httpclient.HTTPError):
                    yield obj._fetch_credentials_async()


class RefreshTestCase(utils.AsyncHTTPTestCase):

    @concurrent.run_on_executor
    def make_request(self, role, access_key, secret_key, token):
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization(
                'default', client=httpclient.HTTPClient())
            with mock.patch.object(obj, '_get_role') as get_role:
                get_role.return_value = role
                obj.refresh()
                return obj

    @concurrent.run_on_executor
    def make_err_request(self, role, access_key, secret_key, token):
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            client = httpclient.HTTPClient()
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj, '_get_role') as get_role:
                get_role.return_value = role
                with mock.patch.object(client, 'fetch') as fetch:
                    fetch.side_effect = httpclient.HTTPError(599)
                    obj.refresh()
                    return obj

    @testing.gen_test
    def test_sync_request(self):
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        obj = yield self.make_request(role, access_key, secret_key, token)
        self.assertEqual(obj.access_key, access_key)
        self.assertEqual(obj.secret_key, secret_key)
        self.assertEqual(obj.security_token, token)

    @testing.gen_test
    def test_sync_error(self):
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        with self.assertRaises(exceptions.NoCredentialsError):
            yield self.make_err_request(role, access_key, secret_key, token)

    @testing.gen_test
    def test_async_request(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj, '_get_role_async') as get_role:
                role_future = concurrent.Future()
                role_future.set_result(role)
                get_role.return_value = role_future
                yield obj.refresh()
                self.assertEqual(obj.access_key, access_key)
                self.assertEqual(obj.secret_key, secret_key)
                self.assertEqual(obj.security_token, token)

    @testing.gen_test
    def test_async_role_error(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(obj, '_get_role_async') as get_role:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(599))
                get_role.return_value = future
                with self.assertRaises(exceptions.NoCredentialsError):
                    yield obj.refresh()

    @testing.gen_test
    def test_async_creds_error(self):
        client = httpclient.AsyncHTTPClient()
        role = uuid.uuid4().hex
        access_key = uuid.uuid4().hex
        secret_key = uuid.uuid4().hex
        token = uuid.uuid4().hex
        url = self.get_url(
            '/latest/meta-data/iam/security-credentials/{}?role={}&access_'
            'key={}&secret_key={}&token={}'.format(
                role, role, access_key, secret_key, token))
        with mock.patch('tornado_aws.config.INSTANCE_ENDPOINT', url):
            obj = config.Authorization('default', client=client)
            with mock.patch.object(
                    obj, '_get_instance_credentials_async') as get_creds:
                future = concurrent.Future()
                future.set_exception(httpclient.HTTPError(502))
                get_creds.return_value = future
                with self.assertRaises(httpclient.HTTPError):
                    yield obj.refresh()
