"""OBS connection policy tests; capture backends are replaced for Linux execution."""

import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from src.config import Config
from src.funcs import load_ui_text


class OBSConnectionSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backends = {}
        for module, name in (
            ('direct_window_capture', 'DirectWindowCapture'),
            ('dxcam_window_capture', 'DxcamWindowCapture'),
            ('spout_capture', 'SpoutCapture'),
        ):
            stub = types.ModuleType('src.' + module)
            setattr(stub, name, Mock())
            backends[stub.__name__] = stub
        spec = importlib.util.spec_from_file_location(
            '_obs_connection_settings_test',
            Path(__file__).resolve().parents[1] / 'src' / 'obs_websocket_manager.py',
        )
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict('sys.modules', backends):
            spec.loader.exec_module(cls.module)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = Config(str(Path(directory.name) / 'config.json'))
        self.config.websocket_password = 'saved password'
        self.config.obs_control_settings = [{'action': 'switch_scene', 'scene': 'Game'}]
        self.manager = self.module.OBSWebSocketManager()
        self.manager.spout_capture = Mock()
        self.manager.config = self.config
        self.manager.ui = load_ui_text(self.config)

    def test_disabled_integration_blocks_all_capture_methods(self):
        for method in ('direct_window', 'direct_window_legacy', 'spout', 'obs_websocket'):
            with self.subTest(method=method):
                self.config.capture_method = method
                self.config.obs_websocket_enabled = False
                self.assertFalse(self.manager.uses_obs_websocket())
                self.assertFalse(self.manager.is_obs_control_enabled())
                self.config.obs_websocket_enabled = True
                self.assertTrue(self.manager.uses_obs_websocket())
                self.assertTrue(self.manager.is_obs_control_enabled())

    def test_disabling_disconnects_and_stops_reconnect_without_closing_capture(self):
        self.config.obs_websocket_enabled = False
        self.manager.client = client = Mock()
        self.manager.is_connected = True
        self.manager.direct_capture = capture = Mock()
        with patch.object(self.manager, 'stop_monitor') as stop_monitor, \
                patch.object(self.module, 'ReqClient') as request_client:
            self.assertFalse(self.manager.connect())
        stop_monitor.assert_called_once()
        client.disconnect.assert_called_once()
        request_client.assert_not_called()
        capture.close.assert_not_called()
        self.manager.spout_capture.stop.assert_not_called()
        self.assertFalse(self.manager.is_connected)
        self.assertIsNone(self.manager.client)
        self.assertTrue(self.manager.is_capture_ready())

    def test_obs_capture_reports_disabled(self):
        self.config.capture_method = 'obs_websocket'
        self.config.obs_websocket_enabled = False
        self.assertEqual(self.manager.get_status(), (self.manager.ui.obs.websocket_disabled, False))
        self.assertFalse(self.manager.is_capture_ready())


if __name__ == '__main__':
    unittest.main()
