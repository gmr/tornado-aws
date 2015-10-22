import sys
sys.path.insert(0, '../')

import tornado_aws

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = 'tornado-aws'
copyright = '2015, Gavin M. Roy'
author = 'Gavin M. Roy'

release = tornado_aws.__version__
version = '.'.join(release.split('.')[0:1])
language = None

exclude_patterns = ['_build']
pygments_style = 'sphinx'
todo_include_todos = True

html_static_path = ['_static']
htmlhelp_basename = 'tornado-awsdoc'

intersphinx_mapping = {'https://docs.python.org/': None,
                       'http://www.tornadoweb.org/en/stable/': None}
