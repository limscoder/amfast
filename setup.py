import os

from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, Feature

from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext

from amfast import __version__

extensions = Feature(
    "AMF encoder/decoder C extension.",
    standard = True,
    optional = True,
    ext_modules = [
        Extension('amfast.encode',
            sources=[os.path.join('amfast', 'ext_src', 'encoder.c'),
                os.path.join('amfast', 'ext_src', 'amf.c')],
            depends=[os.path.join('amfast', 'ext_src', 'amf.h'),
                os.path.join('amfast', 'ext_src', 'context.h')]),
        Extension('amfast.decode',
            sources=[os.path.join('amfast', 'ext_src', 'decoder.c'),
                os.path.join('amfast', 'ext_src', 'amf.c')],
            depends=[os.path.join('amfast', 'ext_src', 'amf.h'),
                os.path.join('amfast', 'ext_src', 'context.h')]),
        Extension('amfast.buffer',
            sources=[os.path.join('amfast', 'ext_src', 'buffer.c')],
            depends=[os.path.join('amfast', 'ext_src', 'buffer.h')]),
        Extension('amfast.context',
            sources=[os.path.join('amfast', 'ext_src', 'context.c')],
            depends=[os.path.join('amfast', 'ext_src', 'context.h')])
    ])

setup(name="AmFast",
    version = __version__,
    description = "Flash remoting framework. Includes support for NetConnection, RemoteObject, IExternizeable, Flex Producer/Consumer messaging, custom type serialization, and a C-based AMF encoder/decoder.",
    url = "http://code.google.com/p/amfast/",
    author = "Dave Thompson",
    author_email = "dthomp325@gmail.com",
    maintainer = "Dave Thompson",
    maintainer_email = "dthomp325@gmail.com",
    keywords = "amf amf0 amf3 flash flex pyamf",
    platforms = ["any"],
    test_suite = "tests.suite",
    packages = ['amfast', 'amfast.class_def', 'amfast.remoting'],
    features = {'extensions': extensions},
    install_requires = [
        'uuid>=1.3.0',
    ],
    classifiers = [
        "Programming Language :: Python :: 2.4",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Utilities"
    ])
