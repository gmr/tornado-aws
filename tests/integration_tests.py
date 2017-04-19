import copy
import json
import os
import unittest
import uuid

from tornado import testing

try:
    from tornado import curl_httpclient
except ImportError:
    curl_httpclient = None

import tornado_aws

from . import utils


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
