"""
IIDX Helper - メインプログラム
OBS連携による自動リザルト保存アプリケーション
"""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer
import time
import traceback
import datetime
from pathlib import Path
import webbrowser, urllib
import copy
import os

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
from src.songinfo import SongDatabase
from src.screen_reader import ScreenReader
from src.result import ResultDatabase, OneResult, DetailedResult
from src.result_stats_writer import ResultStatsWriter
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
from resources import resource, check_latest
from record import musicnamechanges_filename

try:
    with open('version.txt', 'r') as f:
        tmp = f.readline()
        print(tmp)
        SWVER = tmp.strip()[2:] if tmp.startswith('v') else tmp.strip()
except Exception:
    SWVER = "0.0.0"

class MainWindow(MainWindowUI):
    """メインウィンドウクラス - 制御ロジックを担当"""
    
    def __init__(self):
        # 設定とデータベースの初期化
        self.config = Config()
        super().__init__(self.config)
        self.song_database = SongDatabase()
        self.result_database = ResultDatabase(config=self.config)
        self.screen_reader = ScreenReader()
        
        # OBS接続マネージャーの初期化
        self.obs_manager = OBSWebSocketManager()
        self.obs_manager.set_config(self.config)

        # 接続状態変化のシグナルを接続
        self.obs_manager.connection_changed.connect(self.on_obs_connection_changed)

        # その他
        self.result_stats_writer = ResultStatsWriter()
        self.start_time = datetime.datetime.now().timestamp()
        '''起動時刻を覚えておく'''

        # アプリケーション状態
        self.current_mode = detect_mode.init
        self.start_time = time.time()
        self.today_judge = Judge()
        '''本日のプレーの判定内訳'''
        self.current_judge = Judge()
        '''このプレーの判定内訳'''
        self.set_today_judge()
        self.result_database.broadcast_today_updates_data(self.start_time - self.config.autoload_offset*3600)
        self.result_database.broadcast_graph_data(self.start_time - self.config.autoload_offset*3600)
        self.result_timestamp = 0
        self.today_keystroke_count = 0
        self.play_count = 0
        self.last_saved_song = "---"
        self.result_pre = None # 1つ前の認識結果
        self.last_play_mode = None
        '''現在のプレーモード。playの先頭でセットし、その後の検出で使用。'''
        
        # UI初期化
        self.init_ui()
        
        # OBS接続
        self.obs_manager.connect()
        
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
        
        # グローバルホットキーの登録
        self.setup_global_hotkeys()
        
        logger.info("アプリケーション起動完了")
    
    def check_obs_configuration(self):
        """OBS設定をチェックし、問題があれば警告ダイアログを表示"""
        status = self.obs_manager.get_detailed_status()
        
        warnings = []
        
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
    
    def open_config_dialog(self):
        """設定ダイアログを開く"""
        dialog = ConfigDialog(self.config, self.result_database, self.screen_reader, self)
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
    
    def set_today_judge(self):
        '''本日の判定内訳(play中の判定合計)を対象ログから集計'''
        self.today_judge.reset()
        self.play_count = 0
        for r in reversed(self.result_database.results):
            if r.detect_mode == detect_mode.play and r.judge:
                if r.timestamp >= self.start_time - self.config.autoload_offset*3600:
                    self.play_count += 1
                    self.today_judge += r.judge
                else:
                    break

    def update_all_configs(self):
        """全てのクラスに設定を反映"""
        self.config.load_config()  # 最新の設定を読み込み
        self.obs_manager.set_config(self.config)
        self.result_database.song_database.load()  # 必要に応じて再読み込み

        self.result_database.broadcast_today_updates_data(self.start_time - self.config.autoload_offset*3600)
        self.result_database.broadcast_graph_data(self.start_time - self.config.autoload_offset*3600)
        self.set_today_judge()

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
                        bpi=detailed_result.bpi,
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
            if self.current_judge and  self.current_judge.notes() > 0:
                result = self.screen_reader.read_play_screen(self.current_judge)
                self.result_database.add(result)
                self.result_database.save()
                self.result_database.broadcast_graph_data(self.start_time - self.config.autoload_offset*3600)

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
                    
                    elif action == "show_source":
                        scene_name = setting.get("scene")
                        source_name = setting.get("source")
                        if scene_name and source_name:
                            mod_scene_name, scene_item_id = self.obs_manager.search_itemid(scene_name, source_name)
                            if scene_item_id:
                                self.obs_manager.enable_source(mod_scene_name, scene_item_id)
                                print(f"ソースを表示: {scene_name}/{source_name} (id:{scene_item_id})")
                    
                    elif action == "hide_source":
                        scene_name = setting.get("scene")
                        source_name = setting.get("source")
                        if scene_name and source_name:
                            mod_scene_name, scene_item_id = self.obs_manager.search_itemid(scene_name, source_name)
                            if scene_item_id:
                                self.obs_manager.send_command("set_scene_item_enabled",
                                                            scene_name=mod_scene_name,
                                                            scene_item_id=scene_item_id,
                                                            scene_item_enabled=False)
                                self.obs_manager.disable_source(mod_scene_name, scene_item_id)
                                print(f"ソースを非表示: {scene_name}/{source_name} (id:{scene_item_id})")
                                
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
        # 自己べ登録
        if self.result_database.add(result):
            self.statusBar().showMessage(f"選曲画面から自己ベストを登録しました。 -> {result}", 10000)
            self.result_database.save()
    
    def process_play_mode(self):
        """プレー画面での処理"""
        tmp = self.screen_reader.get_judge_from_play_screen(self.last_play_mode)
        # logger.debug(f"mode:{self.last_play_mode}, self.current_judge = {self.current_judge}")
        if tmp:
            self.current_judge = tmp
        # TODO 多分websocketなのでプレイ中に都度送信しても負荷が低い
        # self.result_database.broadcast_graph_data(self.start_time - self.config.autoload_offset*3600)
    
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
                    # リザルトを保存
                    if self.result_database.add(result):
                        self.result_database.save()
                        self.result_database.broadcast_today_updates_data(self.start_time - self.config.autoload_offset*3600)

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
                    )

                self.result_pre = result
        except:
            pass
            # logger.error(f"リザルト処理エラー: {traceback.format_exc()}")
    
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
        self.result_database.write_best_csv()
        
        # OBS切断
        if self.obs_manager.is_connected:
            self.obs_manager.disconnect()
        
        # タイマーを停止
        self.main_timer.stop()
        self.display_timer.stop()

        # WebSocketサーバーとHTMLサーバーを停止
        if hasattr(self.result_database, 'shutdown_servers'):
            self.result_database.shutdown_servers()

        logger.info("アプリケーション終了")
        event.accept()

    def tweet(self):
        '''成果ツイート'''
        msg = f"plays:{self.play_count}, notes:{self.today_judge.notes():,}, {self.today_judge.get_score_rate()*100:.2f}%\n"
        if self.config.enable_judge:
            msg += f"(PG:{self.today_judge.pg:,}, GR:{self.today_judge.gr:,}, GD:{self.today_judge.gd:,}, BD:{self.today_judge.bd:,}, PR:{self.today_judge.pr:,}, CB:{self.today_judge.cb:,})\n"
        if self.config.enable_folder_updates:
            pass
        ontime = datetime.datetime.now() - datetime.datetime.fromtimestamp(self.start_time)
        msg += f"uptime: {str(ontime).split('.')[0]}\n"
        date = datetime.datetime.fromtimestamp(self.start_time)
        logger.info(date.year)
        logger.info(date.month)
        logger.info(self.result_database.get_monthly_notes())
        msg += f"({date.year}/{date.month:02d}: {self.result_database.get_monthly_notes():,})\n"
        msg += '#INFINITAS_daken_counter\n'
        encoded_msg = urllib.parse.quote(msg)
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")

    def write_bpi_csv(self):
        '''BPI Manager用csvの出力'''
        self.result_database.write_bpi_csv(play_style.sp)
        self.result_database.write_bpi_csv(play_style.dp)
        QMessageBox.information(
            self,
            "BPI Manager用csv出力機能",
            "bpi_sp.txt, bpi_dp.txtを出力しました。ファイルを開いてコピー&ペーストしてください。"
        )

def check_resource():
    storage = StorageAccessor()
    informations_filename = f'{define.informations_resourcename}.res'
    logger.debug('check_resource start')
    if check_latest(storage, informations_filename):
        resource.load_resource_informations()

    details_filename = f'{define.details_resourcename}.res'
    if check_latest(storage, details_filename):
        resource.load_resource_details()

    musictable_filename = f'{define.musictable_resourcename}.res'
    if check_latest(storage, musictable_filename):
        resource.load_resource_musictable()

    musicselect_filename = f'{define.musicselect_resourcename}.res'
    if check_latest(storage, musicselect_filename):
        resource.load_resource_musicselect()

    check_latest(storage, musicnamechanges_filename)
    logger.debug('end')

def main():
    """メイン関数"""
    import threading
    threading.Thread(target=check_resource, daemon=True).start()
    # check_resource()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # モダンなスタイルを適用
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    updater = GitHubUpdater(
        github_author='dj-kata',
        github_repo='inf_daken_counter_obsw',
        current_version=SWVER,           # 現在のバージョン
        main_exe_name="notes_counter.exe",  # メインプログラムのexe名
        updator_exe_name="notes_counter.exe",           # アップデート用プログラムのexe名
    )
    
    # メインプログラムから呼び出す場合
    updater.check_and_update()
    
    main()

