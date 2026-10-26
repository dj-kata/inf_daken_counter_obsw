"""Queued VOICEVOX synthesis and audio playback."""

import json
import queue
import random
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.classes import clear_lamp
from src.logger import get_logger
from src.voice_audio import play_wav

logger = get_logger(__name__)

VOICE_DEFAULTS = {
    'enable_voice_guidance': False,
    'voice_startup': True,
    'voice_lane_status': True,
    'voice_chart_info': True,
    'voice_personal_best': True,
    'voice_result_saved': True,
    'voice_errors': True,
    'voice_shutdown': True,
    'voicevox_url': 'http://127.0.0.1:50021',
    'voicevox_speaker_id': 1,
    'voice_output_device': '',
    'voice_volume': 100,
    'voice_pan': 0,
}

LAMP_ANNOUNCEMENTS = {
    clear_lamp.easy: '初イージー',
    clear_lamp.clear: '初ノマゲ',
    clear_lamp.hard: '初ハード',
    clear_lamp.exh: '初エクハ',
    clear_lamp.fc: '初フルコン',
}

OBS_CONTROL_WARNING = 'OBSに接続できません。OBSの起動とOBS制御設定を確認してください'
SPOUT_WARNING = 'Spoutの映像を受信できません。OBSの起動とSpout送信設定を確認してください'

VOICE_TEST_MESSAGES = (
    '打鍵カウンタを起動しました',
    '正規かミラーでプレイしてください',
    '正規譜面を取得中',
    '正規譜面を登録完了しました',
    'ガチ割れ', '逆割れ', 'にーさんごーろく',
    *(f'{lane}バス' for lane in range(1, 8)),
    *LAMP_ANNOUNCEMENTS.values(),
    'スコア更新', 'ミスカウント更新',
    'リザルトを保存しました',
    OBS_CONTROL_WARNING, SPOUT_WARNING,
    '打鍵カウンタを終了しました',
)


def chart_announcements(layout, side):
    """Return only facts established by a complete or partial display layout."""
    if side not in ('1P', '2P') or len(layout) != 7:
        return []
    white_positions = {
        index for index, key in enumerate(layout, 1) if key in '1357W'
    }
    messages = []
    if white_positions in ({1, 2, 3, 4}, {4, 5, 6, 7}):
        right = white_positions == {4, 5, 6, 7}
        messages.append('ガチ割れ' if right == (side == '1P') else '逆割れ')
    elif white_positions == {2, 3, 5, 6}:
        messages.append('にーさんごーろく')
    if '1' in layout:
        messages.append(f'{layout.index("1") + 1}バス')
    return messages


def personal_best_announcements(result):
    """Compare a registered result with its previous personal bests."""
    messages = []
    if (result.lamp in LAMP_ANNOUNCEMENTS
            and (result.pre_lamp is None or result.lamp.value > result.pre_lamp.value)):
        messages.append(LAMP_ANNOUNCEMENTS[result.lamp])
    # An absent/zero previous score represents a first play, not a score update.
    if (result.score is not None and result.pre_score is not None
            and result.pre_score > 0 and result.score > result.pre_score):
        messages.append('スコア更新')
    if (not result.dead and result.bp is not None and result.pre_bp is not None
            and result.pre_bp < 99999999 and result.bp < result.pre_bp):
        messages.append('ミスカウント更新')
    return messages


def synthesize(text, url, speaker):
    """Use the engine's audio_query and synthesis endpoints to obtain WAV bytes."""
    query_url = f'{url}/audio_query?{urlencode({"text": text, "speaker": speaker})}'
    with urlopen(Request(query_url, data=b'', method='POST'), timeout=3) as response:
        query = json.load(response)
    request = Request(
        f'{url}/synthesis?{urlencode({"speaker": speaker})}',
        data=json.dumps(query).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urlopen(request, timeout=10) as response:
        return response.read()


def start_voice_preview(url, speaker, device_id='', volume=100, pan=0):
    """Preview one random announcement without changing saved settings."""
    text = random.choice(VOICE_TEST_MESSAGES)

    def run():
        try:
            play_wav(synthesize(text, url, speaker), device_id, volume, pan)
        except Exception:
            logger.exception('VOICEVOXテスト再生に失敗しました（エンジンの起動と設定を確認してください）')

    worker = threading.Thread(target=run, name='voice-preview', daemon=True)
    worker.start()
    return worker


class VoiceGuidance:
    def __init__(self, config):
        self._lock = threading.RLock()
        self._queue = queue.Queue(maxsize=32)
        self._generation = 0
        self._closing = False
        self._announced = set()
        self._active_obs_errors = set()
        self._connection_thread = None
        self.set_config(config)
        self._worker = threading.Thread(target=self._run, name='voice-guidance', daemon=True)
        self._worker.start()

    def set_config(self, config):
        with self._lock:
            self._settings = {key: getattr(config, key, default) for key, default in VOICE_DEFAULTS.items()}
            self._generation += 1
            self._connection_available = None
            self._next_connection_check = 0

    def poll_connection(self):
        """Return the last probe result and schedule at most one background probe."""
        with self._lock:
            if self._closing or not self._settings['enable_voice_guidance']:
                return None
            if (time.monotonic() >= self._next_connection_check
                    and (self._connection_thread is None or not self._connection_thread.is_alive())):
                self._next_connection_check = time.monotonic() + 5
                self._connection_thread = threading.Thread(
                    target=self._check_connection,
                    args=(self._generation, self._settings['voicevox_url'].rstrip('/')),
                    name='voicevox-connection', daemon=True,
                )
                self._connection_thread.start()
            return self._connection_available

    def _check_connection(self, generation, url):
        try:
            with urlopen(f'{url}/version', timeout=2) as response:
                version = json.load(response)
            available = isinstance(version, str) and bool(version)
        except Exception:
            available = False
        with self._lock:
            if generation == self._generation and not self._closing:
                self._connection_available = available

    def announce(self, category, text):
        with self._lock:
            if (self._closing or not self._settings['enable_voice_guidance']
                    or not self._settings['voice_' + category]):
                return
            try:
                self._queue.put_nowait((self._generation, text, self._settings.copy()))
            except queue.Full:
                logger.warning('音声案内キューが満杯のため案内を省略しました')

    def lane_state(self, state):
        with self._lock:
            phase = state.get('phase')
            if phase == 'preparing':
                self._announced.clear()
            messages = []
            if phase == 'needs_normal':
                messages.append(('lane_status', '正規かミラーでプレイしてください'))
            elif phase == 'recording':
                messages.append(('lane_status', '正規譜面を取得中'))
            elif phase == 'registered':
                messages.append(('lane_status', '正規譜面を登録完了しました'))
            if phase in ('partial', 'confirmed', 'ready', 'recording', 'registered'):
                messages.extend(
                    ('chart_info', text)
                    for text in chart_announcements(state.get('layout') or '', state.get('side'))
                )
            for category, text in messages:
                if text not in self._announced:
                    self._announced.add(text)
                    self.announce(category, text)

    def obs_status(self, *, startup, obs_control_enabled, obs_connected,
                   spout_enabled, spout_connected):
        with self._lock:
            if not self._settings['enable_voice_guidance'] or not self._settings['voice_errors']:
                self._active_obs_errors.clear()
                return
            errors = set()
            if obs_control_enabled and not obs_connected:
                errors.add('obs_control')
                if startup and 'obs_control' not in self._active_obs_errors:
                    self.announce('errors', OBS_CONTROL_WARNING)
            if spout_enabled and not spout_connected:
                errors.add('spout')
                if 'spout' not in self._active_obs_errors:
                    self.announce('errors', SPOUT_WARNING)
            self._active_obs_errors = errors

    def personal_best(self, result):
        for text in personal_best_announcements(result):
            self.announce('personal_best', text)

    def shutdown(self):
        """Drop pending play messages and finish with the optional exit announcement."""
        with self._lock:
            if self._closing:
                return
            self._generation += 1
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
            self.announce('shutdown', '打鍵カウンタを終了しました')
            self._closing = True

    def is_finished(self):
        return not self._worker.is_alive()

    def _run(self):
        cache = {}
        while True:
            try:
                generation, text, settings = self._queue.get(timeout=0.1)
            except queue.Empty:
                with self._lock:
                    if self._closing and self._queue.empty():
                        return
                continue
            try:
                with self._lock:
                    if generation != self._generation:
                        continue
                key = (settings['voicevox_url'].rstrip('/'), settings['voicevox_speaker_id'], text)
                if key not in cache:
                    wav = synthesize(text, key[0], key[1])
                    if len(cache) >= 64:
                        cache.clear()
                    cache[key] = wav
                with self._lock:
                    if generation != self._generation:
                        continue
                play_wav(cache[key], settings['voice_output_device'],
                         settings['voice_volume'], settings['voice_pan'])
            except Exception:
                logger.exception('VOICEVOX音声案内に失敗しました（エンジンの起動と設定を確認してください）')
            finally:
                self._queue.task_done()
