"""Run: .codex-venv/bin/python -B -m unittest misc.test_accounts"""

import bz2
import json
import os
from pathlib import Path
import pickle
import tempfile
import unittest

from src.classes import Judge, average_release, clear_lamp, detect_mode, difficulty, play_style
from src.config import Config
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from src.main_window import MainWindowUI
from src.rival_data import RivalData, RivalManager, RivalScoreEntry
from src.result import BpiArenaAverage, OneResult, PlayOption
from src.result_database import ResultDatabase
from src.database_sqlite import SQLiteDatabase


class AccountConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.json"

    def test_old_config_creates_default_account_and_preserves_rivals(self):
        rivals = [{"name": "RIVAL", "url": "example"}]
        self.config_path.write_text(json.dumps({"rivals": rivals}), encoding="utf-8")
        config = Config(str(self.config_path))
        self.assertEqual(config.selected_account_id, "default")
        self.assertEqual(config.selected_account["name"], "Default")
        self.assertEqual(config.rivals, rivals)
        self.assertEqual(config.account_playlog_path(), "playlog.infdc")
        self.assertEqual(config.account_database_path(), "daken_counter.db")

    def test_account_settings_and_rivals_are_independent(self):
        config = Config(str(self.config_path))
        config.rivals = [{"name": "DEFAULT", "url": "default"}]
        config.accounts.append({
            "id": "second",
            "name": "Second",
            "image_save_path": "second-images",
            "color": "#123456",
            "rivals": [{"name": "SECOND", "url": "second"}],
        })
        self.assertTrue(config.select_account("second"))
        self.assertEqual(config.rivals[0]["name"], "SECOND")
        self.assertEqual(config.effective_image_save_path, "second-images")
        self.assertEqual(config.account_playlog_path(), "accounts/second/playlog.infdc")
        self.assertEqual(config.account_database_path(), "accounts/second/daken_counter.db")
        config.save_config()

        loaded = Config(str(self.config_path))
        self.assertEqual(loaded.selected_account_id, "second")
        self.assertEqual(loaded.rivals[0]["name"], "SECOND")
        legacy_view = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(legacy_view["rivals"][0]["name"], "DEFAULT")
        loaded.select_account("default")
        self.assertEqual(loaded.rivals[0]["name"], "DEFAULT")
        self.assertEqual(loaded.effective_image_save_path, "results")

    def test_result_database_switches_between_separate_files(self):
        legacy_path = self.root / "playlog.infdc"
        default_path = self.root / "daken_counter.db"
        second_path = self.root / "accounts" / "second" / "daken_counter.db"
        default_entry = self._result("default-entry", 100)
        with bz2.BZ2File(legacy_path, "wb") as stream:
            pickle.dump([default_entry], stream)
        database = ResultDatabase(
            storage_path=default_path,
            legacy_pickle_path=legacy_path,
        )
        self.addCleanup(database.shutdown_servers)
        self.assertTrue(legacy_path.exists())
        self.assertEqual(database.results[0].title, "default-entry")
        database._result_image_cache[1] = self.root / "cached.png"
        database.switch_storage(second_path, self.root / "missing.infdc")
        self.assertEqual(database.results, [])
        self.assertEqual(database._result_image_cache, {})
        database.results = [self._result("second-entry", 200)]
        database.save()
        database.switch_storage(default_path, legacy_path)
        restored = database.results[0]
        self.assertEqual(restored.title, "default-entry")
        self.assertEqual(restored.option.arrange, "RANDOM")
        self.assertTrue(restored.option.valid)
        self.assertEqual(restored.judge.pg, 300)
        self.assertEqual(restored.average_release.histogram, [10.5, 20.5])
        self.assertEqual(restored.bpim2_arena_averages[0].rank, "A1")
        self.assertEqual(restored.lane_layout, "1234567")
        self.assertTrue(default_path.exists())
        self.assertTrue(second_path.exists())
        database.switch_storage(second_path, self.root / "missing.infdc")
        database.results[0].official_play_count = 9
        database.save()
        database.switch_storage(default_path, legacy_path)
        database.switch_storage(second_path, self.root / "missing.infdc")
        self.assertEqual(database.results[0].official_play_count, 9)
        database.results.clear()
        database.save()
        database.switch_storage(default_path, legacy_path)
        database.switch_storage(second_path, self.root / "missing.infdc")
        self.assertEqual(database.results, [])
        database.switch_storage(default_path, legacy_path)
        database.results.clear()
        database.save()
        database.switch_storage(second_path, self.root / "missing.infdc")
        database.switch_storage(default_path, legacy_path)
        self.assertEqual(database.results, [])
        self.assertTrue(legacy_path.exists())

    def test_main_window_lists_accounts_and_uses_account_color(self):
        config = Config(str(self.config_path))
        config.accounts.append({
            "id": "second",
            "name": "Second",
            "image_save_path": "",
            "color": "#12ab34",
            "rivals": [],
        })
        config.select_account("second")
        window = MainWindowUI(config)
        self.addCleanup(window.close)
        window.init_ui()
        self.assertEqual(window.account_label.text(), "Second")
        self.assertIn("#12ab34", window.account_label.styleSheet())
        self.assertEqual(
            [action.text() for action in window.account_menu.actions() if action.isCheckable()],
            ["Default", "Second"],
        )

    def test_rival_cache_switches_between_accounts(self):
        legacy_path = self.root / "out" / "rival_log.infdc"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        with bz2.BZ2File(legacy_path, "wb") as stream:
            pickle.dump([self._rival("Default Rival")], stream)
        default_db = SQLiteDatabase(self.root / "daken_counter.db")
        second_db = SQLiteDatabase(self.root / "accounts" / "second" / "daken_counter.db")
        self.addCleanup(default_db.close)
        self.addCleanup(second_db.close)

        manager = RivalManager(database=default_db, legacy_cache_path=str(legacy_path))
        manager.load_cache()
        self.assertTrue(legacy_path.exists())
        self.assertEqual(manager.rivals[0].name, "Default Rival")
        manager.rivals = [self._rival("Second Rival")]
        manager.database = second_db
        manager._save_cache()
        manager.switch_database(second_db, self.root / "missing-rival.infdc")
        self.assertEqual(manager.rivals[0].name, "Second Rival")

    @staticmethod
    def _result(title, timestamp):
        option = PlayOption(None)
        option.valid = True
        option.arrange = "RANDOM"
        result = OneResult(
            title=title,
            play_style=play_style.sp,
            difficulty=difficulty.another,
            lamp=clear_lamp.clear,
            timestamp=timestamp,
            playspeed=None,
            option=option,
            detect_mode=detect_mode.result,
            judge=Judge(300, 100, 20, 5, 7, 12),
            notes=600,
            dead=False,
            average_release=average_release([10.5, 20.5]),
            bpim2=12.34,
            image_path="results/test.png",
            lane_layout="1234567",
            registered_at=timestamp + 1,
            official_play_count=3,
        )
        result.bpim2_arena_averages = [BpiArenaAverage("A1", 2100)]
        return result

    @staticmethod
    def _rival(name):
        rival = RivalData(name)
        entry = RivalScoreEntry()
        entry.lamp = clear_lamp.hard
        entry.score = 2000
        entry.bp = 20
        rival.scores[("TEST", "SPA")] = entry
        return rival


if __name__ == "__main__":
    unittest.main()
