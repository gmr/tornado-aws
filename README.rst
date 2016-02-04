tornado-aws
===========
A low-level Amazon Web Services API client for Tornado

|Version| |Downloads| |Status| |Coverage| |License|

Installation
------------
``tornado-aws`` may be installed via the Python package index with the tool of
your choice. I prefer pip:

.. code:: bash

    pip install tornado-aws

Example
-------

.. code:: python

    import json
    import pprint

    import tornado_aws
    from tornado import gen, ioloop

    HEADERS = {'Content-Type': 'application/x-amz-json-1.0',
               'x-amz-target': 'DynamoDB_20120810.DescribeTable'}
    PAYLOAD = {'TableName': 'my-dynamodb-table'}

    _ioloop = ioloop.IOLoop.instance()

    @gen.coroutine
    def async_request():
        client = tornado_aws.AsyncAWSClient('dynamodb')
        response = yield client.fetch('POST', '/', headers=HEADERS,
                                      body=json.dumps(PAYLOAD))
        x = json.loads(response.body.decode('utf-8'))
        pprint.pprint(x)
        _ioloop.stop()

    _ioloop.add_callback(async_request)
    _ioloop.start()


Documentation
-------------
Documentation is available on `ReadTheDocs <https://tornado-aws.readthedocs.org>`_.

Requirements
------------
-  `Tornado <https://tornadoweb.org>`_

Version History
---------------
Available at https://tornado-aws.readthedocs.org/en/latest/history.html

.. |Version| image:: https://img.shields.io/pypi/v/tornado-aws.svg?
   :target: http://badge.fury.io/py/tornado-aws

.. |Status| image:: https://img.shields.io/travis/gmr/tornado-aws.svg?
   :target: https://travis-ci.org/gmr/tornado-aws

.. |Coverage| image:: https://img.shields.io/codecov/c/github/gmr/tornado-aws.svg?
   :target: https://codecov.io/github/gmr/tornado-aws?branch=master

.. |Downloads| image:: https://img.shields.io/pypi/dm/tornado-aws.svg?
   :target: https://pypi.python.org/pypi/tornado-aws

.. |License| image:: https://img.shields.io/pypi/l/tornado-aws.svg?
   :target: https://tornado-aws.readthedocs.org
