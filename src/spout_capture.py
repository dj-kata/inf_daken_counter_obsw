"""High-frequency Spout receiver shared by screen reading and lane analysis."""

from __future__ import annotations

import ctypes
import sys
import threading
import time

import cv2
import numpy as np

from src.logger import get_logger

logger = get_logger(__name__)

TARGET_SIZE = (1920, 1080)
RETRY_INTERVAL = 2.0
FRAME_TIMEOUT = 5.0
GL_TEXTURE_2D = 0x0DE1
GL_RGBA = 0x1908
GL_UNSIGNED_BYTE = 0x1401
GL_TEXTURE_MIN_FILTER = 0x2801
GL_TEXTURE_MAG_FILTER = 0x2800
GL_LINEAR = 0x2601


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
        self._surface = None

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
        try:
            from PySide6.QtGui import QOffscreenSurface

            self._surface = QOffscreenSurface()
            self._surface.create()
            if not self._surface.isValid():
                raise RuntimeError("OpenGLオフスクリーンサーフェスを作成できません")
        except Exception as exc:
            self._surface = None
            self._emit_status("error", f"Spout受信初期化エラー: {exc}")
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
            self._surface = None
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
        while not self._stop_event.is_set():
            try:
                self._receive()
            except Exception as exc:
                if not self._stop_event.is_set():
                    self._emit_status(
                        "error", f"Spout受信エラー: {exc}（{RETRY_INTERVAL:g}秒後に再試行）"
                    )
                    logger.debug("Spout受信エラー詳細", exc_info=True)
            finally:
                with self._lock:
                    self._connected = False
                    self._latest_frame = None
            if self._stop_event.wait(RETRY_INTERVAL):
                break

    def _receive(self):
        """Run one receiver session; release GL resources before retrying."""
        context = None
        texture = ctypes.c_uint()
        gl = None
        try:
            import SpoutGL
            from PySide6.QtGui import QOpenGLContext

            surface = self._surface
            if surface is None or not surface.isValid():
                raise RuntimeError("OpenGLオフスクリーンサーフェスが無効です")

            context = QOpenGLContext()
            context.setFormat(surface.format())
            if not context.create() or not context.makeCurrent(surface):
                raise RuntimeError("OpenGLコンテキストを作成できません")

            gl = ctypes.WinDLL("opengl32")
            gl.glGenTextures.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
            gl.glGenTextures.restype = None
            gl.glDeleteTextures.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
            gl.glDeleteTextures.restype = None
            gl.glBindTexture.argtypes = [ctypes.c_uint, ctypes.c_uint]
            gl.glBindTexture.restype = None
            gl.glTexParameteri.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_int]
            gl.glTexParameteri.restype = None
            gl.glTexImage2D.argtypes = [
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_void_p,
            ]
            gl.glTexImage2D.restype = None
            gl.glGetTexImage.argtypes = [
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_void_p,
            ]
            gl.glGetTexImage.restype = None

            gl.glGenTextures(1, ctypes.byref(texture))
            if not texture.value:
                raise RuntimeError("OpenGLテクスチャを作成できません")
            gl.glBindTexture(GL_TEXTURE_2D, texture.value)
            gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            gl.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            gl.glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_RGBA,
                1,
                1,
                0,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                None,
            )

            with SpoutGL.SpoutReceiver() as receiver:
                receiver.setReceiverName(self._sender_name)
                pixels = None
                texture_size = None
                connected = False
                next_sender_check = 0.0
                last_frame_at = time.monotonic()
                self._emit_status("waiting", f"Spout送信待ち: {self._sender_name}")

                while not self._stop_event.is_set():
                    result = receiver.receiveTexture(texture.value, GL_TEXTURE_2D, False, 0)
                    is_connected = bool(receiver.isConnected())
                    width = int(receiver.getSenderWidth())
                    height = int(receiver.getSenderHeight())

                    if is_connected != connected:
                        connected = is_connected
                        with self._lock:
                            self._connected = connected
                            if not connected:
                                self._latest_frame = None
                        if connected:
                            last_frame_at = time.monotonic()
                            self._emit_status(
                                "connected",
                                f"Spout接続: {self._sender_name}",
                            )
                        else:
                            self._emit_status("waiting", f"Spout送信待ち: {self._sender_name}")
                            pixels = None
                            texture_size = None

                    if not connected:
                        now = time.monotonic()
                        if now >= next_sender_check:
                            next_sender_check = now + 1.0
                            senders = [str(name) for name in receiver.getSenderList()]
                            if senders:
                                detected = ", ".join(senders[:5])
                                self._emit_status(
                                    "waiting",
                                    f"Spout送信待ち: {self._sender_name}（検出: {detected}）",
                                )
                        self._stop_event.wait(0.05)
                        continue

                    if time.monotonic() - last_frame_at >= FRAME_TIMEOUT:
                        raise TimeoutError(f"接続中に{FRAME_TIMEOUT:g}秒間フレームを取得できませんでした")

                    size = (width, height)
                    if width <= 0 or height <= 0:
                        self._stop_event.wait(0.01)
                        continue

                    if bool(receiver.isUpdated()) or texture_size != size:
                        gl.glBindTexture(GL_TEXTURE_2D, texture.value)
                        gl.glTexImage2D(
                            GL_TEXTURE_2D,
                            0,
                            GL_RGBA,
                            width,
                            height,
                            0,
                            GL_RGBA,
                            GL_UNSIGNED_BYTE,
                            None,
                        )
                        pixels = np.empty((height, width, 4), dtype=np.uint8)
                        texture_size = size
                        continue

                    if result and bool(receiver.isFrameNew()) and pixels is not None:
                        gl.glBindTexture(GL_TEXTURE_2D, texture.value)
                        gl.glGetTexImage(
                            GL_TEXTURE_2D,
                            0,
                            GL_RGBA,
                            GL_UNSIGNED_BYTE,
                            pixels.ctypes.data_as(ctypes.c_void_p),
                        )
                        rgb = pixels[:, :, :3]
                        if size != TARGET_SIZE:
                            rgb = cv2.resize(rgb, TARGET_SIZE, interpolation=cv2.INTER_AREA)
                        else:
                            rgb = np.ascontiguousarray(rgb)
                        with self._lock:
                            self._latest_frame = rgb
                            frame_callback = self.frame_callback
                        last_frame_at = time.monotonic()
                        if frame_callback is not None:
                            frame_callback(rgb)

                    receiver.waitFrameSync(self._sender_name, 16)
        finally:
            if gl is not None and texture.value:
                try:
                    gl.glDeleteTextures(1, ctypes.byref(texture))
                except Exception:
                    pass
            if context is not None:
                try:
                    context.doneCurrent()
                except Exception:
                    pass
