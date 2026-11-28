"""Main-window label behavior tests."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.main_window import ElidedLabel


class ElidedLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_long_text_is_single_line_and_available_as_tooltip(self):
        full_text = "とても長い曲名 " * 20
        label = ElidedLabel()
        label.resize(120, 24)
        label.setText(full_text)

        self.assertNotEqual(label.text(), full_text)
        self.assertIn("…", label.text())
        self.assertNotIn("\n", label.text())
        self.assertEqual(label.toolTip(), full_text)

    def test_short_text_does_not_need_tooltip(self):
        label = ElidedLabel()
        label.resize(300, 24)
        label.setText("短い曲名")

        self.assertEqual(label.text(), "短い曲名")
        self.assertEqual(label.toolTip(), "")


if __name__ == "__main__":
    unittest.main()
