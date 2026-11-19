"""Run: .codex-venv/bin/python -B -m unittest misc.test_songinfo"""

import unittest

from src.songinfo import songinfo_download_url


class SongInfoTests(unittest.TestCase):
    def test_download_url_uses_main_branch(self):
        self.assertEqual(
            songinfo_download_url,
            "https://github.com/dj-kata/inf_daken_counter_obsw/raw/refs/heads/main/songinfo.infdc",
        )


if __name__ == "__main__":
    unittest.main()
