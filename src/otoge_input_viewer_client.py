"""Otoge Input Viewerからプレー中のリリース時間を収集する。"""

import asyncio
import json
import math
import threading
import time

import websockets

from .classes import average_release
from .logger import get_logger


logger = get_logger(__name__)


class OtogeInputViewerClient:
    """OIVの移動平均リリース時間を10秒区間ごとに集約するクライアント。"""

    DEFAULT_URL = "ws://127.0.0.1:8765"
    BUCKET_SECONDS = 10.0
    RECONNECT_SECONDS = 1.0

    def __init__(self, url=DEFAULT_URL, *, autostart=True):
        self.url = url
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._play_started_at = None
        self._buckets = []
        self._received_release = False
        if autostart:
            self.start()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="otoge-input-viewer-client",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def start_play(self, now=None):
        with self._lock:
            self._play_started_at = time.monotonic() if now is None else now
            self._buckets = []
            self._received_release = False

    def finish_play(self, now=None):
        """終了したプレーの10秒区間平均を返す。受信なしならNone。"""
        finished_at = time.monotonic() if now is None else now
        with self._lock:
            if self._play_started_at is None:
                return None
            duration = max(0.0, finished_at - self._play_started_at)
            bucket_count = max(1, math.ceil(duration / self.BUCKET_SECONDS))
            self._ensure_bucket(bucket_count - 1)
            histogram = [
                round(sum(values) / len(values), 1) if values else None
                for values in self._buckets
            ]
            received_release = self._received_release
            self._play_started_at = None
            self._buckets = []
            self._received_release = False
        if not received_release:
            return None
        return average_release(histogram, interval_seconds=self.BUCKET_SECONDS)

    def handle_message(self, message, now=None):
        """WebSocketメッセージを処理する。公開して単体テストにも利用する。"""
        try:
            events = json.loads(message)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(events, list):
            return

        received_at = time.monotonic() if now is None else now
        for event in events:
            if not isinstance(event, dict) or event.get("type") != "release":
                continue
            try:
                value = float(event.get("value"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            with self._lock:
                if self._play_started_at is None:
                    continue
                elapsed = max(0.0, received_at - self._play_started_at)
                bucket_index = int(elapsed // self.BUCKET_SECONDS)
                self._ensure_bucket(bucket_index)
                self._buckets[bucket_index].append(value)
                self._received_release = True

    def _ensure_bucket(self, index):
        while len(self._buckets) <= index:
            self._buckets.append([])

    def _run(self):
        try:
            asyncio.run(self._receive_forever())
        except Exception:
            logger.debug("Otoge Input Viewer受信スレッドを終了しました", exc_info=True)

    async def _receive_forever(self):
        connected_once = False
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self.url,
                    open_timeout=1.0,
                    close_timeout=1.0,
                    ping_interval=20.0,
                ) as websocket:
                    if not connected_once:
                        logger.info(f"Otoge Input Viewerに接続しました: {self.url}")
                        connected_once = True
                    while not self._stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                        except asyncio.TimeoutError:
                            continue
                        self.handle_message(message)
            except (OSError, asyncio.TimeoutError, websockets.ConnectionClosed):
                pass
            if not self._stop_event.is_set():
                await asyncio.sleep(self.RECONNECT_SECONDS)

