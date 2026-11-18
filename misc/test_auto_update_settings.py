"""Run: .codex-venv/bin/python -B -m unittest misc.test_auto_update_settings"""

import json
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from src.config import Config
from src.main_window import MainWindowUI


class AutoUpdateSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_auto_update_defaults_to_enabled_for_existing_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.json'
            config_path.write_text('{}', encoding='utf-8')

            config = Config(str(config_path))

            self.assertTrue(config.enable_auto_update)
            saved = json.loads(config_path.read_text(encoding='utf-8'))
            self.assertTrue(saved['enable_auto_update'])

    def test_disabled_auto_update_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / 'config.json'
            config = Config(str(config_path))
            config.enable_auto_update = False
            config.save_config()

            self.assertFalse(Config(str(config_path)).enable_auto_update)

    def test_basic_settings_dialog_wires_auto_update_checkbox(self):
        source = (
            Path(__file__).resolve().parents[1] / 'src/config_dialog.py'
        ).read_text(encoding='utf-8')

        self.assertIn('self.enable_auto_update_check = QCheckBox', source)
        self.assertIn(
            'self.enable_auto_update_check.setChecked(self.config.enable_auto_update)',
            source,
        )
        self.assertIn(
            'self.config.enable_auto_update = self.enable_auto_update_check.isChecked()',
            source,
        )

    def test_help_menu_has_manual_update_action(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(str(Path(directory) / 'config.json'))
            window = MainWindowUI(config)
            self.addCleanup(window.deleteLater)

            window.create_menu_bar()

            labels = [action.text() for action in window.findChildren(QAction)]
            self.assertIn(window.ui.menu.manual_update, labels)


if __name__ == '__main__':
    unittest.main()
