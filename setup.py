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

TESTS_REQUIRE = ['nose', 'mock', 'coverage']

setuptools.setup(name='tornado-aws',
                 version='0.4.6',
                 description=DESC,
                 long_description=open('README.rst').read(),
                 author='Gavin M. Roy',
                 author_email='gavinmroy@gmail.com',
                 url='http://tornado-aws.readthedocs.org',
                 packages=['tornado_aws'],
                 package_data={'': ['LICENSE', 'README.rst',
                                    'requirements.txt']},
                 include_package_data=True,
                 install_requires=['tornado'],
                 tests_require=TESTS_REQUIRE,
                 license='BSD',
                 classifiers=CLASSIFIERS,
                 zip_safe=True)
