"""RANDOM lane mapping analysis integrated with the main screen capture loop.

The note detector and 5040-permutation elimination are adapted, with the
author's permission, from RandomLaneAnalysis_OCR bundled in this workspace.
"""

from __future__ import annotations

import itertools
import json
import sqlite3
import threading
import time
from contextlib import closing
from functools import wraps
from pathlib import Path

import cv2
import numpy as np

from src.logger import get_logger

logger = get_logger(__name__)


def _synchronized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper

LANES = tuple(range(1, 8))
REGULAR_LAYOUT = "1234567"
MIRROR_LAYOUT = "7654321"
LANE_BOUNDARIES_RATIO = (0.000, 0.153, 0.282, 0.436, 0.564, 0.718, 0.847, 1.000)

COLOR_RANGES = (
    ((85, 80, 80), (130, 255, 255)),
    ((0, 0, 145), (179, 80, 255)),
    ((3, 90, 70), (30, 255, 255)),
    ((130, 70, 60), (175, 255, 255)),
)
MIN_ACTIVE_PIXELS = 8
MIN_ACTIVE_RATIO = 0.035
# Event detection now follows upstream rising edges without frame merging.
CHART_DATA_VERSION = 5
WHITE_LANE_MARGIN = 0.15
BLACK_LANE_MARGIN = 0.08
MORPH_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))

DEFAULT_ROI_1P = (165, 84, 343, 81)
DEFAULT_ROI_2P = (1920 - DEFAULT_ROI_1P[0] - DEFAULT_ROI_1P[2], 84, 343, 81)
DEFAULT_BAND = (55, 75)


def _layout_text(permutation) -> str:
    return "".join(str(permutation.index(random_lane) + 1) for random_lane in LANES)


class NoteDetector:
    def __init__(self, roi, band=DEFAULT_BAND):
        self.roi = tuple(map(int, roi))
        self.band = tuple(map(int, band))
        self.last_lane_state = [False] * 7
        self.event_counter = 0

    def reset(self):
        self.last_lane_state = [False] * 7
        self.event_counter = 0

    def detect(self, rgb_image):
        x, y, width, height = self.roi
        band_y1 = max(0, min(height, self.band[0]))
        band_y2 = max(0, min(height, self.band[1]))
        band_image = rgb_image[y + band_y1:y + band_y2, x:x + width]
        if band_y2 <= band_y1 or band_image.size == 0:
            return None, []

        hsv = cv2.cvtColor(band_image, cv2.COLOR_RGB2HSV)
        combined = None
        for low, high in COLOR_RANGES:
            mask = cv2.inRange(hsv, low, high)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, MORPH_KERNEL)
            combined = mask if combined is None else cv2.bitwise_or(combined, mask)

        lane_state = []
        for lane_index in range(7):
            lane_x1 = round(LANE_BOUNDARIES_RATIO[lane_index] * width)
            lane_x2 = round(LANE_BOUNDARIES_RATIO[lane_index + 1] * width)
            margin_ratio = WHITE_LANE_MARGIN if lane_index + 1 in (1, 3, 5, 7) else BLACK_LANE_MARGIN
            margin = max(2, int((lane_x2 - lane_x1) * margin_ratio))
            lane_mask = combined[:, lane_x1 + margin:lane_x2 - margin]
            if lane_mask.size == 0:
                lane_state.append(False)
                continue
            pixels = cv2.countNonZero(lane_mask)
            ratio = pixels / max(1, lane_mask.shape[0] * lane_mask.shape[1])
            lane_state.append(pixels >= MIN_ACTIVE_PIXELS and ratio >= MIN_ACTIVE_RATIO)

        rising_lanes = [
            index + 1
            for index, (old, new) in enumerate(zip(self.last_lane_state, lane_state))
            if new and not old
        ]
        self.last_lane_state = lane_state
        if not rising_lanes:
            return None, []
        self.event_counter += 1
        return self.event_counter, rising_lanes


class NormalChartRecorder:
    def __init__(self):
        self.events = []
        self.seen_lanes = set()

    def add(self, lanes) -> bool:
        lanes = tuple(sorted(set(map(int, lanes))))
        if not lanes:
            return False
        self.events.append({"event_no": len(self.events) + 1, "event_lanes": list(lanes)})
        self.seen_lanes.update(lanes)
        return self.seen_lanes == set(LANES) and self._identity_is_unique()

    def _identity_is_unique(self) -> bool:
        for permutation in itertools.permutations(LANES):
            if permutation == LANES:
                continue
            if all(
                {permutation[lane - 1] for lane in event["event_lanes"]}
                == set(event["event_lanes"])
                for event in self.events
            ):
                return False
        return True


class RandomMappingAnalyzer:
    def __init__(self, normal_events):
        self.normal_events = normal_events
        self.candidates = list(itertools.permutations(LANES))
        self.pair_index = 0
        self.layout = None
        self.failed = False
        self.failure_reason = None

    def add(self, random_lanes):
        if self.failed or self.layout or self.pair_index >= len(self.normal_events):
            self.failed = self.layout is None
            if self.failed and self.failure_reason is None:
                self.failure_reason = "正規譜面データの末尾までに配置を確定できませんでした"
            return
        event_no = self.pair_index + 1
        normal_lanes = set(self.normal_events[self.pair_index]["event_lanes"])
        random_lanes = set(map(int, random_lanes))
        if len(normal_lanes) != len(random_lanes):
            self.candidates = []
            self.failure_reason = (
                f"イベント{event_no}: 正規{sorted(normal_lanes)} / RANDOM{sorted(random_lanes)}"
            )
        else:
            self.candidates = [
                permutation
                for permutation in self.candidates
                if {permutation[lane - 1] for lane in normal_lanes} == random_lanes
            ]
            if not self.candidates:
                self.failure_reason = (
                    f"イベント{event_no}: 正規{sorted(normal_lanes)} / RANDOM{sorted(random_lanes)}"
                )
        self.pair_index += 1
        if not self.candidates:
            self.failed = True
        elif len(self.candidates) == 1:
            self.layout = _layout_text(self.candidates[0])

    def get_partial_layout(self):
        """Project only facts shared by every surviving mapping, in display order.

        Digits identify original lanes; W/B identify only their key color, and
        ? means neither the lane nor its color is determined.
        """
        if not self.candidates:
            return None
        positions = [set() for _ in LANES]
        for permutation in self.candidates:
            for original, target in enumerate(permutation, 1):
                positions[target - 1].add(original)
        layout = []
        for originals in positions:
            if len(originals) == 1:
                layout.append(str(next(iter(originals))))
            elif all(lane % 2 for lane in originals):
                layout.append("W")
            elif all(lane % 2 == 0 for lane in originals):
                layout.append("B")
            else:
                layout.append("?")
        text = "".join(layout)
        return text if text != "???????" else None


class RandomLaneAnalysis:
    """Coordinates capture frames, chart persistence, and overlay state."""

    def __init__(self, enabled=False, db_path="random_lane.sqlite3", state_path="template/random_lane_state.js",
                 detection_bands=None):
        self._lock = threading.RLock()
        self.enabled = None
        self.db_path = Path(db_path)
        self.state_path = Path(state_path)
        self.detectors = {
            "1P": NoteDetector(DEFAULT_ROI_1P),
            "2P": NoteDetector(DEFAULT_ROI_2P),
        }
        self.mode = None
        self.side = None
        self.chart_key = None
        self.chart_meta = None
        self.recorder = None
        self.analyzer = None
        self.record_mirror = False
        self.result_layout = None
        self._notification = None
        self._last_state = None
        self.capture_supported = True
        self.set_detection_bands(detection_bands)
        self.set_enabled(enabled)

    @_synchronized
    def set_detection_bands(self, bands=None):
        """Apply per-side bands for the next play, cancelling any active capture."""
        bands = bands or {}
        profiles = {}
        for side, roi in (("1P", DEFAULT_ROI_1P), ("2P", DEFAULT_ROI_2P)):
            top, bottom = map(int, bands.get(side, DEFAULT_BAND))
            if not (0 <= top < bottom <= 1080 - roi[1] and bottom - top <= 300):
                raise ValueError(f"Invalid {side} detection band: {(top, bottom)}")
            profiles[side] = (top, bottom)
        if all(self.detectors[side].band == band for side, band in profiles.items()):
            return
        for side, band in profiles.items():
            detector = self.detectors[side]
            x, y, width, _ = detector.roi
            detector.roi = (x, y, width, max(DEFAULT_ROI_1P[3], band[1]))
            detector.band = band
            detector.reset()
        self._reset_session(clear_result_layout=True)
        if self.enabled:
            self._publish("waiting" if self.capture_supported else "unavailable",
                          message="検出帯を変更しました。次のSPプレーから適用します")

    @_synchronized
    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        self.enabled = enabled
        self._reset_session(clear_result_layout=True)
        if enabled:
            self._ensure_database()
            self._publish("waiting", message="次のSPプレーを待っています")
        else:
            self._publish("disabled", message="RANDOM配置認識は無効です")

    @_synchronized
    def set_capture_supported(self, supported: bool, message=None):
        self.capture_supported = bool(supported)
        if self.enabled and not supported:
            self._reset_session()
            self._publish(
                "unavailable",
                message=message or "RANDOM配置認識用の映像入力を利用できません",
            )
        elif self.enabled and self._last_state and self._last_state.get("phase") == "unavailable":
            self._publish("waiting", message=message or "次のSPプレーを待っています")

    @_synchronized
    def start_play(self, *, title, style, difficulty, level, option, play_mode):
        self._reset_session(clear_result_layout=True)
        if not self.enabled:
            return
        if not self.capture_supported:
            self._publish("unavailable", message="RANDOM配置認識用の映像入力を利用できません")
            return
        if not title or style != "sp" or not difficulty or not play_mode:
            self._publish("unsupported", title=title, message="SPの曲名・譜面・プレイサイドを確認できません")
            return

        side = "1P" if play_mode.startswith("sp_1p") else "2P" if play_mode.startswith("sp_2p") else None
        if side is None:
            self._publish("unsupported", title=title, message="DPは現在対象外です")
            return
        if option is None or not getattr(option, "valid", False):
            self._publish("unsupported", title=title, message="オプション画面を一度開いて配置を認識させてください")
            return

        arrange = (getattr(option, "arrange", None) or "REGULAR").upper()
        if arrange in ("OFF", "NORMAL"):
            arrange = "REGULAR"
        if getattr(option, "special", False):
            self._publish("unsupported", title=title, message=f"{arrange}は現在対象外です")
            return

        self.side = side
        self.option_name = arrange
        self.chart_key = f"{title}\x1f{style}\x1f{difficulty}"
        # Keep existing charts at the default band. Other bands need their own
        # event sequences; returning to the default restores the original data.
        band = self.detectors[side].band
        if band != DEFAULT_BAND:
            self.chart_key += f"\x1fband={band[0]}:{band[1]}"
        self.chart_meta = {"title": title, "style": style, "difficulty": difficulty, "level": level}
        self.detectors[side].reset()

        if arrange in ("REGULAR", "MIRROR"):
            self.result_layout = (
                REGULAR_LAYOUT if arrange == "REGULAR" else MIRROR_LAYOUT
            )
            if self._load_chart(self.chart_key):
                self._publish(
                    "ready",
                    title=title,
                    chart=difficulty,
                    layout=self.result_layout,
                    message="正規譜面データは登録済みです",
                )
                return
            self.mode = "record"
            self.recorder = NormalChartRecorder()
            self.record_mirror = arrange == "MIRROR"
            message = (
                "MIRROR譜面を正規配置へ変換して記録中"
                if self.record_mirror
                else "正規譜面データを記録中"
            )
            self._publish(
                "recording",
                title=title,
                chart=difficulty,
                layout=self.result_layout,
                message=message,
            )
        elif arrange in ("RANDOM", "R-RANDOM"):
            events = self._load_chart(self.chart_key)
            if not events:
                self._publish(
                    "needs_normal",
                    title=title,
                    chart=difficulty,
                    message="先にREGULARまたはMIRRORでこの譜面をプレーしてください",
                )
                return
            self.mode = "analyze"
            self.analyzer = RandomMappingAnalyzer(events)
            self._publish(
                "analyzing",
                title=title,
                chart=difficulty,
                message=f"{arrange}配置を解析中",
            )
        else:
            self._publish("unsupported", title=title, chart=difficulty, message=f"{arrange}は現在対象外です")

    @_synchronized
    def process_frame(self, image):
        if not self.enabled or self.mode not in ("record", "analyze") or self.side is None:
            return
        rgb = np.asarray(image)
        if rgb.ndim != 3 or rgb.shape[2] < 3:
            return
        event_no, lanes = self.detectors[self.side].detect(rgb[:, :, :3])
        if not lanes:
            return

        if self.mode == "record":
            if self.record_mirror:
                lanes = [8 - lane for lane in lanes]
            logger.info("正規譜面記録 event=%s lanes=%s", event_no, sorted(lanes))
            recording_complete = self.recorder.add(lanes)
        else:
            recording_complete = False

        if self.mode == "record" and recording_complete:
            self._save_chart(self.chart_key, self.chart_meta, self.recorder.events)
            self.mode = None
            self._publish(
                "registered", **self.chart_meta,
                layout=self.result_layout,
                message=f"正規譜面データを登録しました（{len(self.recorder.events)}イベント）",
            )
        elif self.mode == "analyze":
            pair_index = self.analyzer.pair_index
            normal_lanes = (
                self.analyzer.normal_events[pair_index]["event_lanes"]
                if pair_index < len(self.analyzer.normal_events)
                else []
            )
            candidates_before = len(self.analyzer.candidates)
            self.analyzer.add(lanes)
            logger.info(
                "RANDOM解析 event=%s normal=%s random=%s candidates=%d->%d",
                event_no,
                normal_lanes,
                sorted(lanes),
                candidates_before,
                len(self.analyzer.candidates),
            )
            previous_layout = self.result_layout
            self.result_layout = self.analyzer.get_partial_layout()
            if self.analyzer.layout:
                self.result_layout = self.analyzer.layout
                self.mode = None
                self._publish(
                    "confirmed", **self.chart_meta, layout=self.analyzer.layout,
                    message=f"RANDOM配置: {self.analyzer.layout}",
                )
            elif self.analyzer.failed:
                self.mode = None
                reason = self.analyzer.failure_reason or "イベント列が一致しません"
                logger.warning("RANDOM配置を確定できませんでした: %s", reason)
                self._publish(
                    "failed",
                    **self.chart_meta,
                    layout=self.result_layout or "",
                    message=f"RANDOM配置を確定できませんでした（{reason}）",
                )
            elif self.result_layout and self.result_layout != previous_layout:
                self._publish(
                    "partial", **self.chart_meta, layout=self.result_layout,
                    message="RANDOM配置の一部を特定しました",
                )

    @_synchronized
    def end_play(self):
        if not self.enabled:
            return
        self._reset_session()
        if self.capture_supported:
            self._publish("waiting", message="プレー終了。次のSPプレーを待っています")

    @_synchronized
    def take_notification(self):
        notification = self._notification
        self._notification = None
        return notification

    @_synchronized
    def get_result_lane_layout(self):
        """現在のプレーの配置（W/B/?を含む部分配置も可）を保存用に返す。"""
        return self.result_layout

    def _reset_session(self, *, clear_result_layout=False):
        self.mode = None
        self.side = None
        self.option_name = ""
        self.chart_key = None
        self.chart_meta = None
        self.recorder = None
        self.analyzer = None
        self.record_mirror = False
        if clear_result_layout:
            self.result_layout = None

    def _ensure_database(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS normal_charts (
                    chart_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    style TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    level INTEGER,
                    note_events TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    data_version INTEGER NOT NULL DEFAULT 1
                )"""
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(normal_charts)")
            }
            if "data_version" not in columns:
                conn.execute(
                    "ALTER TABLE normal_charts "
                    "ADD COLUMN data_version INTEGER NOT NULL DEFAULT 1"
                )

    def _load_chart(self, chart_key):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute(
                "SELECT note_events FROM normal_charts "
                "WHERE chart_key=? AND data_version=?",
                (chart_key, CHART_DATA_VERSION),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _save_chart(self, chart_key, meta, events):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """INSERT INTO normal_charts
                   (chart_key,title,style,difficulty,level,note_events,created_at,data_version)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(chart_key) DO UPDATE SET
                       title=excluded.title,
                       style=excluded.style,
                       difficulty=excluded.difficulty,
                       level=excluded.level,
                       note_events=excluded.note_events,
                       created_at=excluded.created_at,
                       data_version=excluded.data_version""",
                (
                    chart_key, meta["title"], meta["style"], meta["difficulty"], meta["level"],
                    json.dumps(events, ensure_ascii=False), int(time.time()), CHART_DATA_VERSION,
                ),
            )
        logger.info("RANDOM配置認識用の正規譜面を登録: %s", chart_key)

    def _publish(self, phase, *, title=None, chart=None, style=None, difficulty=None,
                 level=None, layout="", message=""):
        payload = {
            "phase": phase,
            "option": self.option_name,
            "side": self.side,
            "title": title or "",
            "chart": chart or difficulty or "",
            "layout": layout,
            "message": message,
            "updated_at": int(time.time()),
        }
        self._last_state = payload
        self._notification = message
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            "window.INFDC_RANDOM_LANE_STATE = "
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + ";\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
