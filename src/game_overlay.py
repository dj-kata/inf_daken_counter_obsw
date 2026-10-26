"""Game overlays, owned and updated exclusively by the Qt GUI thread."""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time

from PySide6.QtCore import QLibraryInfo, QRectF, Qt, QtMsgType, QUrl, QUrlQuery, qInstallMessageHandler
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.classes import detect_mode
from src.logger import get_logger
from src.webengine_runtime import configure_frozen_webengine, validate_webengine_version

logger = get_logger(__name__)
_qt_message_handler = None


def install_qt_diagnostics():
    """Persist native Qt fatal messages, which aren't Python exceptions."""
    global _qt_message_handler
    if _qt_message_handler is not None:
        return

    def handler(kind, context, message):
        if kind == QtMsgType.QtFatalMsg:
            logger.critical('Qt fatal: %s', message)
        elif kind == QtMsgType.QtCriticalMsg:
            logger.error('Qt critical: %s', message)
        else:
            logger.debug('Qt: %s', message)
        if previous is not None:
            previous(kind, context, message)

    previous = qInstallMessageHandler(handler)
    _qt_message_handler = handler

# Fit beside the scratch on the keyboard panel, below the note field even
# without LIFT. Coordinates are relative to a 1920x1080 game client.
RANDOM_PROFILES = {'1P': (170, 755, .70), '2P': (1421, 755, .70)}
# Keep a small inset inside the marked safe areas of the 1920x1080 screens.
LOG_RECTS = {
    'song_history': (565, 360, 780, 585),
    'today_results': (22, 615, 564, 180),
}
ACTIVE_LANE_PHASES = {'recording', 'registered', 'ready', 'analyzing', 'partial',
                      'confirmed', 'failed', 'needs_normal'}


def visible_overlay(config, mode, state, capture_ready=True):
    """Select an item; unknown/stale game states must never retain a log."""
    if not config.enable_game_overlay or not capture_ready:
        return None
    if mode == detect_mode.result and config.overlay_song_history:
        return 'song_history'
    if mode == detect_mode.select and config.overlay_today_results:
        return 'today_results'
    if (mode == detect_mode.play and config.overlay_random_lane
            and config.enable_random_lane_analysis
            and state.get('phase') in ACTIVE_LANE_PHASES
            and state.get('side') in RANDOM_PROFILES
            and valid_lane_layout(state.get('layout'))):
        return 'random_lane'
    return None


def valid_lane_layout(layout):
    if not isinstance(layout, str) or len(layout) != 7 or layout == '???????':
        return False
    if any(ch not in '1234567WB?' for ch in layout):
        return False
    known = [ch for ch in layout if ch in '1234567']
    return (len(set(known)) == len(known)
            and sum(ch in '1357W' for ch in layout) <= 4
            and sum(ch in '246B' for ch in layout) <= 3)


def lane_colors(character):
    if character == '?':
        return '#777777', '#000000'
    if character in '246B':
        return '#0066cc', '#ffff00'
    return '#ffffff', '#d00000' if character == '1' else '#000000'


def scaled_rect(rect, game_bbox):
    x, y, width, height = rect
    left, top, right, bottom = game_bbox
    sx, sy = (right - left) / 1920, (bottom - top) / 1080
    return (round(left + x * sx), round(top + y * sy),
            max(1, round(width * sx)), max(1, round(height * sy)))


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self._desktop_rect = None
        if sys.platform == 'win32':
            affinity = ctypes.windll.user32.SetWindowDisplayAffinity
            affinity.argtypes = (wintypes.HWND, wintypes.DWORD)
            affinity.restype = wintypes.BOOL
            # Keep overlays out of desktop/GDI captures used by OCR.
            if not affinity(int(self.winId()), 0x11):  # WDA_EXCLUDEFROMCAPTURE
                logger.warning('Could not exclude game overlay from screen capture')

    def present(self, rect):
        changed = self._desktop_rect != rect or not self.isVisible()
        if not changed:
            return
        self._desktop_rect = rect
        if sys.platform != 'win32':
            self.setGeometry(*rect)
        else:
            # SetWindowPos alone can leave QWidget's cached size (and the
            # browser viewport) at 0x0. Initialize Qt's logical size as well.
            dpr = self.devicePixelRatioF()
            self.resize(max(1, round(rect[2] / dpr)), max(1, round(rect[3] / dpr)))
        self.show()
        if sys.platform == 'win32':
            # Native desktop pixels keep placement correct with mixed DPI and
            # monitors at negative coordinates; Qt handles the resulting resize.
            set_pos = ctypes.windll.user32.SetWindowPos
            set_pos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
            set_pos.restype = wintypes.BOOL
            if not set_pos(int(self.winId()), wintypes.HWND(-1), *rect, 0x0010):
                logger.warning('Failed to position game overlay: %s', rect)


class RandomLaneOverlay(OverlayWindow):
    def __init__(self):
        super().__init__()
        self.layout_text = ''
        self.setWindowTitle('INFINITAS RANDOM overlay')

    def set_layout(self, layout):
        if self.layout_text != layout:
            self.layout_text = layout
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Same panel/key geometry as the original, with this app's lane colors.
        painter.scale(self.width() / 470, self.height() / 96)
        painter.fillRect(QRectF(0, 0, 470, 96), QColor('#171717'))
        painter.setFont(QFont('Consolas', 30, QFont.Bold))
        for i, ch in enumerate(self.layout_text):
            rect = QRectF(14 + i * 64, 12, 58, 72)
            background, foreground = lane_colors(ch)
            painter.fillRect(rect, QColor(background))
            painter.setPen(QPen(QColor('#000000'), 2))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            if ch in '1234567':
                painter.setPen(QColor(foreground))
                painter.drawText(rect, Qt.AlignCenter, ch)


class HtmlLogOverlay(OverlayWindow):
    def __init__(self, template_dir):
        install_qt_diagnostics()
        if getattr(sys, 'frozen', False) and sys.platform == 'win32':
            paths = configure_frozen_webengine(Path(sys.executable).parent)
            logger.info('Qt WebEngine runtime: %s', paths)
        validate_webengine_version(QLibraryInfo.version().toString())
        super().__init__()
        # Do not start Chromium or load its libraries while overlays are disabled
        # or when only the native RANDOM panel is enabled.
        from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile,
                                           QWebEngineScript, QWebEngineSettings,
                                           QWebEngineUrlRequestInterceptor, qWebEngineVersion)
        validate_webengine_version(qWebEngineVersion())
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self.template_dir = Path(template_dir)
        self.view = QWebEngineView(self)
        # An off-the-record profile needs no persistent browser cache. The view
        # is the first child, so its page is destroyed before this profile.
        self.profile = QWebEngineProfile(self)
        class OfflineFonts(QWebEngineUrlRequestInterceptor):
            def interceptRequest(self, info):
                # The game overlay must load while offline, too. Keep the
                # templates' local assets and loopback WebSocket available.
                if info.requestUrl().host() in ('fonts.googleapis.com', 'fonts.gstatic.com'):
                    info.block(True)
        self.font_requests = OfflineFonts(self.profile)
        self.profile.setUrlRequestInterceptor(self.font_requests)
        self.view.setPage(QWebEnginePage(self.profile, self.view))
        self.view.setFocusPolicy(Qt.NoFocus)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        self.view.page().setBackgroundColor(QColor(Qt.transparent))
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        script = QWebEngineScript()
        script.setName('Fit game overlay')
        script.setInjectionPoint(QWebEngineScript.DocumentReady)
        script.setWorldId(QWebEngineScript.MainWorld)
        script.setSourceCode((self.template_dir / 'game_overlay.js').read_text(encoding='utf-8'))
        self.view.page().scripts().insert(script)
        self._source = None
        self.setWindowTitle('INFINITAS log overlay')

    def set_source(self, item, port, show_lane_numbers=False):
        source = (item, port, bool(show_lane_numbers))
        if source == self._source:
            return
        self._source = source
        filename = 'history_cursong.html' if item == 'song_history' else 'today_result.html'
        path = self.template_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        url = QUrl.fromLocalFile(str(path.resolve()))
        query = QUrlQuery()
        query.addQueryItem('websocket_host', '127.0.0.1')
        query.addQueryItem('websocket_port', str(port))
        query.addQueryItem('show_lane_numbers', '1' if show_lane_numbers else '0')
        if item == 'today_results':
            query.addQueryItem('max_rows', '6')
        url.setQuery(query)
        self.view.setUrl(url)


class GameOverlay:
    def __init__(self, config, template_dir=None, error_callback=None):
        self.config = config
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
        self.template_dir = Path(template_dir) if template_dir else base / 'template'
        self.error_callback = error_callback
        self.random_window = None
        self.log_window = None
        self._log_failed = False
        self._target = None
        self._game_bbox = None
        self._next_target_check = 0
        self._closed = False

    def set_config(self, config):
        self.config = config
        self.close()
        self._closed = False

    def _target_bbox(self):
        if sys.platform != 'win32':
            return None
        now = time.monotonic()
        if now >= self._next_target_check:
            self._next_target_check = now + .5
            if self._target is None:
                from src.direct_window_capture import DirectWindowCapture
                self._target = DirectWindowCapture(self.config)
            self._game_bbox = self._target.get_target_bbox()
        return self._game_bbox

    def update(self, mode, state, port, capture_ready=True):
        if self._closed:
            return
        item = visible_overlay(self.config, mode, state, capture_ready)
        bbox = self._target_bbox() if item else None
        if not bbox or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            item = None
        if self.random_window is not None and item != 'random_lane':
            self.random_window.hide()
        if self.log_window is not None and item not in ('song_history', 'today_results'):
            self.log_window.hide()
        if item == 'random_lane':
            if self.random_window is None:
                self.random_window = RandomLaneOverlay()
            self.random_window.set_layout(state['layout'])
            x, y, scale = RANDOM_PROFILES[state['side']]
            self.random_window.present(scaled_rect((x, y, 470 * scale, 96 * scale), bbox))
        elif item in ('song_history', 'today_results') and not self._log_failed:
            try:
                if self.log_window is None:
                    self.log_window = HtmlLogOverlay(self.template_dir)
                self.log_window.set_source(
                    item, port, show_lane_numbers=self.config.overlay_show_lane_numbers
                )
                self.log_window.present(scaled_rect(LOG_RECTS[item], bbox))
            except Exception:
                self._log_failed = True
                logger.exception('Failed to initialize game log overlay')
                if self.error_callback:
                    self.error_callback()

    def close(self):
        self._closed = True
        for window in (self.random_window, self.log_window):
            if window is not None:
                window.close()
                window.deleteLater()
        self.random_window = self.log_window = self._target = None
        self._log_failed = False
        self._game_bbox = None
        self._next_target_check = 0
