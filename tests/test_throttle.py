import asyncio
from unittest import TestCase
from unittest.mock import Mock, patch
import sys
import aiothrottle

PY34 = sys.version_info >= (3, 4)


@asyncio.coroutine
def sleep_mock(*_):
    pass


class TestThrottle(TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def _make_one(self):
        return aiothrottle.Throttle(limit=10, loop=self.loop)

    def _set_time(self, time):
        return patch.object(self.loop, "time", return_value=time)

    def test_parameters(self):
        with self._set_time(111):
            with patch("asyncio.get_event_loop", return_value=self.loop):
                t = aiothrottle.Throttle(10)
                self.assertIs(t._loop, self.loop)
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

    @patch("asyncio.sleep", Mock(wraps=sleep_mock))
    def test_wait_remaining(self):
        t = self._make_one()
        t.add_io(2)
        self.loop.run_until_complete(t.wait_remaining())
        asyncio.sleep.assert_called_with(2/10)

    def test_current_rate(self):
        with self._set_time(111):
            t = self._make_one()
            t.add_io(2)
            self.assertRaises(RuntimeError, t.current_rate)

        with self._set_time(116):
            self.assertEqual(t.current_rate(), 2/5)
            t.reset_io()
            self.assertEqual(t.current_rate(), 0)

    def test_within_limit(self):
        with self._set_time(111):
            t = self._make_one()
        t.add_io(2)
        with self._set_time(116):
            self.assertTrue(t.within_limit())
            t.add_io(60)
            self.assertFalse(t.within_limit())
