"""Run: .codex-venv/bin/python -B -m unittest misc.test_image_save_settings"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from src.classes import config_autosave_image, config_modify_rivalarea
from src.config import Config
from src.image_save_settings import ImageSaveSettings
from src.ui_jp import UIText

ROOT = Path(__file__).resolve().parents[1]


class ImageSaveSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config_path = Path(self.temp.name) / "isolated.json"
        self.config = Config(str(self.config_path))
        self.widget = ImageSaveSettings(UIText)
        self.addCleanup(self.widget.close)
        self.widget.load_config_values(self.config)

    def test_defaults_and_cancel_do_not_change_config(self):
        self.assertTrue(self.widget.autosave_updates_radio.isChecked())
        self.assertTrue(self.widget.rivalarea_invalid_radio.isChecked())
        self.assertFalse(self.widget.write_statistics_check.isChecked())
        self.assertEqual(self.widget.result_image_cache_limit_spin.value(), 0)
        original = self.config_path.read_bytes()
        self.widget.autosave_all_radio.setChecked(True)
        self.widget.close()
        self.assertEqual(self.config.autosave_image_mode, config_autosave_image.only_updates)
        self.assertEqual(self.config_path.read_bytes(), original)

    def test_settings_survive_apply_save_and_reload(self):
        for autosave in config_autosave_image:
            for rivalarea in config_modify_rivalarea:
                for limit in (0, 100, 10000):
                    with self.subTest(autosave=autosave, rivalarea=rivalarea, limit=limit):
                        self.widget.autosave_button_group.button(autosave.value).setChecked(True)
                        self.widget.rivalarea_button_group.button(rivalarea.value).setChecked(True)
                        self.widget.write_statistics_check.setChecked(True)
                        self.widget.result_image_cache_limit_spin.setValue(limit)
                        self.widget.apply_to_config(self.config)
                        self.config.save_config()
                        loaded = Config(str(self.config_path))
                        self.assertEqual(loaded.autosave_image_mode, autosave)
                        self.assertEqual(loaded.modify_rivalarea_mode, rivalarea)
                        self.assertTrue(loaded.write_statistics)
                        self.assertEqual(loaded.result_image_cache_limit, limit)
                        self.widget.load_config_values(loaded)
                        self.assertEqual(self.widget.autosave_button_group.checkedId(), autosave.value)
                        self.assertEqual(self.widget.rivalarea_button_group.checkedId(), rivalarea.value)

    def test_capture_cli_ignores_user_config_and_produces_both_languages(self):
        root = Path(self.temp.name)
        sentinel = root / "config.json"
        original = b'{"websocket_password": "private-test-value", "result_image_cache_limit": 42}'
        sentinel.write_bytes(original)
        for language in ("ja", "en"):
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "misc" / "capture_manual.py"),
                 "--offscreen", "--language", language, "--output-dir", str(root / "images")],
                cwd=root, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            image = QImage(str(root / "images" / f"image-save-{language}.png"))
            self.assertFalse(image.isNull())
            self.assertGreaterEqual(image.width(), 640)
            self.assertGreaterEqual(image.height(), 480)
        self.assertEqual(sentinel.read_bytes(), original)
        self.assertFalse((root / "results").exists())


if __name__ == "__main__":
    unittest.main()
