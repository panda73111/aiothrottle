Throttling, flow controlling StreamReader for aiohttp
=====================================================

Requirements
------------

- Python >= 3.3
- asyncio https://pypi.python.org/pypi/asyncio
- aiohttp https://pypi.python.org/pypi/aiohttp


License
-------

``aiothrottle`` is offered under the GPL v3 license.


Source code
------------

The latest developer version is available in a github repository:
https://github.com/panda73111/aiothrottle


Usage
-----

.. code:: python

    import functools
    import aiohttp
    import aiothrottle

    # setup the rate limit
    kbps = 200
    partial = functools.partial(
        aiothrottle.ThrottledStreamReader, rate_limit=kbps * 1024)
    aiohttp.client_reqrep.ClientResponse.flow_control_class = partial

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
    aiohttp.client_reqrep.ClientResponse.flow_control_class = (
        aiohttp.streams.FlowControlStreamReader)
