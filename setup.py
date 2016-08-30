#!/usr/bin/env python3

import os
from setuptools import setup, find_packages


install_requires = ["aiohttp"]

tests_require = install_requires + ["nose"]


def read_file(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path) as file:
        text = file.read().strip()
    return text

setup(
    name="aiothrottle",
    version="0.1.3",
    packages=find_packages(),
    url="https://github.com/panda73111/aiothrottle",
    download_url=(
        "https://github.com/panda73111/aiothrottle/archive/v0.1.3.tar.gz"),
    license="GPLv3",
    author="Sebastian H\xfcther",
    author_email="sebastian.huether@gmx.de",
    description="Throttling, flow controlling StreamReader for aiohttp",
    long_description="\n\n".join(
        (read_file("README.rst"), read_file("CHANGES.txt"))),
    install_requires=install_requires,
    tests_require=tests_require,
    test_suite="nose.collector",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
    keywords=(
        "throttle bandwidth limit download "
        "http throughput asyncio aiohttp"),
)
