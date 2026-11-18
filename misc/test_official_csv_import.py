"""Run: .codex-venv/bin/python -B -m unittest misc.test_official_csv_import"""

import unittest
import tempfile
import datetime
import time
from pathlib import Path
from types import SimpleNamespace

from src.classes import clear_lamp, detect_mode, difficulty, play_style
from src.config import Config
from src.official_csv_import import (
    OfficialCsvBest,
    OfficialCsvImporter,
    OfficialCsvImportPlan,
    parse_official_csv,
    result_exceeds_official,
)
from src.result import OneResult, PlayOption
from src.result_database import ResultDatabase


def make_result(score=1000, bp=20, lamp=clear_lamp.clear):
    return OneResult(
        title="TEST SONG",
        play_style=play_style.sp,
        difficulty=difficulty.another,
        lamp=lamp,
        timestamp=123,
        playspeed=None,
        option=PlayOption(),
        detect_mode=detect_mode.result,
        score=score,
        bp=bp,
    )


class OfficialCsvParserTests(unittest.TestCase):
    def test_parses_played_charts_and_skips_zero_scores(self):
        text = (
            "バージョン,タイトル,アーティスト,NORMAL スコア,NORMAL 最終スコア更新時刻,"
            "NORMAL ミスカウント,NORMAL クリアタイプ,NORMAL プレー回数,NORMAL 最終プレー日時,"
            "ANOTHER スコア,ANOTHER 最終スコア更新時刻,ANOTHER ミスカウント,"
            "ANOTHER クリアタイプ,ANOTHER プレー回数,ANOTHER 最終プレー日時,\n"
            "1st,TEST SONG,artist,0,2026-01-01 00:00,---,FAILED,1,2026-01-01 00:00,"
            "1234,2026-01-02 00:00,12,HARD CLEAR,2,2026-01-03 00:00,\n"
        )

        parsed = parse_official_csv(text)

        self.assertEqual(parsed.errors, [])
        self.assertEqual(len(parsed.bests), 2)
        normal_failed = parsed.bests[0]
        another_best = parsed.bests[1]
        self.assertEqual(normal_failed.difficulty, difficulty.normal)
        self.assertEqual(normal_failed.score, 0)
        self.assertEqual(normal_failed.play_count, 1)
        self.assertEqual(another_best.difficulty, difficulty.another)
        self.assertEqual(another_best.score, 1234)
        self.assertEqual(another_best.bp, 12)
        self.assertEqual(another_best.lamp, clear_lamp.hard)
        self.assertEqual(another_best.play_count, 2)
        self.assertEqual(
            another_best.registered_at,
            int(datetime.datetime(2026, 1, 3, 0, 0).timestamp()),
        )

    def test_accepts_scored_no_play_and_missing_bp(self):
        text = (
            "タイトル,NORMAL スコア,NORMAL ミスカウント,NORMAL クリアタイプ\n"
            "TEST SONG,650,---,NO PLAY\n"
        )
        parsed = parse_official_csv(text)

        self.assertEqual(parsed.errors, [])
        self.assertEqual(parsed.bests[0].bp, None)
        self.assertEqual(parsed.bests[0].lamp, clear_lamp.noplay)

    def test_last_selected_style_is_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config = Config(str(config_path))
            self.assertEqual(config.official_csv_import_style, "SP")

            config.official_csv_import_style = "DP"
            config.save_config()

            self.assertEqual(
                Config(str(config_path)).official_csv_import_style,
                "DP",
            )


class OfficialCsvCorrectionTests(unittest.TestCase):
    def test_detects_score_bp_and_lamp_overruns(self):
        official = OfficialCsvBest(
            "TEST SONG", difficulty.another, 1000, 20, clear_lamp.clear
        )
        self.assertTrue(result_exceeds_official(make_result(score=1001), official))
        self.assertTrue(result_exceeds_official(make_result(bp=19), official))
        self.assertTrue(result_exceeds_official(make_result(lamp=clear_lamp.hard), official))
        self.assertFalse(result_exceeds_official(make_result(), official))

    def test_build_plan_marks_only_regular_matching_logs(self):
        over = make_result(score=1100)
        other_chart = make_result(score=1200)
        other_chart.title = "OTHER SONG"
        db = SimpleNamespace()
        db.results = [over, other_chart]
        db.song_database = SimpleNamespace(
            search=lambda **kwargs: SimpleNamespace(title="TEST SONG", notes=1000)
        )

        importer = OfficialCsvImporter(db)
        official = OfficialCsvBest(
            "TEST SONG", difficulty.another, 1000, 20, clear_lamp.clear
        )

        plan = importer.build_plan([official], play_style.sp)

        self.assertEqual(plan.delete_indexes, {0})
        self.assertEqual(len(plan.corrected_charts), 1)
        self.assertEqual(len(plan.corrections), 1)
        self.assertEqual(plan.corrections[0].saved_score, 1100)
        self.assertEqual(plan.corrections[0].official_score, 1000)
        self.assertEqual(plan.corrections[0].delete_count, 1)
        self.assertEqual(plan.results[0].detect_mode, detect_mode.select)
        self.assertEqual(plan.results[0].timestamp, 0)
        self.assertIsNotNone(plan.results[0].registered_at)

    def test_build_plan_copies_last_played_time_to_registered_at(self):
        db = SimpleNamespace()
        db.results = []
        db.song_database = SimpleNamespace(
            search=lambda **kwargs: SimpleNamespace(title="TEST SONG", notes=1000)
        )
        registered_at = int(datetime.datetime(2026, 1, 3, 0, 0).timestamp())
        official = OfficialCsvBest(
            "TEST SONG",
            difficulty.another,
            1000,
            20,
            clear_lamp.clear,
            registered_at,
        )

        plan = OfficialCsvImporter(db).build_plan([official], play_style.sp)

        self.assertEqual(plan.results[0].registered_at, registered_at)

    def test_build_plan_copies_official_play_count(self):
        db = SimpleNamespace()
        db.results = []
        db.song_database = SimpleNamespace(
            search=lambda **kwargs: SimpleNamespace(title="TEST SONG", notes=1000)
        )
        official = OfficialCsvBest(
            "TEST SONG",
            difficulty.another,
            1000,
            20,
            clear_lamp.clear,
            play_count=37,
        )

        plan = OfficialCsvImporter(db).build_plan([official], play_style.sp)

        self.assertEqual(plan.results[0].official_play_count, 37)

    def test_select_result_gets_registration_time_when_created(self):
        before = int(time.time())
        result = make_result()
        result.detect_mode = detect_mode.select
        result = OneResult(
            title=result.title,
            play_style=result.play_style,
            difficulty=result.difficulty,
            lamp=result.lamp,
            timestamp=0,
            playspeed=result.playspeed,
            option=result.option,
            detect_mode=detect_mode.select,
            score=result.score,
            bp=result.bp,
        )

        self.assertGreaterEqual(result.registered_at, before)
        self.assertLessEqual(result.registered_at, int(time.time()))

    def test_title_fallback_absorbs_symbols_and_accents(self):
        song = SimpleNamespace(
            title="Ubertreffen",
            play_style=play_style.sp,
            difficulty=difficulty.another,
            notes=1000,
        )
        db = SimpleNamespace(
            results=[],
            song_database=SimpleNamespace(
                songs={"song": song},
                search=lambda **kwargs: None,
            ),
        )
        importer = OfficialCsvImporter(db)
        official = OfficialCsvBest(
            "Übertreffen", difficulty.another, 1000, 20, clear_lamp.clear
        )

        plan = importer.build_plan([official], play_style.sp)

        self.assertEqual(plan.unknown_charts, [])
        self.assertEqual(plan.results[0].title, "Ubertreffen")

    def test_apply_skips_an_exact_existing_best(self):
        class FakeDatabase:
            def __init__(self):
                self.results = [make_result()]
                self.saved = False

            def add(self, result):
                self.results.append(result)
                return True

            def save(self):
                self.saved = True

        db = FakeDatabase()
        importer = OfficialCsvImporter(db)
        result = make_result()
        result.detect_mode = detect_mode.select
        result.timestamp = 0
        progress = []
        imported = importer.apply(
            OfficialCsvImportPlan(results=[result]),
            lambda current, total: progress.append((current, total)),
        )

        self.assertEqual(imported.imported, 0)
        self.assertEqual(imported.skipped, 1)
        self.assertEqual(len(db.results), 1)
        self.assertTrue(db.saved)
        self.assertEqual(progress, [(1, 1)])

    def test_apply_fills_missing_registration_time_on_same_select_best(self):
        class FakeDatabase:
            def __init__(self, existing):
                self.results = [existing]
                self.saved = False

            def add(self, result):
                self.results.append(result)
                return True

            def save(self):
                self.saved = True

        existing = make_result()
        existing.detect_mode = detect_mode.select
        existing.timestamp = 0
        existing.registered_at = None
        db = FakeDatabase(existing)
        importer = OfficialCsvImporter(db)
        imported_result = make_result()
        imported_result.detect_mode = detect_mode.select
        imported_result.timestamp = 0
        imported_result.registered_at = 1234567890

        imported = importer.apply(OfficialCsvImportPlan(results=[imported_result]))

        self.assertEqual(imported.imported, 1)
        self.assertEqual(imported.skipped, 0)
        self.assertEqual(len(db.results), 1)
        self.assertEqual(db.results[0].registered_at, 1234567890)
        self.assertTrue(db.saved)

    def test_apply_skips_same_select_best_with_registration_time(self):
        class FakeDatabase:
            def __init__(self, existing):
                self.results = [existing]

            def add(self, result):
                self.results.append(result)
                return True

            def save(self):
                pass

        existing = make_result()
        existing.detect_mode = detect_mode.select
        existing.timestamp = 0
        existing.registered_at = 1234567890
        db = FakeDatabase(existing)
        imported_result = make_result()
        imported_result.detect_mode = detect_mode.select
        imported_result.timestamp = 0
        imported_result.registered_at = 1234567891

        imported = OfficialCsvImporter(db).apply(
            OfficialCsvImportPlan(results=[imported_result])
        )

        self.assertEqual(imported.imported, 0)
        self.assertEqual(imported.skipped, 1)
        self.assertEqual(len(db.results), 1)
        self.assertEqual(db.results[0].registered_at, 1234567890)

    def test_reimport_does_not_add_the_same_best_twice(self):
        class FakeDatabase:
            def __init__(self):
                self.results = []

            def add(self, result):
                self.results.append(result)
                return True

            def save(self):
                pass

        db = FakeDatabase()
        importer = OfficialCsvImporter(db)
        result = make_result()
        result.detect_mode = detect_mode.select
        plan = OfficialCsvImportPlan(results=[result])

        first = importer.apply(plan)
        second = importer.apply(plan)

        self.assertEqual(first.imported, 1)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.skipped, 1)
        self.assertEqual(len(db.results), 1)

    def test_same_best_updates_play_count_without_adding_result(self):
        class FakeDatabase:
            def __init__(self, existing):
                self.results = [existing]

            def add(self, result):
                self.results.append(result)
                return True

            def save(self):
                pass

        existing = make_result()
        imported_result = make_result()
        imported_result.detect_mode = detect_mode.select
        imported_result.timestamp = 0
        imported_result.official_play_count = 37
        db = FakeDatabase(existing)
        importer = OfficialCsvImporter(db)

        first = importer.apply(OfficialCsvImportPlan(results=[imported_result]))
        second = importer.apply(OfficialCsvImportPlan(results=[imported_result]))

        self.assertEqual(first.imported, 1)
        self.assertEqual(second.skipped, 1)
        self.assertEqual(len(db.results), 1)
        self.assertEqual(db.results[0].official_play_count, 37)

    def test_history_play_counts_separate_counter_and_official(self):
        played = make_result()
        official = make_result()
        official.detect_mode = detect_mode.select
        official.timestamp = 0
        official.official_play_count = 37
        db = ResultDatabase.__new__(ResultDatabase)
        db.config = None
        details = [SimpleNamespace(result=played), SimpleNamespace(result=official)]

        self.assertEqual(db._get_history_play_counts(details), (1, 37))
        self.assertEqual(db._get_history_play_counts(details, battle=True), (1, None))

    def test_zero_score_played_chart_can_be_registered(self):
        db = ResultDatabase.__new__(ResultDatabase)
        db.results = []
        result = make_result(score=0, bp=None, lamp=clear_lamp.failed)
        result.detect_mode = detect_mode.select
        result.pre_score = None
        result.official_play_count = 1

        self.assertTrue(db.add(result))
        self.assertEqual(len(db.results), 1)


if __name__ == "__main__":
    unittest.main()
