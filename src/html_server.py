"""OBSカタログ用HTMLをlocalhostだけに配信するHTTPサーバー。"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

from src.logger import get_logger


logger = get_logger(__name__)


class _CatalogRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, application_root: Path, **kwargs):
        self.application_root = application_root.resolve()
        self.template_dir = (self.application_root / "template").resolve()
        self.websocket_css = (self.application_root / "out" / "websocket.css").resolve()
        super().__init__(*args, directory=str(self.application_root), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        # OBSブラウザソースからの通常アクセスはアプリログへ出力しない。
        pass

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        target = (self.application_root / path.lstrip("/")).resolve()
        if not self._is_allowed(target):
            self.send_error(404, "File not found")
            return None
        return super().send_head()

    def _is_allowed(self, target: Path) -> bool:
        return target == self.websocket_css or target.is_relative_to(self.template_dir)


class _CatalogThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False


class HtmlCatalogHTTPServer:
    """設定された固定ポートでHTMLを配信する。"""

    def __init__(self, application_root: Path):
        self.application_root = Path(application_root).resolve()
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int | None = None

    def start(self, port: int) -> int | None:
        if self.httpd is not None:
            return self.port

        port = int(port)
        handler = partial(
            _CatalogRequestHandler,
            application_root=self.application_root,
        )
        try:
            self.httpd = _CatalogThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as error:
            logger.error(f"OBSカタログHTTPポート {port} を使用できません: {error}")
            self.httpd = None
            return None
        self.port = port

        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="HtmlCatalogHTTPServer",
            daemon=True,
        )
        self.thread.start()
        logger.info(f"OBSカタログHTTPサーバー起動: http://127.0.0.1:{self.port}/")
        return self.port

    def stop(self):
        if self.httpd is None:
            return
        httpd = self.httpd
        thread = self.thread
        self.httpd = None
        self.thread = None
        self.port = None
        try:
            httpd.shutdown()
            httpd.server_close()
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        except Exception as error:
            logger.error(f"OBSカタログ用HTTPサーバー停止エラー: {error}")
        finally:
            logger.info("OBSカタログHTTPサーバー停止")
