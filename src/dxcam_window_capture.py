"""DXGI Desktop Duplication based game screen capture."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

import numpy as np
from PIL import Image

from src.config import Config
from src.direct_window_capture import DirectWindowCapture
from src.infnotebook_compat import np_image_to_screen
from src.logger import get_logger

logger = get_logger(__name__)

_LANDSCAPE_SIZE = (1920, 1080)
_MONITOR_DEFAULTTONEAREST = 0x00000002


class DxcamWindowCapture:
    """Capture the monitor containing the configured game window via dxcam."""

    def __init__(self, config: Config):
        self.config = config
        self.window = DirectWindowCapture(config)
        self.camera = None
        self.hwnd: int | None = None
        self.monitor_handle: int | None = None
        self.last_error = ""
        self.has_successful_frame = False
        self.read_attempt_count = 0
        self._next_error_log_at = 0.0
        self._next_start_attempt_at = 0.0

    def set_config(self, config: Config) -> None:
        self.config = config
        self.window.set_config(config)
        self.close()
        self.last_error = ""
        self.has_successful_frame = False
        self.read_attempt_count = 0
        self._next_start_attempt_at = 0.0

    def close(self) -> None:
        camera = self.camera
        self.camera = None
        self.hwnd = None
        self.monitor_handle = None
        if camera is None:
            return
        try:
            if getattr(camera, "is_capturing", False):
                camera.stop()
        except Exception:
            pass
        try:
            camera.release()
        except Exception:
            pass

    def is_waiting_for_target(self) -> bool:
        return self.window.is_waiting_for_target()

    def clear_pending_error(self) -> None:
        self.window.clear_pending_error()
        if self.is_waiting_for_target():
            self.last_error = ""

    def read_frame(self) -> Image.Image | None:
        frame = self._grab_frame()
        if frame is None:
            return None

        image = Image.fromarray(frame).convert("RGB")
        return self._normalize_size(image)

    def read_screen(self, filename: str = "direct_capture.png"):
        frame = self._grab_frame()
        if frame is None:
            return None

        frame = self._normalize_frame(frame)
        return np_image_to_screen(frame, filename)

    def _grab_frame(self) -> np.ndarray | None:
        self.read_attempt_count += 1
        if self.read_attempt_count <= 3:
            logger.info("DXCAM直接キャプチャ試行: %s回目", self.read_attempt_count)

        if not sys.platform.startswith("win"):
            self.last_error = "DXCAM直接取得はWindows専用です"
            self.has_successful_frame = False
            return None

        if not self._ensure_camera():
            self.has_successful_frame = False
            return None

        try:
            frame = self.camera.grab()
        except Exception as e:
            self.last_error = f"DXCAMで画面取得できませんでした: {e}"
            self.has_successful_frame = False
            self._log_error(self.last_error)
            self.close()
            self._next_start_attempt_at = time.monotonic() + 3.0
            return None

        if frame is None:
            self.last_error = "DXCAMで画面取得できませんでした"
            self.has_successful_frame = False
            return None

        self.last_error = ""
        self.has_successful_frame = True
        return frame

    def _ensure_camera(self) -> bool:
        if self.camera is not None and self.hwnd and self.window._is_window_usable(self.hwnd):
            return True

        now = time.monotonic()
        if now < self._next_start_attempt_at:
            return False

        self.close()
        hwnd = self.window._ensure_window()
        self.last_error = self.window.last_error
        if not hwnd:
            self._next_start_attempt_at = now + 3.0
            return False

        hmonitor = self._monitor_from_window(hwnd)
        if not hmonitor:
            self.last_error = "対象ウィンドウのモニターを特定できません"
            self._log_error(self.last_error)
            self._next_start_attempt_at = now + 3.0
            return False

        try:
            camera = self._create_camera_for_monitor(hmonitor)
        except ImportError:
            self.last_error = "dxcam がインストールされていません"
            self._log_error(self.last_error)
            self._next_start_attempt_at = now + 30.0
            return False
        except Exception as e:
            self.last_error = f"DXCAM初期化に失敗しました: {e}"
            self._log_error(self.last_error)
            self._next_start_attempt_at = now + 3.0
            return False

        if camera is None:
            self.last_error = "対象モニターに対応するDXCAM出力を特定できません"
            self._log_error(self.last_error)
            self._next_start_attempt_at = now + 3.0
            return False

        try:
            camera.start()
        except Exception as e:
            self.last_error = f"DXCAM開始に失敗しました: {e}"
            self._log_error(self.last_error)
            try:
                camera.release()
            except Exception:
                pass
            self._next_start_attempt_at = now + 3.0
            return False

        self.camera = camera
        self.hwnd = hwnd
        self.monitor_handle = hmonitor
        self.last_error = ""
        self._next_start_attempt_at = 0.0
        logger.info("DXCAM直接キャプチャ開始: hwnd=%s monitor=%s", hwnd, hmonitor)
        return True

    def _monitor_from_window(self, hwnd: int) -> int:
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        return int(user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST) or 0)

    def _create_camera_for_monitor(self, hmonitor: int):
        from dxcam import Device, Output, create, enum_dxgi_adapters

        for device_idx, adapter in enumerate(enum_dxgi_adapters()):
            device = Device(adapter)
            for output_idx, output_ptr in enumerate(device.enum_outputs()):
                output = Output(output_ptr)
                if int(output.hmonitor or 0) == hmonitor:
                    return create(
                        device_idx=device_idx,
                        output_idx=output_idx,
                        output_color="RGB",
                        processor_backend="numpy",
                    )
        return None

    def _normalize_size(self, image: Image.Image) -> Image.Image:
        if image.size == _LANDSCAPE_SIZE:
            return image
        return image.resize(_LANDSCAPE_SIZE, Image.Resampling.LANCZOS)

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if (width, height) == _LANDSCAPE_SIZE:
            return np.ascontiguousarray(frame)

        image = Image.fromarray(frame).resize(_LANDSCAPE_SIZE, Image.Resampling.LANCZOS)
        return np.asarray(image, dtype=np.uint8)

    def _log_error(self, message: str, *args) -> None:
        now = time.monotonic()
        if now < self._next_error_log_at:
            return
        self._next_error_log_at = now + 30.0
        logger.error(message, *args)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
