"""
Common testing utilities

"""
import io
import os


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
    os.environ.pop('AWS_DEFAULT_REGION', None)
