"""

"""
import datetime
import hashlib
import hmac
import logging
import os
from os import path

from tornado import httpclient

from awsclient import config

LOGGER = logging.getLogger(__name__)

ALGORITHM = 'AWS4-HMAC-SHA256'


class AWSClient(object):
    """

    """
    def __init__(self, service, profile=None, region=None,
                 access_key=None, secret_key=None):
        self._adapter = self._get_client_adapter()
        self._service = service
        self._profile = profile

        _region, _access_key, _secret_key = region, access_key, secret_key
        if not region or not access_key or not secret_key:
            _region, _access_key, _secret_key = config.get(profile)
        self._region = region or _region
        self._access_key = access_key or _access_key
        self._secret_key = secret_key or _secret_key

    def _get_client_adapter(self):
        """Return a HTTP client

        :rtype: tornado.httpclient.HTTPClient

        """
        return httpclient.HTTPClient()





class AsyncAWSClient(AWSClient):
    """

    """
    def __init__(self, service, profile=None, region=None, access_key=None,
                 secret_key=None, max_clients=100):
        self._max_clients = max_clients
        super(AsyncAWSClient, self).__init__(service, profile, region,
                                             access_key, secret_key)

    def _get_client_adapter(self):
        """Return an asynchronous HTTP client adapter

        :rtype: tornado.httpclient.AsyncHTTPClient

        """
        return httpclient.AsyncHTTPClient(max_clients=self._max_clients)
