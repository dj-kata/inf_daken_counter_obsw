"""
メインウィンドウUI - UIレイアウトと表示更新を担当
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QGroupBox, QGridLayout, QPushButton,
                               QMessageBox)
from PySide6.QtGui import QAction, QActionGroup
import time

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

import sys, os
from src.classes import detect_mode
from src.logger import get_logger
from src.funcs import load_ui_text
from src.score_viewer import ScoreViewer
logger = get_logger(__name__)

# UIの型チェック用
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.ui_jp import UIText

class MainWindowUI(QMainWindow):
    """メインウィンドウのUIレイアウトを担当するクラス"""
    def __init__(self, config):
        super().__init__()
        self.config = config

        # UIテキストをロード
        self.ui:UIText = load_ui_text(self.config)
        
        # UIコンポーネントの参照はここで定義（サブクラスから使用可能）
        self.obs_status_label = None
        self.mode_label = None
        self.uptime_label = None
        self.keystroke_label = None
        self.result_count_label = None
        self.last_song_label = None
        self.save_image_button = None
        self.score_viewer = None
    
    def init_ui(self):
        """UI初期化"""
        # ウィンドウタイトル設定（言語対応）
        self.setWindowTitle(self.ui.window.main_title)
        
        self.restore_window_geometry()
        
        # メニューバーの作成
        self.create_menu_bar()
        
        # 中央ウィジェット
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # OBS接続状態グループ
        obs_group = QGroupBox(self.ui.obs.connection_state)
        obs_layout = QHBoxLayout()
        self.obs_status_label = QLabel(self.ui.obs.not_connected)
        self.obs_status_label.setStyleSheet("color: red; font-weight: bold;")
        obs_layout.addWidget(self.obs_status_label)
        obs_group.setLayout(obs_layout)
        main_layout.addWidget(obs_group)
        
        # 状態情報グループ
        status_group = QGroupBox(self.ui.main.other_info)
        status_layout = QGridLayout()
        
        # ラベル作成
        status_layout.addWidget(QLabel(self.ui.main.current_mode), 0, 0)
        self.mode_label = QLabel(self.ui.mode.init)
        status_layout.addWidget(self.mode_label, 0, 1)
        
        status_layout.addWidget(QLabel(self.ui.main.ontime), 1, 0)
        self.uptime_label = QLabel("00:00:00")
        status_layout.addWidget(self.uptime_label, 1, 1)
        
        status_layout.addWidget(QLabel(self.ui.main.today_notes), 2, 0)
        self.keystroke_label = QLabel("0")
        status_layout.addWidget(self.keystroke_label, 2, 1)
        
        status_layout.addWidget(QLabel(self.ui.main.num_saved_results), 3, 0)
        self.result_count_label = QLabel("0")
        status_layout.addWidget(self.result_count_label, 3, 1)
        
        status_layout.addWidget(QLabel(self.ui.main.last_saved_song), 4, 0)
        self.last_song_label = QLabel("---")
        self.last_song_label.setWordWrap(True)
        status_layout.addWidget(self.last_song_label, 4, 1)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # 画像保存ボタン
        save_button_layout = QHBoxLayout()
        self.save_image_button = QPushButton(self.ui.main.save_image)
        self.save_image_button.clicked.connect(self.save_image)
        save_button_layout.addWidget(self.save_image_button)
        main_layout.addLayout(save_button_layout)
        
        # ストレッチでスペースを埋める
        main_layout.addStretch()
        
        # ステータスバー
        self.statusBar().showMessage(self.ui.main.status_ready)
    
    def create_menu_bar(self):
        """メニューバー作成"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu(self.ui.menu.file)
        
        config_action = QAction(self.ui.menu.base_config, self)
        config_action.triggered.connect(self.open_config_dialog)
        file_menu.addAction(config_action)
        
        obs_action = QAction(self.ui.menu.obs_config, self)
        obs_action.triggered.connect(self.open_obs_dialog)
        file_menu.addAction(obs_action)

        file_menu.addSeparator() ##############################################
        
        # 画像保存アクション
        save_image_action = QAction(self.ui.menu.save_image, self)
        save_image_action.setShortcut("F6")
        save_image_action.triggered.connect(self.save_image)
        file_menu.addAction(save_image_action)
        
        file_menu.addSeparator() ##############################################
        
        exit_action = QAction(self.ui.menu.exit, self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ツールメニュー
        tool_menu = menubar.addMenu(self.ui.menu.tool)
        
        tweet_action = QAction(self.ui.menu.tweet, self)
        tweet_action.triggered.connect(self.tweet)
        tool_menu.addAction(tweet_action)
        score_viewer_action = QAction(self.ui.menu.score_viewer, self)
        score_viewer_action.triggered.connect(self.open_score_viewer)
        tool_menu.addAction(score_viewer_action)
        bpi_action = QAction(self.ui.menu.write_bpi_csv, self)
        bpi_action.triggered.connect(self.write_bpi_csv)
        tool_menu.addAction(bpi_action)

        # 言語メニュー
        language_menu = menubar.addMenu(self.ui.menu.language)
        
        # アクショングループ（排他的選択）
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        
        # 日本語
        action_ja = QAction(self.ui.menu.japanese, self)
        action_ja.setCheckable(True)
        action_ja.setChecked(self.config.language == 'ja')
        action_ja.triggered.connect(lambda: self.change_language('ja'))
        language_group.addAction(action_ja)
        language_menu.addAction(action_ja)
        
        # English
        action_en = QAction(self.ui.menu.english, self)
        action_en.setCheckable(True)
        action_en.setChecked(self.config.language == 'en')
        action_en.triggered.connect(lambda: self.change_language('en'))
        language_group.addAction(action_en)
        language_menu.addAction(action_en)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu(self.ui.menu.help)
        
        about_action = QAction(self.ui.menu.about, self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def restore_window_geometry(self):
        """ウィンドウ位置とサイズを復元"""
        self.setMinimumSize(450, 300)
        if self.config.main_window_geometry:
            import base64
            from PySide6.QtCore import QByteArray
            
            geometry_bytes = base64.b64decode(self.config.main_window_geometry)
            geometry = QByteArray(geometry_bytes)
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 450, 300)
    
    def save_window_geometry(self):
        """ジオメトリを保存"""
        import base64
        
        geometry = self.saveGeometry()
        geometry_str = base64.b64encode(geometry.data()).decode('ascii')
        
        self.config.main_window_geometry = geometry_str
        self.config.save_config()
    
    def setup_global_hotkeys(self):
        """グローバルホットキーの設定"""
        if KEYBOARD_AVAILABLE:
            try:
                # F6キーをグローバルホットキーとして登録
                keyboard.add_hotkey('f6', self.save_image, suppress=False)
                logger.info("グローバルホットキー (F6) を登録しました")
            except Exception as e:
                logger.error(f"グローバルホットキー登録エラー: {e}")
                logger.warning("グローバルホットキーの登録に失敗しました。管理者権限で実行してください。")
        else:
            logger.warning("keyboardライブラリが利用できません。グローバルホットキーは無効です。")
    
    def remove_global_hotkeys(self):
        """グローバルホットキーの解除"""
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.remove_hotkey('f6')
                logger.info("グローバルホットキー (F6) を解除しました")
            except Exception as e:
                logger.error(f"グローバルホットキー解除エラー: {e}")
    
    def update_display(self):
        """表示更新"""
        # OBS接続状態
        try:
            status_msg, is_connected = self.obs_manager.get_status()
            self.obs_status_label.setText(status_msg)
            if is_connected:
                self.obs_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.obs_status_label.setStyleSheet("color: red; font-weight: bold;")

            # モード表示
            mode_names = {
                detect_mode.init: self.ui.mode.init,
                detect_mode.play: self.ui.mode.play,
                detect_mode.select: self.ui.mode.select,
                detect_mode.result: self.ui.mode.result,
                detect_mode.option: self.ui.mode.option
            }
            self.mode_label.setText(mode_names.get(self.current_mode, "不明"))

            # 起動時間
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.uptime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            # 統計情報
            self.today_keystroke_count = self.today_judge.notes
            self.keystroke_label.setText(str(self.today_keystroke_count))
            self.result_count_label.setText(str(self.play_count))
            self.last_song_label.setText(self.last_saved_song)
        except:
            import traceback
            logger.debug(traceback.format_exc())

    def open_score_viewer(self):
        """スコアビューワを開く"""
        try:
            # 既に開いている場合は前面に表示
            if self.score_viewer is not None and self.score_viewer.isVisible():
                self.score_viewer.raise_()
                self.score_viewer.activateWindow()
                return
            
            # result_databaseが存在するか確認
            if not hasattr(self, 'result_database') or self.result_database is None:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "警告",
                    "プレーログデータベースが初期化されていません。"
                )
                return
            
            # スコアビューワを作成
            rival_manager = getattr(self, 'rival_manager', None)
            self.score_viewer = ScoreViewer(self.config, self.result_database, rival_manager=rival_manager, parent=self)
            self.score_viewer.show()
            
            from src.logger import get_logger
            logger = get_logger(__name__)
            logger.info("スコアビューワを起動しました")
        
        except Exception as e:
            from src.logger import get_logger
            logger = get_logger(__name__)
            logger.exception("スコアビューワ起動エラー")
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "エラー",
                f"スコアビューワの起動に失敗しました:\n{str(e)}"
            )
    
    def on_result_updated(self):
        """
        プレーログが更新された時に呼ばれる
        （既存のメソッドに追加するか、新規作成）
        """
        # ... 既存の更新処理 ...
        
        # スコアビューワが開いている場合は更新
        if self.score_viewer is not None and self.score_viewer.isVisible():
            self.score_viewer.refresh_data()

    def change_language(self, language: str):
        """
        言語を変更してアプリケーションを再起動
        
        Args:
            language: 言語コード ('ja' or 'en')
        """
        if language == self.config.language:
            # 既に同じ言語の場合は何もしない
            return
        
        # 設定を保存
        self.config.language = language
        self.config.save_config()
        
        if language == 'en':
            QMessageBox.information(
                self,
                "Language Changed",
                "The new language will be applied when you restart the application."
            )
        else:
            QMessageBox.information(
                self,
                "言語設定変更",
                "言語設定を変更しました。\n次回起動時に反映されます。"
            )
        
    # 以下のメソッドはサブクラスで実装される
    def open_config_dialog(self):
        """設定ダイアログを開く（サブクラスで実装）"""
        raise NotImplementedError
    
    def open_obs_dialog(self):
        """OBS制御設定ダイアログを開く（サブクラスで実装）"""
        raise NotImplementedError
    
    def show_about(self):
        """バージョン情報表示（サブクラスで実装）"""
        raise NotImplementedError
    
    def save_image(self):
        """画像保存処理（サブクラスで実装）"""
        raise NotImplementedError
    
    def tweet(self):
        """ツイート作成 (サブクラスで実装)"""
        raise NotImplementedError
    
    def write_bpi_csv(self):
        '''BPIM用csvの作成 (サブクラスで実装)'''
        raise NotImplementedError
