"""Run: .codex-venv/bin/python -B -m unittest misc.test_database_queries"""

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.classes import Judge, clear_lamp, detect_mode, difficulty, play_style
from src.result import DetailedResult, OneResult, PlayOption
from src.result_database import ResultDatabase


class DatabaseQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = ResultDatabase(
            storage_path=self.root / "daken_counter.db",
            legacy_pickle_path=self.root / "missing.infdc",
        )
        self.addCleanup(self.database.shutdown_servers)

    @staticmethod
    def _option():
        option = PlayOption(None)
        option.valid = True
        return option

    def _score(self, title, score, bp, timestamp):
        return OneResult(
            title=title,
            play_style=play_style.sp,
            difficulty=difficulty.another,
            lamp=clear_lamp.hard,
            timestamp=timestamp,
            playspeed=None,
            option=self._option(),
            detect_mode=detect_mode.result,
            score=score,
            bp=bp,
            notes=1000,
            dead=False,
            registered_at=timestamp,
        )

    def test_chart_logs_and_bests_are_queried_from_sqlite(self):
        first = self._score("TEST ☆ SONG", 1800, 30, 100)
        second = self._score("TEST ☆ SONG", 1900, 20, 200)
        self.database.results = [first, second]
        self.database.save()

        # メモリ側を空にしても、参照結果は保存済みSQLiteから取得する。
        self.database.results = []
        with patch.object(
            self.database.database,
            "query_results",
            wraps=self.database.database.query_results,
        ) as query:
            logs = self.database.search(
                title="TEST SONG",
                style=play_style.sp,
                difficulty=difficulty.another,
            )
            best = self.database.get_best(
                title="TEST SONG",
                style=play_style.sp,
                difficulty=difficulty.another,
            )
            all_bests = self.database.get_all_best_results()

        self.assertGreaterEqual(query.call_count, 3)
        self.assertEqual([detail.result.score for detail in logs], [1800, 1900])
        self.assertEqual(best, [1900, 20, clear_lamp.hard])
        only_best = next(iter(all_bests.values()))
        self.assertEqual(only_best.best_score, 1900)
        self.assertEqual(only_best.min_bp, 20)

    def test_period_statistics_are_queried_from_sqlite(self):
        played_at = int(datetime.datetime(2024, 1, 15, 12, 0).timestamp())
        play = OneResult(
            title="TEST SONG",
            play_style=play_style.sp,
            difficulty=difficulty.another,
            lamp=None,
            timestamp=played_at,
            playspeed=None,
            option=self._option(),
            detect_mode=detect_mode.play,
            judge=Judge(500, 300, 100, 20, 10, 25),
            notes=920,
            registered_at=played_at,
        )
        self.database.results = [play]
        self.database.save()
        self.database.results = []

        target = datetime.datetime(2024, 1, 20)
        self.assertEqual(self.database.get_monthly_notes(target), 920)
        self.assertEqual(self.database.get_yearly_notes(target), 920)
        graph = self.database.get_graph_data(
            int(datetime.datetime(2024, 1, 15).timestamp()),
            int(datetime.datetime(2024, 1, 16).timestamp()),
        )
        self.assertEqual(graph["playcount"], 1)
        self.assertEqual(graph["today_notes"], 920)

    def test_history_display_does_not_refetch_bpim2_synchronously(self):
        result = self._score("TEST SONG", 1900, 20, 200)
        result.bpim2 = 12.34
        result.bpim2_arena_averages = []
        self.database.results = [result]
        self.database.save()

        with patch.object(
            DetailedResult,
            "get_bpim2_bpi_detail",
            side_effect=AssertionError("synchronous BPIM2 fetch"),
        ):
            data = self.database.get_history_cursong_data(
                title="TEST SONG",
                style=play_style.sp,
                difficulty=difficulty.another,
            )

        self.assertEqual(data["best_bpi"], "12.34")
        self.assertNotIn("bpi_near_averages", data)


if __name__ == "__main__":
    unittest.main()
