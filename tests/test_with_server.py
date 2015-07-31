
import asyncio
import logging
import aiohttp
import functools
import sys
import aiothrottle
from aiohttp import web


@asyncio.coroutine
def stream_response(req, res):
    res.enable_chunked_encoding()
    res.start(req)
    for _ in range(1024):
        logging.debug("[server] sending 1 KB")
        res.write(bytes(1024))
        yield from res.drain()
    yield from res.write_eof()


@asyncio.coroutine
def reply(req):
    res = web.StreamResponse()
    asyncio.async(stream_response(req, res))
    return res


def setup_server(loop, port):
    app = web.Application()
    app.router.add_route('GET', '/', reply)

    handler = app.make_handler()
    future = loop.create_server(handler, '0.0.0.0', port)
    srv = loop.run_until_complete(future)
    print('serving on', srv.sockets[0].getsockname())
    return srv, app, handler


@asyncio.coroutine
def run_throttle_test(loop, port):
    res = yield from aiohttp.request("GET", "http://localhost:%d/" % port)
    logging.debug("[test] got response: %s", res)

    start_time = loop.time()

    data = yield from res.read()
    amount = len(data)
    logging.debug("[test] read %d bytes", amount)

    end_time = loop.time()
    if start_time == end_time:
        logging.debug("[test] no time passed!")
    else:
        logging.info(
            "[test] reading rate: %.3f bytes per second",
            amount / (loop.time() - start_time))


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout)

    partial = functools.partial(
        aiothrottle.ThrottledStreamReader, rate_limit=40)
    aiohttp.client_reqrep.ClientResponse.flow_control_class = partial

    loop = asyncio.get_event_loop()

    port = 8080
    srv, app, handler = setup_server(loop, port)

    print("started")
    try:
        loop.run_until_complete(run_throttle_test(loop, port))
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(handler.finish_connections(1.0))
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.finish())
        loop.close()
        print("ended")


main()
