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
        self.assertTrue(r._throttling)
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
        self.assertTrue(r._throttling)

    def test_unlimit_rate(self):
        r = self._make_one()
        r.unlimit_rate()
        self.assertFalse(r._throttling)
        self.assertFalse(self.transp.pause_reading.called)
        self.assertTrue(self.transp.resume_reading.called)

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

    def test_feed_data(self):
        r = self._make_one()
        self.transp.reset_mock()
        self.stream.paused = False
        r.feed_data(b'datadata')
        self.assertTrue(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

    def test_nonfull_buffer_pausing(self):
        with self._set_time(111):
            r = self._make_one()
            r._try_resume()
            self.transp.reset_mock()
            r.feed_data(b"data" * 3)

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))

        self.assertTrue(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

    def test_nonfull_buffer_resuming(self):
        with self._set_time(111):
            r = self._make_one()
            r._try_pause()
            self.transp.reset_mock()
            r.feed_data(b"data")

        with self._set_time(112):
            self.loop.run_until_complete(r.read(4))

        self.assertFalse(self.transp.pause_reading.called)
        self.assertTrue(self.transp.resume_reading.called)

    def test_full_buffer_pausing(self):
        with self._set_time(111):
            r = self._make_one()
            r._try_resume()
            self.transp.reset_mock()
            r.feed_data(b"data" * 6)

        with self._set_time(113):
            self.loop.run_until_complete(r.read(4))

        self.assertTrue(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)

    def test_full_buffer_nonresuming(self):
        with self._set_time(111):
            r = self._make_one()
            r._try_pause()
            self.transp.reset_mock()
            r.feed_data(b"data" * 6)

        with self._set_time(114):
            self.loop.run_until_complete(r.read(4))

        self.assertFalse(self.transp.pause_reading.called)
        self.assertFalse(self.transp.resume_reading.called)
