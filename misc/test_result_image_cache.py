"""Run with: .codex-venv/bin/python -B -m unittest misc.test_result_image_cache"""

import ast
import datetime
import json
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.request

from PIL import Image

from src.classes import config_autosave_image, config_modify_rivalarea, detect_mode
from src.config import Config
from src.mobile_http_server import MobileScoreHTTPServer
from src.result_database import ResultDatabase


class ResultImageCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.new_database()
        self.image = Image.new('RGB', (1920, 1080), (30, 60, 90))

    def new_database(self):
        # Avoid loading/saving the user's playlog or starting application servers.
        with patch('src.result_database.SongDatabase'), \
                patch.object(ResultDatabase, 'load'), patch.object(ResultDatabase, 'save'):
            db = ResultDatabase()
        db.config = SimpleNamespace(result_image_cache_limit=0)
        self.addCleanup(db.shutdown_servers)
        return db

    def result(self, timestamp):
        result = SimpleNamespace(timestamp=timestamp, detect_mode=detect_mode.result,
                                 image_path=None, title='test')
        self.db.results.append(result)
        return result

    def test_unsaved_result_can_be_listed_and_combined(self):
        result = self.result(100)
        self.db.cache_result_image(result, self.image)
        self.assertIsNone(result.image_path)
        self.assertEqual(self.db._mobile_saved_image_results(), [(0, result)])
        self.assertEqual(self.db._mobile_result_image_url(result), '/api/result-images/100')
        combined = self.db.generate_mobile_combined_result_image(['0-100', '0-100'])
        with Image.open(BytesIO(combined)) as image:
            self.assertEqual(image.size, (1920, 1080))
        self.assertIsNone(self.db._mobile_result_by_image_id('0-101'))

    def test_limit_removes_old_temporary_files_but_keeps_saved_files_available(self):
        self.db.config.result_image_cache_limit = 1
        first, second = self.result(100), self.result(200)
        saved = self.root / 'saved.png'
        self.image.save(saved)
        first.image_path = str(saved)
        self.db.cache_result_image(first, self.image)
        old_path = self.db._cached_result_image(first)
        self.db.cache_result_image(second, self.image)
        self.assertFalse(old_path.exists())
        self.assertIsNone(self.db.get_mobile_result_image_data(100))
        self.assertEqual(self.db.get_mobile_result_image_path(100), saved)
        self.assertEqual(len(self.db._mobile_saved_image_results()), 2)
        self.assertIsNotNone(self.db.generate_mobile_combined_result_image(['0-100', '1-200']))

    def test_300_full_hd_images_can_be_retained_then_limited_to_latest_100(self):
        for timestamp in range(1, 301):
            self.db.cache_result_image(self.result(timestamp), self.image)
        cache_dir = Path(self.db._result_image_cache_dir.name)
        self.assertEqual(len(list(cache_dir.glob('*.png'))), 300)
        self.assertEqual(len(self.db._mobile_saved_image_results()), 300)
        self.db.config.result_image_cache_limit = 100
        self.db.trim_result_image_cache()
        self.assertEqual(len(list(cache_dir.glob('*.png'))), 100)
        self.assertEqual(list(self.db._result_image_cache), list(range(201, 301)))
        self.assertIsNone(self.db.get_mobile_result_image_data(200))
        self.assertIsNotNone(self.db.get_mobile_result_image_data(201))

    def test_limit_changes_immediately_and_zero_keeps_all(self):
        for timestamp in range(1, 5):
            self.db.cache_result_image(self.result(timestamp), self.image)
        self.assertEqual(len(self.db._result_image_cache), 4)
        self.db.config.result_image_cache_limit = 2
        self.db.trim_result_image_cache()
        self.assertEqual(list(self.db._result_image_cache), [3, 4])
        self.assertEqual([r.timestamp for _, r in self.db._mobile_saved_image_results()], [3, 4])

    def test_new_session_does_not_reuse_temporary_images_and_shutdown_deletes_them(self):
        result = self.result(100)
        self.db.cache_result_image(result, self.image)
        other = self.new_database()
        other.results = [result]
        self.assertEqual(other._mobile_result_image_url(result), '')
        path = self.db._cached_result_image(result)
        self.db.shutdown_servers()
        self.assertFalse(path.exists())
        self.assertIsNone(result.image_path)

    def test_http_serves_temporary_images_then_falls_back_to_saved_file(self):
        result = self.result(100)
        self.db.cache_result_image(result, self.image)
        server = MobileScoreHTTPServer(self.db, host='127.0.0.1', port=0)
        self.assertTrue(server.start())
        self.addCleanup(server.stop)
        url = f'http://127.0.0.1:{server.httpd.server_port}/api/result-images/100'
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.headers['Content-Type'], 'image/png')
            self.assertEqual(response.read(), self.db.get_mobile_result_image_data(100))
        saved = self.root / 'saved.png'
        self.image.save(saved)
        result.image_path = str(saved)
        self.db.shutdown_servers()
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.read(), saved.read_bytes())

    def save_image_method(self):
        # Run the actual save routine without importing Windows capture or Qt.
        tree = ast.parse(Path('notes_counter.pyw').read_text(encoding='utf-8'))
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'MainWindow')
        method = next(node for node in window.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'save_image')
        namespace = dict(datetime=datetime, Path=Path, config_autosave_image=config_autosave_image,
                         config_modify_rivalarea=config_modify_rivalarea,
                         DetailedResult=object, logger=Mock(),
                         get_chart_name=lambda *args: 'SPA', escape_for_filename=lambda name: name)
        import os
        import traceback
        namespace.update(os=os, traceback=traceback)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'notes_counter.pyw', 'exec'), namespace)
        return namespace['save_image']

    def save_fixture(self, updated=False):
        result = self.result(100)
        result.option = None
        result.lamp = SimpleNamespace(name='hard')
        result.score = 1000
        result.judge = SimpleNamespace(bd=1, pr=2)
        result.play_style = result.difficulty = None
        result.playspeed = None
        result.pre_score = result.pre_bp = result.pre_lamp = None
        result.is_updated = lambda: updated
        config = SimpleNamespace(autosave_image_mode=config_autosave_image.only_updates,
                                 write_statistics=False, modify_rivalarea_mode=config_modify_rivalarea.invalid,
                                 image_save_path=str(self.root / 'results'))
        window = SimpleNamespace(config=config, result_database=self.db,
                                 screen_reader=SimpleNamespace(screen=SimpleNamespace(original=self.image),
                                                               is_result=lambda: True),
                                 _apply_lane_layout_to_result=Mock(), statusBar=lambda: Mock())
        return result, window, SimpleNamespace(result=result)

    def test_no_update_is_retained_without_permanent_file(self):
        result, window, detail = self.save_fixture()
        self.assertFalse(self.save_image_method()(window, skip_no_update=True, detailed_result=detail))
        self.assertIsNotNone(self.db.get_mobile_result_image_data(100))
        self.assertFalse(Path(window.config.image_save_path).exists())
        self.assertIsNone(result.image_path)

    def test_disabled_autosave_still_retains_image(self):
        result, window, detail = self.save_fixture()
        window.config.autosave_image_mode = config_autosave_image.invalid
        self.assertFalse(self.save_image_method()(window, detailed_result=detail, cache_only=True))
        self.assertIsNotNone(self.db.get_mobile_result_image_data(100))
        self.assertIsNone(result.image_path)
        self.assertFalse(Path(window.config.image_save_path).exists())

    def test_manual_save_and_updated_autosave_still_write_permanent_files(self):
        for updated in (False, True):
            with self.subTest(updated=updated):
                result, window, detail = self.save_fixture(updated=updated)
                with patch.object(self.db, 'save'):
                    self.assertTrue(self.save_image_method()(
                        window, detailed_result=detail, skip_no_update=updated))
                self.assertTrue(Path(result.image_path).is_file())

    def test_temporary_image_uses_the_configured_rival_area_edit(self):
        result, window, detail = self.save_fixture()
        window.config.modify_rivalarea_mode = config_modify_rivalarea.cut
        detail.result_side = SimpleNamespace(name='s1p')
        edited = Image.new('RGB', (800, 1080), 'black')
        save = self.save_image_method()
        mosaic = Mock(return_value=self.image)
        cut = Mock(return_value=edited)
        save.__globals__.update(mosaic_other_rival_names=mosaic, cut_rival_area=cut)
        self.assertFalse(save(window, detailed_result=detail, cache_only=True))
        mosaic.assert_called_once_with(self.image, detail.result_side)
        cut.assert_called_once_with(self.image, detail.result_side)
        with Image.open(BytesIO(self.db.get_mobile_result_image_data(100))) as image:
            self.assertEqual(image.size, edited.size)
        self.assertIsNone(result.image_path)

    def test_cache_failure_does_not_prevent_permanent_save(self):
        result, window, detail = self.save_fixture()
        with patch.object(self.db, 'cache_result_image', side_effect=OSError('disk full')), \
                patch.object(self.db, 'save'):
            self.assertTrue(self.save_image_method()(window, detailed_result=detail))
        self.assertTrue(Path(result.image_path).is_file())

    def test_configuration_default_and_round_trip(self):
        path = self.root / 'config.json'
        path.write_text('{}', encoding='utf-8')
        config = Config(config_file=str(path))
        self.assertEqual(config.result_image_cache_limit, 0)
        config.result_image_cache_limit = 100
        config.save_config()
        self.assertEqual(Config(config_file=str(path)).result_image_cache_limit, 100)
        self.assertEqual(json.loads(path.read_text())['result_image_cache_limit'], 100)


if __name__ == '__main__':
    unittest.main()
