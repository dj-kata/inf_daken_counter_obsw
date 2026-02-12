"""ライバルスコアデータの取得・管理モジュール"""
import csv
import io
import re
import requests
from typing import Dict, List, Tuple, Optional

from PySide6.QtCore import QObject, QThread, Signal

from src.classes import clear_lamp
from src.funcs import convert_lamp
from src.logger import get_logger
logger = get_logger(__name__)


class RivalScoreEntry:
    """1譜面分のライバルスコア"""
    __slots__ = ('lamp', 'score', 'bp', 'last_played')

    def __init__(self):
        self.lamp: clear_lamp = clear_lamp.noplay
        self.score: int = 0
        self.bp: int = 99999999
        self.last_played: str = ""


class RivalData:
    """1ライバルの全スコアデータ"""
    def __init__(self, name: str):
        self.name: str = name
        self.scores: Dict[Tuple[str, str], RivalScoreEntry] = {}
        self.error: Optional[str] = None


class RivalFetchWorker(QThread):
    """バックグラウンドでライバルCSVを取得するワーカー"""

    finished = Signal(list)

    def __init__(self, rival_configs: List[Dict[str, str]]):
        super().__init__()
        self.rival_configs = rival_configs
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        results = []
        for config in self.rival_configs:
            if self._is_cancelled:
                break
            rival = RivalData(config["name"])
            try:
                url = self._convert_to_direct_url(config["url"])
                response = requests.get(url, timeout=15)
                response.raise_for_status()
                self._parse_csv(response.text, rival)
                logger.info(f"ライバル '{rival.name}' のCSVを取得しました ({len(rival.scores)}件)")
            except Exception as e:
                rival.error = str(e)
                logger.warning(f"ライバル '{config['name']}' のCSV取得に失敗: {e}")
            results.append(rival)
        self.finished.emit(results)

    @staticmethod
    def _convert_to_direct_url(url: str) -> str:
        """Google Drive共有URLまたはファイルIDを直接ダウンロードURLに変換"""
        # フルURL形式: https://drive.google.com/file/d/{ID}/...
        match = re.search(r'/file/d/([^/]+)', url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        # IDのみ (英数字・ハイフン・アンダースコアのみで構成)
        if re.fullmatch(r'[\w-]+', url):
            return f"https://drive.google.com/uc?export=download&id={url}"
        return url

    @staticmethod
    def _parse_csv(csv_text: str, rival: RivalData):
        """inf_score.csvフォーマットをパースしてRivalDataに格納

        CSV列: LV, Title, mode, Lamp, Score, (rate), BP, Opt(best score), Opt(min bp), Last Played
        """
        reader = csv.reader(io.StringIO(csv_text))
        next(reader, None)  # ヘッダーをスキップ
        for row in reader:
            if len(row) < 7:
                continue
            try:
                title = row[1]
                mode = row[2]
                lamp_str = row[3]
                score_str = row[4]
                bp_str = row[6]
                last_played = row[9] if len(row) > 9 else ""

                entry = RivalScoreEntry()
                entry.lamp = convert_lamp(lamp_str)
                entry.score = int(score_str) if score_str else 0
                entry.bp = int(bp_str) if bp_str else 99999999
                entry.last_played = str(last_played)

                rival.scores[(title, mode)] = entry
            except (ValueError, IndexError):
                continue


class RivalManager(QObject):
    """ライバルデータの取得・保持を管理するクラス"""

    rivals_loaded = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rivals: List[RivalData] = []
        self._worker: Optional[RivalFetchWorker] = None

    def start_fetch(self, rival_configs: List[Dict[str, str]]):
        """全ライバルのCSVをバックグラウンドで取得開始"""
        if not rival_configs:
            self.rivals = []
            self.rivals_loaded.emit()
            return

        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)

        self._worker = RivalFetchWorker(rival_configs)
        self._worker.finished.connect(self._on_fetch_finished)
        self._worker.start()

    def _on_fetch_finished(self, results: List[RivalData]):
        self.rivals = results
        self.rivals_loaded.emit()

    def get_rival_scores(self, title: str, mode: str) -> List[Tuple[str, RivalScoreEntry]]:
        """指定譜面の全ライバルスコアを返す

        Args:
            title: 曲名
            mode: 譜面モード文字列 ("SPA", "DPN" 等)

        Returns:
            (ライバル名, RivalScoreEntry)のリスト
        """
        results = []
        for rival in self.rivals:
            if rival.error:
                continue
            entry = rival.scores.get((title, mode))
            if entry is None and mode.startswith('DP'):
                battle_mode = 'DB' + mode[-1]
                entry = rival.scores.get((title, battle_mode))
            if entry:
                results.append((rival.name, entry))
        return results
