#!/usr/bin/env python3

import io
import asyncio
import time
from asyncio import Event

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
        self._throttle = Throttle(base_stream, limit, interval)

@asyncio.coroutine
def feed_data(stream, stop_event):
    print("feed watch task")
    FEEDING_AMOUNT = 2**30 # 1 GB
    CHUNK_SIZE = 1024
    amount_fed = 0
    while not stop_event.is_set():
        stream.feed_data(bytes(CHUNK_SIZE))
        amount_fed = amount_fed+CHUNK_SIZE
        if amount_fed >= FEEDING_AMOUNT:
            break
    print("feed task ended")

class TestReadTransport(asyncio.ReadTransport):
    # default limit: 1 GB
    def __init__(self, limit=2**30, chunk_size=1024, interval=1.0):
        self.limit = limit
        self.chunk_size = chunk_size
        self.interval = interval
        self._paused = False

class TestProtocol(asyncio.Protocol):
    pass

@asyncio.coroutine
def run_reader_test(base_stream_reader):
    reader = ThrottledStreamReader(base_stream_reader, 512)
    yield from asyncio.sleep(100)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    print("starting")
    try:
        protocol = TestProtocol()
        protocol.connection_made

        base_stream_reader = asyncio.StreamReader()
        base_stream_reader.set_transport
        stop_event = Event()

        asyncio.async(feed_data(base_stream_reader, stop_event))
        loop.run_until_complete(run_reader_test(base_stream_reader))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        print("ended")

