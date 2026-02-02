"""
IIDX Helper - メインプログラム
OBS連携による自動リザルト保存アプリケーション
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import time
import traceback
import datetime

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("警告: keyboardライブラリがインストールされていません。グローバルホットキーは無効です。")
    print("有効にするには: pip install keyboard")

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
from src.main_window import MainWindowUI


class MainWindow(MainWindowUI):
    """メインウィンドウクラス - 制御ロジックを担当"""
    
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

        # 接続状態変化のシグナルを接続
        self.obs_manager.connection_changed.connect(self.on_obs_connection_changed)

        # アプリケーション状態
        self.current_mode = detect_mode.init
        self.start_time = time.time()
        self.today_judge = Judge(0,0,0,0,0,0)
        self.result_timestamp = 0
        '''本日の判定内訳(全曲合計)'''
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
        
        # グローバルホットキーの登録
        self.setup_global_hotkeys()
        
        logger.info("アプリケーション起動完了")
    
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
    
    def save_image(self):
        """
        ゲーム画面のキャプチャ画像を保存する
        
        画像保存処理をここに実装してください。
        - 現在のスクリーンショットを取得
        - 設定に応じて編集（ライバル欄のモザイク/カット、統計情報の書き込み等）
        - 指定されたフォルダに保存
        """
        try:
            logger.info("画像保存ボタンが押されました")
            # TODO: 画像保存処理を実装
            
            self.statusBar().showMessage("画像保存機能は未実装です", 3000)
        except Exception as e:
            logger.error(f"画像保存エラー: {traceback.format_exc()}")
            self.statusBar().showMessage(f"画像保存エラー: {str(e)}", 3000)
    
    def on_obs_connection_changed(self, is_connected: bool, message: str):
        """
        OBS接続状態変化時のハンドラ

        Args:
            is_connected: 接続状態（True=接続中、False=切断）
            message: ステータスメッセージ
        """
        logger.info(f"OBS connection changed: connected={is_connected}, message={message}")

        # UIを更新（スレッドセーフに）
        self.obs_status_label.setText(message)

        if is_connected:
            # 接続成功時
            self.obs_status_label.setStyleSheet("color: green; font-weight: bold;")
            logger.info("OBS接続が確立されました")

            # 必要に応じて追加の処理
            # 例: シーンリストを更新、自動制御を有効化など

        else:
            # 切断時
            self.obs_status_label.setStyleSheet("color: red; font-weight: bold;")
            logger.warning("OBS接続が切断されました")

            # 必要に応じて追加の処理
            # 例: 自動制御を一時停止など

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
            play_mode = self.screen_reader.is_play()
            if play_mode:
                return detect_mode.play
            else:
                return detect_mode.init
    
    def on_mode_changed(self, old_mode: detect_mode, new_mode: detect_mode):
        """モード変更時の処理"""
        logger.info(f"モード変更: {old_mode.name} -> {new_mode.name}")
        
        # OBS制御トリガーの実行
        trigger_map = {
            (detect_mode.init, detect_mode.select): "select_start",
            (detect_mode.result, detect_mode.select): "select_start",
            (detect_mode.init, detect_mode.play): "play_start",
            (detect_mode.select, detect_mode.play): "play_start",
            (detect_mode.init, detect_mode.result): "result_start",
            (detect_mode.play, detect_mode.result): "result_start",
            (detect_mode.play, detect_mode.init): "play_end",
            (detect_mode.result, detect_mode.init): "result_end",
            (detect_mode.select, detect_mode.init): "select_end",
        }
        
        trigger = trigger_map.get((old_mode, new_mode))
        if trigger:
            self.execute_obs_triggers(trigger)


        # if trigger == 'play_end': # プレイ画面が終わるときにtimestamp取得
        if trigger == 'result_start': # リザルト画面に移行したときに一度実行
            self.result_pre = None # 1つ前の認識結果
            self.result_timestamp = int(datetime.datetime.now().timestamp())
    
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
            detailed_result = self.screen_reader.read_result_screen()
            result = detailed_result.result
            result.timestamp = self.result_timestamp
            if result and result.chart_id:
                if result == self.result_pre:
                    logger.debug(f"result == result_pre")
                    # リザルトを保存
                    if self.result_database.add(result):
                        logger.info(f"added!, result={result}")
                        self.result_database.save()

                        # 統計情報の更新
                        self.saved_result_count += 1
                        if result.judge:
                            self.today_judge += result.judge
                            self.today_keystroke_count += (result.judge.pg + result.judge.gr + 
                                                           result.judge.gd + result.judge.bd)


                        # 曲名の更新
                        if detailed_result.songinfo:
                            self.last_saved_song = f"{self.screen_reader.last_title_result} ({detailed_result.songinfo.play_style.name.upper()}{detailed_result.songinfo.difficulty.name[0].upper()})"
                        else:
                            self.last_saved_song = f"{self.screen_reader.last_title_result}"
                        # TODO
                        # if result.songinfo:
                            # self.last_saved_song = f"{result.songinfo.title} " \
                                                #   f"({result.songinfo.play_style.name.upper()}" \
                                                #   f"{result.songinfo.difficulty.name[0].upper()})"

                self.result_pre = result
        except:
            logger.error(f"リザルト処理エラー: {traceback.format_exc()}")
    
    def closeEvent(self, event):
        """ウィンドウクローズイベント"""
        # グローバルホットキーの解除
        self.remove_global_hotkeys()
        
        # OBS接続を切断（監視スレッドも停止）
        self.obs_manager.disconnect()

        # ウィンドウ位置を保存
        self.save_window_geometry()
        
        # OBS切断
        if self.obs_manager.is_connected:
            self.obs_manager.disconnect()
        
        # タイマーを停止
        self.main_timer.stop()
        self.display_timer.stop()

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

