"""Application-wide light/dark theme support."""

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory


THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_MODES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


def normalize_theme_mode(value) -> str:
    return value if value in THEME_MODES else THEME_SYSTEM


def contrasting_text_color(background: QColor) -> QColor:
    """Return black or white according to the WCAG relative luminance."""
    color = QColor(background)

    def linear(channel):
        channel /= 255.0
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear(color.red())
        + 0.7152 * linear(color.green())
        + 0.0722 * linear(color.blue())
    )
    return QColor("#000000" if luminance > 0.179 else "#ffffff")


def set_item_background(item, color):
    """Set a table item's background and a readable matching foreground."""
    background = QColor(color)
    item.setBackground(background)
    item.setForeground(contrasting_text_color(background))


def is_dark_palette(palette=None) -> bool:
    palette = palette or QApplication.palette()
    return (
        palette.color(QPalette.ColorRole.Window).lightness()
        < palette.color(QPalette.ColorRole.WindowText).lightness()
    )


def semantic_text_color(kind: str) -> str:
    dark = is_dark_palette()
    colors = {
        "success": ("#1b5e20", "#81c784"),
        "error": ("#b71c1c", "#ff8a80"),
        "info": ("#0d47a1", "#90caf9"),
        "warning": ("#8a4f00", "#ffcc80"),
    }
    light_color, dark_color = colors[kind]
    return dark_color if dark else light_color


def _dark_palette(base_palette: QPalette) -> QPalette:
    palette = QPalette(base_palette)
    roles = {
        QPalette.ColorRole.Window: "#2b2b2b",
        QPalette.ColorRole.WindowText: "#f0f0f0",
        QPalette.ColorRole.Base: "#1f1f1f",
        QPalette.ColorRole.AlternateBase: "#303030",
        QPalette.ColorRole.ToolTipBase: "#f0f0f0",
        QPalette.ColorRole.ToolTipText: "#1f1f1f",
        QPalette.ColorRole.Text: "#f0f0f0",
        QPalette.ColorRole.Button: "#363636",
        QPalette.ColorRole.ButtonText: "#f0f0f0",
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Link: "#78b7ff",
        QPalette.ColorRole.LinkVisited: "#c59cff",
        QPalette.ColorRole.Highlight: "#3478bd",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#a0a0a0",
        QPalette.ColorRole.Light: "#505050",
        QPalette.ColorRole.Midlight: "#424242",
        QPalette.ColorRole.Dark: "#202020",
        QPalette.ColorRole.Mid: "#292929",
        QPalette.ColorRole.Shadow: "#000000",
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#858585"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor("#454545"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor("#858585"))
    return palette


class _ThemeManager(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.mode = THEME_SYSTEM
        self.light_palette = QStyleFactory.create("Fusion").standardPalette()
        app.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)

    def apply(self, mode: str):
        self.mode = normalize_theme_mode(mode)
        requested = {
            THEME_SYSTEM: Qt.ColorScheme.Unknown,
            THEME_LIGHT: Qt.ColorScheme.Light,
            THEME_DARK: Qt.ColorScheme.Dark,
        }[self.mode]
        self.app.styleHints().setColorScheme(requested)
        effective_dark = self.mode == THEME_DARK or (
            self.mode == THEME_SYSTEM
            and self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        self.app.setPalette(
            _dark_palette(self.light_palette) if effective_dark else self.light_palette
        )

    @Slot(Qt.ColorScheme)
    def _system_scheme_changed(self, _scheme):
        if self.mode == THEME_SYSTEM:
            self.apply(self.mode)


_manager = None


def apply_application_theme(app: QApplication, mode: str):
    global _manager
    if _manager is None or _manager.app is not app:
        _manager = _ThemeManager(app)
    _manager.apply(mode)
