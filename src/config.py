import json
import os
import traceback
import logging, logging.handlers
os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

class Config:
    '''設定を管理するクラス'''
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.oraja_path = ""
        self.player_path = ""
        self.websocket_host = "localhost"
        self.websocket_port = 4444
        self.websocket_password = ""
        self.enable_websocket = False
        self.autoload_offset = 4
        self.enable_register_conditions = True  # 画面判定条件設定機能の有効/無効

        # ツイート機能関連
        self.enable_autotweet = False # 終了時の自動ツイート
        self.enable_judge = False # 判定部分
        self.enable_folder_updates = True # フォルダごとの更新数表示
        
        # ウィンドウ位置設定
        self.main_window_x = 100
        self.main_window_y = 100
        self.main_window_width = 500
        self.main_window_height = 300

        # スキップする難易度表の名前を登録
        # settings.py側はOKListを選択する形になっているが、DiffTableではこちらの方が扱いやすいので変換している。
        self.difftable_nglist = []

        # OBS自動制御設定
        self.obs_control_settings = []
        self.monitor_source_name = ""
        self.recognition_settings = {}
        
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
                    self.enable_websocket = config_data.get("enable_websocket", False)
                    self.enable_autotweet = config_data.get("enable_autotweet", False)
                    self.enable_judge = config_data.get("enable_judge", True)
                    self.enable_folder_updates = config_data.get("enable_folder_updates", False)
                    self.autoload_offset = config_data.get("autoload_offset", 0)
                    self.enable_register_conditions = config_data.get("enable_register_conditions", True)
                    
                    # ウィンドウ位置設定
                    window_config = config_data.get("window", {})
                    self.main_window_x = window_config.get("x", 100)
                    self.main_window_y = window_config.get("y", 100)
                    self.main_window_width = window_config.get("width", 500)
                    self.main_window_height = window_config.get("height", 300)

                    self.difftable_nglist = config_data.get('difftable_nglist', [])

                    # OBS自動制御設定
                    self.obs_control_settings = config_data.get('obs_control_settings', [])
                    self.monitor_source_name = config_data.get('monitor_source_name', "")
                    self.recognition_settings = config_data.get('recognition_settings', {})
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
            "enable_websocket": self.enable_websocket,
            "enable_autotweet": self.enable_autotweet,
            "enable_judge": self.enable_judge,
            "enable_folder_updates": self.enable_folder_updates,
            "autoload_offset": self.autoload_offset,
            # "enable_register_conditions": self.enable_register_conditions,
            "window": {
                "x": self.main_window_x,
                "y": self.main_window_y,
                "width": self.main_window_width,
                "height": self.main_window_height
            },
            "difftable_nglist": self.difftable_nglist,
            "obs_control_settings": self.obs_control_settings,
            "monitor_source_name": self.monitor_source_name,
            "recognition_settings": self.recognition_settings,
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