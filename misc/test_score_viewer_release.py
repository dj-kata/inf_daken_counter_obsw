"""Run: .codex-venv/bin/python -B -m unittest misc.test_score_viewer_release"""

import unittest

from src.classes import average_release
from src.score_viewer import format_average_release


class ScoreViewerReleaseTests(unittest.TestCase):
    def test_formats_summary_and_ten_second_timeline(self):
        summary, detail = format_average_release(
            average_release([25.0, 40.0, None], interval_seconds=10.0)
        )

        self.assertEqual(summary, "32.5 / 3区間")
        self.assertIn("0–10秒: 25.0 ms", detail)
        self.assertIn("10–20秒: 40.0 ms", detail)
        self.assertIn("20–30秒: ---", detail)

    def test_uses_saved_interval_for_timeline(self):
        summary, detail = format_average_release(
            average_release([25.0, 30.0], interval_seconds=5.0)
        )

        self.assertEqual(summary, "27.5 / 2区間")
        self.assertIn("記録区間: 2（1区間5秒）", detail)
        self.assertIn("0–5秒: 25.0 ms", detail)
        self.assertIn("5–10秒: 30.0 ms", detail)

    def test_returns_empty_text_without_release_data(self):
        self.assertEqual(format_average_release(None), ("", ""))
        self.assertEqual(
            format_average_release(average_release([], interval_seconds=10.0)),
            ("", ""),
        )


if __name__ == "__main__":
    unittest.main()
