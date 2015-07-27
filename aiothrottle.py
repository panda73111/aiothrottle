#!/usr/bin/env python3

import asyncio
import time
import logging

class ThrottlingError(Exception):
    """Error during throttling of an asyncio stream"""

    def __init__(self, allowed, added):
        """
        :param allowed: the allowed maximum number of bytes
        :type: int
        :param added: the actual number of bytes added
        :type: int
        """
        self.allowed = allowed
        self.added = added

class Throttle:
    """Throttle for an asnycio stream"""

    def __init__(self, base_stream, byte_limit, interval=1.0):
        """
        :param base_stream: the asyncio stream to be throttled
        :type: asyncio.StreamReader, asyncio.StreamWriter
        :param limit: the limit in bytes to read/write per interval
        :type: int
        :param interval: the limitation time frame (usually one second)
        :type: float
        """
        if base_stream is None:
            raise ValueError("base_stream must not be None")
        if byte_limit < 1:
            raise ValueError("byte_limit must be a positive integer")
        if interval <= 0.0:
            raise ValueError("interval must be positive")

        self.byte_limit = byte_limit
        self.interval = interval
        self._base_stream = base_stream
        self._interv_start = 0
        self._io_in_interv = 0

    def _check_interval(self):
        """checks if the current interval has passed and a new one has started

        :rtype: None
        """
        now = time.time()
        if now - self._interv_start > self.interval:
            self._io_in_interv = 0
            self._interv_start = now

    def allowed_io(self):
        """checks if a requested IO action is allowed

        :returns: number of bytes allowed to read/write
        :rtype: int
        """
        self._check_interval()
        return self.byte_limit - self._io_in_interv

    def add_io(self, byte_count):
        """registers a number of bytes read/written
        Throws a ThrottlingError if more than the allowed number of bytes
        is being added

        :param byte_count: number of bytes to add to the current interval
        :type: int
        :rtype: None
        """
        allowed = self.allowed_io()
        if byte_count > allowed:
            raise ThrottlingError(allowed, byte_count)

        self._io_in_interv += byte_count

class ThrottledStreamReader(asyncio.StreamReader):
    def __init__(self, base_stream, limit, interval=1.0):
        super().__init__()
        self._throttle = Throttle(base_stream, limit, interval)

class TestReadTransport(asyncio.ReadTransport):
    # default limit: 1 GB
    def __init__(
            self, protocol,
            limit=2**30, chunk_size=2**30/10, interval=1.0):
        super().__init__()
        self._protocol = protocol
        self._limit = limit
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

        if self._bytes_fed >= self._limit:
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
    future = asyncio.Future()

    def transport_closed():
        logging.debug("got transport closed callback")
        future.set_result(None)

    base_reader = asyncio.StreamReader()
    reader = ThrottledStreamReader(base_reader, 512)

    protocol = asyncio.StreamReaderProtocol(reader)

    transport = TestReadTransport(protocol)
    transport.closed_callback = transport_closed

    protocol.connection_made(transport)
    transport.open()

    data = b"0"
    while len(data) != 0:
        data = yield from reader.read(int(2**30/10))
        logging.debug("read %d bytes", len(data))

    yield from future

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

