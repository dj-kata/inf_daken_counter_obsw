"""Run: .codex-venv/bin/python -B -m unittest misc.test_random_lane_websocket"""

import asyncio
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, Mock

from src.random_lane_analysis import RandomLaneAnalysis
from src.result_database import ResultDatabase
from src.websocket_server import DataWebSocketServer


class RandomLaneWebSocketTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_state_is_sent_on_connection_and_snapshot_request(self):
        server = DataWebSocketServer()
        state = {'phase': 'confirmed', 'layout': '3172654'}
        # No browser is connected when recognition completes.
        await server.broadcast_random_lane_data(state)
        server.graph_data = {'items': []}
        client = Mock(send=AsyncMock())
        await server.register_client(client)
        messages = [json.loads(call.args[0]) for call in client.send.call_args_list]
        self.assertIn({'type': 'random_lane', 'data': state}, messages)
        self.assertIn({'type': 'graph', 'data': server.graph_data}, messages)
        client.send.reset_mock()
        await server.send_latest_data(client)
        self.assertEqual(json.loads(client.send.call_args_list[0].args[0]),
                         {'type': 'random_lane', 'data': state})

    async def test_failed_client_does_not_block_other_clients_or_latest_state(self):
        server = DataWebSocketServer()
        good = Mock(send=AsyncMock())
        bad = Mock(send=AsyncMock(side_effect=ConnectionError('disconnected')))
        server.clients.update((good, bad))
        state = {'phase': 'partial', 'layout': '???1???'}
        await server.broadcast_random_lane_data(state)
        self.assertEqual(json.loads(good.send.call_args.args[0])['data'], state)
        self.assertEqual(server.random_lane_data, state)

    async def test_capture_thread_delivers_through_database_bridge(self):
        server = DataWebSocketServer()
        server.loop = asyncio.get_running_loop()
        received = asyncio.Event()
        async def send(message):
            received.set()
        client = Mock(send=AsyncMock(side_effect=send))
        server.clients.add(client)
        # Exercise the real database wrapper without loading user data/servers.
        database = ResultDatabase.__new__(ResultDatabase)
        database.ws_server = server
        with tempfile.TemporaryDirectory() as directory:
            thread = threading.Thread(target=RandomLaneAnalysis, kwargs={
                'db_path': Path(directory) / 'charts.sqlite3',
                'state_callback': database.broadcast_random_lane_data,
            })
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            await asyncio.wait_for(received.wait(), timeout=2)
        message = json.loads(client.send.call_args.args[0])
        self.assertEqual(message['type'], 'random_lane')
        self.assertEqual(message['data']['phase'], 'disabled')
        self.assertEqual(server.random_lane_data, message['data'])


if __name__ == '__main__':
    unittest.main()
