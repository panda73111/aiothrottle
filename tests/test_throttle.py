import asyncio
import logging
import unittest
from unittest import mock
import sys
import aiothrottle


PY34 = sys.version_info >= (3, 4)

class TestThrottle(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def _make_one(self):
        return aiothrottle.Throttle(limit=10, loop=self.loop)

    def test_parameters(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            t = self._make_one()
        self.assertEqual(t._limit, 10)
        self.assertEqual(t.limit, 10)
        self.assertEqual(t._io, 0)
        self.assertIs(t._loop, self.loop)
        self.assertEqual(t._reset_time, 111)

    def test_invalid_limit(self):
        self.assertRaises(
            ValueError, aiothrottle.Throttle, limit=0)
        self.assertRaises(
            ValueError, aiothrottle.Throttle, limit=-10)
        t = self._make_one()
        self.assertRaises(
            ValueError, setattr, t, "limit", 0)
        self.assertRaises(
            ValueError, setattr, t, "limit", -10)

    def test_time_left(self):
        t = self._make_one()
        t.add_io(2)
        self.assertEqual(t.time_left(), 2/10)

    def test_add_io(self):
        t = self._make_one()
        t.add_io(2)
        self.assertEqual(t._io, 2)

    def test_reset_io(self):
        t = self._make_one()
        t.add_io(2)
        t.reset_io()
        self.assertEqual(t._io, 0)

    def test_wait_remaining(self):
        @asyncio.coroutine
        def sleep_mock(*_):
            pass

        t = self._make_one()
        asyncio.sleep = mock.Mock(wraps=sleep_mock)
        t.add_io(2)
        self.loop.run_until_complete(t.wait_remaining())
        asyncio.sleep.assert_called_with(2/10)

    def test_current_rate(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            t = self._make_one()
            t.add_io(2)
            if PY34:
                with self.assertLogs(level=logging.WARNING):
                    self.assertEqual(t.current_rate(), -1)
            else:
                self.assertEqual(t.current_rate(), -1)
        with mock.patch.object(self.loop, "time", return_value=116):
            self.assertEqual(t.current_rate(), 2/5)
            t.reset_io()
            self.assertEqual(t.current_rate(), 0)

    def test_within_limit(self):
        with mock.patch.object(self.loop, "time", return_value=111):
            t = self._make_one()
        t.add_io(2)
        with mock.patch.object(self.loop, "time", return_value=116):
            self.assertTrue(t.within_limit())
            t.add_io(60)
            self.assertFalse(t.within_limit())


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
            self.stream, rate_limit=10, buffer_limit=1,
            loop=self.loop, *args, **kwargs)

    def test_read(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'da', 2)
        res = self.loop.run_until_complete(r.read(1))
        self.assertEqual(res, b'd')
        # self.assertTrue(self.transp.resume_reading.called)

    def test_readline(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'data\n', 5)
        res = self.loop.run_until_complete(r.readline())
        self.assertEqual(res, b'data\n')
        # self.assertTrue(self.transp.resume_reading.called)

    def test_readany(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'data', 4)
        res = self.loop.run_until_complete(r.readany())
        self.assertEqual(res, b'data')
        # self.assertTrue(self.transp.resume_reading.called)

    def test_readexactly(self):
        r = self._make_one()
        r.paused = True
        r.feed_data(b'datadata', 8)
        res = self.loop.run_until_complete(r.readexactly(2))
        self.assertEqual(res, b'da')
        # self.assertTrue(self.transp.resume_reading.called)

    def test_feed_data(self):
        r = self._make_one()
        r._stream.paused = False
        r.feed_data(b'datadata', 8)
        # self.assertTrue(self.transp.pause_reading.called)
