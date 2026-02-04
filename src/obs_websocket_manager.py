import time
import threading
import traceback
from typing import Callable, Optional, List, Dict, Any
from PySide6.QtCore import QObject, Signal

from src.config import Config
from src.logger import get_logger
logger = get_logger(__name__)

try:
    from obsws_python import ReqClient
    OBSWS_AVAILABLE = True
except ImportError:
    ReqClient = None
    OBSWS_AVAILABLE = False
    logger.warning("obsws_python not installed. Install with: pip install obsws-python")


class OBSWebSocketManager(QObject):
    """
    OBS WebSocket接続管理クラス（改善版）
    
    機能:
    - 自動再接続
    - 切断検出
    - 接続状態変化通知（Qtシグナル）
    """
    
    # Qtシグナル定義
    connection_changed = Signal(bool, str)  # (is_connected, message)
    
    def __init__(self):
        super().__init__()
        
        self.config: Optional[Config] = None
        self.client: Optional[ReqClient] = None
        self.is_connected = False
        
        # 再接続設定
        self.auto_reconnect = True  # 自動再接続を有効化
        self.reconnect_interval = 5.0  # 再接続試行間隔（秒）
        self.max_reconnect_attempts = 0  # 0=無限に再試行
        
        # 接続監視スレッド
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_running = False
        self.stop_event = threading.Event()
        
        # 画面サイズ設定
        self.picw = 1920
        self.pich = 1080
        self.screen = None
    
    def set_config(self, config: Config):
        """設定をセット"""
        self.config = config
        logger.info(f"OBS WebSocket config set: {config.websocket_host}:{config.websocket_port}")
    
    def connect(self):
        """OBSに接続"""
        if not OBSWS_AVAILABLE:
            self._emit_status("obsws_python がインストールされていません", False)
            return False
        
        if not self.config:
            self._emit_status("設定が読み込まれていません", False)
            return False
        
        try:
            # 既存の接続を切断
            if self.client:
                try:
                    self.client.disconnect()
                except:
                    pass
                self.client = None
            
            # 新しい接続を確立
            logger.info(f"Connecting to OBS WebSocket: {self.config.websocket_host}:{self.config.websocket_port}")
            
            self.client = ReqClient(
                host=self.config.websocket_host,
                port=self.config.websocket_port,
                password=self.config.websocket_password,
                timeout=5
            )
            
            # 接続テスト
            self.client.get_version()
            
            self.is_connected = True
            self._emit_status(f"接続成功 ({self.config.websocket_host}:{self.config.websocket_port})", True)
            
            # 接続監視スレッドを開始
            self.start_monitor()
            
            return True
            
        except Exception as e:
            self.is_connected = False
            self.client = None
            error_msg = f"接続失敗: {str(e)}"
            self._emit_status(error_msg, False)
            logger.error(f"OBS WebSocket connection failed: {e}")
            
            # 自動再接続が有効な場合は監視スレッドを開始
            if self.auto_reconnect:
                self.start_monitor()
            
            return False
    
    def disconnect(self):
        """OBSから切断"""
        logger.info("Disconnecting from OBS WebSocket")
        
        # 監視スレッドを停止
        self.stop_monitor()
        
        # 接続を切断
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
        
        self.is_connected = False
        self._emit_status("切断しました", False)
    
    def start_monitor(self):
        """接続監視スレッドを開始"""
        if self.monitor_running:
            return
        
        self.monitor_running = True
        self.stop_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_connection,
            daemon=True,
            name="OBSMonitorThread"
        )
        self.monitor_thread.start()
        
        logger.info("Connection monitor thread started")
    
    def stop_monitor(self):
        """接続監視スレッドを停止"""
        if not self.monitor_running:
            return
        
        self.monitor_running = False
        self.stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
            self.monitor_thread = None
        
        logger.info("Connection monitor thread stopped")
    
    def _monitor_connection(self):
        """
        接続監視ループ（バックグラウンドスレッド）
        
        機能:
        1. 定期的に接続状態をチェック
        2. 切断を検出したら自動再接続を試みる
        """
        consecutive_failures = 0
        check_interval = 2.0  # 接続確認間隔（秒）
        
        while self.monitor_running and not self.stop_event.is_set():
            try:
                # 設定チェック
                if not self.config:
                    time.sleep(check_interval)
                    continue
                
                # 接続状態チェック
                if self.is_connected and self.client:
                    # 接続中の場合、pingして確認
                    try:
                        self.client.get_version()
                        consecutive_failures = 0  # 成功したらカウンタリセット
                        
                    except Exception as e:
                        # 接続が切れた
                        logger.warning(f"OBS connection lost: {e}")
                        self.is_connected = False
                        self.client = None
                        self._emit_status("接続が切断されました", False)
                        consecutive_failures += 1
                
                else:
                    # 未接続の場合、自動再接続を試みる
                    if self.auto_reconnect:
                        # 最大再接続試行回数チェック
                        if self.max_reconnect_attempts > 0 and consecutive_failures >= self.max_reconnect_attempts:
                            logger.error(f"Max reconnection attempts reached: {self.max_reconnect_attempts}")
                            self._emit_status(f"再接続失敗（{self.max_reconnect_attempts}回試行）", False)
                            time.sleep(check_interval)
                            continue
                        
                        # 再接続試行
                        logger.info(f"Attempting to reconnect to OBS... (attempt {consecutive_failures + 1})")
                        self._emit_status(f"再接続中... ({consecutive_failures + 1}回目)", False)
                        
                        try:
                            self.client = ReqClient(
                                host=self.config.websocket_host,
                                port=self.config.websocket_port,
                                password=self.config.websocket_password,
                                timeout=5
                            )
                            
                            # 接続テスト
                            self.client.get_version()
                            
                            # 成功
                            self.is_connected = True
                            self._emit_status(f"再接続成功 ({self.config.websocket_host}:{self.config.websocket_port})", True)
                            logger.info("OBS reconnection successful")
                            consecutive_failures = 0
                            
                        except Exception as e:
                            # 再接続失敗
                            self.is_connected = False
                            self.client = None
                            consecutive_failures += 1
                            logger.debug(f"Reconnection failed: {e}")
                            
                            # 次の再接続まで待機
                            time.sleep(self.reconnect_interval)
                            continue
                
            except Exception as e:
                logger.error(f"Monitor thread error: {e}\n{traceback.format_exc()}")
            
            # 次のチェックまで待機
            time.sleep(check_interval)
        
        logger.info("Monitor thread terminated")
    
    def _emit_status(self, message: str, is_connected: bool):
        """接続状態変化を通知"""
        self.is_connected = is_connected
        logger.info(f"OBS status: {message} (connected={is_connected})")
        try:
            self.connection_changed.emit(is_connected, message)
        except: # アプリ終了時にエラーを吐かないようにする
            pass
    
    def get_status(self) -> tuple[str, bool]:
        """現在のステータスを取得"""
        if not OBSWS_AVAILABLE:
            return "obsws_python がインストールされていません", False
        elif not self.config:
            return "設定が読み込まれていません", False
        elif self.is_connected:
            return f"接続中 ({self.config.websocket_host}:{self.config.websocket_port})", True
        else:
            return "切断中", False
    
    def send_command(self, command_name: str, **kwargs):
        """
        OBSにコマンドを送信（汎用メソッド）
        
        Args:
            command_name: 実行するコマンド名
            **kwargs: コマンドのパラメータ
            
        Returns:
            コマンドの実行結果、またはエラー時はNone
        """
        if not self.is_connected or not self.client:
            logger.warning(f"OBS WebSocket not connected (command: {command_name})")
            return None
        
        try:
            # 動的にメソッドを呼び出し
            method = getattr(self.client, command_name)
            result = method(**kwargs)
            logger.debug(f"OBS command executed: {command_name}")
            return result
        except AttributeError:
            logger.error(f"Unknown OBS command: {command_name}")
            return None
        except Exception as e:
            logger.error(f"OBS command failed: {command_name}, error: {e}")
            # コマンド失敗時は接続が切れた可能性がある
            # 次の監視ループで自動的に検出・再接続される
            return None
    
    def get_scene_list(self) -> List[Dict]:
        """シーン一覧を取得"""
        try:
            if not self.is_connected or not self.client:
                return []
            res = self.client.get_scene_list()
            return res.scenes
        except Exception as e:
            logger.debug(f"Failed to get scenes: {e}")
            return []
    
    def get_source_list(self, scene: str) -> List[str]:
        """指定シーンのソース一覧を取得"""
        ret = []
        try:
            if not self.is_connected or not self.client:
                return ret
            
            allitem = self.client.get_scene_item_list(scene).scene_items
            for x in allitem:
                if x['isGroup']:
                    grp = self.client.get_group_scene_item_list(x['sourceName']).scene_items
                    for y in grp:
                        ret.append(y['sourceName'])
                ret.append(x['sourceName'])
        except Exception as e:
            logger.debug(f"Failed to get sources: {e}")
        
        ret.reverse()
        return ret
    
    def change_scene(self, name: str):
        """シーンを変更"""
        try:
            if self.is_connected and self.client:
                self.client.set_current_program_scene(name)
                return True
        except Exception as e:
            logger.error(f"Failed to change scene: {e}")
        return False
    
    def change_text(self, source: str, text: str):
        """テキストソースを変更"""
        try:
            if self.is_connected and self.client:
                self.client.set_input_settings(source, {'text': text}, True)
                return True
        except Exception as e:
            logger.debug(f"Failed to change text: {e}")
        return False
    
    def screenshot(self):
        """OBSソースのキャプチャをself.screenに格納"""
        import os
        import sys
        sys.path.append('infnotebook')
        from screenshot import open_screenimage
        
        if not os.path.exists('out'):
            os.makedirs('out')
        dst = os.path.abspath('out/capture.png')
        
        try:
            if self.save_screenshot_dst(self.config.monitor_source_name, dst):
                self.screen = open_screenimage(dst)
            else:
                self.screen = None
        except Exception as e:
            # logger.error(f"Screenshot failed: {e}")
            self.screen = None
    
    def save_screenshot_dst(self, source: str, dst: str) -> bool:
        """スクリーンショットを保存"""
        try:
            if not self.is_connected or not self.client:
                return False
            
            res = self.client.save_source_screenshot(
                source, 'png', dst, 
                self.picw, self.pich, 100
            )
            return True
        except Exception as e:
            # logger.debug(f"Failed to save screenshot: {e}")
            return False
    
    def enable_source(self, scenename: str, sourceid: int):
        """ソースを有効化"""
        try:
            if self.is_connected and self.client:
                self.client.set_scene_item_enabled(scenename, sourceid, enabled=True)
                return True
        except Exception as e:
            logger.error(f"Failed to enable source: {e}")
        return False
    
    def disable_source(self, scenename: str, sourceid: int):
        """ソースを無効化"""
        try:
            if self.is_connected and self.client:
                self.client.set_scene_item_enabled(scenename, sourceid, enabled=False)
                return True
        except Exception as e:
            logger.error(f"Failed to disable source: {e}")
        return False
    
    def search_itemid(self, scene: str, target: str) -> tuple[str, Optional[int]]:
        """ソースのIDを検索"""
        ret = scene, None
        try:
            if not self.is_connected or not self.client:
                return ret
            
            allitem = self.client.get_scene_item_list(scene).scene_items
            for x in allitem:
                if x['sourceName'] == target:
                    ret = scene, x['sceneItemId']
                if x['isGroup']:
                    grp = self.client.get_group_scene_item_list(x['sourceName']).scene_items
                    for y in grp:
                        if y['sourceName'] == target:
                            ret = x['sourceName'], y['sceneItemId']
        except Exception as e:
            logger.debug(f"Failed to search item id: {e}")
        
        return ret
    
    def __del__(self):
        """デストラクタ"""
        self.disconnect()

# メイン関数（テスト用）
if __name__ == "__main__":
    # テスト用のダミー設定
    class DummyConfig:
        def __init__(self):
            self.websocket_host = "localhost"
            self.websocket_port = 4455
            self.websocket_password = ""
            self.enable_register_conditions = True
    
    # テスト用のダミーOBSマネージャー
    class DummyOBSManager:
        def __init__(self):
            self.is_connected = False
        
        def get_scene_list(self):
            return None
        
        def send_command(self, command, **kwargs):
            return None
    
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示
    
    config = DummyConfig()
    obs_manager = DummyOBSManager()
    control_window = OBSControlWindow(root, obs_manager, config)
    
    root.mainloop()