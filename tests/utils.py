"""
Common testing utilities and such

"""
import datetime
import io
import os
import uuid

from tornado import testing, web
from tornado.concurrent import futures


def build_ini(values):
    output = io.BytesIO()
    for section in values:
        output.write('[{}]\n'.format(section).encode('utf-8'))
        for key in values[section]:
            output.write('{0}={1}\n'.format(
                key, values[section][key]).encode('utf-8'))
    output.seek(0)
    return output.read()


def clear_environment():
    os.environ.pop('AWS_CONFIG_FILE', None)
    os.environ.pop('AWS_SHARED_CREDENTIALS_FILE', None)
    os.environ.pop('AWS_DEFAULT_PROFILE', None)
    os.environ.pop('AWS_ACCESS_KEY_ID', None)
    os.environ.pop('AWS_SECRET_ACCESS_KEY', None)


class RequestHandler(web.RequestHandler):

    def get(self, *args, **kwargs):
        if args[0] == 'latest/meta-data/iam/security-credentials/':
            self.write(self.get_argument('role', uuid.uuid4().hex))
        elif args[0] == 'latest/dynamic/instance-identity/document':
            self.write(
                {'region': self.get_argument('region', uuid.uuid4().hex)})
        elif args[0] == \
            'latest/meta-data/iam/security-credentials/{}'.format(
                self.get_argument('role', uuid.uuid4().hex)):
            self.write({
                'AccessKeyId':
                    self.get_argument('access_key', uuid.uuid4().hex),
                'SecretAccessKey':
                    self.get_argument('secret_key', uuid.uuid4().hex),
                'Expiration': datetime.datetime.now().isoformat(),
                'Token': self.get_argument('token', uuid.uuid4().hex)})
        elif args[0].startswith('api'):
            self.write({'result': self.get_argument('expectation', True)})
        else:
            raise web.HTTPError(400, 'Invalid Path')


class AsyncHTTPTestCase(testing.AsyncHTTPTestCase):

    executor = futures.ThreadPoolExecutor(10)

    def get_app(self):
        return web.Application([(r'/(.*)', RequestHandler)])
