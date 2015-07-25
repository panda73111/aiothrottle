
import io
import asyncio

class Throttle:
    def __init__(self, limit, interval):
        self.limit = limit
        self.interval = interval

class ThrottledStreamReader(asyncio.StreamReader):
    def __init__(self, base_stream, limit, interval=1.0):
        self._throttle = Throttle(limit, interval)
        self._buffer = []

class ThrottledStreamWriter(asyncio.StreamWriter):
    def __init__(self, base_stream, limit, interval=1.0):
        self._throttle = Throttle(limit, interval)
        self._buffer = []
