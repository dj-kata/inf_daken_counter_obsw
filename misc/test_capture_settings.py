"""Run: QT_QPA_PLATFORM=offscreen .codex-venv/bin/python -B -m unittest misc.test_capture_settings"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from src.config import Config
from src.obs_dialog import OBSControlDialog


class CaptureSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = Config(str(Path(directory.name) / 'config.json'))

    def dialog(self, method, language='ja'):
        self.config.capture_method = method
        self.config.language = language
        self.config.monitor_source_name = 'saved game source'
        self.config.spout_sender_name = 'game sender'
        with patch.object(OBSControlDialog, 'update_scene_list'):
            dialog = OBSControlDialog(self.config, Mock())
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_new_config_defaults_to_gdi(self):
        self.assertEqual(self.config.capture_method, 'direct_window_legacy')
        self.assertEqual(self.config._load_capture_method({}), 'direct_window_legacy')

    def test_obs_integration_toggle_is_saved_without_clearing_credentials(self):
        self.config.websocket_password = 'saved password'
        self.config.obs_control_settings = [{'timing': 'app_start', 'action': 'switch_scene', 'scene': 'Game'}]
        dialog = self.dialog('direct_window_legacy')
        self.assertTrue(dialog.obs_websocket_enabled_check.isChecked())
        self.assertIs(dialog.layout().itemAt(0).widget(), dialog.obs_websocket_enabled_check)
        dialog.obs_websocket_enabled_check.setChecked(False)
        dialog.accept()
        saved = Config(self.config.config_file)
        self.assertFalse(saved.obs_websocket_enabled)
        self.assertEqual(saved.websocket_password, 'saved password')
        self.assertEqual(saved.obs_control_settings, self.config.obs_control_settings)
        dialog = self.dialog('direct_window_legacy')
        self.assertFalse(dialog.obs_websocket_enabled_check.isChecked())
        dialog.obs_websocket_enabled_check.setChecked(True)
        dialog.accept()
        self.assertTrue(Config(self.config.config_file).obs_websocket_enabled)

    def test_old_config_keeps_obs_integration_enabled(self):
        import json
        Path(self.config.config_file).write_text(
            json.dumps({'capture_method': 'obs_websocket', 'websocket_password': 'saved password'}),
            encoding='utf-8',
        )
        self.assertTrue(Config(self.config.config_file).obs_websocket_enabled)

    def test_existing_capture_methods_and_old_settings_are_preserved(self):
        for method in ('direct_window', 'direct_window_legacy', 'obs_websocket', 'spout'):
            with self.subTest(method=method):
                self.config.capture_method = method
                self.config.save_config()
                self.assertEqual(Config(self.config.config_file).capture_method, method)
        self.assertEqual(self.config._load_capture_method({'websocket_host': 'localhost'}), 'obs_websocket')
        self.assertEqual(self.config._load_capture_method({'random_lane_capture_backend': 'spout'}), 'spout')

    def test_capture_display_and_source_controls_in_both_languages(self):
        for language in ('ja', 'en'):
            for method, expected in (
                ('direct_window', 'DXCAM'), ('direct_window_legacy', 'GDI'),
                ('spout', 'game sender'), ('obs_websocket', 'saved game source'),
            ):
                with self.subTest(language=language, method=method):
                    dialog = self.dialog(method, language)
                    self.assertIn(expected, dialog.monitor_label.text())
                    obs_capture = method == 'obs_websocket'
                    self.assertEqual(dialog.clear_monitor_button.isEnabled(), obs_capture)
                    self.assertEqual(dialog.monitor_hint.isHidden(), obs_capture)
                    index = dialog.action_combo.findData('set_monitor_source')
                    self.assertEqual(dialog.action_combo.model().item(index).isEnabled(), obs_capture)
                    for action in ('show_source', 'hide_source', 'autosave_source'):
                        dialog.action_combo.setCurrentIndex(dialog.action_combo.findData(action))
                        self.assertTrue(dialog.target_source_combo.isEnabled())
                    if not obs_capture:
                        dialog.clear_monitor_source()
                        dialog.action_combo.setCurrentIndex(index)
                        dialog.add_setting()
                        self.assertEqual(self.config.monitor_source_name, 'saved game source')
                        self.assertEqual(self.config.obs_control_settings, [])

    def test_obs_monitor_clear_updates_display(self):
        dialog = self.dialog('obs_websocket')
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
                patch.object(QMessageBox, 'information'):
            dialog.clear_monitor_source()
        self.assertEqual(self.config.monitor_source_name, '')
        self.assertEqual(dialog.monitor_label.text(), dialog.ui.obs.target_source_not_set)


if __name__ == '__main__':
    unittest.main()
