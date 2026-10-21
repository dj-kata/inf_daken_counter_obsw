"""Run: .codex-venv/bin/python -B -m unittest misc.test_random_lane_analysis."""

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
            for i in range(7)
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

    def test_r_random_uses_recorded_chart_and_confirms_first_unique_mapping(self):
        self.save_chart()
        self.start('R-RANDOM')
        self.assertEqual(self.analysis.mode, 'analyze')
        self.assertIn('R-RANDOM', self.analysis._last_state['message'])
        permutation = (3, 4, 5, 6, 7, 1, 2)
        for event in self.events:
            self.analysis.analyzer.add([permutation[n - 1] for n in event['event_lanes']])
            if self.analysis.analyzer.layout:
                break
        self.assertEqual(self.analysis.analyzer.pair_index, 6)
        self.assertEqual(self.analysis.analyzer.layout, lane._layout_text(permutation))

    def test_contradiction_eliminates_candidates_immediately(self):
        analyzer = lane.RandomMappingAnalyzer(self.events)
        analyzer.add([1, 2])
        self.assertTrue(analyzer.failed)
        self.assertEqual(analyzer.candidates, [])
        self.assertIsNone(analyzer.layout)

    def test_exhausted_ambiguous_chart_fails(self):
        analyzer = lane.RandomMappingAnalyzer([{'event_lanes': [1]}])
        analyzer.add([2])
        self.assertFalse(analyzer.failed)
        analyzer.add([3])
        self.assertTrue(analyzer.failed)
        self.assertIsNone(analyzer.layout)

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
        image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        x, y, _, _ = detector.roi
        image[y + 700:y + 720, x + 10:x + 40] = 255
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

    def test_mirror_registration_can_analyze_random_on_either_side(self):
        for side, arrange in (('1P', 'RANDOM'), ('2P', 'R-RANDOM')):
            with self.subTest(side=side, arrange=arrange):
                self.start('MIRROR', side)
                if self.analysis.mode == 'record':
                    events = iter([[8 - n] for n in lane.LANES])
                    self.analysis.detectors[side].detect = lambda image: (1, next(events))
                    for _ in lane.LANES:
                        self.analysis.process_frame(np.zeros((1, 1, 3), dtype=np.uint8))
                    self.assertEqual(self.analysis._last_state['phase'], 'registered')
                self.assertEqual(self.analysis.get_result_lane_layout(), lane.MIRROR_LAYOUT)
                saved = self.analysis._load_chart(self.analysis.chart_key)
                self.assertEqual([e['event_lanes'] for e in saved], [[n] for n in lane.LANES])
                self.analysis.end_play()
                self.start(arrange, side)
                permutation = (4, 1, 7, 2, 6, 3, 5)
                events = iter([[n] for n in permutation])
                self.analysis.detectors[side].detect = lambda image: (1, next(events))
                for _ in lane.LANES:
                    self.analysis.process_frame(np.zeros((1, 1, 3), dtype=np.uint8))
                self.assertEqual(self.analysis._last_state['phase'], 'confirmed')
                self.analysis.end_play()
                self.assertEqual(self.analysis.get_result_lane_layout(), lane._layout_text(permutation))

    def test_events_use_immediate_rising_edges_without_frame_merging(self):
        detector = lane.NoteDetector(lane.DEFAULT_ROI_1P)
        black = np.zeros((1080, 1920, 3), dtype=np.uint8)
        first = black.copy()
        first[139:159, 180:205] = 255
        second = first.copy()
        second[139:159, 230:250] = 255
        self.assertEqual(detector.detect(first), (1, [1]))
        self.assertEqual(detector.detect(second), (2, [2]))
        self.assertEqual(detector.detect(second), (None, []))
        self.assertEqual(detector.detect(black), (None, []))
        self.assertEqual(detector.detect(first), (3, [1]))
        detector.reset()
        self.assertEqual(detector.detect(first), (1, [1]))

    def test_recording_stops_when_identity_is_unique_without_minimum_count(self):
        recorder = lane.NormalChartRecorder()
        self.assertFalse(recorder.add(lane.LANES))
        for n in lane.LANES[:-2]:
            self.assertFalse(recorder.add([n]))
        self.assertTrue(recorder.add([6]))
        self.assertEqual(len(recorder.events), 7)

    def test_old_event_sequences_are_preserved_but_require_reregistration(self):
        import sqlite3
        self.save_chart()
        key = self.analysis.chart_key
        with sqlite3.connect(self.analysis.db_path) as conn:
            conn.execute('UPDATE normal_charts SET data_version=4 WHERE chart_key=?', (key,))
        self.assertIsNone(self.analysis._load_chart(key))
        self.start('MIRROR')
        self.assertEqual(self.analysis.mode, 'record')
        with sqlite3.connect(self.analysis.db_path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM normal_charts').fetchone()[0], 1)

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
                actual = ours.detect(rgb)
                expected = upstream.detect_lanes(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                self.assertEqual(ours.last_lane_state, expected)
                self.assertEqual(actual, upstream.register_events(expected))


if __name__ == '__main__':
    unittest.main()
