"""High-frequency Spout receiver shared by screen reading and lane analysis."""

from __future__ import annotations

import array
import sys
import threading
import time

import cv2
import numpy as np

from src.logger import get_logger

logger = get_logger(__name__)

TARGET_SIZE = (1920, 1080)


class SpoutCapture:
    """Receive RGB frames on a worker thread without blocking the Qt loop."""

    def __init__(self, frame_callback=None):
        self.frame_callback = frame_callback
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sender_name = ""
        self._status = None
        self._last_status = None
        self._connected = False
        self._latest_frame = None

    @staticmethod
    def dependency_error():
        if not sys.platform.startswith("win"):
            return "Spout入力はWindows専用です"
        try:
            import SpoutGL  # noqa: F401
        except Exception as exc:
            return f"SpoutGLを読み込めません: {exc}"
        return None

    def start(self, sender_name: str):
        sender_name = str(sender_name or "Spout_OBS_Filter").strip() or "Spout_OBS_Filter"
        if self._thread and self._thread.is_alive() and sender_name == self._sender_name:
            return False
        if not self.stop():
            self._emit_status("error", "Spout受信スレッドを停止できませんでした")
            return False
        self._sender_name = sender_name
        with self._lock:
            self._status = None
            self._last_status = None
            self._connected = False
            self._latest_frame = None
        error = self.dependency_error()
        if error:
            self._emit_status("error", error)
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="random-lane-spout",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self):
        thread = self._thread
        self._stop_event.set()
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        stopped = thread is None or not thread.is_alive()
        if stopped:
            self._thread = None
            with self._lock:
                self._connected = False
                self._latest_frame = None
        return stopped

    def set_frame_callback(self, frame_callback):
        with self._lock:
            self.frame_callback = frame_callback

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame

    @property
    def is_connected(self):
        with self._lock:
            return self._connected

    def current_status(self):
        with self._lock:
            return self._last_status

    def take_status(self):
        with self._lock:
            status = self._status
            self._status = None
        return status

    def _emit_status(self, kind: str, message: str):
        current = (kind, message)
        with self._lock:
            if current == self._last_status:
                return
            self._last_status = current
            self._status = current
        if kind == "error":
            logger.error(message)
        else:
            logger.info(message)

    def _run(self):
        try:
            import SpoutGL

            rgba_format = SpoutGL.enums.GL_RGBA
            with SpoutGL.SpoutReceiver() as receiver:
                receiver.setReceiverName(self._sender_name)
                buffer = None
                buffer_size = None
                connected = False
                self._emit_status("waiting", f"Spout送信待ち: {self._sender_name}")

                while not self._stop_event.is_set():
                    result = receiver.receiveImage(buffer, rgba_format, False, 0)
                    is_connected = bool(receiver.isConnected())

                    if is_connected != connected:
                        connected = is_connected
                        with self._lock:
                            self._connected = connected
                            if not connected:
                                self._latest_frame = None
                        if connected:
                            self._emit_status(
                                "connected",
                                f"Spout接続: {self._sender_name}",
                            )
                        else:
                            self._emit_status("waiting", f"Spout送信待ち: {self._sender_name}")
                            buffer = None
                            buffer_size = None

                    if not connected:
                        time.sleep(0.05)
                        continue

                    width = int(receiver.getSenderWidth())
                    height = int(receiver.getSenderHeight())
                    size = (width, height)
                    if width <= 0 or height <= 0:
                        time.sleep(0.01)
                        continue

                    if bool(receiver.isUpdated()) or buffer_size != size:
                        buffer = array.array("B", [0]) * (width * height * 4)
                        buffer_size = size
                        continue

                    if result and bool(receiver.isFrameNew()) and buffer is not None:
                        rgba = np.frombuffer(buffer, dtype=np.uint8)
                        if rgba.size == width * height * 4:
                            rgb = rgba.reshape((height, width, 4))[:, :, :3]
                            if size != TARGET_SIZE:
                                rgb = cv2.resize(rgb, TARGET_SIZE, interpolation=cv2.INTER_AREA)
                            else:
                                rgb = np.ascontiguousarray(rgb)
                            with self._lock:
                                self._latest_frame = rgb
                                frame_callback = self.frame_callback
                            if frame_callback is not None:
                                frame_callback(rgb)

                    receiver.waitFrameSync(self._sender_name, 16)
        except Exception as exc:
            with self._lock:
                self._connected = False
                self._latest_frame = None
            self._emit_status("error", f"Spout受信エラー: {exc}")
