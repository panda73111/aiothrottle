#!/usr/bin/env python3

import asyncio
import logging
from aiothrottle import ThrottledStreamReader


class TestReadTransport(asyncio.ReadTransport):
    def __init__(
            self, protocol,
            total_size, chunk_size, interval=1.0, loop=None):
        super().__init__()
        self._protocol = protocol
        self._total_size = total_size
        self._chunk_size = int(chunk_size)
        self._interval = interval
        self._paused = False
        self._closed = False
        self._loop = loop or asyncio.get_event_loop()
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
        self._protocol.eof_received()
        self._protocol.connection_lost(None)
        self.pause_reading()
        self._closed = True
        if self.closed_callback is not None:
            self._loop.call_soon(self.closed_callback)
        logging.debug("[transport] closed")


class TestProtocol(asyncio.streams.FlowControlMixin, asyncio.Protocol):
    """Helper class to adapt between Transport and StreamReader."""

    def __init__(self, loop=None):
        super().__init__(loop=loop)

        self.transport = None
        self.paused = False
        self.reader = None

    def is_connected(self):
        return self.transport is not None

    def set_reader(self, reader):
        self.reader = reader

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = None

        if exc is None:
            self.reader.feed_eof()
        else:
            self.reader.set_exception(exc)

        super().connection_lost(exc)

    def data_received(self, data):
        self.reader.feed_data(data)

    def eof_received(self):
        self.reader.feed_eof()


@asyncio.coroutine
def run_reader_test():
    # test transport: write 1024 bytes, 100 bytes per second
    # throttled reader: limit transmit rate to 40 bytes per second,
    #  while data is requested in 200 byte chunks

    closed_waiter = asyncio.Future()

    def transport_closed():
        logging.debug("[test] got transport closed callback")
        closed_waiter.set_result(None)

    loop = asyncio.get_event_loop()

    protocol = TestProtocol(loop=loop)
    reader = ThrottledStreamReader(protocol, rate_limit=40, loop=loop)
    protocol.set_reader(reader)

    transport = TestReadTransport(
        protocol, total_size=1024, chunk_size=100, loop=loop)
    transport.closed_callback = transport_closed
    transport.open()

    read_more = True
    attempt = 0
    amount = 0
    start_time = loop.time()
    while read_more:
        data = yield from reader.read(200)
        data_len = len(data)

        logging.debug(
            "[test] read attempt %d: read %d bytes",
            attempt, data_len)
        attempt += 1
        amount += data_len

        read_more = data_len != 0

    logging.info(
        "[test] reading rate: %.3f bytes per second",
        amount / (loop.time() - start_time))

    yield from closed_waiter


def main():
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

main()
