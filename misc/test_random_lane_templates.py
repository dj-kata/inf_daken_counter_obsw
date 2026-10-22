"""Run: .codex-venv/bin/python -B -m unittest misc.test_random_lane_templates"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from src.config import Config
from src.random_lane_analysis import RandomLaneAnalysis
from src.random_lane_templates import PlayStartRecognizer, ANCHOR_EXPECTED


class TemplateRecognitionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.folder = self.root / 'テンプレート'
        self.folder.mkdir()
        rng = np.random.default_rng(42)
        self.images = {}
        for filename, size in (
            ('OP_CURRENT_SCORE.png', (25, 190)), ('Op.RANDOM.png', (16, 80)),
            ('Op.MIRROR.png', (16, 100)), ('Op.R-.png', (16, 20)),
            ('Op.S-.png', (16, 20)), ('GET_READY.png', (32, 395)), ('SCRATCH.png', (60, 60)),
        ):
            image = rng.integers(0, 256, (*size, 3), dtype=np.uint8)
            self.images[filename] = image
            self.write_image(filename, image)
        self.recognizer = PlayStartRecognizer(self.folder)

    def write_image(self, filename, image):
        ok, encoded = cv2.imencode('.png', image)
        self.assertTrue(ok)
        (self.folder / filename).write_bytes(encoded.tobytes())

    def frame(self, layout, option='REGULAR', ready=False, anchor=True):
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        def paste(filename, x, y):
            template = self.images[filename]
            h, w = template.shape[:2]
            image[y:y+h, x:x+w] = template
        paste('SCRATCH.png', 21 if layout.startswith('1P') else 1758, 729)
        ax, ay = ANCHOR_EXPECTED[layout]
        if anchor:
            paste('OP_CURRENT_SCORE.png', ax, ay)
        if option in ('RANDOM', 'R-RANDOM', 'S-RANDOM'):
            paste('Op.RANDOM.png', ax + 30, ay + 42)
            if option != 'RANDOM':
                paste('Op.R-.png' if option == 'R-RANDOM' else 'Op.S-.png', ax + 10, ay + 42)
        elif option == 'MIRROR':
            paste('Op.MIRROR.png', ax + 30, ay + 42)
        if ready:
            paste('GET_READY.png', 93 if layout.startswith('1P') else 1432, 525)
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    def test_all_options_both_sides_and_graph_positions_wait_for_ready_disappearance(self):
        for layout in ANCHOR_EXPECTED:
            side = layout[:2]
            for option in ('REGULAR', 'MIRROR', 'RANDOM', 'R-RANDOM', 'S-RANDOM'):
                with self.subTest(layout=layout, option=option):
                    self.recognizer.reset()
                    for _ in range(7):
                        self.assertIsNone(self.recognizer.observe(self.frame(layout, option), side))
                    self.assertEqual(self.recognizer.option, option)
                    for _ in range(3):
                        self.assertIsNone(self.recognizer.observe(self.frame(layout, option, ready=True), side))
                    for _ in range(2):
                        self.assertIsNone(self.recognizer.observe(self.frame(layout, option), side))
                    self.assertEqual(self.recognizer.observe(self.frame(layout, option), side), option)

    def test_missing_anchor_does_not_turn_unknown_into_regular(self):
        for ready in (False, True):
            for _ in range(7 if not ready else 3):
                self.recognizer.observe(self.frame('2P_GRAPH_RIGHT', ready=ready, anchor=False), '2P')
        for _ in range(2):
            self.assertIsNone(self.recognizer.observe(self.frame('2P_GRAPH_RIGHT', anchor=False), '2P'))
        self.assertEqual(self.recognizer.observe(self.frame('2P_GRAPH_RIGHT', anchor=False), '2P'), 'UNKNOWN')
        self.assertIsNone(self.recognizer.option)

    def test_single_ready_flash_and_single_disappearance_do_not_start(self):
        plain = self.frame('2P_GRAPH_RIGHT')
        for _ in range(7):
            self.recognizer.observe(plain, '2P')
        ready = self.frame('2P_GRAPH_RIGHT', ready=True)
        self.recognizer.observe(ready, '2P')
        for _ in range(3):
            self.assertIsNone(self.recognizer.observe(plain, '2P'))
        self.assertFalse(self.recognizer.visible)
        for _ in range(3):
            self.recognizer.observe(ready, '2P')
        self.recognizer.observe(plain, '2P')
        self.recognizer.observe(ready, '2P')
        for _ in range(2):
            self.assertIsNone(self.recognizer.observe(plain, '2P'))
        self.assertEqual(self.recognizer.observe(plain, '2P'), 'REGULAR')

    def analysis(self):
        analysis = RandomLaneAnalysis(True, self.root/'charts.sqlite3', self.root/'state.js',
                                      template_folder=str(self.folder))
        analysis.start_play(title='TITANS RETURN', style='sp', difficulty='LEGGENDARIA',
                            level=12, play_mode='sp_2p_r')
        return analysis

    def test_preplay_17_and_35_never_reach_recorder(self):
        analysis = self.analysis()
        detector = analysis.detectors['2P']
        detector.detect = Mock(return_value=(1, [1, 3, 5, 7]))
        for _ in range(7):
            analysis.process_frame(self.frame('2P_GRAPH_RIGHT'))
        self.assertIsNone(analysis.recorder)
        for _ in range(3):
            analysis.process_frame(self.frame('2P_GRAPH_RIGHT', ready=True))
        for _ in range(2):
            analysis.process_frame(self.frame('2P_GRAPH_RIGHT'))
        detector.detect.assert_not_called()
        analysis.process_frame(self.frame('2P_GRAPH_RIGHT'))
        self.assertEqual(analysis.recorder.events[0]['event_lanes'], [1, 3, 5, 7])
        self.assertEqual(len(analysis.recorder.events), 1)

    def test_mirror_from_template_is_used_without_app_option_state(self):
        analysis = self.analysis()
        analysis.detectors['2P'].detect = Mock(return_value=(1, [7]))
        for i, ready in enumerate((False, True, False)):
            for _ in range(7 if i == 0 else 3):
                analysis.process_frame(self.frame('2P_GRAPH_RIGHT', 'MIRROR', ready))
        self.assertTrue(analysis.record_mirror)
        self.assertEqual(analysis.recorder.events[0]['event_lanes'], [1])

    def test_missing_and_corrupt_files_disable_recording(self):
        for filename in PlayStartRecognizer.REQUIRED_FILES:
            path = self.folder / filename
            original = path.read_bytes()
            path.unlink()
            analysis = self.analysis()
            self.assertEqual(analysis._last_state['phase'], 'unavailable')
            self.assertIsNone(analysis.mode)
            path.write_bytes(b'not an image')
            analysis.set_template_folder(str(self.folder))
            self.assertIsNotNone(analysis.template_error)
            path.write_bytes(original)
        analysis.set_template_folder(str(self.folder))
        self.assertIsNone(analysis.template_error)

    def test_folder_setting_round_trip(self):
        config = Config(str(self.root/'config.json'))
        self.assertEqual(config.random_lane_template_folder, '')
        config.random_lane_template_folder = str(self.folder)
        config.save_config()
        self.assertEqual(Config(config.config_file).random_lane_template_folder, str(self.folder))


class TemplateSettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_folder_browse_save_reload_and_capture_control_state_in_both_languages(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QFileDialog, QScrollArea
        from src.config_dialog import ConfigDialog
        for language in ('ja', 'en'):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                config = Config(str(Path(directory)/'config.json'))
                config.language = language
                config.capture_method = 'spout'
                config.enable_random_lane_analysis = True
                dialog = ConfigDialog(config)
                self.addCleanup(dialog.deleteLater)
                edit = dialog.random_lane_template_folder_edit
                self.assertTrue(edit.isEnabled())
                with patch.object(QFileDialog, 'getExistingDirectory', return_value='C:/画像/templates'):
                    dialog.random_lane_template_browse_button.click()
                self.assertEqual(edit.text(), 'C:/画像/templates')
                self.assertTrue(dialog.findChildren(QScrollArea))
                dialog.accept()
                saved = Config(config.config_file)
                self.assertEqual(saved.random_lane_template_folder, 'C:/画像/templates')
                reopened = ConfigDialog(saved)
                self.addCleanup(reopened.deleteLater)
                self.assertEqual(reopened.random_lane_template_folder_edit.text(), 'C:/画像/templates')
                reopened.enable_random_lane_analysis_check.setChecked(False)
                self.assertFalse(reopened.random_lane_template_folder_edit.isEnabled())
                reopened.capture_method_direct_legacy_radio.click()
                self.assertFalse(reopened.random_lane_template_browse_button.isEnabled())

    def test_random_settings_tab_and_band_edit_lock_keep_saved_values(self):
        from PySide6.QtWidgets import QTabWidget
        from src.config_dialog import ConfigDialog
        for language, basic_label, random_label in (
            ('ja', '基本設定', 'RANDOMレーン認識'),
            ('en', 'Basic Settings', 'RANDOM Lane Recognition'),
        ):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                config = Config(str(Path(directory)/'config.json'))
                config.language = language
                config.capture_method = 'spout'
                config.enable_random_lane_analysis = True
                config.random_lane_detection_bands = {'1P': [55, 75], '2P': [60, 90]}
                dialog = ConfigDialog(config)
                self.addCleanup(dialog.deleteLater)
                tabs = dialog.findChild(QTabWidget)
                self.assertEqual(tabs.tabText(0), basic_label)
                self.assertEqual(tabs.tabText(1), dialog.ui.tab.additional)
                self.assertEqual(tabs.tabText(2), random_label)
                basic = tabs.widget(0).widget()
                random = tabs.widget(2).widget()
                self.assertTrue(basic.isAncestorOf(dialog.spout_sender_edit))
                self.assertFalse(basic.isAncestorOf(dialog.enable_random_lane_analysis_check))
                for control in (dialog.enable_random_lane_analysis_check,
                                dialog.random_lane_template_folder_edit,
                                dialog.random_lane_band_edit_check):
                    self.assertTrue(random.isAncestorOf(control))
                controls = [control for row in dialog.random_lane_band_controls.values() for control in row]
                self.assertTrue(all(random.isAncestorOf(control) for control in controls))
                self.assertTrue(all(not control.isEnabled() for control in controls))
                top, height = dialog.random_lane_band_controls['2P']
                self.assertEqual((top.value(), height.value()), (60, 30))
                dialog.random_lane_band_edit_check.setChecked(True)
                self.assertTrue(all(control.isEnabled() for control in controls))
                height.setValue(40)
                dialog.random_lane_band_edit_check.setChecked(False)
                self.assertTrue(all(not control.isEnabled() for control in controls))
                dialog.accept()
                saved = Config(config.config_file)
                self.assertEqual(saved.random_lane_detection_bands, {'1P': [55, 75], '2P': [60, 100]})
                reopened = ConfigDialog(saved)
                self.addCleanup(reopened.deleteLater)
                self.assertFalse(reopened.random_lane_band_edit_check.isChecked())
                self.assertFalse(reopened.random_lane_band_controls['2P'][1].isEnabled())
                self.assertEqual(reopened.random_lane_band_controls['2P'][1].value(), 40)
                reopened.random_lane_band_edit_check.setChecked(True)
                reopened.enable_random_lane_analysis_check.setChecked(False)
                self.assertFalse(reopened.random_lane_band_edit_check.isEnabled())
                self.assertFalse(reopened.random_lane_band_controls['2P'][1].isEnabled())

    def test_additional_and_image_settings_move_without_changing_saved_values(self):
        from PySide6.QtWidgets import QTabWidget
        from src.config_dialog import ConfigDialog
        for language in ('ja', 'en'):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                config = Config(str(Path(directory)/'config.json'))
                config.language = language
                config.autoload_offset = 4
                dialog = ConfigDialog(config)
                self.addCleanup(dialog.deleteLater)
                tabs = dialog.findChild(QTabWidget)
                basic = tabs.widget(0).widget()
                additional = tabs.widget(1).widget()
                image_index = next(i for i in range(tabs.count()) if tabs.tabText(i) == dialog.ui.tab.image_save)
                image = tabs.widget(image_index).widget()
                self.assertTrue(basic.isAncestorOf(dialog.keep_on_top_check))
                for control in (dialog.enable_autotweet_check, dialog.enable_judge_check,
                                dialog.enable_folder_updates_check, dialog.websocket_data_port,
                                dialog.autoload_offset_spin, dialog.autoload_offset_help_label,
                                dialog.mobile_score_server_enabled_check,
                                dialog.mobile_score_server_port_edit, dialog.mobile_score_server_interface_combo):
                    self.assertTrue(additional.isAncestorOf(control))
                self.assertTrue(image.isAncestorOf(dialog.image_save_path_edit))
                self.assertIs(dialog.autoload_offset_spin.parentWidget(), dialog.websocket_data_port.parentWidget())
                self.assertEqual(dialog.autoload_offset_spin.suffix(), '')
                self.assertEqual(dialog.autoload_offset_spin.text(), '4')
                self.assertIn('20:00', dialog.autoload_offset_help_label.text())
                self.assertIn('16:00', dialog.autoload_offset_spin.toolTip())
                dialog.image_save_path_edit.setText('C:/results')
                dialog.autoload_offset_spin.setValue(5)
                dialog.websocket_data_port.setText('8768')
                dialog.enable_autotweet_check.setChecked(True)
                dialog.mobile_score_server_enabled_check.setChecked(True)
                dialog.mobile_score_server_port_edit.setText('8788')
                dialog.accept()
                saved = Config(config.config_file)
                self.assertEqual(saved.image_save_path, 'C:/results')
                self.assertEqual(saved.autoload_offset, 5)
                self.assertEqual(saved.websocket_data_port, 8768)
                self.assertTrue(saved.enable_autotweet)
                self.assertTrue(saved.mobile_score_server_enabled)
                self.assertEqual(saved.mobile_score_server_port, 8788)


if __name__ == '__main__':
    unittest.main()
