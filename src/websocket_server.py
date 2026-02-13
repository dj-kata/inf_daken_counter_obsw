"""
WebSocketサーバー - リアルタイムデータ配信用
"""
import asyncio
import websockets
import json
import xml.etree.ElementTree as ET
from typing import Set
import logging
import warnings

# asyncio関連の警告を抑制
warnings.filterwarnings('ignore', category=RuntimeWarning, message='coroutine.*was never awaited')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='Enable tracemalloc.*')

# ロガーの設定（src.loggerがない場合のフォールバック）
try:
    from src.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)


class DataWebSocketServer:
    """リアルタイムデータ配信用WebSocketサーバー"""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        self.loop = None
        
        # 各HTMLページ用の最新データ
        self.graph_data = None
        self.today_updates_data = None
        self.history_cursong_data = None
        self.today_stats_data = None
        
    async def register_client(self, websocket):
        """クライアントを登録し、最新データを送信"""
        self.clients.add(websocket)
        logger.info(f"クライアント接続: {websocket.remote_address}, 総接続数: {len(self.clients)}")
        
        # 接続時に最新データを送信
        if self.graph_data:
            await websocket.send(json.dumps({
                'type': 'graph',
                'data': self.graph_data
            }))
        if self.today_updates_data:
            await websocket.send(json.dumps({
                'type': 'today_updates',
                'data': self.today_updates_data
            }))
        if self.history_cursong_data:
            await websocket.send(json.dumps({
                'type': 'history_cursong',
                'data': self.history_cursong_data
            }))
        if self.today_stats_data:
            await websocket.send(json.dumps({
                'type': 'today_stats',
                'data': self.today_stats_data
            }))
    
    async def unregister_client(self, websocket):
        """クライアントを登録解除"""
        self.clients.discard(websocket)
        try:
            logger.info(f"クライアント切断: {websocket.remote_address}, 総接続数: {len(self.clients)}")
        except Exception:
            logger.info(f"クライアント切断, 総接続数: {len(self.clients)}")
    
    async def handler(self, websocket):
        """WebSocket接続ハンドラ（websockets v11以降対応）"""
        try:
            await self.register_client(websocket)
            async for message in websocket:
                # クライアントからのメッセージ処理（必要に応じて）
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except asyncio.CancelledError:
            # サーバー停止時のキャンセルを静かに処理
            pass
        except Exception as e:
            logger.error(f"ハンドラーエラー: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def broadcast_graph_data(self, data: dict):
        """グラフデータをブロードキャスト"""
        self.graph_data = data
        if self.clients:
            message = json.dumps({
                'type': 'graph',
                'data': data
            })
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
    
    async def broadcast_today_updates_data(self, data: dict):
        """本日の更新データをブロードキャスト"""
        self.today_updates_data = data
        if self.clients:
            message = json.dumps({
                'type': 'today_updates',
                'data': data
            })
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
    
    async def broadcast_history_cursong_data(self, data: dict):
        """履歴データをブロードキャスト"""
        self.history_cursong_data = data
        if self.clients:
            message = json.dumps({
                'type': 'history_cursong',
                'data': data
            })
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )

    async def broadcast_today_stats_data(self, data: dict):
        """統計データをブロードキャスト"""
        self.today_stats_data = data
        if self.clients:
            message = json.dumps({
                'type': 'today_stats',
                'data': data
            })
            await asyncio.gather(
                *[client.send(message) for client in self.clients],
                return_exceptions=True
            )
    
    def start(self, loop=None):
        """サーバーを開始（非同期）"""
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        
        async def start_server():
            self.server = await websockets.serve(
                self.handler,
                "localhost",
                self.port
            )
            logger.info(f"WebSocketサーバー起動: ポート {self.port}")
        
        asyncio.run_coroutine_threadsafe(start_server(), loop)
    
    def stop(self):
        """サーバーを停止（すべての接続を閉じてから）"""
        if self.server and self.loop:
            async def stop_server():
                # すべてのクライアント接続を閉じる
                if self.clients:
                    close_tasks = [ws.close() for ws in self.clients.copy()]
                    await asyncio.gather(*close_tasks, return_exceptions=True)
                    logger.info(f"{len(self.clients)}個の接続を閉じました")
                
                # サーバーを停止
                self.server.close()
                await self.server.wait_closed()
                logger.info("WebSocketサーバー停止完了")
            
            # 停止処理を実行して完了を待つ
            future = asyncio.run_coroutine_threadsafe(stop_server(), self.loop)
            try:
                future.result(timeout=5.0)  # 最大5秒待つ
            except Exception as e:
                logger.error(f"サーバー停止エラー: {e}")
    
    def update_graph_data(self, data: dict):
        """グラフデータを更新（同期メソッド）"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_graph_data(data),
                self.loop
            )
    
    def update_today_updates_data(self, data: dict):
        """本日の更新データを更新（同期メソッド）"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_today_updates_data(data),
                self.loop
            )
    
    def update_history_cursong_data(self, data: dict):
        """履歴データを更新（同期メソッド）"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_history_cursong_data(data),
                self.loop
            )

    def update_today_stats_data(self, data: dict):
        """統計データを更新（同期メソッド）"""
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_today_stats_data(data),
                self.loop
            )


def xml_to_dict(element: ET.Element) -> dict:
    """XMLエレメントを辞書に変換"""
    result = {}
    
    # 子要素がない場合はテキストを返す
    if len(element) == 0:
        return element.text or ""
    
    # 子要素がある場合
    for child in element:
        child_data = xml_to_dict(child)
        
        # 同じタグ名の要素が複数ある場合はリストにする
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data
    
    return result