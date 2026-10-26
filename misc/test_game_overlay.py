"""Run: QT_QPA_PLATFORM=offscreen .codex-venv/bin/python -B -m unittest misc.test_game_overlay"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTabWidget

from src.classes import detect_mode
from src.config import Config
from src.game_overlay import (GameOverlay, LOG_RECTS, RANDOM_PROFILES, RandomLaneOverlay, lane_colors,
                              scaled_rect, valid_lane_layout, visible_overlay)


class GameOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = Config(str(Path(temp.name) / 'config.json'))
        self.state = {'phase': 'confirmed', 'side': '1P', 'layout': '3172654'}

    def test_legacy_config_defaults_and_new_settings_round_trip(self):
        Path(self.config.config_file).write_text('{}', encoding='utf-8')
        config = Config(self.config.config_file)
        self.assertFalse(config.enable_game_overlay)
        self.assertFalse(config.overlay_show_lane_numbers)
        for key in ('random_lane', 'song_history', 'today_results'):
            self.assertTrue(getattr(config, 'overlay_' + key))
        config.enable_game_overlay = True
        config.overlay_song_history = False
        config.overlay_show_lane_numbers = True
        config.save_config()
        saved = Config(config.config_file)
        self.assertTrue(saved.enable_game_overlay)
        self.assertFalse(saved.overlay_song_history)
        self.assertTrue(saved.overlay_random_lane)
        self.assertTrue(saved.overlay_today_results)
        self.assertTrue(saved.overlay_show_lane_numbers)

    def test_dialog_both_languages_apply_and_cancel(self):
        from src.config_dialog import ConfigDialog
        for language, label in (('ja', 'オーバーレイ'), ('en', 'Overlay')):
            with self.subTest(language=language):
                self.config.language = language
                self.config.enable_game_overlay = False
                self.config.overlay_random_lane = True
                self.config.overlay_show_lane_numbers = False
                dialog = ConfigDialog(self.config)
                self.addCleanup(dialog.deleteLater)
                tabs = dialog.findChild(QTabWidget)
                self.assertIn(label, [tabs.tabText(i) for i in range(tabs.count())])
                self.assertFalse(dialog.overlay_items_group.isEnabled())
                self.assertFalse(dialog.overlay_log_format_group.isEnabled())
                self.assertFalse(dialog.overlay_show_lane_numbers_check.isChecked())
                self.assertTrue(all(check.isChecked() for check in dialog.overlay_item_checks.values()))
                original = Path(self.config.config_file).read_bytes()
                dialog.enable_game_overlay_check.setChecked(True)
                self.assertTrue(dialog.overlay_items_group.isEnabled())
                self.assertTrue(dialog.overlay_log_format_group.isEnabled())
                dialog.overlay_item_checks['random_lane'].setChecked(False)
                dialog.overlay_show_lane_numbers_check.setChecked(True)
                dialog.reject()
                self.assertFalse(self.config.enable_game_overlay)
                self.assertFalse(self.config.overlay_show_lane_numbers)
                self.assertEqual(Path(self.config.config_file).read_bytes(), original)
                dialog.accept()
                saved = Config(self.config.config_file)
                self.assertTrue(saved.enable_game_overlay)
                self.assertFalse(saved.overlay_random_lane)
                self.assertTrue(saved.overlay_song_history)
                self.assertTrue(saved.overlay_show_lane_numbers)
                reopened = ConfigDialog(saved)
                self.addCleanup(reopened.deleteLater)
                reopened.enable_game_overlay_check.setChecked(False)
                self.assertFalse(reopened.overlay_item_checks['random_lane'].isChecked())
                self.assertTrue(reopened.overlay_item_checks['today_results'].isChecked())
                self.assertTrue(reopened.overlay_show_lane_numbers_check.isChecked())
                self.assertFalse(reopened.overlay_log_format_group.isEnabled())

    def test_modes_and_independent_toggles(self):
        config = self.config
        self.assertIsNone(visible_overlay(config, detect_mode.result, self.state))
        config.enable_game_overlay = True
        config.enable_random_lane_analysis = True
        for mode, key in ((detect_mode.play, 'random_lane'), (detect_mode.result, 'song_history'),
                          (detect_mode.select, 'today_results')):
            with self.subTest(mode=mode):
                self.assertEqual(visible_overlay(config, mode, self.state), key)
                setattr(config, 'overlay_' + key, False)
                self.assertIsNone(visible_overlay(config, mode, self.state))
                setattr(config, 'overlay_' + key, True)
                self.assertIsNone(visible_overlay(config, mode, self.state, capture_ready=False))
        for mode in (detect_mode.init, detect_mode.option):
            self.assertIsNone(visible_overlay(config, mode, self.state))

    def test_random_rejects_stale_disabled_or_invalid_state(self):
        self.config.enable_game_overlay = True
        self.config.enable_random_lane_analysis = True
        for changes in ({'phase': 'idle'}, {'side': None}, {'layout': ''}, {'layout': '???????'}):
            self.assertIsNone(visible_overlay(self.config, detect_mode.play, self.state | changes))
        self.config.enable_random_lane_analysis = False
        self.assertIsNone(visible_overlay(self.config, detect_mode.play, self.state))

    def test_partial_layout_validation_and_app_colors(self):
        for layout in ('1234567', '7654321', '?1??B?W', 'WBWBWBW'):
            self.assertTrue(valid_lane_layout(layout), layout)
        for layout in (None, '', '???????', '123456', '12345678', '1123456', 'WWWWW??', 'BBBB???', '<img!!!'):
            self.assertFalse(valid_lane_layout(layout), layout)
        self.assertEqual(lane_colors('1'), ('#ffffff', '#d00000'))
        self.assertEqual(lane_colors('2'), ('#0066cc', '#ffff00'))
        self.assertEqual(lane_colors('3'), ('#ffffff', '#000000'))
        self.assertEqual(lane_colors('B'), lane_colors('2'))
        self.assertEqual(lane_colors('?')[0], '#777777')

    def test_geometry_scales_and_tracks_negative_monitor_origin(self):
        self.assertEqual(scaled_rect((160, 532, 348, 71), (0, 0, 1920, 1080)),
                         (160, 532, 348, 71))
        self.assertEqual(scaled_rect((160, 532, 348, 72), (-1280, -720, 0, 0)),
                         (-1173, -365, 232, 48))

    def test_log_rectangles_stay_inside_marked_screen_areas(self):
        for item, safe in (('song_history', (559, 353, 1352, 952)),
                           ('today_results', (18, 611, 590, 799))):
            with self.subTest(item=item):
                x, y, width, height = LOG_RECTS[item]
                self.assertGreaterEqual(x, safe[0])
                self.assertGreaterEqual(y, safe[1])
                self.assertLessEqual(x + width, safe[2])
                self.assertLessEqual(y + height, safe[3])

    def test_random_panels_stay_beside_scratch_below_note_field(self):
        # Full HD keyboard interiors measured from both 1P layouts and 2P.
        # These remain below the note field even when LIFT is disabled.
        safe_areas = {'1P': (168, 730, 507, 826), '2P': (1413, 730, 1752, 826)}
        for side, (x, y, scale) in RANDOM_PROFILES.items():
            for bbox in ((0, 0, 1920, 1080), (0, 0, 2560, 1440),
                         (-2560, -1440, 0, 0)):
                with self.subTest(side=side, bbox=bbox):
                    left, top, right, bottom = safe_areas[side]
                    safe_x, safe_y, safe_w, safe_h = scaled_rect(
                        (left, top, right - left, bottom - top), bbox)
                    px, py, width, height = scaled_rect(
                        (x, y, 470 * scale, 96 * scale), bbox)
                    self.assertGreaterEqual(px, safe_x)
                    self.assertGreaterEqual(py, safe_y)
                    self.assertLessEqual(px + width, safe_x + safe_w)
                    self.assertLessEqual(py + height, safe_y + safe_h)

    def test_native_panel_draws_colors_without_accepting_input(self):
        window = RandomLaneOverlay()
        self.addCleanup(window.close)
        window.set_layout('1234567')
        window.resize(470, 96)
        image = window.grab().toImage()
        self.assertEqual(image.pixelColor(20, 20).name(), '#ffffff')
        self.assertEqual(image.pixelColor(80, 20).name(), '#0066cc')
        self.assertTrue(window.windowFlags() & Qt.WindowTransparentForInput)
        self.assertTrue(window.windowFlags() & Qt.WindowDoesNotAcceptFocus)
        self.assertTrue(window.testAttribute(Qt.WA_ShowWithoutActivating))

    def test_controller_switches_hides_disables_and_releases_windows(self):
        self.config.enable_game_overlay = True
        self.config.enable_random_lane_analysis = True
        manager = GameOverlay(self.config)
        self.addCleanup(manager.close)
        with patch.object(manager, '_target_bbox', return_value=(0, 0, 1920, 1080)), \
                patch('src.game_overlay.HtmlLogOverlay') as html_class:
            manager.update(detect_mode.play, self.state, 9876)
            self.assertTrue(manager.random_window.isVisible())
            self.assertEqual(manager.random_window._desktop_rect, (170, 755, 329, 67))
            html_class.assert_not_called()
            manager.update(detect_mode.result, self.state, 9876)
            self.assertFalse(manager.random_window.isVisible())
            html_class.return_value.set_source.assert_called_with('song_history', 9876, show_lane_numbers=False)
            html_class.return_value.present.assert_called_with(LOG_RECTS['song_history'])
            manager.update(detect_mode.select, self.state, 9876)
            html_class.return_value.set_source.assert_called_with('today_results', 9876, show_lane_numbers=False)
            html_class.return_value.present.assert_called_with(LOG_RECTS['today_results'])
            manager.update(detect_mode.option, self.state, 9876)
            html_class.return_value.hide.assert_called()
            self.config.enable_game_overlay = False
            manager.set_config(self.config)
            self.assertIsNone(manager.random_window)
            self.assertIsNone(manager.log_window)
            html_class.return_value.close.assert_called_once()
            html_class.return_value.deleteLater.assert_called_once()

    def test_lane_number_setting_is_shared_by_both_log_screens(self):
        self.config.enable_game_overlay = True
        self.config.overlay_show_lane_numbers = True
        manager = GameOverlay(self.config)
        self.addCleanup(manager.close)
        with patch.object(manager, '_target_bbox', return_value=(0, 0, 1920, 1080)), \
                patch('src.game_overlay.HtmlLogOverlay') as html_class:
            for mode, item in ((detect_mode.result, 'song_history'), (detect_mode.select, 'today_results')):
                manager.update(mode, {}, 8767)
                html_class.return_value.set_source.assert_called_with(item, 8767, show_lane_numbers=True)

    def test_closed_controller_cannot_reopen_during_application_shutdown(self):
        self.config.enable_game_overlay = True
        manager = GameOverlay(self.config)
        manager.close()
        with patch.object(manager, '_target_bbox') as target:
            manager.update(detect_mode.result, {}, 8767)
            target.assert_not_called()

    def test_missing_game_does_not_create_windows(self):
        self.config.enable_game_overlay = True
        manager = GameOverlay(self.config)
        with patch.object(manager, '_target_bbox', return_value=None), \
                patch('src.game_overlay.HtmlLogOverlay') as html_class:
            manager.update(detect_mode.result, {}, 8767)
            html_class.assert_not_called()

    def test_browser_failure_is_reported_once_and_retry_allowed_after_settings(self):
        self.config.enable_game_overlay = True
        callback = Mock()
        manager = GameOverlay(self.config, error_callback=callback)
        self.addCleanup(manager.close)
        with patch.object(manager, '_target_bbox', return_value=(0, 0, 1920, 1080)), \
                patch('src.game_overlay.HtmlLogOverlay', side_effect=ImportError('missing browser')) as html_class, \
                patch('src.game_overlay.logger'):
            manager.update(detect_mode.result, {}, 8767)
            manager.update(detect_mode.result, {}, 8767)
            self.assertEqual(html_class.call_count, 1)
            callback.assert_called_once()
            manager.set_config(self.config)
            manager.update(detect_mode.result, {}, 8767)
            self.assertEqual(html_class.call_count, 2)


if __name__ == '__main__':
    unittest.main()
