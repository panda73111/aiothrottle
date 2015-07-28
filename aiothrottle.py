#!/usr/bin/env python3

import asyncio
import time
import logging
from asyncio import Condition

class Throttle:
    """Throttle for an asnycio stream"""

    def __init__(self, base_stream, rate_limit, interval=1.0):
        """
        :param base_stream: the asyncio stream to be throttled
        :type: asyncio.StreamReader, asyncio.StreamWriter
        :param limit: the limit in bytes to read/write per interval
        :type: int
        :param interval: the limitation time frame (usually one second)
        :type: float
        """
        self.rate_limit = rate_limit
        self.interval = interval
        self._base_stream = base_stream
        self._interv_start = 0
        self._io_in_interv = 0
        self._new_interval_cond = Condition()

    @asyncio.coroutine
    def _new_interval(self):
        """notifies a waiting call that a new interval has started

        :rtype: None
        """
        with (yield from self._new_interval_cond):
            self._new_interval_cond.notify()

    def _reset_interval(self, timestamp):
        self._io_in_interv = 0
        self._interv_start = timestamp
        asyncio.async(self._new_interval())

    def check_interval(self):
        """checks if the current interval has passed and a new one has started

        This has to be called when new data is available, so that waiting
        calls get notified if the interval has passed
        :rtype: None
        """
        now = time.time()
        if now - self._interv_start > self.interval:
            self._reset_interval(now)

    def allowed_io(self):
        """checks if a requested IO action is allowed

        :returns: number of bytes allowed to read/write
        :rtype: int
        """
        self.check_interval()
        return self.rate_limit - self._io_in_interv

    def add_io(self, byte_count):
        """registers a number of bytes read/written

        :param byte_count: number of bytes to add to the current interval
        :type: int
        :rtype: None
        """
        self._io_in_interv += byte_count

class ThrottledStreamReader(asyncio.StreamReader):
    def __init__(self, base_stream, rate_limit, interval=1.0, buf_limit=2**16):
        super().__init__(limit=buf_limit)
        self._throttle = Throttle(base_stream, rate_limit, interval)

class TestReadTransport(asyncio.ReadTransport):
    # default limit: 1 GB
    def __init__(
            self, protocol,
            total_size, chunk_size, interval=1.0):
        super().__init__()
        self._protocol = protocol
        self._total_size = total_size
        self._chunk_size = int(chunk_size)
        self._interval = interval
        self._paused = False
        self._closed = False
        self._loop = asyncio.get_event_loop()
        self._feed_handle = None
        self._bytes_fed = 0
        self.closed_callback = None

    def _schedule_data_feeding(self):
        if self._feed_handle is not None:
            self._feed_handle.cancel()
        self._feed_handle = self._loop.call_later(
            self._interval, self._feed_data)
        logging.debug("scheduled data feed")

    def _feed_data(self):
        logging.debug("feeding %d bytes", self._chunk_size)
        self._protocol.data_received(bytes(self._chunk_size))
        self._bytes_fed += self._chunk_size

        if self._bytes_fed >= self._total_size:
            self._protocol.eof_received()
            self.close()
        elif not self._paused:
            self._schedule_data_feeding()

    def open(self):
        logging.debug("transport opened")
        self._schedule_data_feeding()

    def pause_reading(self):
        if self._feed_handle is not None:
            self._feed_handle.cancel()
            self._feed_handle = None
        self._paused = True
        logging.debug("transport paused")

    def resume_reading(self):
        self._schedule_data_feeding()
        self._paused = False
        logging.debug("transport resumed")

    def close(self):
        self.pause_reading()
        self._closed = True
        if self.closed_callback is not None:
            self._loop.call_soon(self.closed_callback)
        logging.debug("transport closed")

@asyncio.coroutine
def run_reader_test():
    # test transport: write 1024 bytes, 100 bytes per second
    # throttled reader: limit transmit rate to 10 bytes per second,
    #  while data is requested in 200 byte chunks

    closed_waiter = asyncio.Future()

    def transport_closed():
        logging.debug("got transport closed callback")
        closed_waiter.set_result(None)

    base_reader = asyncio.StreamReader()
    reader = ThrottledStreamReader(base_reader, rate_limit=10)

    protocol = asyncio.StreamReaderProtocol(reader)

    transport = TestReadTransport(
        protocol, total_size=1024, chunk_size=100)
    transport.closed_callback = transport_closed

    protocol.connection_made(transport)
    transport.open()

    data = b"0"
    attempt = 0
    amount = 0
    start_time = time.time()
    while len(data) != 0:
        data = yield from reader.read(200)
        logging.debug(
            "read attempt %d: read %d bytes",
            attempt, len(data))
        attempt += 1
        amount += len(data)

    logging.info(
        "reading rate: %.3f bytes per second",
        amount / (time.time() - start_time))

    yield from closed_waiter

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    print("started")
    try:
        loop.run_until_complete(run_reader_test())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("ended")
