aiothrottle
===========

Throttling, flow controlling StreamReader for aiohttp

.. image:: https://img.shields.io/pypi/v/aiothrottle.svg
    :target: https://pypi.python.org/pypi/aiothrottle
    :alt: Package Version

.. image:: https://travis-ci.org/panda73111/aiothrottle.svg?branch=master
    :target: https://travis-ci.org/panda73111/aiothrottle
    :alt: Build Status

.. image:: https://coveralls.io/repos/panda73111/aiothrottle/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/panda73111/aiothrottle?branch=master
    :alt: Coverage Status

.. image:: https://readthedocs.org/projects/aiothrottle/badge/?version=latest
    :target: https://readthedocs.org/projects/aiothrottle/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/aiothrottle.svg
    :target: https://www.python.org/
    :alt: Python Version

.. image:: https://img.shields.io/pypi/l/aiothrottle.svg
    :target: http://opensource.org/licenses/GPL-3.0
    :alt: GPLv3

Requirements
------------

- Python >= 3.4.2
- aiohttp https://pypi.python.org/pypi/aiohttp


License
-------

``aiothrottle`` is offered under the GPL v3 license.


Documentation
-------------

https://aiothrottle.readthedocs.org/


Source code
-----------

The latest developer version is available in a github repository:
https://github.com/panda73111/aiothrottle


Usage
-----

.. code:: python

    import asyncio
    import aiohttp
    import aiothrottle

    @asyncio.coroutine
    def load_file(url):
        response = yield from aiohttp.request("GET", url)

        data = yield from response.read()
        with open("largefile.zip", "wb") as file:
            file.write(data)

        response.close()

    # setup the rate limit to 200 KB/s
    aiothrottle.limit_rate(200 * 1024)

    # download a large file without blocking bandwidth
    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_file(
        "http://example.com/largefile.zip"))

    # unset the rate limit
    aiothrottle.unlimit_rate()


TODO
----

- Upload rate limiting class
- General socket limiting class
