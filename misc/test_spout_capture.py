"""Run: .codex-venv/bin/python -B -m unittest misc.test_spout_capture"""

from types import ModuleType
import threading
import unittest
from unittest.mock import Mock, patch

from src.spout_capture import FRAME_TIMEOUT, RETRY_INTERVAL, SpoutCapture


class SpoutRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.capture = SpoutCapture()
        self.capture._sender_name = 'test-sender'
        self.capture._surface = Mock()
        self.now = 0.0
        self.context = Mock()
        self.gl = Mock()
        self.gl.glGenTextures.side_effect = lambda count, pointer: setattr(pointer._obj, 'value', 1)
        self.receiver = Mock()
        self.receiver.__enter__ = Mock(return_value=self.receiver)
        self.receiver.__exit__ = Mock(return_value=False)
        self.receiver.isConnected.return_value = True
        self.receiver.getSenderWidth.return_value = 1
        self.receiver.getSenderHeight.return_value = 1
        self.receiver.isUpdated.return_value = False
        self.receiver.receiveTexture.return_value = True
        self.receiver.isFrameNew.return_value = True
        self.receiver.waitFrameSync.side_effect = lambda *args: self.advance(1.0)
        self.receiver.getSenderList.return_value = []
        self.spout = ModuleType('SpoutGL')
        self.spout.SpoutReceiver = Mock(return_value=self.receiver)
        qtgui = ModuleType('PySide6.QtGui')
        qtgui.QOpenGLContext = Mock(return_value=self.context)
        for patcher in (
            patch.dict('sys.modules', {'SpoutGL': self.spout, 'PySide6.QtGui': qtgui}),
            patch('src.spout_capture.ctypes.WinDLL', return_value=self.gl, create=True),
            patch('src.spout_capture.TARGET_SIZE', (1, 1)),
            patch('src.spout_capture.time.monotonic', side_effect=lambda: self.now),
            patch('src.spout_capture.logger'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def advance(self, seconds):
        self.now += seconds

    def test_receive_error_recreates_resources_and_resumes_frames(self):
        self.receiver.receiveTexture.side_effect = [RuntimeError('temporary GPU error'), True, True]
        frames = []

        def received(frame):
            frames.append(frame)
            self.capture._stop_event.set()

        def create_receiver():
            if self.spout.SpoutReceiver.call_count == 2:
                # Resources from the failed session must be released first.
                self.assertEqual(self.gl.glDeleteTextures.call_count, 1)
                self.assertEqual(self.context.doneCurrent.call_count, 1)
                self.assertIsNone(self.capture.get_latest_frame())
                self.assertFalse(self.capture.is_connected)
            return self.receiver

        self.spout.SpoutReceiver.side_effect = create_receiver
        self.capture.set_frame_callback(received)
        with patch.object(self.capture._stop_event, 'wait', side_effect=lambda _: self.capture._stop_event.is_set()) as wait:
            self.capture._run()
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].shape, (1, 1, 3))
        self.assertEqual(self.spout.SpoutReceiver.call_count, 2)
        self.assertEqual(self.context.create.call_count, 2)
        self.assertEqual(self.gl.glDeleteTextures.call_count, 2)
        self.assertEqual(self.context.doneCurrent.call_count, 2)
        self.assertIn(unittest.mock.call(RETRY_INTERVAL), wait.call_args_list)
        self.assertEqual(self.capture.current_status()[0], 'connected')

    def test_repeated_errors_retry_until_stopped(self):
        self.capture._connected = True
        self.capture._latest_frame = object()

        def retry_wait(seconds):
            self.assertEqual(seconds, RETRY_INTERVAL)
            self.assertFalse(self.capture.is_connected)
            self.assertIsNone(self.capture.get_latest_frame())
            return receive.call_count >= 3

        with patch.object(self.capture, '_receive', side_effect=RuntimeError('failed')) as receive, \
                patch.object(self.capture._stop_event, 'wait', side_effect=retry_wait):
            self.capture._run()
        self.assertEqual(receive.call_count, 3)
        self.assertIn('再試行', self.capture.current_status()[1])

    def test_stop_interrupts_retry_wait(self):
        waiting = threading.Event()
        real_wait = self.capture._stop_event.wait

        def retry_wait(seconds):
            waiting.set()
            return real_wait(seconds)

        with patch.object(self.capture, '_receive', side_effect=RuntimeError('failed')) as receive, \
                patch.object(self.capture._stop_event, 'wait', side_effect=retry_wait):
            worker = threading.Thread(target=self.capture._run, daemon=True)
            self.capture._thread = worker
            try:
                worker.start()
                self.assertTrue(waiting.wait(timeout=1.0))
                self.assertTrue(self.capture.stop())
                self.assertFalse(worker.is_alive())
            finally:
                self.capture._stop_event.set()
                worker.join(timeout=1.0)
        receive.assert_called_once()

    def test_exception_during_stop_does_not_report_error_or_restart(self):
        def fail_and_stop():
            self.capture._stop_event.set()
            raise RuntimeError('stopping')

        with patch.object(self.capture, '_receive', side_effect=fail_and_stop) as receive:
            self.capture._run()
        receive.assert_called_once()
        self.assertIsNone(self.capture.current_status())

    def test_already_stopped_worker_does_not_create_receiver(self):
        self.capture._stop_event.set()
        self.capture._run()
        self.spout.SpoutReceiver.assert_not_called()

    def test_context_creation_failure_can_recover(self):
        self.context.create.side_effect = [False, True]
        self.capture.set_frame_callback(lambda _: self.capture._stop_event.set())
        with patch.object(self.capture._stop_event, 'wait', side_effect=lambda _: self.capture._stop_event.is_set()):
            self.capture._run()
        self.assertEqual(self.context.create.call_count, 2)
        self.assertEqual(self.capture.current_status()[0], 'connected')

    def test_connected_without_new_frames_times_out_and_releases_resources(self):
        self.receiver.isFrameNew.return_value = False
        with self.assertRaises(TimeoutError):
            self.capture._receive()
        self.assertGreaterEqual(self.now, FRAME_TIMEOUT)
        self.receiver.__exit__.assert_called_once()
        self.gl.glDeleteTextures.assert_called_once()
        self.context.doneCurrent.assert_called_once()

    def test_invalid_frame_dimensions_also_time_out(self):
        self.receiver.getSenderWidth.return_value = 0
        with patch.object(self.capture._stop_event, 'wait', side_effect=self.advance), \
                self.assertRaises(TimeoutError):
            self.capture._receive()
        self.gl.glDeleteTextures.assert_called_once()

    def test_stalled_session_restarts_and_delivers_frames(self):
        self.receiver.isFrameNew.side_effect = lambda: self.spout.SpoutReceiver.call_count > 1
        self.capture.set_frame_callback(lambda _: self.capture._stop_event.set())
        with patch.object(self.capture._stop_event, 'wait', side_effect=lambda _: self.capture._stop_event.is_set()):
            self.capture._run()
        self.assertGreaterEqual(self.now, FRAME_TIMEOUT)
        self.assertEqual(self.spout.SpoutReceiver.call_count, 2)
        self.assertEqual(self.gl.glDeleteTextures.call_count, 2)
        self.assertEqual(self.capture.current_status()[0], 'connected')

    def test_normal_frames_keep_session_alive_beyond_timeout(self):
        frames = []

        def received(frame):
            frames.append(frame)
            if self.now > FRAME_TIMEOUT * 2:
                self.capture._stop_event.set()

        self.capture.set_frame_callback(received)
        self.capture._run()
        self.assertGreater(len(frames), FRAME_TIMEOUT)
        self.spout.SpoutReceiver.assert_called_once()
        self.assertFalse(self.capture.is_connected)
        self.assertIsNone(self.capture.get_latest_frame())

    def test_missing_sender_waits_without_timeout_then_connects(self):
        self.receiver.isConnected.side_effect = lambda: self.now > FRAME_TIMEOUT * 2
        self.capture.set_frame_callback(lambda _: self.capture._stop_event.set())
        with patch.object(self.capture._stop_event, 'wait', side_effect=self.advance):
            self.capture._run()
        self.assertGreater(self.now, FRAME_TIMEOUT * 2)
        self.spout.SpoutReceiver.assert_called_once()
        self.assertEqual(self.capture.current_status()[0], 'connected')


if __name__ == '__main__':
    unittest.main()
