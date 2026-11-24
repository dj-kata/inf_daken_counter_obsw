"""Run: .codex-venv/bin/python -B -m unittest misc.test_legacy_migration"""

import pickle
import tempfile
import unittest
from pathlib import Path

from src.classes import clear_lamp, difficulty, play_style
from src.legacy_migration import load_v2_results
from src.result_database import ResultDatabase


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_v2_alllog_converts_directly_into_sqlite_and_keeps_source(self):
        source = self.root / "alllog.pkl"
        item = [
            "v2",
            "TEST SONG",
            "SPA",
            1000,
            None,
            None,
            None,
            "H-CLEAR",
            None,
            1800,
            None,
            25,
            "RAN",
            "2024-01-02 03:04",
        ]
        with source.open("wb") as stream:
            pickle.dump([item], stream)

        results, total = load_v2_results(source)
        self.assertEqual(total, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].play_style, play_style.sp)
        self.assertEqual(results[0].difficulty, difficulty.another)
        self.assertEqual(results[0].lamp, clear_lamp.hard)
        self.assertEqual(results[0].option.arrange, "RANDOM")

        database = ResultDatabase(
            storage_path=self.root / "daken_counter.db",
            legacy_pickle_path=self.root / "missing.infdc",
        )
        self.addCleanup(database.shutdown_servers)
        for result in results:
            self.assertTrue(database.add(result))
        database.save()
        database.switch_storage(
            self.root / "other.db",
            self.root / "missing-other.infdc",
        )
        database.switch_storage(
            self.root / "daken_counter.db",
            self.root / "missing.infdc",
        )
        self.assertEqual(len(database.results), 1)
        self.assertEqual(database.results[0].title, "TEST SONG")
        self.assertTrue(source.exists())


if __name__ == "__main__":
    unittest.main()
