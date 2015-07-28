"""
Rekt
====

rekt is a wrapper around the requests library that makes generic rest
operations less painful. I was frustrated with the implementation of
many service specific rest wrappers especially for google apis, this
library is meant to be generic and dynamic enough by templating the common
client code for most rest services.
"""
import re
import ast
from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('rekt/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

setup(
    name='rekt',
    version=version,
    url='http://github.com/vengefuldrx/rekt/',
    license='Apache License Version 2',
    author='Dillon Hicks',
    author_email='chronodynamic@gmail.com',
    description='A requests wrapper library for dynamically generating rest clients',
    long_description=__doc__,
    packages=['rekt'],
    package_data={'rekt' : ['specs/*.yaml']},
    include_package_data=True,
    platforms='any',
    install_requires=[
        'requests',
        'PyYaml',
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    entry_points='''
        [console_scripts]
        rekt=rekt:main
    '''
)
