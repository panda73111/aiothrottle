
import asyncio
import aiohttp
import logging


LOGGER = logging.getLogger(__package__)


class Throttle:
    """Throttle for IO operations"""

    def __init__(self, rate_limit, loop=None):
        """
        :param rate_limit: the limit in bytes to read/write per interval
        :type: int
        """
        self.rate_limit = rate_limit
        self._io = 0
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self._interv_start = loop.time()

    def time_left(self):
        """returns the number of seconds left until the rate limit is reached

        :returns: seconds left until the rate limit is reached
        :rtype: float
        """
        remaining = self._io / self.rate_limit
        LOGGER.debug("[throttle] time remaining: %.3f", remaining)
        return remaining

    def add_io(self, byte_count):
        """registers a number of bytes read/written

        :param byte_count: number of bytes to add to the current interval
        :type: int
        :rtype: None
        """
        self._io += byte_count
        LOGGER.debug(
            "[throttle] added bytes: %d, now: %d",
            byte_count, self._io)

    def reset_io(self):
        """resets the registered IO actions

        :rtype: None
        """
        self._io = 0
        LOGGER.debug("[throttle] reset IO")

    @asyncio.coroutine
    def wait_remaining(self):
        """waits until the rate limit is reached

        :rtype: None
        """
        time_left = self.time_left()
        LOGGER.debug("[throttle] sleeping for %.3f seconds", time_left)
        yield from asyncio.sleep(time_left)


class ThrottledStreamReader(aiohttp.StreamReader):

    def __init__(
            self, stream, rate_limit,
            buffer_limit=2**16, loop=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._loop = loop or asyncio.get_event_loop()
        self._throttle = Throttle(rate_limit, self._loop)
        self._stream = stream
        self._b_limit = buffer_limit * 2
        self._check_handle = None

        # resume transport reading
        if stream.paused:
            try:
                stream.transport.resume_reading()
            except AttributeError:
                pass

    def _try_pause(self):
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
        if not self._stream.paused:
            return
        try:
            self._stream.transport.resume_reading()
        except AttributeError:
            pass
        else:
            self._stream.paused = False
            LOGGER.debug("[reader] resumed")

    def feed_data(self, data, size=0):
        LOGGER.debug("[reader] got fed %d bytes", len(data))
        super().feed_data(data)
        self._throttle.reset_io()
        self._throttle.add_io(len(data))
        self._check_limits()

    def _check_callback(self):
        self._check_handle = None
        self._try_resume()

    def _check_limits(self):
        if self._check_handle is not None:
            self._check_handle.cancel()

        self._try_pause()

        # watch the buffer limit
        buf_size = len(self._buffer)
        if buf_size < self._b_limit:

            # resume as soon as the target rate is reached
            self._check_handle = self._loop.call_later(
                self._throttle.time_left(), self._check_callback)

    @asyncio.coroutine
    def read(self, byte_count=-1):
        LOGGER.debug("[reader] reading %d bytes", byte_count)
        data = yield from super().read(byte_count)
        self._check_limits()
        return data

    @asyncio.coroutine
    def readline(self):
        LOGGER.debug("[reader] reading line")
        data = yield from super().readline()
        self._check_limits()
        return data

    @asyncio.coroutine
    def readany(self):
        LOGGER.debug("[reader] reading anything")
        data = yield from super().readany()
        self._check_limits()
        return data

    @asyncio.coroutine
    def readexactly(self, byte_count):
        LOGGER.debug("[reader] reading exactly %d bytes", byte_count)
        data = yield from super().readexactly(byte_count)
        self._check_limits()
        return data
