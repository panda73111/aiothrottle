
import asyncio
import logging
import aiohttp
import functools
import sys
import aiothrottle


@asyncio.coroutine
def run_throttle_test(loop, url):
    res = yield from aiohttp.request("GET", url)
    logging.debug("[test] got response: %s", res)

    start_time = loop.time()

    read_next = True
    amount = 0
    while read_next:
        # read 1 MB chunks
        data = yield from res.content.read(2**20)
        data_len = len(data)
        amount += data_len
        read_next = data_len != 0
    logging.debug("[test] read %d bytes", amount)

    end_time = loop.time()
    if start_time == end_time:
        logging.debug("[test] no time passed!")
    else:
        time_passed = loop.time() - start_time
        bps = amount / time_passed
        logging.info(
            "[test] %d:%02d passed, reading rate: %.3f KB/s",
            time_passed / 60, time_passed % 60, bps / 1024)


@asyncio.coroutine
def run_limit_test(loop, kbps):
    logging.info("[test] limiting to %d KB/s", kbps)
    partial = functools.partial(
        aiothrottle.ThrottledStreamReader, rate_limit=kbps * 1024)
    aiohttp.client_reqrep.ClientResponse.flow_control_class = partial

    url = "http://ipv4.download.thinkbroadband.com/10MB.zip"
    yield from run_throttle_test(loop, url)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        # filename=r"R:\output.txt"
        )

    print("started")
    loop = asyncio.get_event_loop()
    try:
        for kbps in range(100, 850, 50):
            loop.run_until_complete(run_limit_test(loop, kbps))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("ended")


main()
