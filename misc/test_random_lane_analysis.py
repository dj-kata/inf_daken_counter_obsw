"""Run with the existing environment: python -B -m unittest misc.test_random_lane_analysis."""

import ast
import itertools
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import cv2
import numpy as np

from src.config import Config
from src import random_lane_analysis as lane


class RandomLaneIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.analysis = lane.RandomLaneAnalysis(
            enabled=True, db_path=root / 'charts.sqlite3', state_path=root / 'state.js'
        )
        self.events = [
            {'event_no': i + 1, 'event_lanes': [i % 7 + 1]}
            for i in range(lane.MIN_NORMAL_EVENTS)
        ]

    def start(self, arrange='REGULAR', side='1P'):
        self.analysis.start_play(
            title='test song', style='sp', difficulty='ANOTHER', level=12,
            option=SimpleNamespace(valid=True, special=False, arrange=arrange),
            play_mode=f'sp_{side.lower()}',
        )

    def save_chart(self):
        self.start()
        self.analysis._save_chart(
            self.analysis.chart_key, self.analysis.chart_meta, self.events
        )

    def test_r_random_uses_recorded_chart_and_keeps_noise_tolerance(self):
        self.save_chart()
        self.start('R-RANDOM')
        self.assertEqual(self.analysis.mode, 'analyze')
        self.assertIn('R-RANDOM', self.analysis._last_state['message'])
        permutation = (3, 4, 5, 6, 7, 1, 2)
        for i, event in enumerate(self.events):
            lanes = [permutation[n - 1] for n in event['event_lanes']]
            if i in (2, 11):
                lanes = [1, 2]  # Misdetection must not eliminate the true mapping.
            self.analysis.analyzer.add(lanes)
            if self.analysis.analyzer.layout:
                break
        self.assertGreaterEqual(self.analysis.analyzer.pair_index, lane.MIN_ANALYSIS_EVENTS)
        self.assertEqual(self.analysis.analyzer.layout, lane._layout_text(permutation))

    def test_band_change_isolates_charts_and_restores_defaults(self):
        self.save_chart()
        original_key = self.analysis.chart_key
        self.analysis.set_detection_bands({'1P': [55, 95]})
        self.assertIsNone(self.analysis.mode)
        self.start('RANDOM')
        self.assertEqual(self.analysis._last_state['phase'], 'needs_normal')
        self.assertNotEqual(self.analysis.chart_key, original_key)
        self.analysis.set_detection_bands()
        self.start('RANDOM')
        self.assertEqual(self.analysis.chart_key, original_key)
        self.assertEqual(self.analysis.mode, 'analyze')

    def test_unchanged_bands_do_not_cancel_a_play(self):
        self.start()
        recorder = self.analysis.recorder
        self.analysis.set_detection_bands({'1P': [55, 75], '2P': [55, 75]})
        self.assertIs(self.analysis.recorder, recorder)

    def test_bands_are_independent_and_roi_expands(self):
        self.analysis.set_detection_bands({'2P': [696, 996]})
        self.assertEqual(self.analysis.detectors['1P'].band, lane.DEFAULT_BAND)
        detector = self.analysis.detectors['2P']
        self.assertEqual(detector.roi[3], 996)
        detector.armed = True
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        x, y, _, _ = detector.roi
        image[y + 700:y + 720, x + 10:x + 40] = 255
        detector.detect(image)
        self.assertEqual(detector.detect(image), (1, [1]))

    def test_invalid_band_update_is_atomic(self):
        with self.assertRaises(ValueError):
            self.analysis.set_detection_bands({'1P': [55, 100], '2P': [900, 1000]})
        self.assertEqual(self.analysis.detectors['1P'].band, lane.DEFAULT_BAND)

    def test_mirror_recording_and_result_persistence(self):
        self.start('MIRROR')
        self.assertTrue(self.analysis.record_mirror)
        self.analysis.detectors['1P'].detect = lambda image: (1, [7])
        self.analysis.process_frame(np.zeros((1, 1, 3), dtype=np.uint8))
        self.assertEqual(self.analysis.recorder.events[0]['event_lanes'], [1])
        self.analysis.end_play()
        self.assertEqual(self.analysis.get_result_lane_layout(), lane.MIRROR_LAYOUT)
        self.assertIsNone(self.analysis._load_chart('test song\x1fsp\x1fANOTHER'))

    def test_start_animation_is_excluded_before_note_events(self):
        from unittest.mock import patch
        detector = lane.NoteDetector(lane.DEFAULT_ROI_1P)
        black = np.zeros((1080, 1920, 3), dtype=np.uint8)
        white = black.copy()
        white[139:159, 165:508] = 255
        with patch.object(lane.time, 'monotonic', return_value=0.0) as clock:
            detector.reset()
            for when in (0.1, 0.8):
                clock.return_value = when
                self.assertEqual(detector.detect(white), (None, []))
                detector.detect(black)
            for _ in range(lane.ARM_CLEAR_FRAMES):
                detector.detect(black)
            self.assertTrue(detector.armed)
            self.assertEqual(detector.event_counter, 0)
            detector.detect(white)
            self.assertEqual(detector.detect(black), (1, list(lane.LANES)))

    def test_recording_requires_minimum_sample_and_unique_identity(self):
        recorder = lane.NormalChartRecorder()
        for _ in range(lane.MIN_NORMAL_EVENTS):
            self.assertFalse(recorder.add(lane.LANES))
        for n in lane.LANES[:-2]:
            self.assertFalse(recorder.add([n]))
        self.assertTrue(recorder.add([6]))

    def test_config_round_trip_and_invalid_side_fallback(self):
        path = Path(self.temp.name) / 'config.json'
        config = Config(str(path))
        config.random_lane_detection_bands = {'1P': [55, 95], '2P': [900, 996]}
        config.save_config()
        self.assertEqual(Config(str(path)).random_lane_detection_bands,
                         config.random_lane_detection_bands)
        self.assertEqual(Config._load_random_lane_detection_bands(
            {'1P': [3, 20], '2P': [900, 1000]}), {'1P': [3, 20], '2P': [55, 75]})
        for invalid in (None, [], {'1P': ['55', '75']}, {'1P': [True, 20]},
                        {'1P': [0, 301]}, {'1P': [55, 55]}):
            self.assertEqual(Config._load_random_lane_detection_bands(invalid)['1P'], [55, 75])

    def test_note_masks_match_updated_upstream_for_both_sides(self):
        source = Path('RandomLaneAnalysis_OCR/iidx_main.py')
        if not source.exists():
            self.skipTest('Optional upstream checkout is absent')
        # Load just the pure detector, without starting upstream Windows/Spout/UI code.
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        detector_class = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                              and n.name == 'RealtimeV5NoteDetector')
        names = {'LANE_BOUNDARIES_RATIO', 'MIN_ACTIVE_PIXELS', 'MIN_ACTIVE_RATIO',
                 'WHITE_LANE_DETECTION_MARGIN_RATIO', 'BLACK_LANE_DETECTION_MARGIN_RATIO',
                 'MORPH_KERNEL'}
        names.update(f'{color}_HSV_{bound}' for color in ('BLUE', 'WHITE', 'ORANGE', 'PURPLE')
                     for bound in ('LOW', 'HIGH'))
        constants = [n for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
        scope = {'cv2': cv2}
        exec(compile(ast.Module(body=constants + [detector_class], type_ignores=[]),
                     str(source), 'exec'), scope)
        rng = np.random.default_rng(20261020)
        for roi, band in itertools.product((lane.DEFAULT_ROI_1P, lane.DEFAULT_ROI_2P),
                                           ((55, 75), (55, 95))):
            roi = (*roi[:3], max(roi[3], band[1]))
            ours = lane.NoteDetector(roi, band)
            ours.armed = True
            upstream = scope['RealtimeV5NoteDetector'](roi, band)
            for _ in range(10):
                rgb = np.zeros((1080, 1920, 3), dtype=np.uint8)
                x, y, w, h = roi
                for index in range(7):
                    if rng.random() < 0.5:
                        left = round(lane.LANE_BOUNDARIES_RATIO[index] * w) + 10
                        color = ((255, 255, 255), (0, 100, 255), (255, 100, 0),
                                 (190, 0, 255))[index % 4]
                        rgb[y + band[0]:y + band[0] + 5, x + left:x + left + 20] = color
                ours.detect(rgb)
                expected = upstream.detect_lanes(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                self.assertEqual(ours.last_lane_state, expected)


if __name__ == '__main__':
    unittest.main()
