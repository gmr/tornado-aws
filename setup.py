import setuptools

CLASSIFIERS = ['Development Status :: 4 - Beta',
               'Intended Audience :: Developers',
               'License :: OSI Approved :: BSD License',
               'Operating System :: OS Independent',
               'Programming Language :: Python :: 2',
               'Programming Language :: Python :: 2.7',
               'Programming Language :: Python :: 3',
               'Programming Language :: Python :: 3.3',
               'Programming Language :: Python :: 3.4',
               'Programming Language :: Python :: 3.5',
               'Programming Language :: Python :: Implementation :: CPython',
               'Programming Language :: Python :: Implementation :: PyPy',
               'Topic :: Communications',
               'Topic :: Internet',
               'Topic :: Software Development :: Libraries']

DESC = 'A low-level Amazon Web Services API client for Tornado'


setuptools.setup(name='tornado-aws',
                 version='0.5.0',
                 description=DESC,
                 long_description=open('README.rst').read(),
                 author='Gavin M. Roy',
                 author_email='gavinmroy@gmail.com',
                 url='http://tornado-aws.readthedocs.org',
                 packages=['tornado_aws'],
                 package_data={'': ['LICENSE', 'README.rst',
                                    'requires/installation.txt']},
                 include_package_data=True,
                 install_requires=open('requires/installation.txt').read(),
                 tests_require=open('requires/testing.txt').read(),
                 license='BSD',
                 classifiers=CLASSIFIERS,
                 zip_safe=True)
