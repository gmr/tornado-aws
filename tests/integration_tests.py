import copy
import json
import logging
import os
import unittest
import uuid

from tornado import gen, httpclient, testing

try:
    from tornado import curl_httpclient
except ImportError:
    curl_httpclient = None

import tornado_aws

from . import utils

LOGGER = logging.getLogger(__name__)

CREATE_BUCKET_BODY = """\
<CreateBucketConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <LocationConstraint>test</LocationConstraint>
</CreateBucketConfiguration>
"""


class DynamoDBTestCase(testing.AsyncTestCase):

    TABLE_DEFINITION = {
        "AttributeDefinitions": [
            {
                "AttributeName": "ForumName",
                "AttributeType": "S"
            },
            {
                "AttributeName": "Subject",
                "AttributeType": "S"
            },
            {
                "AttributeName": "LastPostDateTime",
                "AttributeType": "S"
            }
        ],
        "TableName": "Thread",
        "KeySchema": [
            {
                "AttributeName": "ForumName",
                "KeyType": "HASH"
            },
            {
                "AttributeName": "Subject",
                "KeyType": "RANGE"
            }
        ],
        "LocalSecondaryIndexes": [
            {
                "IndexName": "LastPostIndex",
                "KeySchema": [
                    {
                        "AttributeName": "ForumName",
                        "KeyType": "HASH"
                    },
                    {
                        "AttributeName": "LastPostDateTime",
                        "KeyType": "RANGE"
                    }
                ],
                "Projection": {
                    "ProjectionType": "KEYS_ONLY"
                }
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    }

    def setUp(self):
        super(DynamoDBTestCase, self).setUp()
        utils.clear_environment()
        os.environ['AWS_ACCESS_KEY_ID'] = str(uuid.uuid4())
        os.environ['AWS_SECRET_ACCESS_KEY'] = str(uuid.uuid4())
        os.environ['AWS_DEFAULT_REGION'] = 'local'
        self.client = tornado_aws.AsyncAWSClient(
            'dynamodb', endpoint='http://localhost:8000')

    @testing.gen_test
    def test_create_table(self):
        definition = copy.deepcopy(self.TABLE_DEFINITION)
        definition['TableName'] = str(uuid.uuid4())
        result = yield self.client.fetch(
            'POST', '/', body=json.dumps(definition).encode('utf-8'),
            headers={
                'x-amz-target': 'DynamoDB_20120810.CreateTable',
                'Content-Type': 'application/x-amz-json-1.0'})
        self.assertEqual(result.code, 200)
        body = json.loads(result.body.decode('utf-8'))
        self.assertEqual(
            body['TableDescription']['TableName'], definition['TableName'])
        self.assertEqual(body['TableDescription']['TableStatus'], 'CREATING')


class UseCurlDynamoDBTestCase(DynamoDBTestCase):

    def setUp(self):
        super(UseCurlDynamoDBTestCase, self).setUp()
        utils.clear_environment()
        os.environ['AWS_ACCESS_KEY_ID'] = str(uuid.uuid4())
        os.environ['AWS_SECRET_ACCESS_KEY'] = str(uuid.uuid4())
        os.environ['AWS_DEFAULT_REGION'] = 'local'
        self.client = tornado_aws.AsyncAWSClient(
            'dynamodb', endpoint='http://localhost:8000', use_curl=True)

    @unittest.skipIf(curl_httpclient is None, 'pycurl not installed')
    def test_create_table(self):
        return super(UseCurlDynamoDBTestCase, self).test_create_table()

    @testing.gen_test
    @unittest.skipIf(curl_httpclient is None, 'pycurl not installed')
    def test_invalid_endpoint(self):
        client = tornado_aws.AsyncAWSClient(
            'dynamodb', endpoint='http://localhost', use_curl=True)
        definition = copy.deepcopy(self.TABLE_DEFINITION)
        definition['TableName'] = str(uuid.uuid4())
        with self.assertRaises(httpclient.HTTPError):
            yield client.fetch(
                'POST', '/', body=json.dumps(definition).encode('utf-8'),
                headers={
                    'x-amz-target': 'DynamoDB_20120810.CreateTable',
                    'Content-Type': 'application/x-amz-json-1.0'})


class S3TestCase(testing.AsyncTestCase):

    def setUp(self):
        super(S3TestCase, self).setUp()
        utils.clear_environment()
        os.environ['AWS_ACCESS_KEY_ID'] = str(uuid.uuid4())
        os.environ['AWS_SECRET_ACCESS_KEY'] = str(uuid.uuid4())
        os.environ['AWS_DEFAULT_REGION'] = 'local'
        self.client = tornado_aws.AsyncAWSClient(
            's3', endpoint='http://localhost:4567')
        self.bucket = uuid.uuid4().hex
        self.headers = {'Host': '{}.s3.amazonaws.com'.format(self.bucket)}

    def get(self, key):
        LOGGER.debug('Getting object from s3://%s/%s', self.bucket, key)
        return self.client.fetch('GET', '/{}'.format(key), headers=self.headers)

    @gen.coroutine
    def store(self, key, value):
        LOGGER.debug('Storing revision to s3://%s/%s', self.bucket, key)
        headers = dict(self.headers)
        headers['x-amx-storage-class'] = 'STANDARD_IA'
        headers['x-amz-server-side-encryption'] = 'AES256'
        response = yield self.client.fetch(
            'PUT', '/{}'.format(key), headers=headers, body=value)
        return response.code == 200

    @testing.gen_test
    def test_store_and_get(self):
        result = yield self.client.fetch(
            'PUT', '/', self.headers, body=CREATE_BUCKET_BODY.encode('utf-8'))
        record = {
            'id': str(uuid.uuid4()),
            'version': 2,
            'data': str(uuid.uuid4())}
        response = yield self.store(
            record['id'], json.dumps(record).encode('utf-8'))
        self.assertTrue(response)
        response = yield self.get(record['id'])
        self.assertDictEqual(record, json.loads(response.body.decode('utf-8')))
