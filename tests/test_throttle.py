import asyncio
import unittest
import unittest.mock
import aiothrottle


class TestThrottledStreamReader(unittest.TestCase):

    def setUp(self):
        self.stream = unittest.mock.Mock()
        self.transp = self.stream.transport
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    def _make_one(self, *args, **kwargs):
        return aiothrottle.ThrottledStreamReader(
            self.stream, rate_limit=10, limit=10,
            loop=self.loop, *args, **kwargs)

    def test_read(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'da', 2)
        res = self.loop.run_until_complete(r.read(1))
        self.assertEqual(res, b'd')
        self.assertTrue(self.transp.resume_reading.called)

    def test_readline(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'data\n', 5)
        res = self.loop.run_until_complete(r.readline())
        self.assertEqual(res, b'data\n')
        self.assertTrue(self.transp.resume_reading.called)

    def test_readany(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'data', 4)
        res = self.loop.run_until_complete(r.readany())
        self.assertEqual(res, b'data')
        self.assertTrue(self.transp.resume_reading.called)

    def test_readexactly(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'datadata', 8)
        res = self.loop.run_until_complete(r.readexactly(2))
        self.assertEqual(res, b'da')
        self.assertTrue(self.transp.resume_reading.called)

    def test_feed_data(self):
        r = self._make_one()
        r._stream.paused = False
        r.feed_data(b'datadata', 8)
        self.assertTrue(self.transp.pause_reading.called)
