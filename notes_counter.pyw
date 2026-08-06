"""
IIDX Helper - メインプログラム
OBS連携による自動リザルト保存アプリケーション
"""

import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)
from PySide6.QtCore import QTimer,Qt,Signal
import traceback
import datetime
from pathlib import Path
import webbrowser, urllib
import copy
import os
import threading

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
from src.obs_websocket_manager import OBSWebSocketManager
from src.songinfo import SongDatabase, download_latest_songinfo
from src.screen_reader import ScreenReader
from src.result import OneResult, DetailedResult, bpim2_savecache
from src.result_database import ResultDatabase
from src.result_stats_writer import ResultStatsWriter
from src.rival_data import RivalManager
from src.logger import get_logger
logger = get_logger('notes_counter')

from src.config_dialog import ConfigDialog
from src.obs_dialog import OBSControlDialog
from src.main_window import MainWindowUI
from src.storage import StorageAccessor
from src.update import GitHubUpdater

sys.path.append('infnotebook')
from define import define
# from src.resources import resource, check_latest
from resources import resource, download_latestresource
from record import musicnamechanges_filename

try:
    with open('version.txt', 'r') as f:
        tmp = f.readline()
        print(tmp)
        SWVER = tmp.strip()[2:] if tmp.startswith('v') else tmp.strip()
except Exception:
    SWVER = "0.0.0"

class MusicSelectScoreImportDialog(QDialog):
    """選曲画面から認識したスコアを確認して手動登録するダイアログ"""

    CHART_CANDIDATES = ["SPB", "SPN", "SPH", "SPA", "SPL", "DPN", "DPH", "DPA", "DPL"]

    def __init__(self, ui, result: OneResult, parent=None):
        super().__init__(parent)
        self.ui = ui
        self.setWindowTitle(self.ui.manual_music_select_import.title)

        layout = QVBoxLayout()
        self.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self.title_edit = QLineEdit(result.title or "")
        form_layout.addRow(self.ui.manual_music_select_import.recognized_title, self.title_edit)

        self.chart_combo = QComboBox()
        self.chart_combo.setEditable(True)
        self.chart_combo.addItems(self.CHART_CANDIDATES)
        chart_name = get_chart_name(result.play_style, result.difficulty)
        if chart_name:
            index = self.chart_combo.findText(chart_name)
            if index >= 0:
                self.chart_combo.setCurrentIndex(index)
            else:
                self.chart_combo.setEditText(chart_name)
        form_layout.addRow(self.ui.manual_music_select_import.recognized_chart, self.chart_combo)

        lamp_text = str(result.lamp) if result.lamp else ""
        form_layout.addRow(self.ui.manual_music_select_import.recognized_lamp, QLineEdit(lamp_text))
        score_text = "" if result.score is None else str(result.score)
        form_layout.addRow(self.ui.manual_music_select_import.recognized_score, QLineEdit(score_text))
        bp_text = "" if result.bp is None else str(result.bp)
        form_layout.addRow(self.ui.manual_music_select_import.recognized_bp, QLineEdit(bp_text))

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText(self.ui.manual_music_select_import.register)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # ランプ/スコア/BPは確認用なので編集不可にする
        for row in range(2, 5):
            widget = form_layout.itemAt(row, QFormLayout.FieldRole).widget()
            widget.setReadOnly(True)

    @property
    def edited_title(self) -> str:
        return self.title_edit.text().strip()

    @property
    def edited_chart(self) -> str:
        return self.chart_combo.currentText().strip()

class MainWindow(MainWindowUI):
    """メインウィンドウクラス - 制御ロジックを担当"""
    songinfo_update_finished = Signal(bool, str)
    manual_music_select_import_requested = Signal()
    bpim2_fetch_finished = Signal(object, object)
    
    def __init__(self):
        # 設定とデータベースの初期化
        self.config = Config()
        super().__init__(self.config)
        self.manual_music_select_import_requested.connect(self.manual_music_select_import)
        self.bpim2_fetch_finished.connect(self.on_bpim2_fetch_finished)
        self.song_database = SongDatabase()
        self.result_database = ResultDatabase(config=self.config)
        self.rival_manager = RivalManager(parent=self)
        self.result_database.rival_manager = self.rival_manager
        self.screen_reader = ScreenReader()
        self.songinfo_update_finished.connect(self.on_songinfo_update_finished)
        
        # OBS接続マネージャーの初期化
        self.obs_manager = OBSWebSocketManager()
        self.obs_manager.set_config(self.config)

        # 接続状態変化のシグナルを接続
        self.obs_manager.connection_changed.connect(self.on_obs_connection_changed)

        # その他
        self.result_stats_writer = ResultStatsWriter()
        '''起動時刻を覚えておく'''

        # アプリケーション状態
        self.current_mode = detect_mode.init
        self._start_time = int(datetime.datetime.now().timestamp())
        self.today_judge = Judge()
        '''本日のプレーの判定内訳'''
        self.current_judge = Judge()
        '''このプレーの判定内訳'''
        self.set_today_judge()
        self.result_timestamp = 0
        self.today_keystroke_count = 0
        self.play_count = 0
        self.last_saved_song = "---"
        self.result_pre = None # 1つ前の認識結果
        self.current_option = None
        '''最後に設定したオプション'''
        self.last_play_mode = None
        '''現在のプレーモード。playの先頭でセットし、その後の検出で使用。'''
        self._bpim2_fetching_keys = set()
        '''BPIM2取得中の譜面キー。選曲画面で同じ曲を連打しないためのガード。'''
        self._pending_select_bpim2_args = None
        '''選曲画面でカーソル停止待ち中の譜面キー。'''
        self._scheduled_select_bpim2_args = None
        '''現在タイマーに積まれている選曲画面BPI取得キー。'''
        
        # HTMLを更新しておく
        self.result_database.broadcast_today_updates_data(self.start_time_with_offset)
        self.result_database.broadcast_graph_data(self.start_time_with_offset)
        self.result_database.broadcast_today_stats_data(self.start_time_with_offset)
        self.result_database.broadcast_option_data(self.current_option)

        # UI初期化
        self.init_ui()
        # 最前面表示
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.config.keep_on_top)
        
        # OBS接続
        self.obs_manager.connect()
        
        # v2からの引き継ぎ確認（OBS設定チェックより先に実行）
        QTimer.singleShot(500, self.check_startup_migration)

        # 曲情報DBを起動後にバックグラウンド更新し、完了次第反映
        QTimer.singleShot(0, self.start_songinfo_update)

        # OBS設定チェックと警告表示（接続試行後に少し待ってからチェック）
        QTimer.singleShot(1000, self.check_obs_configuration)
        
        # アプリ起動時のOBS処理
        self.execute_obs_triggers('app_start')

        # メインループタイマーの設定（100ms間隔）
        self.main_timer = QTimer()
        self.main_timer.timeout.connect(self.main_loop)
        self.main_timer.start(100)
        
        # 表示更新タイマー（500ms間隔）
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(500)

        # 選曲画面BPI取得はカーソルが一定時間止まってから実行する
        self.select_bpim2_timer = QTimer()
        self.select_bpim2_timer.setSingleShot(True)
        self.select_bpim2_timer.timeout.connect(self.fetch_pending_select_bpim2)
        
        # グローバルホットキーの登録
        self.setup_global_hotkeys()

        # ライバルデータ: キャッシュから即座に読み込み → バックグラウンドで最新を取得
        if self.config.rivals:
            self.rival_manager.load_cache()
            self.rival_manager.start_fetch(self.config.rivals)

        logger.info("アプリケーション起動完了")

    def start_songinfo_update(self):
        """songinfo.infdcの更新をバックグラウンドで開始"""
        threading.Thread(target=self._download_songinfo_update, daemon=True).start()

    def _download_songinfo_update(self):
        try:
            count = download_latest_songinfo()
            self.songinfo_update_finished.emit(
                True, f"曲情報DBを更新しました ({count}譜面)"
            )
        except Exception:
            logger.error(f"曲情報DB更新エラー: {traceback.format_exc()}")
            self.songinfo_update_finished.emit(False, "曲情報DBの更新に失敗しました")

    def on_songinfo_update_finished(self, success: bool, message: str):
        """DL済みの曲情報DBを即座に再読込し、表示データへ反映"""
        if success:
            self.song_database.load()
            self.result_database.song_database.load()
            self.screen_reader.songinfo.load()
            self.result_database.broadcast_today_updates_data(self.start_time_with_offset)
            self.result_database.broadcast_today_stats_data(self.start_time_with_offset)
            if self.result_pre and self.result_pre.chart_id:
                option = self.result_pre.option
                self.result_database.broadcast_history_cursong_data(
                    title=self.result_pre.title,
                    style=self.result_pre.play_style,
                    difficulty=self.result_pre.difficulty,
                    battle=option.battle if option else None,
                    playspeed=self.result_pre.playspeed,
                )
            if self.score_viewer:
                self.score_viewer.refresh_data()
            logger.info(message)
        else:
            logger.warning(message)
        self.statusBar().showMessage(message, 3000)

    @property
    def start_time(self) -> int:
        '''起動時刻(read only)'''
        return self._start_time

    @property
    def start_time_with_offset(self) -> int:
        '''オフセット込みの起動時間'''
        return self._start_time - self.config.autoload_offset * 3600
    
    def check_obs_configuration(self):
        """OBS設定をチェックし、問題があれば警告ダイアログを表示"""
        status = self.obs_manager.get_detailed_status()
        
        warnings = []

        # TODO 英語化
        
        # OBS WebSocket接続チェック
        if not status['is_connected']:
            warnings.append("• OBS WebSocketに接続できていません")
        
        # 監視対象ソース設定チェック
        if not status['is_source_configured']:
            warnings.append("• 監視対象ソースが設定されていません")
        
        # 警告がある場合はダイアログを表示
        if warnings:
            warning_message = "OBS設定に問題があります:\n\n" + "\n".join(warnings)
            warning_message += "\n\nOBSが起動していること及び、本アプリの設定を確認してください。"
            warning_message += "\n(メニュー: ファイル → OBS制御設定)"
            
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("OBS設定の警告")
            msg_box.setText(warning_message)
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()
            
            logger.warning(f"OBS configuration warning: {warnings}")

    def check_startup_migration(self):
        """起動時にv2からの引き継ぎが必要か確認し、ダイアログを表示する"""
        if not Path('settings.json').exists():
            return

        # メジャーアップデートの通知
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle(self.ui.window.major_update_title)
        msg_box.setText(self.ui.message.major_update)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()

        # v2設定インポートの確認
        reply = QMessageBox.question(
            self,
            self.ui.window.import_v2_config_title,
            self.ui.message.ask_import_v2_config,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.import_v2_config()

    def import_v2_config(self):
        """v2のsettings.jsonからself.configに設定をインポートする (スケルトン)"""
        with open('settings.json', 'r') as f:
            import json
            v2_settings:dict = json.load(f)
        self.config.websocket_host = v2_settings['host'] if 'host' in v2_settings else self.config.websocket_host
        self.config.websocket_port = int(v2_settings['port']) if 'port' in v2_settings else self.config.websocket_port
        self.config.websocket_password = v2_settings['passwd'] if 'passwd' in v2_settings else self.config.websocket_password
        self.config.monitor_source_name = v2_settings['obs_source'] if 'obs_source' in v2_settings else self.config.monitor_source_name
        self.config.image_save_path = v2_settings['autosave_dir'] if 'autosave_dir' in v2_settings else self.config.image_save_path
        self.config.modify_rivalarea_mode = config_modify_rivalarea.mosaic if v2_settings.get('autosave_mosaic', False) else self.config.modify_rivalarea_mode
        self.config.enable_autotweet = v2_settings['tweet_on_exit'] if 'tweet_on_exit' in v2_settings else self.config.enable_autotweet
        self.config.autosave_image_mode = config_autosave_image.all if v2_settings.get('autosave_always', False) in v2_settings else self.config.autosave_image_mode
        self.config.obs_scene_collection = v2_settings['scene_collection'] if 'scene_collection' in v2_settings else self.config.obs_scene_collection

        QMessageBox.information(
            self,
            self.ui.window.import_v2_config_title,
            self.ui.message.notify_rename_v2_config,
        )

        file_path = Path('settings.json')
        file_path.rename('settings.json.bak')


    def open_config_dialog(self):
        """設定ダイアログを開く"""
        old_rivals = copy.deepcopy(self.config.rivals)
        dialog = ConfigDialog(self.config, self.result_database, self.screen_reader, self)
        if dialog.exec():
            # 設定が保存された場合、全てのクラスに設定を反映
            self.update_all_configs()
            # ライバル設定が変更された場合は再取得
            if self.config.rivals != old_rivals:
                self.rival_manager.start_fetch(self.config.rivals)
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
    
    def set_today_judge(self):
        '''本日の判定内訳(play中の判定合計)を対象ログから集計'''
        self.today_judge.reset()
        self.play_count = 0
        for r in reversed(self.result_database.results):
            if r.detect_mode == detect_mode.play and r.judge:
                if r.timestamp >= self.start_time_with_offset:
                    self.play_count += 1
                    self.today_judge += r.judge
                else:
                    break

    def update_all_configs(self):
        """全てのクラスに設定を反映"""
        self.config.load_config()  # 最新の設定を読み込み
        self.obs_manager.set_config(self.config)
        self.result_database.song_database.load()  # 必要に応じて再読み込み

        self.result_database.broadcast_today_updates_data(self.start_time_with_offset)
        self.result_database.broadcast_graph_data(self.start_time_with_offset)
        self.result_database.broadcast_today_stats_data(self.start_time_with_offset)
        self.set_today_judge()

        # 最前面表示
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.config.keep_on_top)
        self.show()

        # OBS接続状態の再評価
        if not self.obs_manager.is_connected:
            self.obs_manager.connect()
    
    def show_about(self):
        """バージョン情報表示"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, self.ui.window.about_title, 
                         f"INFINITAS daken counter {SWVER}\n\n"
                         "author: dj-kata")
    
    def save_image(self, skip_no_update:bool=False, detailed_result:DetailedResult=None):
        """
        ゲーム画面のキャプチャ画像を保存する。リザルト画面なら曲名などをファイル名に入れる。
        """
        try:
            date = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            if self.screen_reader.is_result():
                detailed_result = detailed_result if detailed_result else self.screen_reader.read_result_screen()
                # TODO ここで最後に追加したresultを使うほうがよい、自己べ情報が上書きされるため
                detailed_result.result = self.result_database.results[-1]
                result = detailed_result.result
                if skip_no_update and (self.config.autosave_image_mode == config_autosave_image.only_updates): # 更新している場合のみ保存
                    if not result.is_updated():
                        logger.debug(f"skipped!, pre score:{result.pre_score}, bp:{result.pre_bp}, lamp:{result.pre_lamp}")
                        self.statusBar().showMessage(f"伸びていないのでスキップします。", 10000)
                        return False

                if detailed_result.result.option:
                    filename = f"inf_{detailed_result.result.title}_{get_chart_name(detailed_result.result.play_style, detailed_result.result.difficulty, detailed_result.result.option.battle)}"
                else:
                    filename = f"inf_{detailed_result.result.title}_{get_chart_name(detailed_result.result.play_style, detailed_result.result.difficulty)}"
                filename += f"_{detailed_result.result.lamp.name}"
                filename += f"_ex{detailed_result.result.score}"
                filename += f"_bp{result.judge.bd + result.judge.pr}"
                if detailed_result.result.playspeed:
                    filename += f"_x{detailed_result.result.playspeed}" # 速度変更時
                filename += f'_{date}'
            else:
                filename = f"inf_{date}"

            # 保存対象となる画像データ
            screen = self.screen_reader.screen.original

            # モザイク処理
            if self.screen_reader.is_result(): # リザルト
                if self.config.write_statistics:
                    # 統計情報ウィンドウを追加
                    sp12_clear = None
                    sp12_hard = None
                    if detailed_result.songinfo:
                        sp12_clear = detailed_result.songinfo.sp12_clear
                        sp12_hard = detailed_result.songinfo.sp12_hard
                    bpi_detail = detailed_result.bpi_detail
                    screen = self.result_stats_writer.write_statistics(
                        screen,
                        title=result.title,
                        level=detailed_result.level,
                        play_style=result.play_style,
                        difficulty=result.difficulty,
                        ex_score=result.score,
                        bp=result.judge.bd + result.judge.pr,
                        max_notes=detailed_result.result.notes,
                        lamp=result.lamp,
                        bpi=bpi_detail.value,
                        bpi_label=bpi_detail.label,
                        bpi_arena_average_text=bpi_detail.arena_average_text,
                        sp12_clear=sp12_clear,
                        sp12_hard=sp12_hard,
                    )
                if self.config.modify_rivalarea_mode == config_modify_rivalarea.mosaic: # モザイク処理する場合
                    screen = mosaic_rival_area(screen, detailed_result.result_side)
                    screen = mosaic_other_rival_names(screen, detailed_result.result_side)
                elif self.config.modify_rivalarea_mode == config_modify_rivalarea.cut: # カットする場合
                    screen = mosaic_other_rival_names(screen, detailed_result.result_side)
                    screen = cut_rival_area(screen, detailed_result.result_side)

                    filename += f"_cut{detailed_result.result_side.name[1:]}"

            # 画像を保存
            filename += '.png'
            filename = escape_for_filename(filename)
            os.makedirs(self.config.image_save_path, exist_ok=True)
            full_path = Path(self.config.image_save_path) / filename
            logger.info(f"autosaved! dst = {full_path}")
            screen.save(full_path)
            self.statusBar().showMessage(f"保存しました -> {filename}", 10000)
            return True
            
        except Exception as e:
            logger.error(f"画像保存エラー: {traceback.format_exc()}")
            self.statusBar().showMessage(f"画像保存エラー: {str(e)}", 3000)
            return False
    
    def on_obs_connection_changed(self, is_connected: bool, message: str):
        """
        OBS接続状態変化時のハンドラ

        Args:
            is_connected: 接続状態（True=接続中、False=切断）
            message: ステータスメッセージ
        """
        # logger.info(f"OBS connection changed: connected={is_connected}, message={message}")

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
            # logger.warning("OBS接続が切断されました")

            # 必要に応じて追加の処理
            # 例: 自動制御を一時停止など

    def main_loop(self):
        """メインループ - 100ms毎に呼ばれる"""
        try:
            # OBS連携が有効な場合のみスクリーンショット取得
            if self.obs_manager.is_connected and self.config.monitor_source_name != "":
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
                    elif self.current_mode == detect_mode.option:
                        self.process_option_mode()
        
        except Exception as e:
            logger.error(f"メインループエラー: {traceback.format_exc()}")
    
    def detect_current_mode(self) -> detect_mode:
        """現在のゲーム画面状態を判定"""
        if self.screen_reader.is_result():
            return detect_mode.result
        elif self.screen_reader.is_select():
            return detect_mode.select
        elif self.screen_reader.is_option():
            return detect_mode.option
        else:
            play_mode = self.screen_reader.is_play()
            if play_mode:
                return detect_mode.play
            else:
                return detect_mode.init
    
    def on_mode_changed(self, old_mode: detect_mode, new_mode: detect_mode):
        """モード変更時の処理"""
        # logger.info(f"モード変更: {old_mode.name} -> {new_mode.name}")
        
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


        if trigger == 'play_start': # プレー画面の先頭で実行
            self.last_play_mode = self.screen_reader.detect_playside()

        if trigger == 'play_end': # プレー画面の終わりに実行
            if self.current_judge and  self.current_judge.notes > 0:
                result = self.screen_reader.read_play_screen(self.current_judge)
                self.result_database.add(result)
                self.result_database.save()
                self.result_database.broadcast_graph_data(self.start_time_with_offset)
                self.result_database.broadcast_today_stats_data(self.start_time_with_offset)

                # 統計情報の更新
                self.play_count += 1
                self.today_judge += self.current_judge
                self.current_judge.reset()

        if trigger == 'result_start': # リザルト画面の先頭で実行
            self.result_pre = None # 1つ前の認識結果
            self.result_timestamp = int(datetime.datetime.now().timestamp())

    def execute_obs_triggers(self, trigger: str):
        """指定されたトリガーのOBS制御を実行"""
        # logger.debug(f"OBSトリガー実行: {trigger}")
        try:
            # OBS制御ウィンドウが作成されていなくても設定は実行できるよう、
            # 直接設定データを読み込んで実行
            from src.obs_control import OBSControlData
            
            control_data = OBSControlData()
            control_data.set_config(self.config)
            settings = control_data.get_settings_by_trigger(trigger)
            
            if not settings:
                # logger.debug(f"制御設定がないのでスキップ")
                return  # 該当する設定がない場合は何もしない
            
            if not self.obs_manager.is_connected:
                # logger.debug(f"OBS未接続のため、トリガー '{trigger}' をスキップ")
                return
            
            for setting in settings:
                try:
                    action = setting["action"]
                    # logger.debug(f"action = {action}")
                    
                    if action == "switch_scene":
                        target_scene = setting.get("scene")
                        if target_scene:
                            self.obs_manager.change_scene(target_scene)
                            print(f"シーンを切り替え: {target_scene}")
                    
                    elif action in ("show_source", "hide_source"):
                        scene_name = setting.get("scene")
                        source_name = setting.get("source")
                        if scene_name and source_name:
                            mod_scene_name, scene_item_id = self.obs_manager.search_itemid(scene_name, source_name)
                            if scene_item_id:
                                enabled = (action == "show_source")
                                if enabled:
                                    self.obs_manager.enable_source(mod_scene_name, scene_item_id)
                                else:
                                    self.obs_manager.disable_source(mod_scene_name, scene_item_id)
                                state = "表示" if enabled else "非表示"
                                print(f"ソースを{state}: {scene_name}/{source_name} (id:{scene_item_id})")

                    elif action == "autosave_source": # キャプチャを自動保存
                        scene_name = setting.get("scene")
                        source_name = setting.get("source")
                        if scene_name and source_name:
                            mod_scene_name, scene_item_id = self.obs_manager.search_itemid(scene_name, source_name)
                            if scene_item_id:
                                # 表示しておかないと最新の状態を保存できないので表示
                                # self.obs_manager.enable_source(mod_scene_name, scene_item_id)
                                filename = os.path.splitext(source_name)[0]
                                filename += f"_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.png"
                                dst = Path(self.config.image_save_path).resolve() / filename
                                self.obs_manager.save_screenshot_dst(source_name, str(dst), disable_wh=True)
                                
                except Exception as e:
                    print(f"制御実行エラー (trigger: {trigger}, setting: {setting}): {e}")
                    
        except Exception as e:
            print(traceback.format_exc())
            print(f"トリガー実行エラー ({trigger}): {e}")
    
    def process_select_mode(self):
        """選曲画面での処理"""
        detailed_result = self.screen_reader.read_music_select_screen()
        if not detailed_result:
            return False
        result = detailed_result.result
        result.timestamp = 0 # 更新日は不明という扱いにする
        # xml更新
        self.result_database.broadcast_history_cursong_data(title=result.title, style=result.play_style, difficulty=result.difficulty)
        self.schedule_select_bpim2_fetch(result.title, result.play_style, result.difficulty)
        if not getattr(detailed_result, 'music_select_difficulty_confirmed', False):
            return False
        if not self.config.enable_music_select_score_import:
            return False
        # 自己べ登録
        if self.result_database.add(result):
            self.statusBar().showMessage(f"選曲画面から自己ベストを登録しました。 -> {result}", 10000)
            self.result_database.save()
            self.result_database.broadcast_history_cursong_data(title=result.title, style=result.play_style, difficulty=result.difficulty)
            if self.score_viewer:
                self.score_viewer.refresh_data()

    def _parse_manual_chart(self, chart_text: str, fallback_style: play_style = None):
        """手動登録ダイアログの譜面表記を play_style / difficulty に変換する"""
        normalized = chart_text.strip().upper().replace(" ", "").replace("　", "")
        style = fallback_style
        diff_text = normalized

        if normalized.startswith("SP"):
            style = play_style.sp
            diff_text = normalized[2:]
        elif normalized.startswith("DP"):
            style = play_style.dp
            diff_text = normalized[2:]
        elif normalized.startswith("DB"):
            style = play_style.dp
            diff_text = normalized[2:]

        diff = convert_difficulty(diff_text)
        if style is None or diff is None:
            return None, None
        return style, diff

    def _register_music_select_result(self, detailed_result: DetailedResult) -> bool:
        """選曲画面由来のリザルトを通常の選曲画面登録と同じ扱いで保存する"""
        result = detailed_result.result
        result.timestamp = 0 # 更新日は不明という扱いにする
        if self.result_database.add(result):
            self.result_database.save()
            self.result_database.broadcast_history_cursong_data(title=result.title, style=result.play_style, difficulty=result.difficulty)
            if self.score_viewer:
                self.score_viewer.refresh_data()
            self.fetch_bpim2_async(detailed_result)
            return True
        return False

    def _bpim2_fetch_key(self, result: OneResult):
        if not result:
            return None
        return (result.title, result.play_style, result.difficulty, result.score)

    def fetch_bpim2_async(self, detailed_result: DetailedResult):
        """BPIM2取得をUIスレッドから逃がす。登録自体は待たせない。"""
        if not detailed_result or not detailed_result.result:
            return
        result = detailed_result.result
        key = self._bpim2_fetch_key(result)
        if key is None or key in self._bpim2_fetching_keys:
            return
        self._bpim2_fetching_keys.add(key)

        def worker():
            try:
                bpi_detail = detailed_result._get_bpim2_bpi_detail()
                if bpi_detail and bpi_detail.source == 'bpim2' and bpi_detail.value is not None:
                    self.bpim2_fetch_finished.emit(result, bpi_detail)
                else:
                    logger.debug(f"BPIM2 async fetch returned no value: {result}")
            except Exception:
                logger.debug(f"BPIM2 async fetch failed: {traceback.format_exc()}")
            finally:
                self._bpim2_fetching_keys.discard(key)

        threading.Thread(target=worker, daemon=True).start()

    def schedule_select_bpim2_fetch(self, title, style, difficulty):
        """選曲画面でカーソルが止まってからBPIM2を取得するよう予約する。"""
        if not title or not style or not difficulty:
            self._pending_select_bpim2_args = None
            self._scheduled_select_bpim2_args = None
            self.select_bpim2_timer.stop()
            return
        args = (title, style, difficulty)
        self._pending_select_bpim2_args = args
        if self._scheduled_select_bpim2_args == args:
            return
        self._scheduled_select_bpim2_args = args
        self.select_bpim2_timer.start(1000)

    def fetch_pending_select_bpim2(self):
        """最後に予約された選曲画面の譜面についてBPIM2取得を開始する。"""
        if not self._pending_select_bpim2_args:
            return
        title, style, difficulty = self._pending_select_bpim2_args
        self._scheduled_select_bpim2_args = self._pending_select_bpim2_args
        self.fetch_current_best_bpim2_async(title, style, difficulty)

    def fetch_current_best_bpim2_async(self, title, style, difficulty):
        """表示中譜面の保存済みベストBPIを、infnotebook側キャッシュ/APIで更新する。"""
        results = self.result_database.search(title=title, style=style, difficulty=difficulty)
        best_detail = None
        best_score = None
        for detail in results:
            score = detail.result.score
            if type(score) is not int:
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_detail = detail
            elif score == best_score and best_detail:
                if getattr(detail.result, 'bpim2', None) is None:
                    best_detail = detail
                elif not getattr(detail.result, 'bpim2_arena_averages', None):
                    best_detail = detail
        if best_detail is not None:
            self.fetch_bpim2_async(best_detail)

    def on_bpim2_fetch_finished(self, result: OneResult, bpi_detail):
        """バックグラウンド取得したBPIM2を保存・再配信する。"""
        if not result or not bpi_detail or bpi_detail.value is None:
            return
        result.bpim2 = bpi_detail.value
        result.bpim2_arena_averages = bpi_detail.arena_averages
        arena_count = len(bpi_detail.arena_averages or [])
        logger.info(f"BPIM2 fetched: {result.title} {get_chart_name(result.play_style, result.difficulty)} score={result.score} bpi={bpi_detail.value:.2f} arena_averages={arena_count}")
        self.result_database.save()
        self.result_database.broadcast_history_cursong_data(
            title=result.title,
            style=result.play_style,
            difficulty=result.difficulty,
        )
        self.result_database.broadcast_today_updates_data(self.start_time_with_offset)
        self.result_database.broadcast_today_stats_data(self.start_time_with_offset)
        if self.score_viewer:
            self.score_viewer.refresh_data()

    def manual_music_select_import(self):
        """選曲画面から認識したスコアを確認して手動登録する"""
        if not self.screen_reader.is_select():
            return False

        detailed_result = self.screen_reader.read_music_select_screen()
        if not detailed_result:
            return False

        result = detailed_result.result
        if not (result and result.title and result.lamp and result.score is not None):
            return False

        dialog = MusicSelectScoreImportDialog(self.ui, result, self)
        if dialog.exec() != QDialog.Accepted:
            return False

        style, diff = self._parse_manual_chart(dialog.edited_chart, fallback_style=result.play_style)
        if not dialog.edited_title or style is None or diff is None:
            QMessageBox.warning(
                self,
                self.ui.manual_music_select_import.invalid_chart_title,
                self.ui.manual_music_select_import.invalid_chart_message,
            )
            return False

        result.title = dialog.edited_title
        result.play_style = style
        result.difficulty = diff

        # 曲名/譜面を編集した場合も、登録先の曲情報は編集後の内容に合わせる
        detailed_result.songinfo = self.result_database.song_database.search(
            title=result.title,
            play_style=result.play_style,
            difficulty=result.difficulty,
        ) or self.result_database.song_database.search(chart_id=result.chart_id)
        detailed_result._bpi_detail = None

        if self._register_music_select_result(detailed_result):
            self.statusBar().showMessage(
                self.ui.manual_music_select_import.registered.format(result=result),
                10000,
            )
            return True

        self.statusBar().showMessage(self.ui.manual_music_select_import.not_registered, 5000)
        return False
    
    def process_play_mode(self):
        """プレー画面での処理"""
        tmp = self.screen_reader.get_judge_from_play_screen(self.last_play_mode)
        # logger.debug(f"mode:{self.last_play_mode}, self.current_judge = {self.current_judge}")
        if tmp:
            self.current_judge = tmp
        # TODO 多分websocketなのでプレイ中に都度送信しても負荷が低い
        # self.result_database.broadcast_graph_data(self.start_time_with_offset)
    
    def process_result_mode(self):
        """リザルト画面での処理"""
        try:
            detailed_result = self.screen_reader.read_result_screen()
            result = detailed_result.result
            result.timestamp = self.result_timestamp
            if result and result.chart_id:
                if result == self.result_pre:
                    # DBxの場合の処理
                    if result.option.battle and result.lamp == clear_lamp.assist:
                        if result.judge.cb == 0:
                            # CB0ならフルコンにする
                            result.lamp = clear_lamp.fc
                        elif self.current_option is not None and self.current_option.option_gauge is not None:
                            # ゲージを検出できていた場合、そのゲージにする
                            result.lamp = self.current_option.option_gauge.convert()
                    # リザルトを保存
                    if self.result_database.add(result):
                        self.result_database.save()
                        if self.score_viewer:
                            self.score_viewer.refresh_data()
                        self.result_database.broadcast_today_updates_data(self.start_time_with_offset)
                        self.result_database.broadcast_today_stats_data(self.start_time_with_offset)
                        self.fetch_bpim2_async(detailed_result)

                        # 画像の保存
                        if self.config.autosave_image_mode is not config_autosave_image.invalid:
                            detailed_result.result = result # best_bpなどはaddで付与されるので渡しておく
                            if self.save_image(skip_no_update=self.config.autosave_image_mode==config_autosave_image.only_updates, detailed_result=detailed_result):
                                # 曲名の更新
                                self.last_saved_song = get_title_with_chart(result.title, result.play_style, result.difficulty)

                    # xml更新
                    self.result_database.broadcast_history_cursong_data(
                        title=result.title
                        ,style=result.play_style
                        ,difficulty=result.difficulty
                        ,battle=result.option.battle
                        ,playspeed=result.playspeed
                    )

                self.result_pre = result
        except Exception:
            # logger.error(f"リザルト処理エラー: {traceback.format_exc()}")
            pass

    def process_option_mode(self):
        """オプション画面での処理"""
        self.current_option = self.screen_reader.read_option_screen()
        self.result_database.broadcast_option_data(self.current_option)
    
    def closeEvent(self, event):
        """アプリ終了時に実行する処理"""
        # アプリ終了時のOBS処理
        self.execute_obs_triggers('app_end')

        # グローバルホットキーの解除
        self.remove_global_hotkeys()
        
        # OBS接続を切断（監視スレッドも停止）
        self.obs_manager.disconnect()

        # ウィンドウ位置を保存
        self.save_window_geometry()

        # 終了時ツイート
        if self.config.enable_autotweet:
            self.tweet()

        # csv出力
        csv_path = self.config.csv_export_path or None
        self.result_database.write_best_csv(csv_path=csv_path)

        if bpim2_savecache is not None:
            bpim2_savecache()
        
        # タイマーを停止
        self.main_timer.stop()
        self.display_timer.stop()
        self.select_bpim2_timer.stop()

        # スコアビューワを終了
        if self.score_viewer is not None:
            self.score_viewer.close()

        # WebSocketサーバーとHTMLサーバーを停止
        if hasattr(self.result_database, 'shutdown_servers'):
            self.result_database.shutdown_servers()

        logger.info("アプリケーション終了")
        event.accept()

    def tweet(self):
        '''成果ツイート'''
        msg = f"plays:{self.play_count}, notes:{self.today_judge.notes:,}, {self.today_judge.score_rate*100:.2f}%\n"
        if self.config.enable_judge:
            msg += f"(PG:{self.today_judge.pg:,}, GR:{self.today_judge.gr:,}, GD:{self.today_judge.gd:,}, BD:{self.today_judge.bd:,}, PR:{self.today_judge.pr:,}, CB:{self.today_judge.cb:,})\n"

        ontime = datetime.datetime.now() - datetime.datetime.fromtimestamp(self.start_time)
        msg += f"uptime: {str(ontime).split('.')[0]}\n"

        if self.config.enable_folder_updates:
            msg += self._collect_today_updates()
        date = datetime.datetime.fromtimestamp(self.start_time)
        msg += f"({date.year}/{date.month:02d}: {self.result_database.get_monthly_notes():,})\n"
        msg += '#INFINITAS_daken_counter\n'
        encoded_msg = urllib.parse.quote(msg)
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")

    def _collect_today_updates(self) -> str:
        '''本日のリザルトからレベル別ランプ更新数・新規AA/AAA/MAX-数を集計'''
        # 本日のresultモードのリザルトを収集
        today_results = []
        for r in reversed(self.result_database.results):
            if r.detect_mode == detect_mode.result:
                if r.timestamp >= self.start_time_with_offset:
                    today_results.append(r)
                else:
                    break

        if not today_results:
            return ""

        # SP/DPそれぞれで集計
        sp_results = [r for r in today_results if r.play_style == play_style.sp]
        dp_results = [r for r in today_results if r.play_style == play_style.dp]

        has_sp = len(sp_results) > 0
        has_dp = len(dp_results) > 0
        both = has_sp and has_dp

        lines = []
        if has_sp:
            if both:
                lines.append("(SP)")
            lines.extend(self._collect_updates_for_style(sp_results))
        if has_dp:
            if both:
                lines.append("(DP)")
            lines.extend(self._collect_updates_for_style(dp_results))

        return '\n'.join(lines) + '\n' if lines else ""

    def _collect_updates_for_style(self, results) -> list:
        '''指定されたリザルト群からレベル別の成果を集計してリストで返す'''
        # ランプ更新の集計 (同一譜面は最良のもののみ)
        best_lamp_updates = {}
        for r in results:
            if r.pre_lamp and r.lamp.value > r.pre_lamp.value:
                if r.chart_id not in best_lamp_updates or r.lamp.value > best_lamp_updates[r.chart_id].lamp.value:
                    best_lamp_updates[r.chart_id] = r

        # スコアランク更新の集計 (同一譜面は最良のもののみ)
        best_scores = {}
        for r in results:
            if r.notes and r.score:
                if r.chart_id not in best_scores or r.score > best_scores[r.chart_id].score:
                    best_scores[r.chart_id] = r

        # レベル別に統合して集計: {level: {項目名: count}}
        updates_by_level = {}

        # ランプ更新を集計
        for r in best_lamp_updates.values():
            songinfo = self.result_database.song_database.search(chart_id=r.chart_id)
            lv = songinfo.level if songinfo else 0
            if lv not in updates_by_level:
                updates_by_level[lv] = {}
            lamp_name = r.lamp.name.upper()
            updates_by_level[lv][lamp_name] = updates_by_level[lv].get(lamp_name, 0) + 1

        # スコアランク更新を集計
        for r in best_scores.values():
            if not r.notes or not r.score:
                continue
            rate = r.score / (r.notes * 2)
            pre_rate = r.pre_score / (r.notes * 2) if r.pre_score else 0
            rank_name = None
            if rate > 17/18 and pre_rate <= 17/18:
                rank_name = 'MAX-'
            elif rate > 16/18 and pre_rate <= 16/18:
                rank_name = 'AAA'
            elif rate > 14/18 and pre_rate <= 14/18:
                rank_name = 'AA'
            if rank_name:
                songinfo = self.result_database.song_database.search(chart_id=r.chart_id)
                lv = songinfo.level if songinfo else 0
                if lv not in updates_by_level:
                    updates_by_level[lv] = {}
                updates_by_level[lv][rank_name] = updates_by_level[lv].get(rank_name, 0) + 1

        if not updates_by_level:
            return []

        # ランプ・ランクの表示順序
        display_order = ['EASY', 'CLEAR', 'HARD', 'EXH', 'FC', 'AA', 'AAA', 'MAX-']

        lines = []
        for lv in sorted(updates_by_level.keys()):
            items = updates_by_level[lv]
            parts = []
            for key in display_order:
                if key in items:
                    parts.append(f"{key}+{items[key]}")
            # display_orderに含まれないものも念のため出力
            for key in sorted(items.keys()):
                if key not in display_order:
                    parts.append(f"{key}+{items[key]}")
            if parts:
                lv_str = f"☆{lv}" if lv else "☆?"
                lines.append(f"{lv_str} {', '.join(parts)}")

        return lines

    def write_bpi_csv(self):
        '''BPI Manager用csvの出力'''
        self.result_database.write_bpi_csv(play_style.sp)
        self.result_database.write_bpi_csv(play_style.dp)
        QMessageBox.information(
            self,
            "BPI Manager用csv出力機能",
            "bpi_sp.txt, bpi_dp.txtを出力しました。ファイルを開いてコピー&ペーストしてください。"
        )

_RESOURCES = [
    (define.screenrecognition_resourcename, resource.load_resource_screenrecognition),
    (define.informations_resourcename, resource.load_resource_informations),
    (define.details_resourcename,      resource.load_resource_details),
    (define.resultothers_resourcename, resource.load_resource_resultothers),
    (define.musictable_resourcename,   resource.load_resource_musictable),
    (define.musicselect_resourcename,  resource.load_resource_musicselect),
    (define.notesradar_resourcename,   resource.load_resource_notesradar),
    (define.unofficialdifficulty_resourcename, resource.load_resource_unofficialdifficulty),
    (define.deeper_resourcename,       resource.load_resource_deeper),
]

def check_resource():
    storage_acc = StorageAccessor()
    logger.debug('check_resource start')
    for res_name, load_func in _RESOURCES:
        if download_latestresource(storage_acc, f'{res_name}.res'):
            logger.debug(f"check ok, {res_name}")
            load_func()
    download_latestresource(storage_acc, musicnamechanges_filename)
    logger.debug('end')

def main():
    """メイン関数"""
    import threading
    threading.Thread(target=check_resource, daemon=True).start()
    # check_resource()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # モダンなスタイルを適用
    
    window = MainWindow()
    window.setWindowIcon(QIcon('src/icon.ico'))
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    updater = GitHubUpdater(
        github_author='dj-kata',
        github_repo='inf_daken_counter_obsw',
        zipfile_basename='inf_daken_counter',
        current_version=SWVER,           # 現在のバージョン
        main_exe_name="notes_counter.exe",  # メインプログラムのexe名
        updator_exe_name="notes_counter.exe",           # アップデート用プログラムのexe名
    )
    
    # メインプログラムから呼び出す場合
    updater.check_and_update()
    
    main()
