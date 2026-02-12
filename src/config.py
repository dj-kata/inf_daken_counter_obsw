import json
import os
import traceback
from src.logger import get_logger
logger = get_logger(__name__)
from src.classes import config_autosave_image, config_modify_rivalarea, music_pack

class Config:
    '''設定を管理するクラス'''
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.oraja_path = ""
        self.player_path = ""
        self.websocket_host = "localhost"
        self.websocket_port = 4444
        self.websocket_password = ""
        self.autoload_offset = 4
        self.main_window_geometry = None

        # ツイート機能関連
        self.enable_autotweet = False # 終了時の自動ツイート
        self.enable_judge = False # 判定部分
        self.enable_folder_updates = True # フォルダごとの更新数表示
        
        # ウィンドウ位置設定
        self.main_window_x = 100
        self.main_window_y = 100
        self.main_window_width = 500
        self.main_window_height = 300

        # OBS自動制御設定
        self.obs_control_settings = []
        self.monitor_source_name = ""

        self.image_save_path = 'results'

        # 言語設定
        self.language = 'ja'  # 'ja' or 'en'
        
        # WebSocketデータ配信ポート
        self.websocket_data_port = 8767
        
        # スコアビューワ設定
        self.score_viewer_style = 'SP'  # 'SP', 'DP', 'Battle'
        self.score_viewer_levels = list(range(1, 13))  # [1, 2, ..., 12]
        
        # 楽曲パック集計対象設定（デフォルトはunknown以外の全て）
        self.target_music_packs = [pack.name for pack in music_pack if pack != music_pack.unknown]
        
        # 画像保存設定
        self.autosave_image_mode = config_autosave_image.only_updates  # 画像保存条件
        self.modify_rivalarea_mode = config_modify_rivalarea.invalid  # ライバル欄編集方法
        self.write_statistics = False  # 統計情報を書き込むか

        # ライバルスコア設定
        self.rivals = []  # [{"name": "...", "url": "..."}]
        self.csv_export_path = ''  # inf_score.csvの出力先 (空=ルート直下)

        self.load_config()
        self.save_config()
    
    def load_config(self):
        """設定ファイルから設定を読み込む"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.oraja_path = config_data.get("oraja_path", "")
                    self.player_path = config_data.get("player_path", "")
                    self.websocket_host = config_data.get("websocket_host", "localhost")
                    self.websocket_port = config_data.get("websocket_port", 4444)
                    self.websocket_password = config_data.get("websocket_password", "")
                    self.enable_autotweet = config_data.get("enable_autotweet", False)
                    self.enable_judge = config_data.get("enable_judge", True)
                    self.enable_folder_updates = config_data.get("enable_folder_updates", False)
                    self.autoload_offset = config_data.get("autoload_offset", 0)
                    self.main_window_geometry = config_data.get("main_window_geometry", None)
                    
                    # ウィンドウ位置設定
                    window_config = config_data.get("window", {})
                    self.main_window_x = window_config.get("x", 100)
                    self.main_window_y = window_config.get("y", 100)
                    self.main_window_width = window_config.get("width", 500)
                    self.main_window_height = window_config.get("height", 300)

                    # OBS自動制御設定
                    self.obs_control_settings = config_data.get('obs_control_settings', [])
                    self.monitor_source_name = config_data.get('monitor_source_name', "")

                    # リザルト画像保存先フォルダ
                    self.image_save_path = config_data.get('image_save_path', 'results')
                    
                    # WebSocketポート設定
                    self.websocket_data_port = config_data.get('websocket_data_port', 8767)

                    # 言語設定
                    self.language = config_data.get('language', 'ja')
                    
                    # スコアビューワ設定
                    self.score_viewer_style = config_data.get('score_viewer_style', 'SP')
                    self.score_viewer_levels = config_data.get('score_viewer_levels', list(range(1, 13)))
                    
                    # 楽曲パック集計対象設定
                    self.target_music_packs = config_data.get('target_music_packs', [])
                    
                    # 設定ファイルに存在しない新しい楽曲パックを自動的に追加
                    # (将来music_packに項目が追加された際の対応)
                    all_packs = [pack.name for pack in music_pack if pack != music_pack.unknown]
                    for pack_name in all_packs:
                        if pack_name not in self.target_music_packs:
                            self.target_music_packs.append(pack_name)
                    
                    # 画像保存設定
                    self.autosave_image_mode = config_autosave_image(config_data.get('autosave_image_mode', config_autosave_image.invalid.value))
                    self.modify_rivalarea_mode = config_modify_rivalarea(config_data.get('modify_rivalarea_mode', config_modify_rivalarea.invalid.value))
                    self.write_statistics = config_data.get('write_statistics', False)

                    # ライバルスコア設定
                    self.rivals = config_data.get('rivals', [])
                    self.csv_export_path = config_data.get('csv_export_path', '')
            except Exception as e:
                logger.error(traceback.format_exc())
                print(f"設定ファイル読み込みエラー: {e}")
    
    def save_config(self):
        """設定ファイルに設定を保存する"""
        config_data = {
            "oraja_path": self.oraja_path,
            "player_path": self.player_path,
            "websocket_host": self.websocket_host,
            "websocket_port": self.websocket_port,
            "websocket_password": self.websocket_password,
            "enable_autotweet": self.enable_autotweet,
            "enable_judge": self.enable_judge,
            "enable_folder_updates": self.enable_folder_updates,
            "autoload_offset": self.autoload_offset,
            "main_window_geometry": self.main_window_geometry,
            "obs_control_settings": self.obs_control_settings,
            "monitor_source_name": self.monitor_source_name,
            "image_save_path": self.image_save_path,
            "websocket_data_port": self.websocket_data_port,
            "target_music_packs": self.target_music_packs,
            "autosave_image_mode": self.autosave_image_mode.value,
            "modify_rivalarea_mode": self.modify_rivalarea_mode.value,
            "write_statistics": self.write_statistics,
            "language": self.language,
            "score_viewer_style": self.score_viewer_style,
            "score_viewer_levels": self.score_viewer_levels,
            "rivals": self.rivals,
            "csv_export_path": self.csv_export_path,
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(traceback.format_exc())
            print(f"設定ファイル保存エラー: {e}")
    
    def save_window_position(self, x, y, width, height):
        """ウィンドウ位置を保存"""
        self.main_window_x = x
        self.main_window_y = y
        self.main_window_width = width
        self.main_window_height = height
        self.save_config()
    
    def get_target_file_path(self):
        """監視対象のファイルパスを取得する（例：指定フォルダ内のtarget.txtファイル）"""
        if self.oraja_path:
            return os.path.join(self.oraja_path, "target.txt")
        return ""
    
    def __str__(self):
        out = 'obs_control_settings: '
        for s in self.obs_control_settings:
            print(f"{s},")