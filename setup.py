#!/usr/bin/env python3

import sys
from setuptools import setup, find_packages


install_requires = ["aiohttp"]
if sys.version_info < (3, 4):
    install_requires += ["asyncio"]

setup(
    name="aiothrottle",
    version="0.1.0",
    packages=find_packages(),
    url="https://github.com/panda73111/aiothrottle",
    license="GPLv3",
    author="Sebastian H\xfcther",
    author_email="sebastian.huether@gmx.de",
    description="Throttled flow controlling StreamReader for aiohttp",
    install_requires=install_requires
)
