
"""
Throttle: Manages rate limiting for general connections
ThrottledStreamReader: Throttles aiohttp downloads
"""

import asyncio
import aiohttp
import logging
import functools


LOGGER = logging.getLogger(__package__)


class Throttle:
    """Throttle for IO operations

    As soon as an IO action is registered using :meth:`add_io`,
    :meth:`time_left` returns the seconds to wail until
    ``[byte count] / [time passed] = [rate limit]``.
    After that, :meth:`reset_io` has to be called to measure the new rate.
    """

    def __init__(self, limit, loop=None):
        """
        :param int limit: the limit in bytes to read/write per second
        :raises: :class:`ValueError`: invalid rate given
        """
        self._limit = 0
        self.limit = limit
        self._io = 0
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self._interv_start = loop.time()

    @property
    def limit(self):
        """
        :returns: the limit in bytes to read/write per second
        :rtype: int
        """
        return self._limit

    @limit.setter
    def limit(self, value):
        """
        :param value: the limit in bytes to read/write per second
        :raises: :class:`ValueError` invalid rate given
        """
        if value <= 0:
            raise ValueError("rate_limit has to be greater than 0")
        self._limit = value

    def time_left(self):
        """returns the number of seconds left until the rate limit is reached

        :returns: seconds left until the rate limit is reached
        :rtype: float
        """
        remaining = self._io / self._limit
        LOGGER.debug("[throttle] time remaining: %.3f", remaining)
        return remaining

    def add_io(self, byte_count):
        """registers a number of bytes read/written

        :param int byte_count: number of bytes to add to the current rate
        """
        self._io += byte_count
        LOGGER.debug(
            "[throttle] added bytes: %d, now: %d",
            byte_count, self._io)

    def reset_io(self):
        """resets the registered IO actions"""
        self._io = 0
        LOGGER.debug("[throttle] reset IO")

    @asyncio.coroutine
    def wait_remaining(self):
        """waits until the rate limit is reached"""
        time_left = self.time_left()
        LOGGER.debug("[throttle] sleeping for %.3f seconds", time_left)
        yield from asyncio.sleep(time_left)


class ThrottledStreamReader(aiohttp.StreamReader):
    """Throttling, flow controlling :class:`aiohttp.streams.StreamReader` for :meth:`aiohttp.request`

    Usage:
        >>> import functools
        >>> import aiohttp
        >>> import aiothrottle
        >>> kbps = 200
        >>> partial = functools.partial(
        >>>     aiothrottle.ThrottledStreamReader, rate_limit=kbps * 1024)
        >>> aiohttp.client_reqrep.ClientResponse.flow_control_class = partial
    """

    def __init__(
            self, stream, rate_limit,
            buffer_limit=2**16, loop=None, *args, **kwargs):
        """
        :param stream: the base stream containing the transport
        :type: aiohttp.parsers.StreamParser
        :param int rate_limit: the rate limit in bytes per second
        :param int buffer_limit: the internal buffer limit in bytes
        :param loop: the asyncio event loop
        :type: asyncio.base_events.BaseEventLoop
        :param tuple args: arguments passed through to StreamReader
        :param dict kwargs: keyword arguments passed through to StreamReader
        """
        super().__init__(*args, **kwargs)

        self._loop = loop or asyncio.get_event_loop()
        self._throttle = Throttle(rate_limit, self._loop)
        self._stream = stream
        self._b_limit = buffer_limit * 2
        self._check_handle = None
        self._limiting = True

        # resume transport reading
        if stream.paused:
            try:
                stream.transport.resume_reading()
            except AttributeError:
                pass

    def __del__(self):
        if self._check_handle is not None:
            self._check_handle.cancel()

    def limit_rate(self, limit):
        """Sets the rate limit of this response

        :param limit: the limit in bytes to read/write per second

        .. versionadded:: 0.1.1
        """
        self._throttle.limit = limit
        self._limiting = True

    def unlimit_rate(self):
        """Unlimits the rate of this response

        .. versionadded:: 0.1.1
        """
        self._limiting = False

    def _try_pause(self):
        """Pauses the transport if not already paused"""
        if self._stream.paused:
            return
        try:
            self._stream.transport.pause_reading()
        except AttributeError:
            pass
        else:
            self._stream.paused = True
            LOGGER.debug("[reader] paused")

    def _try_resume(self):
        """Resumed the transport if paused"""
        if not self._stream.paused:
            return
        try:
            self._stream.transport.resume_reading()
        except AttributeError:
            pass
        else:
            self._stream.paused = False
            LOGGER.debug("[reader] resumed")

    def feed_data(self, data, _=0):
        """Feeds data into the internal buffer"""
        LOGGER.debug("[reader] got fed %d bytes", len(data))
        super().feed_data(data)
        self._throttle.reset_io()
        self._throttle.add_io(len(data))
        self._check_limits()

    def _check_callback(self):
        """Tries to resume the transport after target limit is reached"""
        self._check_handle = None
        self._try_resume()

    def _check_buffer_limit(self, resume):
        """Controls the size of the internal buffer"""
        size = len(self._buffer)
        if self._stream.paused:
            if resume and size < self._b_limit:
                self._try_resume()
        else:
            if size > self._b_limit:
                self._try_pause()

    def _check_limits(self):
        """Controls rate and buffer size by pausing and resuming the transport"""
        if self._check_handle is not None:
            self._check_handle.cancel()
            self._check_handle = None

        if not self._limiting:
            self._check_buffer_limit(True)
            return

        self._try_pause()

        # watch the buffer limit
        buf_size = len(self._buffer)
        if buf_size < self._b_limit:

            # resume as soon as the target rate is reached
            self._check_handle = self._loop.call_later(
                self._throttle.time_left(), self._check_callback)

    @asyncio.coroutine
    def read(self, byte_count=-1):
        """Reads at most the requested number of bytes from the internal buffer

        :param int byte_count: the number of bytes to read
        :returns: the data
        :rtype: bytes
        """
        LOGGER.debug("[reader] reading %d bytes", byte_count)
        data = yield from super().read(byte_count)
        self._check_buffer_limit(not self._limiting)
        return data

    @asyncio.coroutine
    def readline(self):
        """Reads bytes from the internal buffer until ``\\n`` is found

        :returns: the data
        :rtype: bytes
        """
        LOGGER.debug("[reader] reading line")
        data = yield from super().readline()
        self._check_buffer_limit(not self._limiting)
        return data

    @asyncio.coroutine
    def readany(self):
        """Reads the bytes next received from the internal buffer

        :returns: the data
        :rtype: bytes
        """
        LOGGER.debug("[reader] reading anything")
        data = yield from super().readany()
        self._check_buffer_limit(not self._limiting)
        return data

    @asyncio.coroutine
    def readexactly(self, byte_count):
        """Reads the requested number of bytes from the internal buffer

        This raises :class:`asyncio.IncompleteReadError` if
        the stream ended before enough bytes were received

        :param int byte_count: the number of bytes to read
        :returns: the data
        :rtype: bytes
        """
        LOGGER.debug("[reader] reading exactly %d bytes", byte_count)
        data = yield from super().readexactly(byte_count)
        self._check_buffer_limit(not self._limiting)
        return data


def limit_rate(limit):
    """Limits the rate of all subsequent aiohttp requests

    :param limit: the limit in bytes to read/write per second

    .. versionadded:: 0.1.1
    """
    partial = functools.partial(
        ThrottledStreamReader, rate_limit=limit)
    aiohttp.client_reqrep.ClientResponse.flow_control_class = partial


def unlimit_rate():
    """Unlimits the rate of all subsequent aiohttp requests

    .. versionadded:: 0.1.1
    """
    aiohttp.client_reqrep.ClientResponse.flow_control_class = (
        aiohttp.streams.FlowControlStreamReader)
