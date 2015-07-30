
import asyncio
import aiohttp
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
        self._interv_start = timestamp if timestamp >= 0 else self._loop.time()
        logging.debug("[throttle] reset interval")

    def time_left(self):
        """returns the number of seconds left in the current interval

        If the interval has already passed, this returns 0.

        :returns: seconds left until the interval ends
        :rtype: float
        """
        now = self._loop.time()
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


class ThrottledStreamReader(aiohttp.StreamReader):

    def __init__(
            self, stream, rate_limit, interval=1.0,
            buffer_limit=2**16, loop=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._loop = loop or asyncio.get_event_loop()
        self._throttle = Throttle(
            rate_limit, interval, self._loop)
        self._stream = stream
        self._b_limit = buffer_limit * 2
        self._bytes_fed = 0

        # resume transport reading
        if stream.paused:
            try:
                stream.transport.resume_reading()
            except AttributeError:
                pass

    def _try_pause(self):
        try:
            self._stream.transport.pause_reading()
        except AttributeError:
            pass
        else:
            self._stream.paused = True

    def _try_resume(self):
        try:
            self._stream.transport.resume_reading()
        except AttributeError:
            pass
        else:
            self._stream.paused = False

    def feed_data(self, data, size=0):
        has_waiter = (
            self._waiter is not None and not self._waiter.cancelled())

        super().feed_data(data)

        # watch the buffer limit
        if (
                not self._stream.paused and
                not has_waiter and len(self._buffer) > self._b_limit):
            self._try_pause()
            return

        # watch the rate limit
        data_len = len(data)
        allowed = self._throttle.allowed_io()
        if allowed - data_len <= 0:
            self._try_pause()
            time_left = self._throttle.time_left()
            self._loop.call_later(time_left, self._check_limits)

    def _check_limits(self):
        # watch the rate limit
        allowed = self._throttle.allowed_io()
        if allowed - self._bytes_fed <= 0:
            self._bytes_fed += self._throttle.rate_limit
            time_left = self._throttle.time_left()
            self._loop.call_later(time_left, self._check_limits)
            return

        # watch the buffer limit
        size = len(self._buffer)
        if self._stream.paused:
            if size < self._b_limit:
                self._try_resume()
        else:
            if size > self._b_limit:
                self._try_pause()

    @asyncio.coroutine
    def read(self, byte_count=-1):
        logging.debug("reading %d bytes", byte_count)
        data = yield from super().read(byte_count)
        self._check_limits()
        return data

    @asyncio.coroutine
    def readline(self):
        logging.debug("reading line")
        data = yield from super().readline()
        self._check_limits()
        return data

    @asyncio.coroutine
    def readany(self):
        logging.debug("reading anything")
        data = yield from super().readany()
        self._check_limits()
        return data

    @asyncio.coroutine
    def readexactly(self, byte_count):
        logging.debug("reading exactly %d bytes", byte_count)
        data = yield from super().readexactly(byte_count)
        self._check_limits()
        return data
