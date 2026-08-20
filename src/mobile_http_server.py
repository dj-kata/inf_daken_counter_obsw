"""スマホ向けスコア閲覧HTTPサーバ。"""

from __future__ import annotations

import json
import mimetypes
import socket
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from src.logger import get_logger

logger = get_logger(__name__)


class _MobileThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True


class MobileScoreHTTPServer:
    """ResultDatabase の内容をLAN内ブラウザへ配信する軽量HTTPサーバ。"""

    def __init__(self, result_database, host: str = "0.0.0.0", port: int = 8787):
        self.result_database = result_database
        self.host = host
        self.port = int(port)
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self):
        if self.httpd is not None:
            return
        self._stopping.clear()

        try:
            self.httpd = _MobileThreadingHTTPServer(
                (self.host, self.port),
                self._make_handler(),
            )
        except OSError as e:
            logger.error(f"スマホ向けHTTPサーバ起動失敗: {self.host}:{self.port} {e}")
            self.httpd = None
            return

        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="MobileScoreHTTPServer",
            daemon=True,
        )
        self.thread.start()
        logger.info(f"スマホ向けHTTPサーバ起動: http://{self.host}:{self.port}/")

    def stop(self):
        if self.httpd is None:
            return
        self._stopping.set()
        httpd = self.httpd
        thread = self.thread
        self.httpd = None
        try:
            httpd.shutdown()
            httpd.server_close()
            if thread and thread.is_alive():
                thread.join(timeout=2.0)
        except Exception as e:
            logger.error(f"スマホ向けHTTPサーバ停止エラー: {e}")
        finally:
            self.thread = None
            logger.info("スマホ向けHTTPサーバ停止")

    def _make_handler(self):
        result_database = self.result_database
        stopping = self._stopping

        class Handler(BaseHTTPRequestHandler):
            server_version = "INFINITASMobileHTTP/1.0"

            def log_message(self, format, *args):
                logger.debug("HTTP " + format, *args)

            def do_GET(self):
                if stopping.is_set():
                    self._safe_send_error(HTTPStatus.SERVICE_UNAVAILABLE, "server stopping")
                    return

                parsed = urlparse(self.path)
                path = unquote(parsed.path)
                query = parse_qs(parsed.query)

                try:
                    if path == "/" or path == "/index.html":
                        self._send_file(Path("template") / "mobile_score_viewer.html")
                    elif path.startswith("/api/"):
                        self._handle_api(path, query)
                    else:
                        self._send_error(HTTPStatus.NOT_FOUND, "not found")
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    logger.debug(f"HTTPクライアント切断: {path}")
                except socket.timeout:
                    logger.debug(f"HTTPクライアントタイムアウト: {path}")
                except Exception as e:
                    logger.error(f"スマホ向けHTTPリクエストエラー: {e}\n{traceback.format_exc()}")
                    self._safe_send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal error")

            def _handle_api(self, path: str, query: dict[str, list[str]]):
                lock = getattr(result_database, "_mobile_api_lock", None)
                if lock is not None:
                    with lock:
                        return self._handle_api_unlocked(path, query)
                return self._handle_api_unlocked(path, query)

            def _handle_api_unlocked(self, path: str, query: dict[str, list[str]]):
                if path == "/api/folders":
                    self._send_json(result_database.get_mobile_folders_data())
                    return
                if path.startswith("/api/folders/style/"):
                    parts = path.strip("/").split("/")
                    if len(parts) == 6 and parts[0] == "api" and parts[1] == "folders" and parts[2] == "style" and parts[4] == "level":
                        style_text = parts[3].upper()
                        level_text = parts[5]
                        self._send_json(
                            result_database.get_mobile_level_folder_data(
                                int(level_text),
                                style_text,
                            )
                        )
                        return
                if path.startswith("/api/folders/level/"):
                    level_text = path.rsplit("/", 1)[-1]
                    self._send_json(result_database.get_mobile_level_folder_data(int(level_text)))
                    return
                if path == "/api/folders/history":
                    limit = int((query.get("limit") or ["200"])[0])
                    offset = int((query.get("offset") or ["0"])[0])
                    self._send_json(result_database.get_mobile_history_data(limit, offset))
                    return
                if path == "/api/folders/receipt":
                    self._send_json(result_database.get_mobile_receipt_data())
                    return
                if path == "/api/folders/daily":
                    mode = (query.get("mode") or ["daily"])[0]
                    self._send_json(result_database.get_mobile_daily_folders_data(mode))
                    return
                if path.startswith("/api/folders/daily/month/"):
                    month_key = path.rsplit("/", 1)[-1]
                    self._send_json(result_database.get_mobile_monthly_daily_folders_data(month_key))
                    return
                if path.startswith("/api/folders/daily/year/"):
                    year_key = path.rsplit("/", 1)[-1]
                    self._send_json(result_database.get_mobile_yearly_month_folders_data(year_key))
                    return
                if path.startswith("/api/folders/daily/"):
                    date_key = path.rsplit("/", 1)[-1]
                    self._send_json(result_database.get_mobile_daily_log_data(date_key))
                    return
                if path == "/api/folders/current":
                    self._send_json(result_database.get_mobile_current_folder_data())
                    return
                if path.startswith("/api/result-images/"):
                    timestamp = path.rsplit("/", 1)[-1]
                    image_path = result_database.get_mobile_result_image_path(int(timestamp))
                    if image_path is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "image not found")
                    else:
                        self._send_file(image_path)
                    return
                if path.startswith("/api/charts/"):
                    chart_id = path.rsplit("/", 1)[-1]
                    data = result_database.get_mobile_chart_detail_data(chart_id)
                    if data is None:
                        self._send_error(HTTPStatus.NOT_FOUND, "chart not found")
                    else:
                        self._send_json(data)
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "api not found")

            def _send_json(self, data: dict):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self._send_body(
                    HTTPStatus.OK,
                    body,
                    "application/json; charset=utf-8",
                    cache_control="no-store",
                )

            def _send_file(self, path: Path):
                if not path.exists() or not path.is_file():
                    self._send_error(HTTPStatus.NOT_FOUND, "file not found")
                    return
                body = path.read_bytes()
                content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                if path.suffix.lower() == ".html":
                    content_type = "text/html; charset=utf-8"
                self._send_body(HTTPStatus.OK, body, content_type, cache_control="no-cache")

            def _send_error(self, status: HTTPStatus, message: str):
                body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
                self._send_body(status, body, "application/json; charset=utf-8")

            def _safe_send_error(self, status: HTTPStatus, message: str):
                try:
                    self._send_error(status, message)
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass

            def _send_body(
                self,
                status: HTTPStatus,
                body: bytes,
                content_type: str,
                cache_control: str | None = None,
            ):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                if cache_control:
                    self.send_header("Cache-Control", cache_control)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
