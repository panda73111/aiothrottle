#!/usr/bin/env python3

import os
import sys
from setuptools import setup, find_packages
from aiothrottle import __version__


install_requires = ["aiohttp"]
if sys.version_info < (3, 4):
    install_requires += ["asyncio"]


def read_file(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path) as file:
        text = file.read().strip()
    return text

setup(
    name="aiothrottle",
    version=__version__,
    packages=find_packages(),
    url="https://github.com/panda73111/aiothrottle",
    download_url=(
        "https://github.com/panda73111/aiothrottle/archive/v0.1.1.tar.gz"),
    license="GPLv3",
    author="Sebastian H\xfcther",
    author_email="sebastian.huether@gmx.de",
    description="Throttling, flow controlling StreamReader for aiohttp",
    long_description="\n\n".join(
        (read_file("README.rst"), read_file("CHANGES.txt"))),
    install_requires=install_requires,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],
    keywords=(
        "throttle bandwidth limit download "
        "http throughput asyncio aiohttp"),
)
