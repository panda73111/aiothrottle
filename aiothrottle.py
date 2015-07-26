
import io
import asyncio
import time
from asyncio import Event

class Throttle:
    def __init__(self, base_stream, limit, interval):
        if base_stream is None:
            raise ValueError("base_stream must not be None")
        if limit < 1:
            raise ValueError("limit must be a positive integer")
        if interval <= 0.0:
            raise ValueError("interval must be positive")

        self.limit = limit
        self.interval = interval
        self._base_stream = base_stream
        self._last_check_time = 0

class ThrottledStreamReader(asyncio.StreamReader):
    def __init__(self, base_stream, limit, interval=1.0):
        self._throttle = Throttle(base_stream, limit, interval)

class ThrottledStreamWriter(asyncio.StreamWriter):
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
        yield from asyncio.
    print("feed task ended")

class TestReadTransport(asyncio.ReadTransport):
    # default limit: 1 GB
    def __init__(self, limit=2**30, chunk_size=1024, interval=1.0):
        self.limit = limit
        self.chunk_size = chunk_size
        self.interval = interval
        self._paused = False

class TestProtocol(asyncio.Protocol):
    

@asyncio.coroutine
def run_reader_test(base_stream_reader):
    reader = ThrottledStreamReader(base_stream_reader, 512)
    yield from asyncio.sleep(100)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    print("starting")
    try:
        protocol = TestProcol()
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
