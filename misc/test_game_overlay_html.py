"""Offscreen integration test with Qt WebEngine and an isolated WebSocket server.

Run with QT_QPA_PLATFORM=offscreen in an environment with Qt WebEngine's native
libraries. Container-only Chromium flags, if needed, belong in the invocation.
"""

import json
from pathlib import Path
import threading
import time
import unittest

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from websockets.sync.server import serve

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

from src.game_overlay import HtmlLogOverlay, LOG_RECTS


@unittest.skipIf(QWebEngineView is None, 'Qt WebEngine native libraries are unavailable')
class GameOverlayHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def wait_for(self, predicate, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(.01)
        self.fail('Timed out waiting for overlay HTML')

    def javascript(self, script):
        result = []
        self.window.view.page().runJavaScript(script, result.append)
        self.wait_for(lambda: len(result) > 0)
        return result[0]

    def setUp(self):
        self.connections = []
        history_item = {'date': '2026/10/25 12:34', 'lamp': 5, 'score': 1800,
                        'score_rate': .9, 'bp': 12, 'opt': 'RANDOM', 'lane_layout': '3172654'}
        today_item = dict(history_item, title='Overlay test song', difficulty='SPA', lv=12,
                          notes=1000, pre_score=1700, pre_bp=15, pre_lamp=4, bpi='15.00')
        self.history = {'music': 'Overlay test song', 'difficulty': 'SPA', 'lv': 12,
                        'notes': 1000, 'best_score': 1800, 'best_score_rate': .9,
                        'best_bp': 12, 'best_lamp': 5, 'best_bpi': '15.00',
                        'items': [dict(history_item) for _ in range(25)]}
        self.today = {'items': [dict(today_item) for _ in range(30)]}

        def handler(connection):
            self.connections.append(connection)
            connection.send(json.dumps({'type': 'history_cursong', 'data': self.history}))
            connection.send(json.dumps({'type': 'today_updates', 'data': self.today}))
            for _ in connection:
                pass

        self.server = serve(handler, '127.0.0.1', 0)
        self.port = self.server.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.window = HtmlLogOverlay(Path(__file__).resolve().parents[1] / 'template')
        self.loaded = []
        self.window.view.loadFinished.connect(self.loaded.append)
        self.window.present((0, 0, 1260, 900))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        for connection in self.connections:
            connection.close()
        self.server.shutdown()
        self.thread.join(timeout=3)

    def assert_fits(self):
        size = []
        def has_fitted():
            size[:] = json.loads(self.javascript("""JSON.stringify((() => {
                const rect = document.getElementById('all').getBoundingClientRect();
                return [rect.width, rect.height, innerWidth, innerHeight];
            })())"""))
            return (size[2] > 0 and size[3] > 0
                    and size[0] <= size[2] + 1 and size[1] <= size[3] + 1)
        # Fitting is scheduled with requestAnimationFrame after data/layout changes.
        self.wait_for(has_fitted)
        self.assertGreater(size[2], 0)
        self.assertGreater(size[3], 0)
        self.assertLessEqual(size[0], size[2] + 1)
        self.assertLessEqual(size[1], size[3] + 1)

    def test_real_templates_receive_snapshots_live_updates_and_fit_all_rows(self):
        self.window.present(LOG_RECTS['song_history'])
        self.window.set_source('song_history', self.port)
        self.wait_for(lambda: bool(self.loaded))
        self.assertTrue(self.loaded[-1])
        self.wait_for(lambda: self.javascript("document.querySelectorAll('#result tbody tr').length") == 20)
        self.assertIn('Overlay test song', self.javascript('document.body.innerText'))
        self.assertIn('1800', self.javascript('document.body.innerText'))
        self.assert_fits()
        self.history['music'] = 'Updated title'
        self.connections[-1].send(json.dumps({'type': 'history_cursong', 'data': self.history}))
        self.wait_for(lambda: self.javascript("document.querySelector('.title-name')?.textContent") == 'Updated title')
        self.assert_fits()
        self.window.present(LOG_RECTS['today_results'])
        self.window.set_source('today_results', self.port)
        self.loaded.clear()
        self.wait_for(lambda: bool(self.loaded))
        self.assertTrue(self.loaded[-1])
        self.wait_for(lambda: self.javascript("document.querySelectorAll('#results-tbody tr').length") == 6)
        self.assertIn('Overlay test song', self.javascript('document.body.innerText'))
        self.assert_fits()
        previous_width = self.javascript('innerWidth')
        x, y, width, height = LOG_RECTS['today_results']
        self.window.present((x, y, width // 2, height // 2))
        # present() uses physical desktop pixels on Windows; Chromium and Qt
        # widgets use logical pixels when display scaling is enabled.
        self.wait_for(lambda: self.javascript('innerWidth') == self.window.view.width()
                      and self.window.view.width() < previous_width)
        self.assert_fits()
        self.assertTrue(self.window.profile.isOffTheRecord())

    def test_shared_lane_number_format_switches_both_views_and_falls_back_without_layout(self):
        for data in (self.history, self.today):
            data['items'][1]['lane_layout'] = None
            data['items'][2]['lane_layout'] = '?1??B?W'
        for item, table in (('song_history', '#result tbody'), ('today_results', '#results-tbody')):
            with self.subTest(item=item):
                self.window.present(LOG_RECTS[item])
                for enabled in (False, True, False):
                    self.loaded.clear()
                    self.window.set_source(item, self.port, show_lane_numbers=enabled)
                    self.wait_for(lambda: bool(self.loaded))
                    self.assertTrue(self.loaded[-1])
                    self.wait_for(lambda: self.javascript(f'document.querySelectorAll("{table} tr").length') > 2)
                    self.assertEqual(self.javascript("document.documentElement.classList.contains('lane-numbers-enabled')"), enabled)
                    display = self.javascript(f'getComputedStyle(document.querySelector("{table} tr:first-child .lane-option-numbers")).display')
                    self.assertEqual(display != 'none', enabled)
                    if enabled:
                        digits = self.javascript(f'Array.from(document.querySelectorAll("{table} tr:first-child .lane-option-key"), key => key.textContent).join("")')
                        self.assertEqual(digits, '3172654')
                        self.assertEqual(self.javascript(f'document.querySelectorAll("{table} tr:nth-child(2) .lane-option").length'), 0)
                        fallback = self.javascript(f'document.querySelector("{table} tr:nth-child(2)").textContent')
                        self.assertIn('RAN', fallback)
                        self.assertEqual(self.javascript(f'document.querySelectorAll("{table} tr:nth-child(3) .lane-option-key").length'), 7)
                        self.assertEqual(self.javascript(f'document.querySelectorAll("{table} tr:nth-child(3) .lane-option-key-unknown").length'), 4)
                    self.assert_fits()


if __name__ == '__main__':
    unittest.main()
