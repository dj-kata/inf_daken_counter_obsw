"""Run: .codex-venv/bin/python -B -m unittest misc.test_accounts"""

import bz2
import json
import os
from pathlib import Path
import pickle
import tempfile
from types import SimpleNamespace
import unittest

from src.config import Config
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from src.main_window import MainWindowUI
from src.rival_data import RivalData, RivalManager
from src.result_database import ResultDatabase


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
        default_path = self.root / "playlog.infdc"
        second_path = self.root / "accounts" / "second" / "playlog.infdc"
        database = ResultDatabase(storage_path=default_path)
        self.addCleanup(database.shutdown_servers)
        default_entry = SimpleNamespace(lane_layout=None, official_play_count=None, value="default")
        second_entry = SimpleNamespace(lane_layout=None, official_play_count=None, value="second")
        database.results = [default_entry]
        database._result_image_cache[1] = self.root / "cached.png"
        database.switch_storage(second_path)
        self.assertEqual(database.results, [])
        self.assertEqual(database._result_image_cache, {})
        database.results = [second_entry]
        database.switch_storage(default_path)
        self.assertEqual(database.results[0].value, "default")
        with bz2.BZ2File(second_path, "rb") as stream:
            self.assertEqual(pickle.load(stream)[0].value, "second")

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
        default_path = self.root / "out" / "rival_log.infdc"
        second_path = self.root / "accounts" / "second" / "rival_log.infdc"
        for path, name in ((default_path, "Default Rival"), (second_path, "Second Rival")):
            path.parent.mkdir(parents=True, exist_ok=True)
            with bz2.BZ2File(path, "wb") as stream:
                pickle.dump([RivalData(name)], stream)

        manager = RivalManager(cache_path=str(default_path))
        manager.load_cache()
        self.assertEqual(manager.rivals[0].name, "Default Rival")
        manager.switch_cache(str(second_path))
        self.assertEqual(manager.rivals[0].name, "Second Rival")


if __name__ == "__main__":
    unittest.main()
