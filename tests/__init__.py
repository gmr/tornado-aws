import logging
import os

LOGGER = logging.getLogger(__name__)


def setup_module():
    """Ensure the test environment variables are set"""
    try:
        with open('build/test-environment') as f:
            for line in f:
                if line.startswith('export '):
                    line = line[7:]
                name, _, value = line.strip().partition('=')
                LOGGER.debug('Setting os.environ[%s] = %r', name, value)
                os.environ[name] = value
    except IOError:
        pass
