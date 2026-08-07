"""WindowsゲームウィンドウをPIL Imageとして直接取得する。"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageGrab
from PySide6.QtGui import QGuiApplication, QImage

from src.config import Config
from src.logger import get_logger

logger = get_logger(__name__)

_LANDSCAPE_SIZE = (1920, 1080)
_MONITORINFOF_PRIMARY = 0x00000001
_SRCCOPY = 0x00CC0020
_DIB_RGB_COLORS = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_byte),
        ("rgbGreen", ctypes.c_byte),
        ("rgbRed", ctypes.c_byte),
        ("rgbReserved", ctypes.c_byte),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", ctypes.POINTER(_RGBQUAD)),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class DirectWindowCapture:
    """指定exe/タイトルのウィンドウを直接キャプチャする薄いラッパー。"""

    def __init__(self, config: Config):
        self.config = config
        self.hwnd: int | None = None
        self.last_error = ""
        self.has_successful_frame = False
        self.read_attempt_count = 0
        self._next_error_log_at = 0.0

    def set_config(self, config: Config) -> None:
        self.config = config
        self.hwnd = None
        self.last_error = ""
        self.has_successful_frame = False
        self.read_attempt_count = 0

    def read_frame(self) -> Image.Image | None:
        self.read_attempt_count += 1
        if self.read_attempt_count <= 3:
            logger.info("直接キャプチャ試行: %s回目", self.read_attempt_count)

        try:
            if not sys.platform.startswith("win"):
                self.last_error = "直接取得はWindows専用です"
                self.has_successful_frame = False
                return None

            hwnd = self._ensure_window()
            if not hwnd:
                self.has_successful_frame = False
                return None

            x, y, width, height = self._client_geometry(hwnd)
            if width <= 0 or height <= 0:
                self.last_error = "対象ウィンドウのクライアント領域を取得できません"
                self.hwnd = None
                self.has_successful_frame = False
                return None

            image = self._grab_client_area(hwnd, x, y, width, height)
            if image is None:
                self.last_error = "対象ウィンドウの画像取得に失敗しました"
                self.hwnd = None
                self.has_successful_frame = False
                return None

            self.last_error = ""
            self.has_successful_frame = True
            return self._normalize_size(image)
        except Exception as e:
            self.last_error = str(e)
            self.hwnd = None
            self.has_successful_frame = False
            self._log_error("直接キャプチャエラー: %s", e)
            return None

    def _ensure_window(self) -> int | None:
        if self.hwnd and self._is_window_usable(self.hwnd):
            return self.hwnd

        self.hwnd = self._find_target_window()
        if not self.hwnd:
            exe = self.config.direct_capture_exe
            title = self.config.direct_capture_title
            self.last_error = f"対象ウィンドウが見つかりません: {exe} / {title}"
            self._log_error(self.last_error)
        else:
            self.last_error = ""
            logger.info("直接キャプチャ対象を検出: hwnd=%s", self.hwnd)
        return self.hwnd

    def _find_target_window(self) -> int | None:
        user32 = ctypes.windll.user32
        user32.EnumWindows.argtypes = None
        enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        target_exe = self.config.direct_capture_exe.strip().casefold()
        target_title = self.config.direct_capture_title.strip().casefold()
        fallback_title = "beatmania IIDX INFINITAS".casefold()
        title_matches: list[int] = []
        exe_matches: list[int] = []

        def callback(hwnd, _lparam):
            if not self._is_window_usable(hwnd):
                return True

            title = self._window_text(hwnd)
            exe_name = self._window_process_name(hwnd)
            hwnd_int = int(hwnd)
            title_cf = title.casefold()
            title_matches_target = bool(
                (target_title and target_title in title_cf)
                or fallback_title in title_cf
            )
            exe_matches_target = bool(target_exe and exe_name.casefold() == target_exe)

            if title_matches_target:
                title_matches.append(hwnd_int)
                return False

            if exe_matches_target:
                exe_matches.append(hwnd_int)
            return True

        user32.EnumWindows(enum_windows_proc(callback), 0)
        if title_matches:
            return title_matches[0]
        return exe_matches[0] if exe_matches else None

    def _is_window_usable(self, hwnd: int) -> bool:
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
            return False
        if user32.IsIconic(hwnd):
            return False
        return True

    def _window_text(self, hwnd: int) -> str:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def _window_process_name(self, hwnd: int) -> str:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if not process_id.value:
            return ""

        handle = kernel32.OpenProcess(0x1000, False, process_id.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return ""
            return buffer.value.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(handle)

    def _client_geometry(self, hwnd: int) -> tuple[int, int, int, int]:
        user32 = ctypes.windll.user32
        client_rect = wintypes.RECT()
        window_rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
            return 0, 0, 0, 0
        if not user32.GetWindowRect(hwnd, ctypes.byref(window_rect)):
            return 0, 0, 0, 0

        client_origin = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(client_origin)):
            return 0, 0, 0, 0

        x = client_origin.x - window_rect.left
        y = client_origin.y - window_rect.top
        width = client_rect.right - client_rect.left
        height = client_rect.bottom - client_rect.top
        return x, y, width, height

    def _client_screen_bbox(self, hwnd: int) -> tuple[int, int, int, int] | None:
        user32 = ctypes.windll.user32
        client_rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(client_rect)):
            return None

        top_left = wintypes.POINT(client_rect.left, client_rect.top)
        bottom_right = wintypes.POINT(client_rect.right, client_rect.bottom)
        if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
            return None
        if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
            return None
        return top_left.x, top_left.y, bottom_right.x, bottom_right.y

    def _grab_client_area(self, hwnd: int, x: int, y: int, width: int, height: int) -> Image.Image | None:
        bbox = self._client_screen_bbox(hwnd)
        if bbox is not None:
            image = self._grab_with_gdi(bbox)
            if image is not None:
                return image

        if bbox is not None:
            try:
                all_screens = self._should_grab_all_screens(bbox)
                return ImageGrab.grab(bbox=bbox, all_screens=all_screens).convert("RGB")
            except Exception as e:
                self._log_error("ImageGrabで直接キャプチャできませんでした: %s", e)

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None

        pixmap = screen.grabWindow(hwnd, x, y, width, height)
        if pixmap.isNull():
            return None
        return self._qimage_to_pil(pixmap.toImage())

    def _grab_with_gdi(self, bbox: tuple[int, int, int, int]) -> Image.Image | None:
        left, top, right, bottom = bbox
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        gdi32 = ctypes.windll.gdi32
        screen_dc = gdi32.CreateDCW("DISPLAY", None, None, None)
        if not screen_dc:
            return None

        memory_dc = None
        bitmap = None
        try:
            memory_dc = gdi32.CreateCompatibleDC(screen_dc)
            bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
            if not memory_dc or not bitmap:
                return None

            gdi32.SelectObject(memory_dc, bitmap)
            if not gdi32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, left, top, _SRCCOPY):
                return None

            bitmap_info = _BITMAPINFO()
            bitmap_info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bitmap_info.bmiHeader.biWidth = width
            bitmap_info.bmiHeader.biHeight = height
            bitmap_info.bmiHeader.biPlanes = 1
            bitmap_info.bmiHeader.biBitCount = 24
            bitmap_info.bmiHeader.biCompression = 0
            bitmap_info.bmiHeader.biSizeImage = 0

            stride = ((width * 3 + 3) // 4) * 4
            buffer = ctypes.create_string_buffer(stride * height)
            if not gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(bitmap_info), _DIB_RGB_COLORS):
                return None

            return Image.frombytes("RGB", (width, height), buffer, "raw", "BGR", stride, -1).copy()
        except Exception as e:
            self._log_error("GDIで直接キャプチャできませんでした: %s", e)
            return None
        finally:
            if bitmap:
                gdi32.DeleteObject(bitmap)
            if memory_dc:
                gdi32.DeleteDC(memory_dc)
            gdi32.DeleteDC(screen_dc)

    def _should_grab_all_screens(self, bbox: tuple[int, int, int, int]) -> bool:
        if bool(getattr(self.config, "direct_capture_all_monitors", False)):
            return True

        primary_rect = self._primary_monitor_rect()
        if primary_rect is None:
            return False

        left, top, right, bottom = bbox
        primary_left, primary_top, primary_right, primary_bottom = primary_rect
        return (
            left < primary_left
            or top < primary_top
            or right > primary_right
            or bottom > primary_bottom
        )

    def _primary_monitor_rect(self) -> tuple[int, int, int, int] | None:
        user32 = ctypes.windll.user32
        user32.EnumDisplayMonitors.argtypes = None
        result: list[tuple[int, int, int, int]] = []
        enum_monitor_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HANDLE,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )

        def callback(hmonitor, _hdc, _rect, _lparam):
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                if info.dwFlags & _MONITORINFOF_PRIMARY:
                    rect = info.rcMonitor
                    result.append((rect.left, rect.top, rect.right, rect.bottom))
                    return False
            return True

        if not user32.EnumDisplayMonitors(None, None, enum_monitor_proc(callback), 0):
            return None
        return result[0] if result else None

    def _qimage_to_pil(self, image: QImage) -> Image.Image:
        image = image.convertToFormat(QImage.Format.Format_RGB888)
        width = image.width()
        height = image.height()
        stride = image.bytesPerLine()
        data = image.constBits().tobytes()
        return Image.frombytes("RGB", (width, height), data, "raw", "RGB", stride).copy()

    def _normalize_size(self, image: Image.Image) -> Image.Image:
        if image.size == _LANDSCAPE_SIZE:
            return image
        return image.resize(_LANDSCAPE_SIZE, Image.Resampling.LANCZOS)

    def _log_error(self, message: str, *args) -> None:
        now = time.monotonic()
        if now < self._next_error_log_at:
            return
        self._next_error_log_at = now + 30.0
        logger.error(message, *args)
