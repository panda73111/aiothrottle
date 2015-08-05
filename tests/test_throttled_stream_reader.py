import asyncio
import unittest
from unittest import mock
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
        r = aiothrottle.ThrottledStreamReader(
            self.stream, rate_limit=10, buffer_limit=1,
            loop=self.loop, *args, **kwargs)
        return r

    def test_parameters(self):
        with mock.patch("asyncio.get_event_loop", return_value=self.loop):
            r = aiothrottle.ThrottledStreamReader(self.stream, 10, 1)
            self.assertIs(r._loop, self.loop)

        r = self._make_one()
        self.assertIs(r._loop, self.loop)
        self.assertIsInstance(r._throttle, aiothrottle.Throttle)
        self.assertEqual(r._throttle.limit, 10)
        self.assertIs(r._stream, self.stream)
        self.assertEqual(r._b_limit, 2 * 1)
        self.assertFalse(r._b_limit_reached)
        self.assertIsNone(r._check_handle)
        self.assertTrue(r._throttling)
        self.assertTrue(self.transp.resume_reading.called)

    def test_attribute_error(self):
        with mock.patch.object(
                self.stream, "transport", mock.Mock(spec=[])):
            # test catching AttributeError on stream.transport
            r = self._make_one()
            r.feed_data(b'data', 4)
            self.loop.run_until_complete(r.read(4))
            r.feed_data(b'data', 4)
            self.loop.run_until_complete(r.readany())
            r.feed_data(b'data', 4)
            self.loop.run_until_complete(r.readexactly(4))
            r.feed_data(b'data\n', 5)
            self.loop.run_until_complete(r.readline())

    def test_read(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            r = self._make_one()
            r.feed_data(b'da', 2)
        with mock.patch.object(self.loop, "time", return_value=112):
            res = self.loop.run_until_complete(r.read(1))
        self.assertEqual(res, b'd')

    def test_readline(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            r = self._make_one()
            r.feed_data(b'data\n', 5)
        with mock.patch.object(self.loop, "time", return_value=112):
            res = self.loop.run_until_complete(r.readline())
        self.assertEqual(res, b'data\n')

    def test_readany(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            r = self._make_one()
            r.feed_data(b'data', 4)
        with mock.patch.object(self.loop, "time", return_value=112):
            res = self.loop.run_until_complete(r.readany())
        self.assertEqual(res, b'data')

    def test_readexactly(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            r = self._make_one()
            r.feed_data(b'datadata', 8)
        with mock.patch.object(self.loop, "time", return_value=112):
            res = self.loop.run_until_complete(r.readexactly(2))
        self.assertEqual(res, b'da')

    def test_feed_data(self):
        r = self._make_one()
        self.stream.paused = False
        r.feed_data(b'datadata', 8)
        self.assertTrue(self.transp.pause_reading.called)
