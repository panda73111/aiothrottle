Throttling, flow controlling StreamReader for aiohttp
=====================================================

.. image:: https://img.shields.io/pypi/v/aiothrottle.svg
    :target: https://pypi.python.org/pypi/aiothrottle

.. image:: https://readthedocs.org/projects/aiothrottle/badge/?version=latest
    :target: https://readthedocs.org/projects/aiothrottle/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/pyversions/aiothrottle.svg
    :target: https://www.python.org/

.. image:: https://img.shields.io/pypi/l/aiothrottle.svg
    :target: http://opensource.org/licenses/GPL-3.0

Requirements
------------

- Python >= 3.3
- asyncio https://pypi.python.org/pypi/asyncio
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

    import functools
    import aiohttp
    import aiothrottle

    # setup the rate limit to 200 KB/s
    aiothrottle.limit_rate(200 * 1024)

    # download a large file without blocking bandwidth
    response = aiohttp.request("GET", "http://example.com/largefile.zip")
    with open("largefile.zip", "wb") as file:
        read_next = True
        while read_next:
            # read 1 MB chunks
            chunk = response.content.read(2**20)
            file.write(chunk)
            read_next = len(chunk) != 0
    response.close()

    # unset the rate limit
    aiothrottle.unlimit_rate()


TODO
----

- Unit tests
- Upload rate limiting class
- General socket limiting class
