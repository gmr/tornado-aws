import json
import logging
import pprint

from tornado import gen, ioloop

import tornado_aws

HEADERS = {'Content-Type': 'application/x-amz-json-1.0',
           'x-amz-target': 'DynamoDB_20120810.DescribeTable'}
PAYLOAD = {'TableName': 'prod-us-east-1-history'}


@gen.coroutine
def async_request():
    client = tornado_aws.AsyncAWSClient('dynamodb', use_curl=True)
    response = yield client.fetch('POST', '/', headers=HEADERS,
                                  body=json.dumps(PAYLOAD))
    x = json.loads(response.body.decode('utf-8'))
    pprint.pprint(x)
    ioloop.IOLoop.instance().stop()


logging.basicConfig(level=logging.DEBUG)
_ioloop = ioloop.IOLoop.instance()
_ioloop.add_callback(async_request)
_ioloop.start()
