"""Run: QT_QPA_PLATFORM=offscreen .codex-venv/bin/python -B -m unittest misc.test_voice_guidance"""

import ast
import json
import queue
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.config import Config
from src.classes import clear_lamp, config_autosave_image
from src.voice_guidance import (VOICE_DEFAULTS, VOICE_TEST_MESSAGES, VoiceGuidance,
                                chart_announcements, personal_best_announcements,
                                start_voice_preview, synthesize, OBS_CONTROL_WARNING, SPOUT_WARNING)


def personal_best_result(**changes):
    values = dict(lamp=clear_lamp.hard, pre_lamp=clear_lamp.easy,
                  score=2000, pre_score=1900, bp=20, pre_bp=30, dead=False)
    values.update(changes)
    return SimpleNamespace(**values)


class PersonalBestAnnouncementTests(unittest.TestCase):
    def test_each_improved_lamp_and_first_clear(self):
        for lamp, text in (
            (clear_lamp.easy, '初イージー'), (clear_lamp.clear, '初ノマゲ'),
            (clear_lamp.hard, '初ハード'), (clear_lamp.exh, '初エクハ'),
            (clear_lamp.fc, '初フルコン'),
        ):
            for previous in (None, clear_lamp.noplay, clear_lamp(lamp.value - 1)):
                with self.subTest(lamp=lamp, previous=previous):
                    result = personal_best_result(lamp=lamp, pre_lamp=previous,
                                                  pre_score=None, pre_bp=None)
                    self.assertEqual(personal_best_announcements(result), [text])

    def test_all_updates_are_announced_in_order(self):
        self.assertEqual(personal_best_announcements(personal_best_result()),
                         ['初ハード', 'スコア更新', 'ミスカウント更新'])

    def test_equal_or_worse_results_are_silent(self):
        for lamp in (clear_lamp.failed, clear_lamp.assist, clear_lamp.hard):
            result = personal_best_result(lamp=lamp, pre_lamp=clear_lamp.hard,
                                          score=1900, bp=30)
            self.assertEqual(personal_best_announcements(result), [])
        self.assertEqual(personal_best_announcements(personal_best_result(
            lamp=clear_lamp.failed, score=1800, bp=40)), [])

    def test_no_score_or_bp_update_for_first_play_or_unknown_values(self):
        for score, bp in ((None, None), (0, 99999999)):
            self.assertEqual(personal_best_announcements(personal_best_result(
                pre_lamp=clear_lamp.noplay, pre_score=score, pre_bp=bp)), ['初ハード'])
        self.assertEqual(personal_best_announcements(personal_best_result(
            lamp=None, score=None, bp=None)), [])

    def test_score_and_misscount_updates_are_independent(self):
        for changes, expected in (
            ({'bp': 30}, ['スコア更新']),
            ({'score': 1900}, ['ミスカウント更新']),
            ({'bp': 0, 'score': 1900}, ['ミスカウント更新']),
            ({'dead': True}, ['スコア更新']),
        ):
            result = personal_best_result(lamp=clear_lamp.failed, **changes)
            self.assertEqual(personal_best_announcements(result), expected)


class PersonalBestResultIntegrationTests(unittest.TestCase):
    def setUp(self):
        # Exercise the real result handler without loading Windows capture APIs.
        tree = ast.parse(Path('notes_counter.pyw').read_text(encoding='utf-8'))
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'MainWindow')
        method = next(node for node in window.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'process_result_mode')
        namespace = dict(clear_lamp=clear_lamp, config_autosave_image=config_autosave_image,
                         get_title_with_chart=Mock(), logger=Mock())
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'notes_counter.pyw', 'exec'), namespace)
        self.process = namespace['process_result_mode']
        self.result = personal_best_result(
            chart_id='test', title='test', play_style=None, difficulty=None, playspeed=None,
            option=SimpleNamespace(valid=True, battle=False))
        self.window = Mock()
        self.window._result_screen_handled = False
        self.window.result_pre = self.result
        self.window.score_viewer = None
        self.window.result_database.add.return_value = True
        self.window.screen_reader.read_result_screen.return_value = SimpleNamespace(result=self.result)
        self.window.config.autosave_image_mode = config_autosave_image.invalid
        self.window._set_result_screen_handled.side_effect = lambda value: setattr(
            self.window, '_result_screen_handled', value)

    def test_accepted_result_is_announced_once_even_when_screen_is_read_again(self):
        self.process(self.window)
        self.process(self.window)
        self.window.result_database.save.assert_called_once()
        self.window.voice_guidance.personal_best.assert_called_once_with(self.result)
        self.window.voice_guidance.announce.assert_called_once_with('result_saved', 'リザルトを保存しました')

    def test_rejected_or_unstable_result_is_not_announced(self):
        self.window.result_database.add.return_value = False
        self.process(self.window)
        self.window.voice_guidance.personal_best.assert_not_called()
        self.window.voice_guidance.announce.assert_not_called()
        self.window._result_screen_handled = False
        self.window.result_pre = None
        self.process(self.window)
        self.window.voice_guidance.personal_best.assert_not_called()
        self.window.voice_guidance.announce.assert_not_called()

    def test_save_failure_does_not_announce_success(self):
        self.window.result_database.save.side_effect = OSError('save failed')
        self.process(self.window)
        self.window.voice_guidance.announce.assert_not_called()

    def test_result_without_personal_best_update_still_announces_saved(self):
        self.result.lamp = self.result.pre_lamp
        self.result.score = self.result.pre_score
        self.result.bp = self.result.pre_bp
        self.assertEqual(personal_best_announcements(self.result), [])
        self.process(self.window)
        self.window.voice_guidance.announce.assert_called_once_with('result_saved', 'リザルトを保存しました')


class OBSErrorIntegrationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path('notes_counter.pyw').read_text(encoding='utf-8'))
        window = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == 'MainWindow')
        methods = [node for node in window.body if isinstance(node, ast.FunctionDef)
                   and node.name in ('_update_voice_obs_errors', 'check_obs_configuration')]
        self.namespace = dict(QMessageBox=Mock(), logger=Mock())
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'notes_counter.pyw', 'exec'), self.namespace)
        self.window = Mock()
        self.window._closing = False
        self.window._voice_obs_startup_checked = True

    def test_spout_is_checked_even_with_random_analysis_and_websocket_disabled(self):
        manager = self.window.obs_manager
        manager.is_spout_capture.return_value = True
        manager.is_obs_control_enabled.return_value = False
        manager.is_connected = False
        manager.is_capture_ready.return_value = False
        self.namespace['_update_voice_obs_errors'](self.window)
        self.window.voice_guidance.obs_status.assert_called_once_with(
            startup=False, obs_control_enabled=False, obs_connected=False,
            spout_enabled=True, spout_connected=False)

    def test_startup_check_runs_before_websocket_early_return(self):
        self.window._voice_obs_startup_checked = False
        self.window.obs_manager.uses_obs_websocket.return_value = False
        self.namespace['check_obs_configuration'](self.window)
        self.assertTrue(self.window._voice_obs_startup_checked)
        self.window._update_voice_obs_errors.assert_called_once_with(startup=True)

    def test_no_announcements_before_startup_check_or_during_shutdown(self):
        self.window._voice_obs_startup_checked = False
        self.namespace['_update_voice_obs_errors'](self.window)
        self.window._voice_obs_startup_checked = True
        self.window._closing = True
        self.namespace['_update_voice_obs_errors'](self.window)
        self.window.voice_guidance.obs_status.assert_not_called()


class ChartAnnouncementTests(unittest.TestCase):
    def test_split_and_reverse_for_both_sides(self):
        for layout, side, expected in (
            ('2461357', '1P', 'ガチ割れ'), ('1357246', '1P', '逆割れ'),
            ('1357246', '2P', 'ガチ割れ'), ('2461357', '2P', '逆割れ'),
        ):
            with self.subTest(layout=layout, side=side):
                self.assertEqual(chart_announcements(layout, side)[0], expected)

    def test_requested_examples(self):
        self.assertEqual(chart_announcements('2716354', '1P'), ['にーさんごーろく', '3バス'])
        self.assertEqual(chart_announcements('6175423', '1P'), ['2バス'])

    def test_partial_facts_and_unknown_sides(self):
        self.assertEqual(chart_announcements('BWWBWWB', '1P'), ['にーさんごーろく'])
        self.assertEqual(chart_announcements('BBBWWWW', '2P'), ['逆割れ'])
        self.assertEqual(chart_announcements('???1???', '1P'), ['4バス'])
        for layout, side in (('???????', '1P'), ('', '1P'), ('1234567', None)):
            self.assertEqual(chart_announcements(layout, side), [])


class VoiceWorkerTests(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(**VOICE_DEFAULTS)
        self.config.enable_voice_guidance = True
        self.synthesis = patch('src.voice_guidance.synthesize', return_value=b'wav').start()
        self.play = patch('src.voice_guidance.play_wav').start()
        self.addCleanup(patch.stopall)
        self.voice = VoiceGuidance(self.config)
        self.addCleanup(self.stop)

    def stop(self):
        self.voice.shutdown()
        self.voice._worker.join(timeout=3)
        self.assertTrue(self.voice.is_finished())

    def flush(self):
        self.voice._queue.join()

    def test_connection_probe_detects_failure_then_recovers_without_announcements(self):
        self.config.voicevox_url = 'http://localhost:50022/'
        for category in ('startup', 'lane_status', 'missing_chart', 'chart_info', 'personal_best', 'result_saved', 'errors', 'shutdown'):
            setattr(self.config, 'voice_' + category, False)
        self.voice.set_config(self.config)
        response = Mock()
        response.read.return_value = b'"0.26.0"'
        with patch('src.voice_guidance.urlopen') as request, \
                patch('src.voice_guidance.time.monotonic', return_value=0) as now:
            request.side_effect = OSError('not running')
            self.voice.poll_connection()
            self.voice._connection_thread.join(3)
            self.assertFalse(self.voice.poll_connection())
            request.assert_called_once_with('http://localhost:50022/version', timeout=2)
            request.side_effect = None
            request.return_value.__enter__.return_value = response
            now.return_value = 5
            self.voice.poll_connection()
            self.voice._connection_thread.join(3)
            self.assertTrue(self.voice.poll_connection())
            self.assertEqual(request.call_count, 2)
        self.synthesis.assert_not_called()

    def test_disabled_guidance_does_not_probe_or_report_unavailable(self):
        self.config.enable_voice_guidance = False
        self.voice.set_config(self.config)
        with patch('src.voice_guidance.urlopen') as request:
            self.assertIsNone(self.voice.poll_connection())
            request.assert_not_called()
        self.voice.shutdown()
        self.assertIsNone(self.voice.poll_connection())

    def test_inflight_probe_does_not_block_or_overwrite_new_settings(self):
        entered = threading.Event()
        release = threading.Event()

        def slow_request(*args, **kwargs):
            entered.set()
            release.wait(3)
            raise OSError('old URL unavailable')

        with patch('src.voice_guidance.urlopen', side_effect=slow_request) as request:
            self.voice.poll_connection()
            self.assertTrue(entered.wait(3))
            self.assertIsNone(self.voice.poll_connection())
            request.assert_called_once()
            self.config.enable_voice_guidance = False
            self.voice.set_config(self.config)
            release.set()
            self.voice._connection_thread.join(3)
        self.assertIsNone(self.voice.poll_connection())
        self.assertIsNone(self.voice._connection_available)

    def test_master_and_category_switches(self):
        self.config.enable_voice_guidance = False
        self.voice.set_config(self.config)
        self.voice.announce('startup', 'start')
        self.flush()
        self.synthesis.assert_not_called()
        self.config.enable_voice_guidance = True
        self.config.voice_startup = False
        self.voice.set_config(self.config)
        self.voice.announce('startup', 'start')
        self.flush()
        self.synthesis.assert_not_called()
        self.voice.announce('lane_status', 'status')
        self.flush()
        self.synthesis.assert_called_once_with('status', 'http://127.0.0.1:50021', 1)

    def test_lane_messages_and_partial_deduplication_reset_next_play(self):
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'needs_normal'})
        self.voice.lane_state({'phase': 'recording'})
        self.voice.lane_state({'phase': 'partial', 'side': '1P', 'layout': 'BWWBWWB'})
        self.voice.lane_state({'phase': 'confirmed', 'side': '1P', 'layout': '2716354'})
        self.voice.lane_state({'phase': 'confirmed', 'side': '1P', 'layout': '2716354'})
        self.flush()
        self.assertEqual([call.args[0] for call in self.synthesis.call_args_list], [
            '正規譜面が登録されていません。レーン表示をスキップします。', '正規譜面を取得中', 'にーさんごーろく', '3バス',
        ])
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'confirmed', 'side': '1P', 'layout': '2716354'})
        self.flush()
        self.assertEqual(self.play.call_count, 6)
        self.assertEqual(self.synthesis.call_count, 4)  # WAVs are reused.

    def test_registration_complete_uses_lane_category_once_per_play(self):
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'registered'})
        self.voice.lane_state({'phase': 'registered'})
        self.flush()
        self.synthesis.assert_called_once_with('正規譜面を登録完了しました', 'http://127.0.0.1:50021', 1)
        self.config.voice_lane_status = False
        self.voice.set_config(self.config)
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'registered'})
        self.flush()
        self.assertEqual(self.play.call_count, 1)

    def test_missing_chart_switch_is_independent_of_lane_status(self):
        self.config.voice_missing_chart = False
        self.voice.set_config(self.config)
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'needs_normal'})
        self.voice.lane_state({'phase': 'recording'})
        self.flush()
        self.synthesis.assert_called_once_with('正規譜面を取得中', 'http://127.0.0.1:50021', 1)
        self.synthesis.reset_mock()
        self.config.voice_missing_chart = True
        self.config.voice_lane_status = False
        self.voice.set_config(self.config)
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'recording'})
        self.voice.lane_state({'phase': 'registered'})
        self.voice.lane_state({'phase': 'needs_normal'})
        self.flush()
        self.synthesis.assert_called_once_with(
            '正規譜面が登録されていません。レーン表示をスキップします。',
            'http://127.0.0.1:50021', 1)

    def test_obs_errors_are_independent_and_not_repeated_until_spout_recovers(self):
        status = dict(startup=True, obs_control_enabled=True, obs_connected=False,
                      spout_enabled=True, spout_connected=False)
        self.voice.obs_status(**status)
        status['startup'] = False
        self.voice.obs_status(**status)
        self.voice.obs_status(**status)
        self.flush()
        self.assertEqual([call.args[0] for call in self.synthesis.call_args_list],
                         [OBS_CONTROL_WARNING, SPOUT_WARNING])
        status.update(obs_connected=True, spout_connected=True)
        self.voice.obs_status(**status)
        status.update(obs_connected=False, spout_connected=False)
        self.voice.obs_status(**status)
        self.flush()
        self.assertEqual(self.play.call_count, 3)  # Spout can warn again; OBS control is startup-only.

    def test_spout_does_not_require_obs_websocket_or_lane_analysis(self):
        self.voice.obs_status(startup=True, obs_control_enabled=False, obs_connected=False,
                              spout_enabled=True, spout_connected=True)
        self.flush()
        self.synthesis.assert_not_called()
        self.voice.obs_status(startup=False, obs_control_enabled=False, obs_connected=False,
                              spout_enabled=True, spout_connected=False)
        self.flush()
        self.synthesis.assert_called_once_with(SPOUT_WARNING, 'http://127.0.0.1:50021', 1)

    def test_disabled_error_category_suppresses_obs_and_spout_announcements(self):
        self.config.voice_errors = False
        self.voice.set_config(self.config)
        status = dict(startup=True, obs_control_enabled=True, obs_connected=False,
                      spout_enabled=True, spout_connected=False)
        self.voice.obs_status(**status)
        self.flush()
        self.synthesis.assert_not_called()
        self.config.voice_errors = True
        self.voice.set_config(self.config)
        self.voice.obs_status(**status)
        self.flush()
        self.assertEqual(self.play.call_count, 2)

    def test_engine_failure_does_not_stop_later_announcements(self):
        self.synthesis.side_effect = [OSError('engine unavailable'), b'wav', b'wav']
        with patch('src.voice_guidance.logger') as logger:
            self.voice.announce('startup', 'start')
            self.voice.announce('chart_info', '2バス')
            self.flush()
            logger.exception.assert_called_once()
        self.play.assert_called_once_with(b'wav', '', 100, 0)

    def test_each_category_can_be_disabled_independently(self):
        for category in ('startup', 'lane_status', 'missing_chart', 'chart_info', 'personal_best', 'result_saved', 'errors', 'shutdown'):
            with self.subTest(category=category):
                setattr(self.config, 'voice_' + category, False)
                self.voice.set_config(self.config)
                self.voice.announce(category, category)
                self.flush()
                self.synthesis.assert_not_called()
                setattr(self.config, 'voice_' + category, True)

    def test_personal_best_category_queues_all_updates_and_can_be_disabled(self):
        self.voice.personal_best(personal_best_result())
        self.flush()
        self.assertEqual([call.args[0] for call in self.synthesis.call_args_list],
                         ['初ハード', 'スコア更新', 'ミスカウント更新'])
        self.synthesis.reset_mock()
        self.config.voice_personal_best = False
        self.voice.set_config(self.config)
        self.voice.personal_best(personal_best_result())
        self.flush()
        self.synthesis.assert_not_called()

    def test_selected_output_is_passed_to_playback(self):
        self.config.voice_output_device = 'headphones'
        self.config.voice_volume = 35
        self.config.voice_pan = -60
        self.voice.set_config(self.config)
        self.voice.announce('startup', 'start')
        self.flush()
        self.play.assert_called_once_with(b'wav', 'headphones', 35, -60)

    def test_chart_switch_suppresses_all_chart_details(self):
        self.config.voice_chart_info = False
        self.voice.set_config(self.config)
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'confirmed', 'side': '1P', 'layout': '2461357'})
        self.flush()
        self.synthesis.assert_not_called()
        self.voice.lane_state({'phase': 'preparing'})
        self.voice.lane_state({'phase': 'confirmed', 'side': '2P', 'layout': '2716354'})
        self.flush()
        self.synthesis.assert_not_called()

    def test_settings_change_discards_pending_audio_and_shutdown_is_last(self):
        entered = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)

        def slow_synthesis(*args):
            entered.set()
            self.assertTrue(release.wait(3))
            return b'old audio'

        self.synthesis.side_effect = slow_synthesis
        self.voice.announce('startup', 'start')
        self.assertTrue(entered.wait(3))
        self.voice.announce('chart_info', '2バス')
        self.voice.set_config(self.config)
        self.voice.shutdown()
        self.voice.shutdown()
        self.voice.announce('chart_info', '3バス')
        release.set()
        self.voice._worker.join(3)
        self.assertTrue(self.voice.is_finished())
        self.assertEqual([call.args[0] for call in self.synthesis.call_args_list], [
            'start', '打鍵カウンタを終了しました',
        ])
        self.play.assert_called_once()

    def test_shutdown_queued_at_idle_timeout_is_still_played(self):
        original_get = self.voice._queue.get
        first = True

        def get_with_shutdown(**kwargs):
            nonlocal first
            if first:
                first = False
                self.voice.shutdown()
                raise queue.Empty
            return original_get(**kwargs)

        with patch.object(self.voice._queue, 'get', side_effect=get_with_shutdown):
            self.voice._worker.join(3)
        self.assertTrue(self.voice.is_finished())
        self.synthesis.assert_called_once_with(
            '打鍵カウンタを終了しました', 'http://127.0.0.1:50021', 1,
        )
        self.play.assert_called_once()

    def test_http_api_contract(self):
        query = Mock()
        query.read.return_value = b'{"speedScale": 1.0}'
        audio = Mock()
        audio.read.return_value = b'wav'
        with patch('src.voice_guidance.urlopen') as request:
            request.return_value.__enter__.side_effect = [query, audio]
            self.assertEqual(synthesize('2バス', 'http://127.0.0.1:50021', 3), b'wav')
        first, second = request.call_args_list
        self.assertIn('/audio_query?', first.args[0].full_url)
        self.assertIn('speaker=3', first.args[0].full_url)
        self.assertEqual(first.args[0].method, 'POST')
        self.assertEqual(second.args[0].full_url, 'http://127.0.0.1:50021/synthesis?speaker=3')
        self.assertEqual(json.loads(second.args[0].data), {'speedScale': 1.0})


class VoiceSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / 'config.json')
        devices = patch('src.config_dialog.audio_output_devices', return_value=[
            ('speakers', 'Speakers'), ('headphones', 'Headphones'),
        ])
        devices.start()
        self.addCleanup(devices.stop)

    def test_defaults_for_new_and_existing_config_and_roundtrip(self):
        for existing in (False, True):
            if existing:
                Path(self.path).write_text('{}')
            config = Config(self.path)
            self.assertFalse(config.enable_voice_guidance)
            for category in ('startup', 'lane_status', 'missing_chart', 'chart_info', 'personal_best', 'result_saved', 'errors', 'shutdown'):
                self.assertTrue(getattr(config, 'voice_' + category))
        config.enable_voice_guidance = True
        config.voice_chart_info = False
        config.voice_missing_chart = False
        config.voice_personal_best = False
        config.voice_result_saved = False
        config.voice_errors = False
        config.voicevox_url = 'http://localhost:50022'
        config.voicevox_speaker_id = 8
        config.voice_output_device = 'headphones'
        config.voice_volume = 35
        config.voice_pan = -60
        config.save_config()
        saved = Config(self.path)
        for key in VOICE_DEFAULTS:
            self.assertEqual(getattr(saved, key), getattr(config, key))

    def test_dialog_controls_and_persistence_in_both_languages(self):
        from PySide6.QtWidgets import QApplication
        from src.config_dialog import ConfigDialog

        app = QApplication.instance() or QApplication([])
        for language in ('ja', 'en'):
            config = Config(self.path)
            config.language = language
            dialog = ConfigDialog(config)
            self.addCleanup(dialog.deleteLater)
            self.assertIs(dialog.voice_basic_group.parentWidget().layout().itemAt(0).widget(), dialog.voice_basic_group)
            self.assertIs(dialog.voicevox_url_edit.parentWidget(), dialog.voice_basic_group)
            self.assertTrue(dialog.voice_basic_group.isEnabled())
            self.assertIs(dialog.enable_voice_guidance_check,
                          dialog.enable_voice_guidance_check.parentWidget().layout().itemAt(0).layout().itemAt(0).widget())
            dialog.enable_voice_guidance_check.setChecked(False)
            self.assertFalse(dialog.voice_options.isEnabled())
            dialog.enable_voice_guidance_check.setChecked(True)
            self.assertTrue(dialog.voice_options.isEnabled())
            dialog.voice_item_checks['lane_status'].setChecked(False)
            self.assertTrue(dialog.voice_item_checks['missing_chart'].isChecked())
            dialog.voice_item_checks['missing_chart'].setChecked(False)
            self.assertEqual(list(dialog.voice_item_checks)[-4:], ['personal_best', 'result_saved', 'errors', 'shutdown'])
            self.assertTrue(dialog.voice_item_checks['personal_best'].isChecked())
            dialog.voice_item_checks['personal_best'].setChecked(False)
            self.assertTrue(dialog.voice_item_checks['result_saved'].isChecked())
            dialog.voice_item_checks['result_saved'].setChecked(False)
            self.assertTrue(dialog.voice_item_checks['errors'].isChecked())
            dialog.voice_item_checks['errors'].setChecked(False)
            dialog.voicevox_speaker_spin.setValue(8)
            dialog.voice_volume_spin.setValue(35)
            dialog.voice_pan_spin.setValue(-60)
            dialog.voice_output_combo.setCurrentIndex(dialog.voice_output_combo.findData('headphones'))
            dialog.voicevox_url_edit.setText('http://localhost:50022/')
            original = Path(self.path).read_bytes()
            dialog.reject()
            self.assertEqual(Path(self.path).read_bytes(), original)
            self.assertEqual(config.enable_voice_guidance, language == 'en')
            dialog.accept()
            saved = Config(self.path)
            self.assertTrue(saved.enable_voice_guidance)
            self.assertFalse(saved.voice_lane_status)
            self.assertFalse(saved.voice_missing_chart)
            self.assertFalse(saved.voice_personal_best)
            self.assertFalse(saved.voice_result_saved)
            self.assertFalse(saved.voice_errors)
            self.assertEqual(saved.voicevox_speaker_id, 8)
            self.assertEqual(saved.voice_output_device, 'headphones')
            self.assertEqual(saved.voice_volume, 35)
            self.assertEqual(saved.voice_pan, -60)
            self.assertEqual(saved.voicevox_url, 'http://localhost:50022')
            # Keep the next language's initial state at the default for this item.
            saved.voice_personal_best = True
            saved.voice_missing_chart = True
            saved.voice_result_saved = True
            saved.voice_errors = True
            saved.save_config()

    def test_preview_uses_unsaved_settings_when_guidance_disabled(self):
        from PySide6.QtWidgets import QApplication
        from src.config_dialog import ConfigDialog

        app = QApplication.instance() or QApplication([])
        config = Config(self.path)
        dialog = ConfigDialog(config)
        self.addCleanup(dialog.deleteLater)
        original = Path(self.path).read_bytes()
        dialog.voicevox_url_edit.setText(' http://localhost:50022/ ')
        dialog.voicevox_speaker_spin.setValue(8)
        dialog.voice_volume_spin.setValue(35)
        dialog.voice_pan_spin.setValue(-60)
        dialog.voice_output_combo.setCurrentIndex(dialog.voice_output_combo.findData('headphones'))
        self.assertFalse(dialog.enable_voice_guidance_check.isChecked())
        self.assertTrue(dialog.voice_test_button.isEnabled())
        row = dialog.enable_voice_guidance_check.parentWidget().layout().itemAt(0).layout()
        self.assertIs(row.itemAt(1).widget(), dialog.voice_test_button)
        with patch('src.config_dialog.start_voice_preview') as preview:
            preview.return_value.is_alive.return_value = True
            dialog.voice_test_button.click()
            preview.assert_called_once_with('http://localhost:50022', 8, 'headphones', 35, -60)
            self.assertFalse(dialog.voice_test_button.isEnabled())
            dialog._poll_voice_test()
            self.assertFalse(dialog.voice_test_button.isEnabled())
            preview.return_value.is_alive.return_value = False
            dialog._poll_voice_test()
            self.assertTrue(dialog.voice_test_button.isEnabled())
        self.assertEqual(Path(self.path).read_bytes(), original)
        self.assertEqual(config.voicevox_speaker_id, 1)

    def test_unavailable_output_is_preserved_in_dialog_and_saved_config(self):
        from PySide6.QtWidgets import QApplication
        from src.config_dialog import ConfigDialog

        app = QApplication.instance() or QApplication([])
        config = Config(self.path)
        config.voice_output_device = 'disconnected'
        dialog = ConfigDialog(config)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.voice_output_combo.currentData(), 'disconnected')
        self.assertEqual(dialog.voice_output_combo.currentText(), dialog.ui.voice.output_unavailable)
        dialog.accept()
        self.assertEqual(Config(self.path).voice_output_device, 'disconnected')


class VoicePreviewTests(unittest.TestCase):
    def test_random_message_is_synthesized_and_played(self):
        with (patch('src.voice_guidance.random.choice', return_value='にーさんごーろく') as choose,
              patch('src.voice_guidance.synthesize', return_value=b'wav') as synthesis,
              patch('src.voice_guidance.play_wav') as play):
            worker = start_voice_preview('http://localhost:50022', 8, 'headphones', 35, -60)
            worker.join(3)
            self.assertFalse(worker.is_alive())
            choose.assert_called_once_with(VOICE_TEST_MESSAGES)
            synthesis.assert_called_once_with('にーさんごーろく', 'http://localhost:50022', 8)
            play.assert_called_once_with(b'wav', 'headphones', 35, -60)

    def test_preview_failure_is_logged_and_worker_finishes(self):
        with (patch('src.voice_guidance.synthesize', side_effect=OSError('unavailable')),
              patch('src.voice_guidance.play_wav') as play,
              patch('src.voice_guidance.logger') as logger):
            worker = start_voice_preview('http://localhost:50022', 8)
            worker.join(3)
            self.assertFalse(worker.is_alive())
            logger.exception.assert_called_once()
            play.assert_not_called()


class VoiceWarningUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_warning_visibility_and_localized_message(self):
        from src.main_window import MainWindowUI

        with tempfile.TemporaryDirectory() as directory:
            for language in ('ja', 'en'):
                config = Config(str(Path(directory) / 'config.json'))
                config.language = language
                config.enable_voice_guidance = True
                window = MainWindowUI(config)
                window.voice_guidance = Mock()
                window.save_image = lambda: None
                with patch.object(window, 'create_menu_bar'), patch.object(window, 'restore_window_geometry'):
                    window.init_ui()
                self.addCleanup(window.deleteLater)
                self.assertEqual(window.voice_warning_label.text(), window.ui.main.voicevox_unavailable)
                for available, hidden in ((None, True), (False, False), (True, True)):
                    window.voice_guidance.poll_connection.return_value = available
                    window.update_voice_warning()
                    self.assertEqual(window.voice_warning_label.isHidden(), hidden)
                window.voice_guidance.poll_connection.return_value = False
                config.enable_voice_guidance = False
                window.update_voice_warning()
                self.assertTrue(window.voice_warning_label.isHidden())


if __name__ == '__main__':
    unittest.main()
