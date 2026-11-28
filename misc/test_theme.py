"""Run: QT_QPA_PLATFORM=offscreen .codex-venv/bin/python -B -m unittest misc.test_theme"""

import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from src.config import Config
from src.theme import apply_application_theme, contrasting_text_color, set_item_background


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle('Fusion')

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config_path = Path(directory.name) / 'config.json'

    def test_config_defaults_validates_and_persists_theme(self):
        config = Config(str(self.config_path))
        self.assertEqual(config.theme, 'system')
        config.theme = 'dark'
        config.save_config()
        self.assertEqual(Config(str(self.config_path)).theme, 'dark')

        self.config_path.write_text(json.dumps({'theme': 'invalid'}), encoding='utf-8')
        self.assertEqual(Config(str(self.config_path)).theme, 'system')

    def test_light_and_dark_palettes_have_readable_text(self):
        apply_application_theme(self.app, 'dark')
        dark = self.app.palette()
        self.assertLess(
            dark.color(QPalette.ColorRole.Window).lightness(),
            dark.color(QPalette.ColorRole.WindowText).lightness(),
        )

        apply_application_theme(self.app, 'light')
        light = self.app.palette()
        self.assertGreater(
            light.color(QPalette.ColorRole.Window).lightness(),
            light.color(QPalette.ColorRole.WindowText).lightness(),
        )

    def test_contrasting_text_for_scene_row_colors(self):
        self.assertEqual(contrasting_text_color(QColor('#e8f5e9')), QColor('#000000'))
        self.assertEqual(contrasting_text_color(QColor('#17304f')), QColor('#ffffff'))

        item = QTableWidgetItem('Game')
        set_item_background(item, QColor('#e3f2fd'))
        self.assertEqual(item.foreground().color(), QColor('#000000'))


if __name__ == '__main__':
    unittest.main()
