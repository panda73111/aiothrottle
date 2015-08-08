import asyncio
import functools
from unittest import TestCase
from unittest.mock import Mock, patch
import aiohttp
from aiohttp.client_reqrep import ClientResponse
import aiothrottle


class TestThrottledStreamReader(TestCase):

    def setUp(self):
        self.stream = Mock()
        self.stream.paused = True
        self.transp = self.stream.transport
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    def _make_one(self):
        r = aiothrottle.ThrottledStreamReader(
            self.stream, rate_limit=10, buffer_limit=10, loop=self.loop)
        return r

    def _set_time(self, time):
        return patch.object(self.loop, "time", return_value=time)

    def test_parameters(self):
        with patch("asyncio.get_event_loop", return_value=self.loop):
            r = aiothrottle.ThrottledStreamReader(self.stream, 10, 1)
            self.assertIs(r._loop, self.loop)

        r = self._make_one()
        self.assertIs(r._loop, self.loop)
        self.assertIsInstance(r._throttle, aiothrottle.Throttle)
        self.assertEqual(r.rate_limit, 10)
        self.assertEqual(r._throttle.limit, 10)
        self.assertIs(r._stream, self.stream)
        self.assertEqual(r._b_limit, 2 * 10)
        self.assertFalse(r._b_limit_reached)
        self.assertIsNone(r._check_handle)
        self.assertTrue(r.throttling)
        self.assertTrue(self.transp.resume_reading.called)

    def test_attribute_error(self):
        with patch.object(
                self, "stream", Mock(spec=["paused"])):
            # test catching AttributeError on stream.transport
            r = self._make_one()
            self.stream.paused = False
            r._try_pause()
            self.stream.paused = True
            r._try_resume()

    def test_limit_rate(self):
        r = self._make_one()
        r.limit_rate(20)
        self.assertEqual(r._throttle.limit, 20)
        self.assertTrue(r.throttling)

    def test_unlimit_rate(self):
        r = self._make_one()
        r.unlimit_rate()
        self.assertFalse(r.throttling)
        self.assertFalse(self.stream.paused)

    def test_global_limit_rate(self):
        aiothrottle.limit_rate(10)
        klass = ClientResponse.flow_control_class
        self.assertIsInstance(klass, functools.partial)
        r = klass(self.stream, loop=self.loop)
        self.assertIsInstance(r, aiothrottle.ThrottledStreamReader)
        self.assertEqual(r._throttle.limit, 10)

    def test_global_unlimit_rate(self):
        aiothrottle.limit_rate(10)
        aiothrottle.unlimit_rate()
        klass = ClientResponse.flow_control_class
        self.assertIs(klass, aiohttp.streams.FlowControlStreamReader)

    def test_pause(self):
        r = self._make_one()
        self.transp.reset_mock()

        self.stream.paused = True
        r._try_pause()
        self.assertFalse(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

        self.stream.paused = False
        r._try_pause()
        self.assertTrue(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

    def test_resume(self):
        r = self._make_one()
        self.transp.reset_mock()

        self.stream.paused = False
        r._try_resume()
        self.assertFalse(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

        self.stream.paused = True
        r._try_resume()
        self.assertFalse(self.transp.pause_reading.called)
        self.assertTrue(self.transp.resume_reading.called)

    def test_read(self):
        r = self._make_one()
        r.feed_data(b'da')
        res = self.loop.run_until_complete(r.read(1))
        self.assertEqual(res, b'd')

    def test_readline(self):
        r = self._make_one()
        r.feed_data(b'data\n')
        res = self.loop.run_until_complete(r.readline())
        self.assertEqual(res, b'data\n')

    def test_readany(self):
        r = self._make_one()
        r.feed_data(b'data')
        res = self.loop.run_until_complete(r.readany())
        self.assertEqual(res, b'data')

    def test_readexactly(self):
        r = self._make_one()
        r.feed_data(b'datadata')
        res = self.loop.run_until_complete(r.readexactly(2))
        self.assertEqual(res, b'da')

    def _make_one_nonfull_buffer(self):
        with self._set_time(111):
            r = self._make_one()
            self.transp.reset_mock()
            r.feed_data(b"data" * 3)
        return r

    def _make_one_full_buffer(self):
        r = self._make_one_nonfull_buffer()
        with self._set_time(111):
            r.feed_data(b"data" * 3)
        return r

    def test_nonfull_buffer(self):
        r = self._make_one_nonfull_buffer()
        self.assertFalse(r._b_limit_reached)

    def test_full_buffer(self):
        r = self._make_one_full_buffer()
        self.assertTrue(r._b_limit_reached)

    def test_scheduling_resume(self):
        r = self._make_one_nonfull_buffer()
        self.assertIsNotNone(r._check_handle)
        self.assertEqual(r._check_handle._when, 111 + 12 / 10)

    def test_nonscheduling_resume(self):
        r = self._make_one_full_buffer()
        self.assertIsNone(r._check_handle)

    def test_check_callback(self):
        r = self._make_one_nonfull_buffer()
        r._check_callback()
        self.assertIsNone(r._check_handle)
        self.assertFalse(self.stream.paused)

    def test_callback_cancel(self):
        r = self._make_one()
        handle = Mock()
        r._check_handle = handle
        del r
        self.assertTrue(handle.cancel.called)

    def test_throttling_nonfull_buffer_pausing(self):
        r = self._make_one_nonfull_buffer()
        self.assertTrue(self.stream.paused)

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))
            self.assertTrue(self.stream.paused)

    def test_throttling_full_buffer_pausing(self):
        r = self._make_one_full_buffer()
        self.assertTrue(self.stream.paused)

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))
            self.assertTrue(self.stream.paused)

    def test_nonthrottling_nonfull_buffer_nonpausing_read(self):
        r = self._make_one_nonfull_buffer()
        r.unlimit_rate()
        self.assertFalse(self.stream.paused)

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))
            self.assertFalse(self.stream.paused)

    def test_nonthrottling_full_buffer_pausing_read(self):
        r = self._make_one_full_buffer()
        r.unlimit_rate()
        self.assertTrue(self.stream.paused)

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))
            self.assertTrue(self.stream.paused)
            self.loop.run_until_complete(r.read(20))
            self.assertFalse(self.stream.paused)

    def test_nonthrottling_nonfull_buffer_nonpausing_feed(self):
        r = self._make_one_nonfull_buffer()
        r.unlimit_rate()
        r.feed_data(b"data")
        self.assertFalse(self.stream.paused)

    def test_nonthrottling_full_buffer_pausing_feed(self):
        r = self._make_one_full_buffer()
        r.unlimit_rate()
        r.feed_data(b"data")
        self.assertTrue(self.stream.paused)

    def test_nonthrottling_nonfull_buffer_resuming_feed(self):
        r = self._make_one_nonfull_buffer()
        r.unlimit_rate()
        r._try_pause()
        r.feed_data(b"data")
        self.assertFalse(self.stream.paused)

    def test_nonthrottling_full_buffer_nonresuming_feed(self):
        r = self._make_one_full_buffer()
        r.unlimit_rate()
        r._try_pause()
        r.feed_data(b"data")
        self.assertTrue(self.stream.paused)
