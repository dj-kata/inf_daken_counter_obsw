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
from pathlib import Path
import webbrowser, urllib
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
from src.result import ResultDatabase, OneResult
from src.result_stats_writer import ResultStatsWriter
from src.logger import get_logger
logger = get_logger('notes_counter')

from src.config_dialog import ConfigDialog
from src.obs_dialog import OBSControlDialog
from src.main_window import MainWindowUI
from src.storage import StorageAccessor

sys.path.append('infnotebook')
from define import define
# from src.resources import resource, check_latest
from resources import resource, check_latest
from record import musicnamechanges_filename

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

        # その他
        self.result_stats_writer = ResultStatsWriter()
        self.start_time = datetime.datetime.now().timestamp()
        '''起動時刻を覚えておく'''

        # アプリケーション状態
        self.current_mode = detect_mode.init
        self.start_time = time.time()
        self.today_judge = Judge(0,0,0,0,0,0)
        '''本日の判定内訳(全曲合計)'''
        for r in reversed(self.result_database.results):
            if r.judge and r.timestamp >= self.start_time - self.config.autoload_offset*3600:
                self.today_judge += r.judge
            else:
                break
        self.current_judge = Judge(0,0,0,0,0,0)
        '''このプレーの判定内訳。プレー画面終了後にプレー画面に移行していない場合に使う。'''
        self.result_timestamp = 0
        self.today_keystroke_count = 0
        self.saved_result_count = 0
        self.last_saved_song = "---"
        self.result_pre = None # 1つ前の認識結果
        self.last_play_mode = None
        '''現在のプレーモード。playの先頭でセットし、その後の検出で使用。'''
        
        # UI初期化
        self.init_ui()
        
        # OBS接続
        self.obs_manager.connect()
        
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

        self.today_judge = Judge(0,0,0,0,0,0)
        '''本日の判定内訳(全曲合計)'''
        for r in reversed(self.result_database.results):
            if r.timestamp >= self.start_time - self.config.autoload_offset*3600:
                if r.judge:
                    self.today_judge += r.judge
            else:
                break
        
        # OBS接続状態の再評価
        if not self.obs_manager.is_connected:
            self.obs_manager.connect()
    
    def show_about(self):
        """バージョン情報表示"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "バージョン情報", 
                         "IIDX Helper v1.0\n\n"
                         "OBS連携による自動リザルト保存アプリケーション")
    
    def save_image(self, skip_no_update:bool=False):
        """
        ゲーム画面のキャプチャ画像を保存する。リザルト画面なら曲名などをファイル名に入れる。
        """
        try:
            date = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            if self.screen_reader.is_result():
                detailed_result = self.screen_reader.read_result_screen()
                result = detailed_result.result
                if skip_no_update and (self.config.autosave_image_mode == config_autosave_image.only_updates): # 更新している場合のみ保存
                    result.pre_score,result.pre_bp,result.pre_lamp = self.result_database.get_best(title=result.title, style=result.play_style, difficulty=result.difficulty, battle=result.option.battle)
                    if not result.is_updated():
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
                if self.config.modify_rivalarea_mode == config_modify_rivalarea.mosaic: # モザイク処理する場合
                    screen = mosaic_rival_area(screen, detailed_result.result_side)
                    screen = mosaic_other_rival_names(screen, detailed_result.result_side)
                elif self.config.modify_rivalarea_mode == config_modify_rivalarea.cut: # カットする場合
                    screen = mosaic_other_rival_names(screen, detailed_result.result_side)
                    screen = cut_rival_area(screen, detailed_result.result_side)
                    # 統計情報ウィンドウを追加
                    screen = self.result_stats_writer.write_statistics(
                        screen,
                        title=result.title,
                        level=detailed_result.level,
                        play_style=result.play_style.name.upper(),
                        difficulty=result.difficulty.name.upper()[0],
                        ex_score=result.score,
                        bp=result.judge.bd + result.judge.pr,
                        max_notes=detailed_result.notes,
                        lamp=result.lamp.name.upper(),
                    )
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
        if trigger == 'play_start': # プレー画面の先頭で実行
            self.last_play_mode = self.screen_reader.detect_playside()
            logger.debug(f"current_judge: {self.current_judge}")
            if self.current_judge:
                self.today_judge += self.current_judge
                # リスタートしている場合、選曲画面で最後に選択した曲として登録
                if self.current_judge.pg + self.current_judge.gr + self.current_judge.gd + self.current_judge.bd > 0:
                    result = OneResult(
                        title=self.screen_reader.last_select_title,
                        play_style=self.screen_reader.last_select_style,
                        difficulty=self.screen_reader.last_select_difficulty,
                        lamp=clear_lamp.failed,
                        timestamp=int(datetime.datetime.now().timestamp()),
                        judge=self.current_judge,
                        dead=True,
                        playspeed=None, # 速度変更中のクイックリトライは正しく記録できないが、ノーツ数しか見ないのでOKとする。
                        option=None,    # battle利用時のクイックリトライは正しく記録できないが、ノーツ数しか見ないのでOKとする。
                    )
                    self.result_database.add(result)
                    self.result_database.save()
                self.current_judge = Judge(0,0,0,0,0,0)

        if trigger == 'result_start': # リザルト画面の先頭で実行
            self.result_pre = None # 1つ前の認識結果
            self.result_timestamp = int(datetime.datetime.now().timestamp())

    def execute_obs_triggers(self, trigger: str):
        """指定されたトリガーのOBS制御を実行"""
        logger.debug(f"OBSトリガー実行: {trigger}")
        try:
            # OBS制御ウィンドウが作成されていなくても設定は実行できるよう、
            # 直接設定データを読み込んで実行
            from src.obs_control import OBSControlData
            
            control_data = OBSControlData()
            control_data.set_config(self.config)
            settings = control_data.get_settings_by_trigger(trigger)
            
            if not settings:
                logger.debug(f"制御設定がないのでスキップ")
                return  # 該当する設定がない場合は何もしない
            
            if not self.obs_manager.is_connected:
                logger.debug(f"OBS未接続のため、トリガー '{trigger}' をスキップ")
                return
            
            for setting in settings:
                try:
                    action = setting["action"]
                    logger.debug(f"action = {action}")
                    
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
        result = detailed_result.result
        result.pre_score,result.pre_bp,result.pre_lamp = self.result_database.get_best(title=result.title, style=result.play_style, difficulty=result.difficulty, battle=result.option.battle)
        # logger.debug(f"best = score:{best_score},bp:{best_bp}, lamp:{best_lamp}")
        if result.is_updated():
            if self.result_database.add(result):
                self.statusBar().showMessage(f"選曲画面から自己ベストを登録しました。 -> {result}", 10000)
                self.result_database.save()
    
    def process_play_mode(self):
        """プレー画面での処理"""
        tmp = self.screen_reader.read_play_screen(self.last_play_mode)
        if tmp:
            self.current_judge = self.screen_reader.read_play_screen(self.last_play_mode)
        # logger.debug(f"mode:{self.last_play_mode}, self.current_judge = {self.current_judge}")
    
    def process_result_mode(self):
        """リザルト画面での処理"""
        # ここにresult画面での処理を実装
        # 例: リザルト読み取りと保存
        try:
            self.current_judge = Judge(0,0,0,0,0,0)
            detailed_result = self.screen_reader.read_result_screen()
            result = detailed_result.result
            result.timestamp = self.result_timestamp
            if result and result.chart_id:
                if result == self.result_pre:
                    # リザルトを保存
                    if self.result_database.add(result):
                        logger.info(f"added!, result={result}")
                        self.result_database.save()

                        # 画像の保存
                        if self.config.autosave_image_mode is not config_autosave_image.invalid:
                            if self.save_image(skip_no_update=self.config.autosave_image_mode==config_autosave_image.only_updates):
                                # 曲名の更新
                                self.last_saved_song = get_title_with_chart(result.title, result.play_style, result.difficulty)

                        # 統計情報の更新
                        self.saved_result_count += 1
                        if result.judge:
                            self.today_judge += result.judge

                self.result_pre = result
        except:
            logger.error(f"リザルト処理エラー: {traceback.format_exc()}")
    
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
        
        # OBS切断
        if self.obs_manager.is_connected:
            self.obs_manager.disconnect()
        
        # タイマーを停止
        self.main_timer.stop()
        self.display_timer.stop()

        logger.info("アプリケーション終了")
        event.accept()

    def tweet(self):
        '''成果ツイート'''
        # 対象となるリザルトを取り出す
        today_results = []
        for r in reversed(self.result_database.results): # 新しい順に探索
            if r.judge and r.timestamp >= self.start_time - self.config.autoload_offset*3600:
                today_results.append(r)
            else:
                break
        msg = f"plays:{len(today_results)}, notes:{self.today_judge.notes():,}, {self.today_judge.get_score_rate()*100:.2f}%\n"
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

def check_resource():
    storage = StorageAccessor()
    informations_filename = f'{define.informations_resourcename}.res'
    logger.debug('check_resource start')
    if check_latest(storage, informations_filename):
        resource.load_resource_informations()
    logger.debug('')

    details_filename = f'{define.details_resourcename}.res'
    if check_latest(storage, details_filename):
        resource.load_resource_details()
    logger.debug('')

    musictable_filename = f'{define.musictable_resourcename}.res'
    if check_latest(storage, musictable_filename):
        resource.load_resource_musictable()
    logger.debug('')

    musicselect_filename = f'{define.musicselect_resourcename}.res'
    if check_latest(storage, musicselect_filename):
        resource.load_resource_musicselect()
    logger.debug('')

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
    main()

