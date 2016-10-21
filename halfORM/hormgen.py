#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""\
Generates a python package from a PostgreSQL database
"""

import re
import os

from halfORM.model import Model

SETUP_TEMPLATE = '''\
"""Package Python pour l'exploitation de la BD du SI du LIRMM
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='{package_name}',

    version='0.0.0',

    description='Package for {dbname} PG',
    long_description=long_description,

    # url='',

    # author='',
    # author_email='',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    keywords='',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    install_requires=['halfORM'],

)
'''

DB_CONNECTOR_TEMPLATE = """\
#-*- coding: utf-8 -*-

from halfORM.model import Model

db = Model('{dbname}')
"""

RELATION_TEMPLATE = """\
#-*- coding: utf-8 -*-

from {dbname}.db_connector import db

class {class_name}:
    __db = db
    def __new__(cls, **kwargs):
        return cls.__db.relation('{fqtn}', **kwargs)
"""

def camel_case(name):
    """Transform a string in camel case."""
    ccname = []
    name = name.lower()
    capitalize = True
    for char in name:
        if not char.isalnum():
            capitalize = True
            continue
        if capitalize:
            ccname.append(char.upper())
            capitalize = False
            continue
        ccname.append(char)
    return ''.join(ccname)

AP_DESCRIPTION = """Generates python package from a PG database"""
AP_EPILOG = """"""

def main():
    """Script entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=AP_DESCRIPTION,
        epilog=AP_EPILOG)
    #group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "-p", "--package_name", help="Python package name default to DB_NAME"
    )
    parser.add_argument("db_name", help="Database name")
    args = parser.parse_args()
    package_name = args.package_name and args.package_name or args.db_name

    if not os.path.exists(package_name):
        os.mkdir(package_name)
        open('{}/db_connector.py'.format(package_name), 'w').write(
            DB_CONNECTOR_TEMPLATE)

    model = Model(args.db_name)
    for relation in model.relations():
        _, fqtn = relation.split()
        path = fqtn.split('.')

        fqtn = '.'.join(path[1:])

        path[0] = package_name
        module_path = '{}.py'.format('/'.join(path))
        module_name = path[-1]
        path = '/'.join(path[:-1])
        if not os.path.exists(path):
            os.makedirs(path)
        open(module_path, 'w').write(
            RELATION_TEMPLATE.format(
                dbname=args.db_name,
                class_name=camel_case(module_name), fqtn=fqtn))
    for root, dirs, files in os.walk(package_name):
        all_ = (
            [dir for dir in dirs if dir != '__pycache__'] +
            [file.replace('.py', '')
             for file in files
             if re.findall('.py$', file) and
             file != '__init__.py' and
             file != '__pycache__']
        )
        open('{}/__init__.py'.format(root), 'w').write(
            '__all__ = {}\n'.format(all_))

if __name__ == '__main__':
    main()
