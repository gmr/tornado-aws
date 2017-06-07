from os import path
import setuptools

CLASSIFIERS = ['Development Status :: 4 - Beta',
               'Intended Audience :: Developers',
               'License :: OSI Approved :: BSD License',
               'Operating System :: OS Independent',
               'Programming Language :: Python :: 2',
               'Programming Language :: Python :: 2.7',
               'Programming Language :: Python :: 3',
               'Programming Language :: Python :: 3.4',
               'Programming Language :: Python :: 3.5',
               'Programming Language :: Python :: 3.6',
               'Programming Language :: Python :: Implementation :: CPython',
               'Programming Language :: Python :: Implementation :: PyPy',
               'Topic :: Communications',
               'Topic :: Internet',
               'Topic :: Software Development :: Libraries']

DESC = 'A low-level Amazon Web Services API client for Tornado'


def read_requirements(name):
    requirements = []
    try:
        with open(path.join('requires', name)) as req_file:
            for line in req_file:
                if '#' in line:
                    line = line[:line.index('#')]
                line = line.strip()
                if line.startswith('-r'):
                    requirements.extend(read_requirements(line[2:].strip()))
                elif line and not line.startswith('-'):
                    requirements.append(line)
    except IOError:
        pass
    return requirements


setuptools.setup(
    name='tornado-aws',
    version='0.8.0',
    description=DESC,
    long_description=open('README.rst').read(),
    author='Gavin M. Roy',
    author_email='gavinmroy@gmail.com',
    url='http://tornado-aws.readthedocs.org',
    packages=['tornado_aws'],
    package_data={'': ['LICENSE', 'README.rst', 'requires/installation.txt']},
    include_package_data=True,
    install_requires=read_requirements('requires/installation.txt'),
    extras_require={'curl': ['pycurl']},
    tests_require=read_requirements('requires/testing.txt'),
    license='BSD',
    classifiers=CLASSIFIERS,
    zip_safe=True)
