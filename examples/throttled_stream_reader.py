#!/usr/bin/env python3

import asyncio
import os
import aiohttp
import aiothrottle


@asyncio.coroutine
def load_file(url, loop):
    response = yield from aiohttp.request("GET", url, loop=loop)
    size = int(response.headers.get("Content-Length", "0"))

    start_time = loop.time()

    with open(os.devnull, "wb") as file:
        read_next = True
        loaded = 0
        prev_progress = -1
        prev_print_time = start_time
        prev_print_loaded = 0
        while read_next:
            # read 1 MB chunks
            chunk = yield from response.content.read(2**20)
            file.write(chunk)

            chunk_len = len(chunk)
            loaded += chunk_len

            progress = int(loaded * 100 / size)
            if progress and progress != prev_progress:
                # print progress and current download rate
                now = loop.time()
                period = now - prev_print_time
                loaded_since = loaded - prev_print_loaded
                temp_rate = loaded_since / period
                print("%d%% - %d KB/s" % (progress, temp_rate / 1024))
                prev_print_time = now
                prev_print_loaded = loaded
            prev_progress = progress

            read_next = chunk_len != 0
    response.close()

    end_time = loop.time()
    download_time = end_time - start_time

    print(
        "download rate: %d KB/s" %
        int(size / download_time / 1024))


def main():
    # setup the rate limit to 200 KB/s
    aiothrottle.limit_rate(200 * 1024)

    # download a large file without blocking bandwidth
    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_file(
        "http://ipv4.download.thinkbroadband.com/10MB.zip", loop))

    # unset the rate limit
    aiothrottle.unlimit_rate()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
