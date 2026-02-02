"""
メインウィンドウUI - UIレイアウトと表示更新を担当
"""

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QGroupBox, QGridLayout, QPushButton)
from PySide6.QtGui import QAction
import time

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

from src.classes import detect_mode
from src.logger import logger


class MainWindowUI(QMainWindow):
    """メインウィンドウのUIレイアウトを担当するクラス"""
    
    def __init__(self):
        super().__init__()
        # UIコンポーネントの参照はここで定義（サブクラスから使用可能）
        self.obs_status_label = None
        self.mode_label = None
        self.uptime_label = None
        self.keystroke_label = None
        self.result_count_label = None
        self.last_song_label = None
        self.save_image_button = None
    
    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("INFINITAS daken counter")
        
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
        obs_group = QGroupBox("OBS接続状態")
        obs_layout = QHBoxLayout()
        self.obs_status_label = QLabel("未接続")
        self.obs_status_label.setStyleSheet("color: red; font-weight: bold;")
        obs_layout.addWidget(self.obs_status_label)
        obs_group.setLayout(obs_layout)
        main_layout.addWidget(obs_group)
        
        # 状態情報グループ
        status_group = QGroupBox("状態情報")
        status_layout = QGridLayout()
        
        # ラベル作成
        status_layout.addWidget(QLabel("現在のモード:"), 0, 0)
        self.mode_label = QLabel("初期化中")
        status_layout.addWidget(self.mode_label, 0, 1)
        
        status_layout.addWidget(QLabel("起動時間:"), 1, 0)
        self.uptime_label = QLabel("00:00:00")
        status_layout.addWidget(self.uptime_label, 1, 1)
        
        status_layout.addWidget(QLabel("本日の打鍵数:"), 2, 0)
        self.keystroke_label = QLabel("0")
        status_layout.addWidget(self.keystroke_label, 2, 1)
        
        status_layout.addWidget(QLabel("保存したリザルト数:"), 3, 0)
        self.result_count_label = QLabel("0")
        status_layout.addWidget(self.result_count_label, 3, 1)
        
        status_layout.addWidget(QLabel("最後に保存した曲:"), 4, 0)
        self.last_song_label = QLabel("---")
        self.last_song_label.setWordWrap(True)
        status_layout.addWidget(self.last_song_label, 4, 1)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # 画像保存ボタン
        save_button_layout = QHBoxLayout()
        self.save_image_button = QPushButton("画像保存 (F6)")
        self.save_image_button.clicked.connect(self.save_image)
        save_button_layout.addWidget(self.save_image_button)
        main_layout.addLayout(save_button_layout)
        
        # ストレッチでスペースを埋める
        main_layout.addStretch()
        
        # ステータスバー
        self.statusBar().showMessage("準備完了")
    
    def create_menu_bar(self):
        """メニューバー作成"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル(&F)")
        
        # 画像保存アクション
        save_image_action = QAction("画像保存(&S)", self)
        save_image_action.setShortcut("F6")
        save_image_action.triggered.connect(self.save_image)
        file_menu.addAction(save_image_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("終了(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 設定メニュー
        settings_menu = menubar.addMenu("設定(&S)")
        
        config_action = QAction("基本設定(&C)...", self)
        config_action.triggered.connect(self.open_config_dialog)
        settings_menu.addAction(config_action)
        
        obs_action = QAction("OBS制御設定(&O)...", self)
        obs_action.triggered.connect(self.open_obs_dialog)
        settings_menu.addAction(obs_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu("ヘルプ(&H)")
        
        about_action = QAction("バージョン情報(&A)", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def restore_window_geometry(self):
        """ウィンドウ位置とサイズを復元"""
        if self.config.main_window_geometry:
            import base64
            from PySide6.QtCore import QByteArray
            
            geometry_bytes = base64.b64decode(self.config.main_window_geometry)
            geometry = QByteArray(geometry_bytes)
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 500, 300)
    
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
                logger.debug(f"グローバルホットキー解除エラー: {e}")
    
    def update_display(self):
        """表示更新"""
        # OBS接続状態
        status_msg, is_connected = self.obs_manager.get_status()
        self.obs_status_label.setText(status_msg)
        if is_connected:
            self.obs_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.obs_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # モード表示
        mode_names = {
            detect_mode.init: "初期化中",
            detect_mode.play: "プレー中",
            detect_mode.select: "選曲画面",
            detect_mode.result: "リザルト"
        }
        self.mode_label.setText(mode_names.get(self.current_mode, "不明"))
        
        # 起動時間
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.uptime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # 統計情報
        self.keystroke_label.setText(str(self.today_keystroke_count))
        self.result_count_label.setText(str(self.saved_result_count))
        self.last_song_label.setText(self.last_saved_song)
    
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
