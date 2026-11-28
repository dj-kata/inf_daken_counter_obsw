"""OBSへドラッグできるHTMLテンプレートのカタログ。"""

from dataclasses import dataclass
from pathlib import Path
import sys

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, QUrl, QUrlQuery
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class HtmlView:
    filename: str
    title_ja: str
    title_en: str
    description_ja: str
    description_en: str
    width: int
    height: int
    thumbnail_filename: str | None = None
    idle_display_options: bool = False

    @property
    def source_name(self) -> str:
        return f"infdc_{Path(self.filename).stem}"

    def title(self, language: str) -> str:
        return self.title_en if language == "en" else self.title_ja

    def description(self, language: str) -> str:
        return self.description_en if language == "en" else self.description_ja


# 先頭4件は、初めて使う人に勧める主要ビューとして順序を固定する。
HTML_VIEWS = (
    HtmlView(
        "whole_layout.html", "配信画面レイアウト", "Streaming layout",
        "時計・履歴・グラフなどをまとめて表示", "Combined clock, history, graph, and more",
        1920, 1080, "view-whole-layout.png",
    ),
    HtmlView(
        "history_cursong.html", "現在の曲のプレー履歴", "Current song history",
        "現在選択している曲のプレー履歴", "Play history for the currently selected song",
        1920, 1080, "view-history.png",
    ),
    HtmlView(
        "today_receipt.html", "本日の成果レシート", "Today's achievements receipt",
        "本日の更新内容をレシート形式で表示", "Today's updates in a receipt-style view",
        1500, 1500, "view-receipt.png",
    ),
    HtmlView(
        "today_result.html", "本日のプレーログ", "Today's play log",
        "本日のプレー結果を一覧表示", "List of today's play results",
        1920, 1080, "view-today-result.png",
    ),
    HtmlView(
        "today_stats.html", "本日の統計", "Today's statistics",
        "打鍵数・レベル別統計とプレーログ", "Notes, level statistics, and play log",
        2600, 2200, "view-today-stats.png",
    ),
    HtmlView(
        "rival.html", "ライバル比較", "Rival comparison",
        "現在の曲と登録ライバルを比較", "Compare the current song with registered rivals",
        1920, 1080, "view-rival.png",
    ),
    HtmlView(
        "graph.html", "ノーツ数グラフ", "Notes graph",
        "本日のノーツ数の推移", "Today's notes progress",
        500, 250, "view-graph.png",
    ),
    HtmlView(
        "random_lane.html", "RANDOMレーン配置", "RANDOM lane layout",
        "認識したSPのレーン配置", "Recognized SP lane layout",
        800, 200, "view-random-lane.png", True,
    ),
    HtmlView(
        "option.html", "プレーオプション", "Play options",
        "現在のプレーオプション", "Current play options", 500, 250,
        "view-option.png",
    ),
    HtmlView(
        "all_info.html", "複合情報ビュー", "Combined information view",
        "履歴・ライバル・グラフ・レシートをまとめて表示", "Combined history, rivals, graph, and receipt",
        3000, 1080, "view-all-info.png",
    ),
    HtmlView(
        "column_log_cur_graph.html", "横並びダッシュボード", "Horizontal dashboard",
        "プレーログ・単曲履歴・グラフを横並びで表示", "Play log, song history, and graph side by side",
        4100, 440, "view-column-log-cur-graph.png",
    ),
)


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def build_obs_source_url(
    view: HtmlView,
    server_port: int,
    show_when_idle: bool = True,
) -> QUrl:
    """OBSのURLドロップが解釈するソース名とサイズを付ける。"""
    source_url = QUrl(f"http://127.0.0.1:{server_port}/template/{view.filename}")
    query = QUrlQuery()
    query.addQueryItem("layer-name", view.source_name)
    query.addQueryItem("layer-width", str(view.width))
    query.addQueryItem("layer-height", str(view.height))
    if view.idle_display_options:
        query.addQueryItem("show_when_idle", "1" if show_when_idle else "0")
    source_url.setQuery(query)
    return source_url


def thumbnail_path(view: HtmlView, template_dir: Path) -> Path | None:
    if not view.thumbnail_filename:
        return None
    packaged_path = template_dir / "thumbnails" / view.thumbnail_filename
    if packaged_path.exists():
        return packaged_path
    development_path = (
        template_dir.parent / "docs" / "images" / "wiki" / view.thumbnail_filename
    )
    return development_path if development_path.exists() else packaged_path


class HtmlDragLabel(QLabel):
    def __init__(self, text: str, source_url: QUrl, drag_pixmap: QPixmap, parent=None):
        super().__init__(text, parent)
        self.source_url = source_url
        self.drag_pixmap = drag_pixmap
        self.drag_start_position = QPoint()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMinimumHeight(42)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #6aa9ff; border-radius: 6px;"
            " background: #17304f; color: white; font-weight: bold; padding: 6px; }"
            "QLabel:hover { background: #214a78; }"
            "QLabel:disabled { border-color: #666; background: #333; color: #999; }"
        )

    def set_source(self, source_url: QUrl):
        self.source_url = source_url

    def set_available(self, available: bool):
        self.setEnabled(available)
        self.setCursor(
            Qt.CursorShape.OpenHandCursor if available else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.isEnabled():
            return
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return
        distance = (event.position().toPoint() - self.drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        mime_data = QMimeData()
        mime_data.setUrls([self.source_url])
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        if not self.drag_pixmap.isNull():
            preview = self.drag_pixmap.scaled(
                QSize(240, 140),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            drag.setPixmap(preview)
            drag.setHotSpot(QPoint(preview.width() // 2, preview.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class HtmlViewCard(QFrame):
    def __init__(
        self,
        view: HtmlView,
        template_dir: Path,
        server_port: int,
        server_running: bool,
        language: str,
        parent=None,
    ):
        super().__init__(parent)
        self.view = view
        self.server_port = server_port
        self.show_when_idle = True
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #555; border-radius: 8px; background: #252525; }"
            "QLabel { border: none; background: transparent; color: #eee; }"
            "QRadioButton { border: none; color: #eee; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        pixmap = QPixmap()
        preview_path = thumbnail_path(view, template_dir)
        if preview_path is not None:
            pixmap = QPixmap(str(preview_path))
        thumbnail = QLabel()
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setFixedSize(400, 220)
        thumbnail.setStyleSheet("background: #111; border-radius: 5px;")
        if pixmap.isNull():
            thumbnail.setText(view.filename)
        else:
            thumbnail.setPixmap(
                pixmap.scaled(
                    thumbnail.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(thumbnail)

        title = QLabel(view.title(language))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        description = QLabel(view.description(language))
        description.setStyleSheet("color: #ccc;")
        layout.addWidget(description)

        if view.idle_display_options:
            options = QWidget()
            options_layout = QHBoxLayout(options)
            options_layout.setContentsMargins(0, 0, 0, 0)
            options_layout.setSpacing(12)
            options_layout.addWidget(
                QLabel("Display:" if language == "en" else "表示:")
            )
            self.always_radio = QRadioButton(
                "Always" if language == "en" else "常時表示"
            )
            self.play_only_radio = QRadioButton(
                "During play only" if language == "en" else "プレー中のみ"
            )
            self.always_radio.setChecked(True)
            self.idle_button_group = QButtonGroup(self)
            self.idle_button_group.addButton(self.always_radio)
            self.idle_button_group.addButton(self.play_only_radio)
            options_layout.addWidget(self.always_radio)
            options_layout.addWidget(self.play_only_radio)
            options_layout.addStretch()
            layout.addWidget(options)

        size_prefix = "Recommended size" if language == "en" else "推奨サイズ"
        size_label = QLabel(f"{size_prefix}: {view.width} × {view.height}")
        size_label.setStyleSheet("color: #a9cfff;")
        layout.addWidget(size_label)

        drag_text = "Drag here to OBS" if language == "en" else "ここをOBSへD&D"
        self.drag_label = HtmlDragLabel(
            drag_text,
            build_obs_source_url(view, server_port, self.show_when_idle),
            pixmap,
            self,
        )
        tooltip = (
            "Drag this area onto the OBS preview."
            if language == "en"
            else "この部分をOBSのプレビュー画面へドラッグしてください"
        )
        self.drag_label.setToolTip(tooltip)
        self.drag_label.set_available(server_running)
        layout.addWidget(self.drag_label)

        if view.idle_display_options:
            self.always_radio.toggled.connect(self.update_source)

    def set_server(self, server_port: int, running: bool):
        self.server_port = server_port
        self.update_source()
        self.drag_label.set_available(running)

    def update_source(self, *_):
        if self.view.idle_display_options:
            self.show_when_idle = self.always_radio.isChecked()
        self.drag_label.set_source(
            build_obs_source_url(
                self.view,
                self.server_port,
                self.show_when_idle,
            )
        )


class HtmlCatalogWindow(QWidget):
    def __init__(
        self,
        server_port: int,
        server_running: bool = True,
        port_change_callback=None,
        template_dir: Path | None = None,
        language: str = "ja",
        parent=None,
    ):
        super().__init__(parent, Qt.WindowType.Window)
        self.server_port = server_port
        self.server_running = server_running
        self.port_change_callback = port_change_callback
        self.language = language
        template_dir = Path(template_dir) if template_dir else application_root() / "template"
        self.setWindowTitle(
            "OBS Templates - HTML Catalog"
            if language == "en"
            else "OBS用テンプレート - HTMLカタログ"
        )
        self.resize(920, 720)
        self.setMinimumSize(500, 420)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        port_layout = QHBoxLayout()
        port_label = QLabel("Template HTTP port:" if language == "en" else "テンプレート配信用ポート:")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(server_port)
        self.apply_port_button = QPushButton("Apply" if language == "en" else "適用")
        self.apply_port_button.clicked.connect(self.apply_port)
        self.port_status = QLabel()
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_spin)
        port_layout.addWidget(self.apply_port_button)
        port_layout.addWidget(self.port_status)
        port_layout.addStretch()
        outer_layout.addLayout(port_layout)

        port_warning = QLabel(
            "After changing the port, remove existing OBS sources and drag them again."
            if language == "en"
            else "ポート変更後は、既存のOBSソースを削除してD&Dし直してください。"
        )
        port_warning.setStyleSheet("color: #d08000; padding: 0 4px 6px 4px;")
        port_warning.setWordWrap(True)
        outer_layout.addWidget(port_warning)
        self.update_port_status()

        guide_text = (
            "Drag 'Drag here to OBS' for the desired view onto the OBS preview. "
            "Choose Yes if OBS asks for confirmation."
            if language == "en"
            else "使いたいビューの「ここをOBSへD&D」を、OBSのプレビュー画面へドラッグしてください。"
            "確認画面が表示された場合は「はい」を選んでください。"
        )
        guide = QLabel(guide_text)
        guide.setWordWrap(True)
        guide.setStyleSheet("font-size: 14px; padding: 2px 4px 8px 4px;")
        outer_layout.addWidget(guide)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll_area)

        contents = QWidget()
        grid = QGridLayout(contents)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.cards = []
        for index, view in enumerate(HTML_VIEWS):
            card = HtmlViewCard(
                view,
                template_dir,
                server_port,
                server_running,
                language,
            )
            self.cards.append(card)
            grid.addWidget(card, index // 2, index % 2)
        scroll_area.setWidget(contents)

    def apply_port(self):
        requested_port = self.port_spin.value()
        if self.port_change_callback is None:
            return
        if not self.port_change_callback(requested_port):
            if self.server_running:
                self.port_spin.setValue(self.server_port)
            title = "OBS Templates" if self.language == "en" else "OBS用テンプレート"
            message = (
                f"Port {requested_port} is already in use. Choose another port."
                if self.language == "en"
                else f"ポート {requested_port} は使用中です。別のポートを指定してください。"
            )
            QMessageBox.warning(self, title, message)
            self.update_port_status()
            return

        self.server_port = requested_port
        self.server_running = True
        for card in self.cards:
            card.set_server(requested_port, True)
        self.update_port_status()

    def update_port_status(self):
        if self.server_running:
            text = "Running" if self.language == "en" else "起動中"
            self.port_status.setStyleSheet("color: #188038; font-weight: bold;")
        else:
            text = "Unavailable" if self.language == "en" else "使用不可"
            self.port_status.setStyleSheet("color: #d93025; font-weight: bold;")
        self.port_status.setText(text)
