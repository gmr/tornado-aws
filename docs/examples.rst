Examples
========
The following example uses invokes the ``DescribeTable`` endpoint for DynamoDB:

.. code:: python

    import json
    import pprint

    import tornado_aws
    from tornado import gen, ioloop

    HEADERS = {'Content-Type': 'application/x-amz-json-1.0',
               'x-amz-target': 'DynamoDB_20120810.DescribeTable'}
    PAYLOAD = {'TableName': 'prod-us-east-1-history-events'}

    @gen.coroutine
    def async_request():
        client = tornado_aws.AsyncAWSClient('dynamodb')
        response = yield client.fetch('POST', '/', headers=HEADERS,
                                      body=json.dumps(PAYLOAD))
        x = json.loads(response.body.decode('utf-8'))
        pprint.pprint(x)
        ioloop.IOLoop.instance().stop()

    _ioloop = ioloop.IOLoop.instance()
    _ioloop.add_callback(async_request)
    _ioloop.start()
