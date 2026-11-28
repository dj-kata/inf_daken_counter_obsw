"""Run: .codex-venv/bin/python -B -m unittest misc.test_otoge_input_viewer_client"""

import json
import unittest

from src.otoge_input_viewer_client import OtogeInputViewerClient


class OtogeInputViewerClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OtogeInputViewerClient(autostart=False)

    def test_collects_release_averages_in_ten_second_buckets(self):
        self.client.handle_message(self._notes_message(100, 20), now=99.0)
        self.client.start_play(now=100.0)
        self.client.handle_message(self._notes_message(103, 21), now=101.0)
        self.client.handle_message(self._release_message(20.0), now=101.0)
        self.client.handle_message(self._notes_message(110, 22), now=109.9)
        self.client.handle_message(self._release_message(30.0), now=109.9)
        self.client.handle_message(self._notes_message(111, 22), now=110.0)
        self.client.handle_message(self._release_message(40.0), now=110.0)

        release = self.client.finish_play(now=121.0)

        self.assertEqual(release.histogram, [25.0, 40.0, None])
        self.assertEqual(release.interval_seconds, 10.0)
        self.assertEqual(release.key_counts_cumulative, [0, 10, 11, 11])
        self.assertEqual(release.other_counts_cumulative, [0, 2, 2, 2])
        self.assertEqual(release.release_sample_counts, [2, 1, 0])
        self.assertEqual(release.total, 32.5)

    def test_ignores_messages_outside_play_and_invalid_events(self):
        self.client.handle_message(self._release_message(20.0), now=99.0)
        self.client.start_play(now=100.0)
        self.client.handle_message("not-json", now=101.0)
        self.client.handle_message(json.dumps([{"type": "density", "value": "10"}]), now=102.0)

        self.assertIsNone(self.client.finish_play(now=111.0))

    def test_new_play_does_not_reuse_previous_release_values(self):
        self.client.start_play(now=100.0)
        self.client.handle_message(self._release_message(20.0), now=101.0)
        self.client.start_play(now=200.0)
        self.client.handle_message(self._release_message(50.0), now=201.0)

        release = self.client.finish_play(now=205.0)

        self.assertEqual(release.histogram, [50.0])

    def test_counter_reset_during_play_invalidates_only_cumulative_counts(self):
        self.client.handle_message(self._notes_message(100, 20), now=99.0)
        self.client.start_play(now=100.0)
        self.client.handle_message(self._notes_message(1, 0), now=101.0)
        self.client.handle_message(self._release_message(50.0), now=101.0)

        release = self.client.finish_play(now=105.0)

        self.assertEqual(release.histogram, [50.0])
        self.assertIsNone(release.key_counts_cumulative)
        self.assertIsNone(release.other_counts_cumulative)
        self.assertEqual(release.release_sample_counts, [1])

    @staticmethod
    def _release_message(value):
        return json.dumps([{"type": "release", "value": str(value)}])

    @staticmethod
    def _notes_message(key, other):
        return json.dumps([
            {
                "type": "notes",
                "value": key + other,
                "key": key,
                "other": other,
                "other_label": "scr",
            }
        ])


if __name__ == "__main__":
    unittest.main()
