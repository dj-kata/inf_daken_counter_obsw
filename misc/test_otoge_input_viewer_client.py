"""Run: .codex-venv/bin/python -B -m unittest misc.test_otoge_input_viewer_client"""

import json
import unittest

from src.otoge_input_viewer_client import OtogeInputViewerClient


class OtogeInputViewerClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OtogeInputViewerClient(autostart=False)

    def test_collects_release_averages_in_ten_second_buckets(self):
        self.client.start_play(now=100.0)
        self.client.handle_message(self._release_message(20.0), now=101.0)
        self.client.handle_message(self._release_message(30.0), now=109.9)
        self.client.handle_message(self._release_message(40.0), now=110.0)

        release = self.client.finish_play(now=121.0)

        self.assertEqual(release.histogram, [25.0, 40.0, None])
        self.assertEqual(release.interval_seconds, 10.0)
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

    @staticmethod
    def _release_message(value):
        return json.dumps([{"type": "release", "value": str(value)}])


if __name__ == "__main__":
    unittest.main()
