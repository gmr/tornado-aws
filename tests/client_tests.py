import contextlib
import io
import json
import os
import tempfile
import unittest
import uuid

import mock
from tornado import httpclient, httputil

from tornado_aws import client, exceptions

from . import utils


class TestCase(unittest.TestCase):

    CLIENT = client.AWSClient

    def setUp(self):
        super(TestCase, self).setUp()
        utils.clear_environment()
        self.creds = {
            'default': {
                'aws_access_key_id': uuid.uuid4().hex,
                'aws_secret_access_key': uuid.uuid4().hex}}

    def get_client(self, *args, **kwargs):
        return self.CLIENT(*args, **kwargs)

    @contextlib.contextmanager
    def client_with_no_creds(self, *args, **kwargs):
        handle = tempfile.NamedTemporaryFile()
        handle.write(utils.build_ini({'default': {}}))
        handle.flush()
        handle.seek(0)
        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
        yield self.get_client(*args, **kwargs)
        handle.close()

    @contextlib.contextmanager
    def client_with_default_creds(self, *args, **kwargs):
        handle = tempfile.NamedTemporaryFile()
        handle.write(utils.build_ini(self.creds))
        handle.flush()
        handle.seek(0)
        os.environ['AWS_SHARED_CREDENTIALS_FILE'] = handle.name
        yield self.get_client(*args, **kwargs)
        handle.close()


class ClientConfigTestCase(TestCase):

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


class AMZErrorTestCase(TestCase):

    def test_awz_error(self):
        content = b'{"__type": "MissingAuthenticationTokenException", ' \
                  b'"message": "Missing Authentication Token"}'
        expectation = {'__type': 'MissingAuthenticationTokenException',
                       'message': 'Missing Authentication Token'}
        with self.client_with_default_creds('s3') as obj:
            self.assertDictEqual(obj._parse_awz_error(content), expectation)

    def test_unsupported_payload(self):
        content = b'{"message": "Missing Authentication Token"}'
        with self.client_with_default_creds('invalid') as obj:
            self.assertIsNone(obj._parse_awz_error(content))


class XMLErrorTestCase(TestCase):

    def test_ec2_error(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>' \
                  b'<Response><Errors><Error><Code>InvalidAction</Code>' \
                  b'<Message>The action CreateVolume is not valid for t' \
                  b'his web service.</Message></Error></Errors><Request' \
                  b'ID>cb159b66-84a7-43bf-8a02-c839cc50b164</RequestID>' \
                  b'</Response>'
        expectation = {
            'Code': 'InvalidAction',
            'Message': 'The action CreateVolume is not valid for this '
                       'web service.',
            'RequestId': 'cb159b66-84a7-43bf-8a02-c839cc50b164'}
        with self.client_with_default_creds('s3') as obj:
            self.assertDictEqual(obj._parse_xml_error(content), expectation)

    def test_advertising_error(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>\n<Errors>' \
                  b'<Error><Code>AWS.InvalidAccount</Code><Message>T' \
                  b'he provided token has expired.</Message></Error></Errors>'
        expectation = {'Code': 'AWS.InvalidAccount',
                       'Message': 'The provided token has expired.'}
        with self.client_with_default_creds('s3') as obj:
            self.assertDictEqual(obj._parse_xml_error(content), expectation)

    def test_s3_error(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>\n<Error>' \
                  b'<Code>ExpiredToken</Code><Message>The provided ' \
                  b'token has expired.</Message><RequestId>DA1C5F5' \
                  b'26B1A0EF2</RequestId><HostId>381a948d-a988-4e7' \
                  b'a-aefe-e27e82555bed</HostId></Error>'
        expectation = {'Code': 'ExpiredToken',
                       'HostId': '381a948d-a988-4e7a-aefe-e27e82555bed',
                       'Message': 'The provided token has expired.',
                       'RequestId': 'DA1C5F526B1A0EF2'}
        with self.client_with_default_creds('s3') as obj:
            self.assertDictEqual(obj._parse_xml_error(content), expectation)

    def test_simpledb_error(self):
        content = b'<MissingAuthenticationTokenException><Message>' \
                  b'Missing Authentication Token</Message></Missin' \
                  b'gAuthenticationTokenException>'
        expectation = {'Code': 'MissingAuthenticationTokenException',
                       'Message': 'Missing Authentication Token'}
        with self.client_with_default_creds('simpledb') as obj:
            self.assertDictEqual(obj._parse_xml_error(content), expectation)

    def test_unparsable_error(self):
        content = b'error'
        with self.client_with_default_creds('invalid') as obj:
            with self.assertRaises(ValueError):
                obj._parse_xml_error(content)

    def test_unsupported_error(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>\n<Errs>' \
                  b'<Err><Code>AWS.InvalidAccount</Code><Message>T' \
                  b'he provided token has expired.</Message></Err></Errs>'
        with self.client_with_default_creds('invalid') as obj:
            with self.assertRaises(ValueError):
                obj._parse_xml_error(content)


class ProcessErrorTestCase(TestCase):

    def test_599_bypasses_processing(self):
        error = httpclient.HTTPError(599, 'Timeout')
        with self.client_with_default_creds('dynamodb') as obj:
            self.assertEqual(obj._process_error(error), (False, None))

    def test_process_error_awz_creds(self):
        content = b'{"__type": "MissingAuthenticationTokenException", ' \
                  b'"message": "Missing Authentication Token"}'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/test')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/x-amz-json-1.1',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        error = httpclient.HTTPError(400, 'Bad Request', response)
        with self.client_with_default_creds('dynamodb') as obj:
            result = obj._process_error(error)
            self.assertTrue(result[0])

    def test_process_dynamodb_error_creds(self):
        content = b'{"__type": "com.amazonaws.dynamodb.v20120810#MissingAut' \
                  b'henticationTokenException",  "message": "Missing Authen' \
                  b'tication Token"}'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/test')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/x-amz-json-1.0',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        error = httpclient.HTTPError(400, 'Bad Request', response)
        with self.client_with_default_creds('dynamodb') as obj:
            result = obj._process_error(error)
            self.assertTrue(result[0])
            self.assertIsInstance(result[1], exceptions.AWSError)

    def test_process_error_s3(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>\n<Error>' \
                  b'<Code>ExpiredToken</Code><Message>The provided ' \
                  b'token has expired.</Message><RequestId>DA1C5F5' \
                  b'26B1A0EF2</RequestId><HostId>381a948d-a988-4e7' \
                  b'a-aefe-e27e82555bed</HostId></Error>'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/xml',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        error = httpclient.HTTPError(400, 'Bad Request', response)
        with self.client_with_default_creds('s3') as obj:
            result = obj._process_error(error)
            self.assertTrue(result[0])
            self.assertIsInstance(result[1], exceptions.AWSError)

    def test_process_error_ec2_non_auth(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>' \
                  b'<Response><Errors><Error><Code>InvalidAction</Code>' \
                  b'<Message>The action CreateVolume is not valid for t' \
                  b'his web service.</Message></Error></Errors><Request' \
                  b'ID>cb159b66-84a7-43bf-8a02-c839cc50b164</RequestID>' \
                  b'</Response>'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/xml',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        error = httpclient.HTTPError(400, 'Bad Request', response)
        with self.client_with_default_creds('dynamodb') as obj:
            result = obj._process_error(error)
            self.assertFalse(result[0])
            self.assertIsInstance(result[1], exceptions.AWSError)

    def test_process_simpledb_non_auth(self):
        content = b'<?xml version="1.0" encoding="UTF-8"?>' \
                  b'<Response><Errors><Error><Code>InvalidAction</Code>' \
                  b'<Message>The action CreateVolume is not valid for t' \
                  b'his web service.</Message></Error></Errors><Request' \
                  b'ID>cb159b66-84a7-43bf-8a02-c839cc50b164</RequestID>' \
                  b'</Response>'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'x-amzn-RequestId': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        error = httpclient.HTTPError(400, 'Bad Request', response)
        with self.client_with_default_creds('dynamodb') as obj:
            result = obj._process_error(error)
            self.assertFalse(result[0])
            self.assertIsInstance(result[1], exceptions.AWSError)

    def test_process_bogus_response(self):
        content = b'Slow Down'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'x-amzn-RequestId': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 503, headers, stream)
        error = httpclient.HTTPError(503, 'Bad Request', response)
        with self.client_with_default_creds('s3') as obj:
            self.assertEqual(obj._process_error(error), (False, None))


class ClientFetchTestCase(TestCase):

    @staticmethod
    def mock_ok_response():
        content = b'{"foo": "bar"}'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'x-amzn-RequestId': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Content-Type': 'application/x-amz-json-1.0',
             'Server': 'Server',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        return httpclient.HTTPResponse(request, 200, headers, stream)

    @staticmethod
    def mock_auth_exception():
        content = b'<?xml version="1.0" encoding="UTF-8"?>\n<Error>' \
                  b'<Code>ExpiredToken</Code><Message>The provided ' \
                  b'token has expired.</Message><RequestId>DA1C5F5' \
                  b'26B1A0EF2</RequestId><HostId>381a948d-a988-4e7' \
                  b'a-aefe-e27e82555bed</HostId></Error>'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/xml',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        return httpclient.HTTPError(400, 'Bad Request', response)

    @staticmethod
    def mock_error_exception():
        content = b'<?xml version="1.0" encoding="UTF-8"?>' \
                  b'<Response><Errors><Error><Code>InvalidAction</Code>' \
                  b'<Message>The action CreateVolume is not valid for t' \
                  b'his web service.</Message></Error></Errors><Request' \
                  b'ID>cb159b66-84a7-43bf-8a02-c839cc50b164</RequestID>' \
                  b'</Response>'
        stream = io.BytesIO(content)
        request = httpclient.HTTPRequest('/')
        headers = httputil.HTTPHeaders(
            {'Content-Type': 'application/xml',
             'Server': 'Server',
             'X-Amz-Request-Id': '3840c615-0503-4a53-a2f6-07afa795a5d6',
             'Date': 'Tue, 06 Jun 2017 18:31:47 GMT'})
        response = httpclient.HTTPResponse(request, 400, headers, stream)
        return httpclient.HTTPError(400, 'Bad Request', response)

    def test_fetch_success(self):
        with self.client_with_default_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                fetch.return_value=self.mock_ok_response()
                body = json.dumps({'foo': 'bar'}).encode('utf-8')
                result = obj.fetch(
                    'POST', '/', body=body,
                    headers={'x-amz-target': 'DynamoDB_20120810.CreateTable',
                             'Content-Type': 'application/x-amz-json-1.0'})
                self.assertEqual(result.code, 200)
                fetch.assert_called_once()

                # Get the first argument of the call into fetch
                request = fetch.call_args_list[0][0][0]
                self.assertEqual(request.method, 'POST')
                self.assertEqual(request.headers['Content-Type'],
                                 'application/x-amz-json-1.0')

    def test_fetch_no_headers(self):
        with self.client_with_default_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                fetch.return_value=self.mock_ok_response()
                body = json.dumps({'foo': 'bar'})
                result = obj.fetch('POST', '/', body=body)
                self.assertEqual(result.code, 200)
                fetch.assert_called_once()

                # Get the first argument of the call into fetch
                request = fetch.call_args_list[0][0][0]
                self.assertEqual(request.method, 'POST')

    def test_fetch_needs_credentials(self):
        with self.client_with_default_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                with mock.patch.object(obj._auth_config, 'refresh') as refresh:
                    obj._auth_config._local_credentials = False
                    obj._auth_config._access_key = None
                    fetch.return_value = self.mock_ok_response()
                    body = json.dumps({'foo': 'bar'}).encode('utf-8')
                    result = obj.fetch(
                        'POST', '/', body=body,
                        headers={
                            'x-amz-target': 'DynamoDB_20120810.CreateTable',
                            'Content-Type': 'application/x-amz-json-1.0'})
                    self.assertEqual(result.code, 200)
                    fetch.assert_called_once()
                    refresh.assert_called_once()

                    # Get the first argument of the call into fetch
                    request = fetch.call_args_list[0][0][0]
                    self.assertEqual(request.method, 'POST')
                    self.assertEqual(request.headers['Content-Type'],
                                     'application/x-amz-json-1.0')

    def test_fetch_when_client_raises_error(self):
        with self.client_with_default_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                with self.assertRaises(exceptions.AWSError):
                    fetch.side_effect = self.mock_error_exception()
                    obj.fetch(
                        'GET', '/',
                        query_args={'list_type': '2', 'delimiter': '/'},
                        headers={'Host': 'bucket.s3.amazonaws.com'})

    def test_fetch_when_client_needs_credentials(self):
        with self.client_with_no_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                with mock.patch.object(obj._auth_config, 'refresh') as refresh:
                    with mock.patch.object(obj._auth_config, 'reset') as reset:
                        fetch.side_effect = [self.mock_auth_exception(),
                                             self.mock_ok_response()]
                        result = obj.fetch(
                            'GET', '/',
                            query_args={'list_type': '2', 'delimiter': '/'},
                            headers={'Host': 'bucket.s3.amazonaws.com'})
                        self.assertEqual(result.code, 200)
                        reset.assert_called_once()
                        self.assertEqual(fetch.call_count, 2)
                        self.assertEqual(refresh.call_count, 2)

    def test_fetch_when_client_fails_credentials(self):
        with self.client_with_no_creds('s3') as obj:
            with mock.patch.object(obj._client, 'fetch') as fetch:
                with mock.patch.object(obj._auth_config, 'refresh') as refresh:
                    with mock.patch.object(obj._auth_config, 'reset') as reset:
                        fetch.side_effect = [self.mock_auth_exception(),
                                             self.mock_auth_exception()]
                        with self.assertRaises(exceptions.AWSError):
                            result = obj.fetch(
                                'GET', '/',
                                query_args={'list_type': '2', 'delimiter': '/'},
                                headers={'Host': 'bucket.s3.amazonaws.com'})
                            self.assertEqual(result.code, 200)
                        self.assertEqual(reset.call_count, 2)
                        self.assertEqual(fetch.call_count, 2)
                        self.assertEqual(refresh.call_count, 2)
