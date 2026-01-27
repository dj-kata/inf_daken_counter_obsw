"""
IIDX Helper - メインプログラム
OBS連携による自動リザルト保存アプリケーション
"""

import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QMenuBar, QMenu, QStatusBar,
                               QGroupBox, QGridLayout)
from PySide6.QtCore import QTimer, QTime, Qt
from PySide6.QtGui import QAction
import time
import traceback

from src.config import Config
from src.classes import detect_mode, play_style, difficulty, clear_lamp
from src.funcs import *
from src.obs_control import OBSWebSocketManager
from src.songinfo import SongDatabase
from src.screen_reader import ScreenReader
from src.result import ResultDatabase
from src.logger import logger

from src.config_dialog import ConfigDialog
from src.obs_dialog import OBSControlDialog

class MainWindow(QMainWindow):
    """メインウィンドウクラス"""
    
    def __init__(self):
        super().__init__()
        
        # 設定とデータベースの初期化
        self.config = Config()
        self.song_database = SongDatabase()
        self.result_database = ResultDatabase()
        self.screen_reader = ScreenReader()
        
        # OBS接続マネージャーの初期化
        self.obs_manager = OBSWebSocketManager()
        self.obs_manager.set_config(self.config)
        
        # アプリケーション状態
        self.current_mode = detect_mode.init
        self.start_time = time.time()
        self.today_keystroke_count = 0
        self.saved_result_count = 0
        self.last_saved_song = "---"
        
        # UI初期化
        self.init_ui()
        
        # OBS接続
        self.obs_manager.connect()
        
        # メインループタイマーの設定（100ms間隔）
        self.main_timer = QTimer()
        self.main_timer.timeout.connect(self.main_loop)
        self.main_timer.start(100)
        
        # 表示更新タイマー（500ms間隔）
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(500)
        
        logger.info("アプリケーション起動完了")
    
    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("IIDX Helper")
        self.setGeometry(
            self.config.main_window_x,
            self.config.main_window_y,
            self.config.main_window_width,
            self.config.main_window_height
        )
        
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
        
        # ストレッチでスペースを埋める
        main_layout.addStretch()
        
        # ステータスバー
        self.statusBar().showMessage("準備完了")
    
    def create_menu_bar(self):
        """メニューバー作成"""
        menubar = self.menuBar()
        
        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル(&F)")
        
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
    
    def open_config_dialog(self):
        """設定ダイアログを開く"""
        dialog = ConfigDialog(self.config, self)
        if dialog.exec():
            # 設定が保存された場合、全てのクラスに設定を反映
            self.update_all_configs()
            logger.info("設定を更新しました")
            self.statusBar().showMessage("設定を更新しました", 3000)
    
    def open_obs_dialog(self):
        """OBS制御設定ダイアログを開く"""
        dialog = OBSControlDialog(self.config, self.obs_manager, self)
        if dialog.exec():
            # 設定が保存された場合、全てのクラスに設定を反映
            self.update_all_configs()
            logger.info("OBS制御設定を更新しました")
            self.statusBar().showMessage("OBS制御設定を更新しました", 3000)
    
    def update_all_configs(self):
        """全てのクラスに設定を反映"""
        self.config.load_config()  # 最新の設定を読み込み
        self.obs_manager.set_config(self.config)
        self.result_database.song_database.load()  # 必要に応じて再読み込み
        
        # OBS接続状態の再評価
        if not self.obs_manager.is_connected:
            self.obs_manager.connect()
    
    def show_about(self):
        """バージョン情報表示"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "バージョン情報", 
                         "IIDX Helper v1.0\n\n"
                         "OBS連携による自動リザルト保存アプリケーション")
    
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
    
    def main_loop(self):
        """メインループ - 100ms毎に呼ばれる"""
        try:
            # OBS連携が有効な場合のみスクリーンショット取得
            if self.obs_manager.is_connected:
                self.obs_manager.screenshot()
                
                if self.obs_manager.screen is not None:
                    self.screen_reader.update_screen(self.obs_manager.screen)
                    
                    # 現在のゲーム画面状態を判定
                    new_mode = self.detect_current_mode()
                    
                    # モードが変わった場合のイベント処理
                    if new_mode != self.current_mode:
                        self.on_mode_changed(self.current_mode, new_mode)
                        self.current_mode = new_mode
                    
                    # 各モードでの処理
                    if self.current_mode == detect_mode.select:
                        self.process_select_mode()
                    elif self.current_mode == detect_mode.play:
                        self.process_play_mode()
                    elif self.current_mode == detect_mode.result:
                        self.process_result_mode()
        
        except Exception as e:
            logger.error(f"メインループエラー: {traceback.format_exc()}")
    
    def detect_current_mode(self) -> detect_mode:
        """現在のゲーム画面状態を判定"""
        if self.screen_reader.is_result():
            return detect_mode.result
        elif self.screen_reader.is_select():
            return detect_mode.select
        else:
            return detect_mode.init
    
    def on_mode_changed(self, old_mode: detect_mode, new_mode: detect_mode):
        """モード変更時の処理"""
        logger.info(f"モード変更: {old_mode.name} -> {new_mode.name}")
        
        # OBS制御トリガーの実行
        trigger_map = {
            (detect_mode.init, detect_mode.select): "select_start",
            (detect_mode.select, detect_mode.play): "play_start",
            (detect_mode.play, detect_mode.result): "result_start",
            (detect_mode.result, detect_mode.select): "select_start",
        }
        
        trigger = trigger_map.get((old_mode, new_mode))
        if trigger:
            self.execute_obs_triggers(trigger)
    
    def execute_obs_triggers(self, trigger: str):
        """指定されたトリガーのOBS制御を実行"""
        # OBS制御設定から該当するトリガーの設定を取得して実行
        # この部分は実際のOBS制御ロジックに応じて実装
        logger.debug(f"OBSトリガー実行: {trigger}")
        pass
    
    def process_select_mode(self):
        """選曲画面での処理"""
        # ここにselect画面での処理を実装
        # 例: 選曲情報の読み取りなど
        pass
    
    def process_play_mode(self):
        """プレー画面での処理"""
        # ここにplay画面での処理を実装
        # 例: プレー中の情報表示など
        pass
    
    def process_result_mode(self):
        """リザルト画面での処理"""
        # ここにresult画面での処理を実装
        # 例: リザルト読み取りと保存
        try:
            result = self.screen_reader.read_result_screen()
            if result and result.chart_id:
                # リザルトを保存
                self.result_database.add(
                    judge=result.judge,
                    lamp=result.lamp,
                    option=result.option,
                    _chart_id=result.chart_id,
                    playspeed=result.playspeed
                )
                self.result_database.save()
                
                # 統計情報の更新
                self.saved_result_count += 1
                if result.judge:
                    self.today_keystroke_count += (result.judge.pg + result.judge.gr + 
                                                   result.judge.gd + result.judge.bd + result.judge.pr)
                
                # 曲名の更新
                if result.songinfo:
                    self.last_saved_song = f"{result.songinfo.title} " \
                                          f"({result.songinfo.play_style.name.upper()}" \
                                          f"{result.songinfo.difficulty.name[0].upper()})"
                
                logger.info(f"リザルト保存: {result}")
        except Exception as e:
            logger.error(f"リザルト処理エラー: {traceback.format_exc()}")
    
    def closeEvent(self, event):
        """ウィンドウクローズイベント"""
        # ウィンドウ位置を保存
        self.config.save_window_position(
            self.x(), self.y(), 
            self.width(), self.height()
        )
        
        # OBS切断
        if self.obs_manager.is_connected:
            self.obs_manager.disconnect()
        
        logger.info("アプリケーション終了")
        event.accept()


def main():
    """メイン関数"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # モダンなスタイルを適用
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
