"""OBS connection policy tests; capture backends are replaced for Linux execution."""

import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from src.config import Config
from src.funcs import load_ui_text
from src.obs_dialog import OBSControlDialog


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

    def test_spout_control_allows_obs_without_authentication(self):
        self.config.capture_method = 'spout'
        self.config.websocket_password = ''
        self.assertTrue(self.manager.is_obs_control_enabled())
        self.assertTrue(self.manager.uses_obs_websocket())

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

    def test_direct_capture_without_rules_does_not_connect_automatically(self):
        self.config.capture_method = 'direct_window'
        self.config.obs_control_settings = []
        with patch.object(self.manager, 'stop_monitor') as stop_monitor, \
                patch.object(self.module, 'ReqClient') as request_client:
            self.assertFalse(self.manager.connect())
        stop_monitor.assert_called_once()
        request_client.assert_not_called()

    def test_forced_setup_connection_works_without_control_rules(self):
        self.config.capture_method = 'direct_window'
        self.config.obs_control_settings = []
        client = Mock()
        with patch.object(self.module, 'OBSWS_AVAILABLE', True), \
                patch.object(self.module, 'ReqClient', return_value=client) as request_client, \
                patch.object(self.manager, 'start_monitor') as start_monitor, \
                patch.object(self.manager, '_apply_scene_collection') as apply_collection:
            self.assertTrue(self.manager.connect(force=True))
        request_client.assert_called_once_with(
            host=self.config.websocket_host,
            port=self.config.websocket_port,
            password=self.config.websocket_password,
            timeout=5,
        )
        client.get_version.assert_called_once_with()
        apply_collection.assert_called_once_with()
        start_monitor.assert_called_once_with()
        self.assertTrue(self.manager.is_connected)

    def test_forced_setup_connection_respects_disabled_integration(self):
        self.config.capture_method = 'direct_window'
        self.config.obs_control_settings = []
        self.config.obs_websocket_enabled = False
        with patch.object(self.module, 'ReqClient') as request_client:
            self.assertFalse(self.manager.connect(force=True))
        request_client.assert_not_called()

    def test_dialog_applies_connection_fields_before_reconnect(self):
        dialog = types.SimpleNamespace(
            config=self.config,
            obs_websocket_enabled_check=Mock(isChecked=Mock(return_value=True)),
            websocket_host_edit=Mock(text=Mock(return_value='127.0.0.1')),
            websocket_port_spin=Mock(value=Mock(return_value=4455)),
            websocket_password_edit=Mock(text=Mock(return_value='new password')),
        )
        OBSControlDialog._apply_websocket_settings(dialog)
        self.assertTrue(self.config.obs_websocket_enabled)
        self.assertEqual(self.config.websocket_host, '127.0.0.1')
        self.assertEqual(self.config.websocket_port, 4455)
        self.assertEqual(self.config.websocket_password, 'new password')

    def test_dialog_reconnect_forces_initial_setup_connection(self):
        dialog = types.SimpleNamespace(
            _apply_websocket_settings=Mock(),
            obs_manager=Mock(),
            update_scene_list=Mock(),
            ui=types.SimpleNamespace(
                message=types.SimpleNamespace(
                    success='success',
                    reconnected_to_obs='connected',
                    error_title='error',
                    failed_reconnection_to_obs='failed',
                ),
            ),
        )
        dialog.obs_manager.connect.return_value = True
        with patch('src.obs_dialog.QMessageBox.information') as information:
            OBSControlDialog.reconnect_obs(dialog)
        dialog._apply_websocket_settings.assert_called_once_with()
        dialog.obs_manager.disconnect.assert_called_once_with()
        dialog.obs_manager.connect.assert_called_once_with(force=True)
        dialog.update_scene_list.assert_called_once_with()
        information.assert_called_once_with(dialog, 'success', 'connected')

    def test_obs_capture_reports_disabled(self):
        self.config.capture_method = 'obs_websocket'
        self.config.obs_websocket_enabled = False
        self.assertEqual(self.manager.get_status(), (self.manager.ui.obs.websocket_disabled, False))
        self.assertFalse(self.manager.is_capture_ready())


if __name__ == '__main__':
    unittest.main()
