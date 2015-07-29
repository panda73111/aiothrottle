#!/usr/bin/env python3

import asyncio
import aiohttp
import time
import logging

class Throttle:
    """Throttle for IO operations"""

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
        logging.debug("[throttle] reset interval")

    def time_left(self):
        """returns the number of seconds left in the current interval

        If the interval has already passed, this returns 0.

        :returns: seconds left until the interval ends
        :rtype: float
        """
        now = time.time()
        if now - self._interv_start > self.interval:
            logging.debug("[throttle] seconds left: 0")
            return 0

        remaining = self.interval - (now - self._interv_start)
        logging.debug("[throttle] seconds left: %.3f", remaining)
        return remaining

    def allowed_io(self):
        """checks if a requested IO action is allowed

        :returns: number of bytes allowed to read/write
        :rtype: int
        """
        if self.time_left() == 0:
            self._reset_interval()
        allowed = self.rate_limit - self._io_in_interv
        logging.debug("[throttle] allowed bytes: %d", allowed)
        return allowed

    def add_io(self, byte_count):
        """registers a number of bytes read/written

        :param byte_count: number of bytes to add to the current interval
        :type: int
        :rtype: None
        """
        self._io_in_interv += byte_count
        logging.debug(
            "[throttle] added bytes: %d, now: %d",
            byte_count, self._io_in_interv)

    @asyncio.coroutine
    def wait_remaining(self):
        """waits until the current interval has passed

        This makes sure a new IO action is allowed
        :rtype: None
        """
        time_left = self.time_left()
        logging.debug("[throttle] sleeping for %.3f seconds", time_left)
        yield from asyncio.sleep(time_left)

class ThrottledFlowControlStreamReader(aiohttp.StreamReader):

    def __init__(self, stream, limit=DEFAULT_LIMIT, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._stream = stream
        self._b_limit = limit * 2

        # resume transport reading
        if stream.paused:
            try:
                self._stream.transport.resume_reading()
            except (AttributeError, NotImplementedError):
                pass

    def feed_data(self, data, size=0):
        has_waiter = self._waiter is not None and not self._waiter.cancelled()

        super().feed_data(data)

        if (not self._stream.paused and
                not has_waiter and len(self._buffer) > self._b_limit):
            try:
                self._stream.transport.pause_reading()
            except (AttributeError, NotImplementedError):
                pass
            else:
                self._stream.paused = True

    def _maybe_resume(self):
        size = len(self._buffer)
        if self._stream.paused:
            if size < self._b_limit:
                try:
                    self._stream.transport.resume_reading()
                except (AttributeError, NotImplementedError):
                    pass
                else:
                    self._stream.paused = False
        else:
            if size > self._b_limit:
                try:
                    self._stream.transport.pause_reading()
                except (AttributeError, NotImplementedError):
                    pass
                else:
                    self._stream.paused = True

    @maybe_resume
    def read(self, byte_count=-1):
        data = yield from super().read(byte_count)
        self._maybe_resume()
        return data

    @maybe_resume
    def readline(self):
        data = yield from super().readline()
        self._maybe_resume()
        return data

    @maybe_resume
    def readany(self):
        data = yield from super().readany()
        self._maybe_resume()
        return data

    @maybe_resume
    def readexactly(self, byte_count):
        data = yield from super().readexactly(byte_count)
        self._maybe_resume()
        return data

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
    # throttled reader: limit transmit rate to 40 bytes per second,
    #  while data is requested in 200 byte chunks

    closed_waiter = asyncio.Future()

    def transport_closed():
        logging.debug("[test] got transport closed callback")
        closed_waiter.set_result(None)

    base_reader = asyncio.StreamReader()
    reader = ThrottledStreamReader(base_reader, rate_limit=40)

    protocol = asyncio.StreamReaderProtocol(reader)

    transport = TestReadTransport(
        protocol, total_size=1024, chunk_size=100)
    transport.closed_callback = transport_closed
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
