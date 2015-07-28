#!/usr/bin/env python3

import asyncio
import time
import logging

class Throttle:
    """Throttle for an asyncio stream"""

    def __init__(self, rate_limit, interval=1.0, loop=None):
        """
        :param rate_limit: the limit in bytes to read/write per interval
        :type: int
        :param interval: the limitation time frame in seconds
        :type: float
        """
        self.rate_limit = rate_limit
        self.interval = interval
        self._interv_start = 0
        self._io_in_interv = 0
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def _reset_interval(self, timestamp=-1):
        """starts a new interval at the given timestamp
        
        :param timestamp: the timestamp in seconds of the interval start
        :type: float
        :rtype: None
        """
        self._io_in_interv = 0
        self._interv_start = timestamp if timestamp >= 0 else time.time()

    def time_left(self):
        """returns the number of seconds left in the current interval
        
        If the interval has already passed, this returns 0.

        :returns: seconds left until the interval ends
        :rtype: float
        """
        now = time.time()
        if now - self._interv_start > self.interval:
            return 0

        remaining = self.interval - (now - self._interv_start)
        return remaining

    def allowed_io(self):
        """checks if a requested IO action is allowed

        :returns: number of bytes allowed to read/write
        :rtype: int
        """
        if self.time_left() == 0:
            self._reset_interval()
        return self.rate_limit - self._io_in_interv

    def add_io(self, byte_count):
        """registers a number of bytes read/written

        :param byte_count: number of bytes to add to the current interval
        :type: int
        :rtype: None
        """
        self._io_in_interv += byte_count

    @asyncio.coroutine
    def wait_remaining(self):
        """waits until the current interval has passed

        This makes sure a new IO action is allowed
        :rtype: None
        """
        time_left = self.time_left()
        yield from asyncio.sleep(time_left)

class ThrottledStreamReader:
    def __init__(self, base_stream, rate_limit, interval=1.0):
        self._throttle = Throttle(rate_limit, interval)
        self._base_stream = base_stream
        self._transport = None

    def exception(self):
        return self._base_stream.exception

    def set_exception(self, exc):
        self._base_stream.set_exception(exc)

    def set_transport(self, transport):
        self._base_stream.set_transport(transport)
        self._transport = transport

    def feed_eof(self):
        self._base_stream.feed_eof()

    def at_eof(self):
        return self._base_stream.at_eof()

    def feed_data(self, data):
        self._base_stream.feed_data(data)
        self._throttle.check_interval()

    @asyncio.coroutine
    def readline(self):
        return (yield from self._base_stream.readline())

    @asyncio.coroutine
    def read(self, n=-1):
        if not n:
            return b""

        data = bytearray()
        bytes_left = n

        while not self._base_stream.at_eof() and (n < 0 or bytes_left > 0):
            to_read = self._throttle.allowed_io()
            logging.debug("[reader] allowed bytes to read: %d", to_read)
            if bytes_left > 0:
                to_read = min(to_read, bytes_left)

            chunk = yield from self._base_stream.read(to_read)
            data.extend(chunk)
            logging.debug("[reader] read chunk of size %d", len(chunk))

            self._throttle.add_io(len(chunk))

            if self._throttle.allowed_io() == 0:
                self._transport.pause_reading()
                yield from self._throttle.wait_remaining()
                self._transport.resume_reading()

            bytes_left -= len(chunk)

        return bytes(data)

    @asyncio.coroutine
    def readexactly(self, n):
        return (yield from self._base_stream.readexactly(n))

class TestReadTransport(asyncio.ReadTransport):
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
        logging.debug("[transport] scheduled data feed")

    def _feed_data(self):
        if self._closed:
            raise RuntimeError("closed")
        logging.debug("[transport] feeding %d bytes", self._chunk_size)
        self._protocol.data_received(bytes(self._chunk_size))
        self._bytes_fed += self._chunk_size

        if self._bytes_fed >= self._total_size:
            self._protocol.eof_received()
            self.close()
        elif not self._paused:
            self._schedule_data_feeding()

    def open(self):
        if self._closed:
            raise RuntimeError("closed")
        self._protocol.connection_made(self)
        logging.debug("[transport] opened")
        self._feed_data()

    def pause_reading(self):
        if self._closed:
            raise RuntimeError("closed")
        if self._paused:
            raise RuntimeError("already paused")
        if self._feed_handle is not None:
            self._feed_handle.cancel()
            self._feed_handle = None
        self._paused = True
        logging.debug("[transport] paused")

    def resume_reading(self):
        if self._closed:
            raise RuntimeError("closed")
        if not self._paused:
            raise RuntimeError("not paused")
        self._schedule_data_feeding()
        self._paused = False
        logging.debug("[transport] resumed")

    def close(self):
        if self._closed:
            return
        self._protocol.connection_lost(None)
        self.pause_reading()
        self._closed = True
        if self.closed_callback is not None:
            self._loop.call_soon(self.closed_callback)
        logging.debug("[transport] closed")

@asyncio.coroutine
def run_reader_test():
    # test transport: write 1024 bytes, 100 bytes per second
    # throttled reader: limit transmit rate to 10 bytes per second,
    #  while data is requested in 200 byte chunks

    closed_waiter = asyncio.Future()

    def transport_closed():
        logging.debug("[test] got transport closed callback")
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
            "[test] read attempt %d: read %d bytes",
            attempt, len(data))
        attempt += 1
        amount += len(data)

    logging.info(
        "[test] reading rate: %.3f bytes per second",
        amount / (time.time() - start_time))

    yield from closed_waiter

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S")
    loop = asyncio.get_event_loop()

    print("started")
    try:
        loop.run_until_complete(run_reader_test())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("ended")
