# coding: utf-8
from setuptools import setup, find_packages
import codecs
from os import path
import io
import re

with io.open("reki/__init__.py", "rt", encoding="utf8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)

here = path.abspath(path.dirname(__file__))

with codecs.open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='reki',

    version=version,

    description='A data preparation tool for CEMC/CMA.',
    long_description=long_description,
    long_description_content_type='text/markdown',

    url='https://github.com/cemc-oper/reki',
    project_urls={
        "Documentation": 'https://reki.readthedocs.io',
    },

    author='perillaroc',
    author_email='perillaroc@gmail.com',

    license='Apache License 2.0',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],

    keywords='cemc data grib2',

    packages=find_packages(exclude=['docs', 'tests', 'example']),

    include_package_data=True,

    install_requires=[
        "pyyaml",
        "jinja2",
        "numpy",
        "pandas",
        "xarray",
        "eccodes",
        "click",
        "tqdm",
    ],

    extras_require={
        "cfgrib": [
            "cfgrib",
        ],
        "gdata": [
            "protobuf",
            "requests",
        ],
        "test": ['pytest'],
        "cov": ['pytest-cov', 'codecov']
    },

    entry_points={
        "console_scripts": [
        ],
    }
)
