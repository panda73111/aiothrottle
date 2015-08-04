#!/usr/bin/env python3

import asyncio
import aiohttp
import aiothrottle


@asyncio.coroutine
def load_file(url):
    response = yield from aiohttp.request("GET", url)
    size = int(response.headers.get("Content-Length", "0"))

    loop = asyncio.get_event_loop()
    start_time = loop.time()

    with open("largefile.zip", "wb") as file:
        read_next = True
        loaded = 0
        while read_next:
            # read 1 MB chunks
            chunk = yield from response.content.read(2**20)
            file.write(chunk)

            print("%d%%" % int(loaded * 100 / size))

            chunk_len = len(chunk)
            loaded += chunk_len
            read_next = chunk_len != 0
    response.close()

    end_time = loop.time()
    download_time = end_time - start_time

    print("download rate: %d KB/s",
          int(size / download_time / 1024))

# setup the rate limit to 200 KB/s
aiothrottle.limit_rate(200 * 1024)

# download a large file without blocking bandwidth
loop = asyncio.get_event_loop()
loop.run_until_complete(load_file(
    "http://ipv4.download.thinkbroadband.com/5MB.zip"))

# unset the rate limit
aiothrottle.unlimit_rate()
