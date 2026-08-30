# ResultDatabase - リザルトの永続化・検索・配信を担当
from .classes import *
from .funcs import *
from .songinfo import *
from .result import PlayOption, CurrentOption, OneResult, DetailedResult, OneBestData
from .logger import get_logger
from .config import Config

logger = get_logger(__name__)
import os
import sys
import datetime
import math
import bz2, pickle
import traceback
import functools
import csv
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
import copy
import threading
from io import BytesIO

from PIL import Image


def _to_int_or_none(value):
    """文字列/数値のどちらで来てもintへ寄せる。変換不能ならNone。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float_or_none(value):
    """文字列/数値のどちらで来てもfloatへ寄せる。変換不能ならNone。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_katate_band(songinfo):
    """譜面レベルに対応する片手難易度帯を返す。"""
    if not songinfo:
        return None
    level = _to_int_or_none(getattr(songinfo, "level", None))
    if level == 12:
        return getattr(songinfo, "katate_12", None)
    if level == 11:
        return getattr(songinfo, "katate_11", None)
    return None


def _mobile_chart_id(title, style, diff, battle: bool = False):
    chart_id = calc_chart_id(title, style, diff, battle=battle)
    if chart_id and battle:
        return f"dbx:{chart_id}"
    return chart_id


def _split_mobile_chart_id(chart_id: str) -> tuple[str, bool | None]:
    if isinstance(chart_id, str) and chart_id.startswith("dbx:"):
        return chart_id[4:], True
    return chart_id, None


def _mobile_result_image_id(index: int, result: OneResult) -> str:
    return f"{index}-{int(result.timestamp)}"


def _ws_broadcast(ws_method_name: str):
    """WebSocket配信用デコレータ。ws_serverがNoneなら何もしない。"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.ws_server is None:
                return
            try:
                data = func(self, *args, **kwargs)
                getattr(self.ws_server, ws_method_name)(data)
            except Exception as e:
                logger.error(f"{func.__name__} エラー: {traceback.format_exc()}")

        return wrapper

    return decorator


def _extract_songinfo_fields(songinfo) -> dict:
    """songinfoから非公式難易度フィールドを辞書で返す"""
    if not songinfo:
        return {}
    fields = {}
    for attr, key in [
        ("dp_unofficial", "dp_unofficial_lv"),
        ("sp12_hard", "sp_12hard"),
        ("sp12_clear", "sp_12clear"),
        ("sp11_hard", "sp_11hard"),
        ("sp11_clear", "sp_11clear"),
        ("dp_ereter_easy", "dp_ereter_easy"),
        ("dp_ereter_hard", "dp_ereter_hard"),
        ("dp_ereter_exh", "dp_ereter_exh"),
    ]:
        val = getattr(songinfo, attr, None)
        fields[key] = str(val) if val else ""
    katate_band = _get_katate_band(songinfo)
    fields["katate_band"] = str(katate_band) if katate_band else ""
    return fields


class ResultDatabase:
    """全リザルトを保存するためのクラス"""

    def __init__(self, config: Config = None):
        self.song_database = SongDatabase()
        """曲情報クラスのインスタンス。検索用。"""
        self.results: List[OneResult] = []
        """全リザルトが格納されるリスト。OneResultが1エントリとなる。"""

        # WebSocketサーバー関連の初期化
        self.config = config
        self.ws_server = None
        self.ws_loop = None
        self.ws_thread = None
        self.rival_manager = None
        self.mobile_http_server = None
        self._mobile_http_server_signature = None
        self._mobile_api_lock = threading.RLock()
        self.app_start_time = int(datetime.datetime.now().timestamp())

        # configが渡された場合のみWebSocketサーバーを起動
        if config is not None:
            self._init_websocket_server()
            self._init_mobile_http_server()
            # WebSocket設定をCSSファイルに書き込み
            self._write_websocket_config()

        self.load()
        self.save()

    def _write_websocket_config(self):
        """WebSocketポート番号をCSSファイルに書き込む"""
        try:
            os.makedirs("out", exist_ok=True)

            css_content = f"""/* WebSocket設定 - 自動生成ファイル */
    :root {{
        --websocket-port: {self.config.websocket_data_port};
    }}
    """

            css_path = Path("out") / "websocket.css"
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css_content)

            logger.info(f"WebSocket設定を書き込みました: {css_path}")
            logger.debug(f"  ポート番号: {self.config.websocket_data_port}")
        except Exception as e:
            logger.error(f"WebSocket設定ファイル書き込みエラー: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def _init_websocket_server(self):
        """WebSocketサーバーを初期化（HTMLサーバーは不要）"""
        import asyncio
        import threading
        from .websocket_server import DataWebSocketServer

        # WebSocket用の非同期イベントループを別スレッドで起動
        self.ws_loop = asyncio.new_event_loop()
        self.ws_thread = threading.Thread(
            target=self._start_websocket_loop, daemon=True
        )
        self.ws_thread.start()

        # WebSocketサーバーの起動
        self.ws_server = DataWebSocketServer(self.config.websocket_data_port)
        self.ws_server.start(self.ws_loop)

        logger.info(f"WebSocketサーバー起動: ポート {self.config.websocket_data_port}")

    def _init_mobile_http_server(self):
        """スマホ向けHTTPサーバーを初期化。"""
        signature = self._mobile_config_signature()
        self._mobile_http_server_signature = signature
        if not signature[0]:
            return
        from .mobile_http_server import MobileScoreHTTPServer

        _, host, port = signature
        self.mobile_http_server = MobileScoreHTTPServer(self, host=host, port=port)
        if not self.mobile_http_server.start():
            self.mobile_http_server = None

    def _mobile_config_signature(self):
        """モバイルHTTPサーバーの再起動要否判定に使う設定値。"""
        if not self.config:
            return (False, "0.0.0.0", 8787)
        enabled = bool(getattr(self.config, "mobile_score_server_enabled", False))
        host = getattr(self.config, "mobile_score_server_host", "0.0.0.0") or "0.0.0.0"
        port = _to_int_or_none(getattr(self.config, "mobile_score_server_port", 8787))
        if port is None:
            port = 8787
        return (enabled, host, port)

    def restart_mobile_http_server(self, force: bool = False):
        """設定変更後にスマホ向けHTTPサーバーを再起動する。"""
        with self._mobile_api_lock:
            signature = self._mobile_config_signature()
            server_running = bool(
                self.mobile_http_server and self.mobile_http_server.is_running()
            )
            expected_running = signature[0]
            if (
                not force
                and self._mobile_http_server_signature == signature
                and server_running == expected_running
            ):
                logger.debug("スマホ向けHTTPサーバ設定変更なし: 再起動をスキップ")
                return

            if self.mobile_http_server:
                self.mobile_http_server.stop()
                self.mobile_http_server = None
            self._mobile_http_server_signature = None
            if self.config:
                self._init_mobile_http_server()

    def _start_websocket_loop(self):
        """WebSocket用イベントループをスレッドで実行"""
        import asyncio

        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_forever()

    def shutdown_servers(self):
        """サーバーを停止（アプリケーション終了時に呼び出す）"""
        if self.ws_server:
            self.ws_server.stop()
        with self._mobile_api_lock:
            if self.mobile_http_server:
                self.mobile_http_server.stop()
                self.mobile_http_server = None
        if self.ws_loop:
            self.ws_loop.call_soon_threadsafe(self.ws_loop.stop)
        logger.info("サーバーを停止しました")

    def update_websocket_port(self, port: int):
        """WebSocketポート番号を更新"""
        if self.config:
            self.config.websocket_data_port = port
            self._write_websocket_config()  # CSSファイルを更新
            logger.info(f"WebSocketポート更新: {port}")

    @_ws_broadcast("update_graph_data")
    def broadcast_graph_data(self, start_time: int):
        """グラフデータをWebSocketで配信"""
        return self.get_graph_data(start_time)

    @_ws_broadcast("update_option_data")
    def broadcast_option_data(self, option: CurrentOption):
        """グラフデータをWebSocketで配信"""
        return self.get_option_data(option)

    @_ws_broadcast("update_today_updates_data")
    def broadcast_today_updates_data(self, start_time: int):
        """本日の更新データをWebSocketで配信"""
        return self.get_today_updates_data(start_time)

    @_ws_broadcast("update_history_cursong_data")
    def broadcast_history_cursong_data(
        self,
        title: str,
        style,
        difficulty,
        battle: bool = None,
        playspeed: float = None,
        allscratch: bool = False,
        regularspeed: bool = False,
    ):
        """履歴データをWebSocketで配信"""
        return self.get_history_cursong_data(
            title, style, difficulty, battle, playspeed, allscratch, regularspeed
        )

    @_ws_broadcast("update_today_stats_data")
    def broadcast_today_stats_data(self, start_time: int):
        """統計データをWebSocketで配信"""
        return self.get_today_stats_data(start_time)

    _SPECIAL_ARRANGE_KEYWORDS = ["H-RAN", "SYMM-RAN", "SYNC-RAN"]

    def _filter_results_for_best(
        self,
        results: List[DetailedResult],
        playspeed: float = None,
        battle: bool = False,
        allscratch: bool = False,
        regularspeed: bool = False,
    ) -> List[DetailedResult]:
        """自己ベスト計算用にリザルトをフィルタリングする。

        以下の3ケースに分けて対象リザルトを絞り込む:
        - playspeed is not None: 同一playspeedの detect_mode.result のみ
        - battle=True: battle=True の detect_mode.result のみ
        - 上記以外: playspeed=None かつ battleでない detect_mode.result / detect_mode.select

        Args:
            results: フィルタ対象のリザルトリスト
            playspeed: 再生速度（Noneは通常速度）
            battle: バトルモードかどうか
            allscratch: all-scr利用時かどうか
            regularspeed: regul-speed利用時かどうか

        Returns:
            フィルタ済みリザルトのリスト
        """
        filtered = []

        for r in results:
            # detect_mode.play は常に除外（途中落ちの判定ができないため）
            if r.result.detect_mode == detect_mode.play:
                continue
            # 特殊配置オプション(H-RAN, SYMM-RAN, SYNC-RAN)は常に除外
            if r.result.option and r.result.option.arrange:
                if any(
                    kw in r.result.option.arrange
                    for kw in self._SPECIAL_ARRANGE_KEYWORDS
                ):
                    continue

            option = r.result.option
            if option is None:
                option = PlayOption(None)

            # playspeed指定時: 同一playspeedの detect_mode.result のみ
            # None と 1.0 は等価として扱う
            target_speed = 1.0 if playspeed is None else playspeed
            result_speed = 1.0 if r.result.playspeed is None else r.result.playspeed

            if allscratch != option.allscratch:
                continue
            if regularspeed != option.regularspeed:
                continue
            if result_speed != target_speed:
                continue

            if battle:
                if not option.battle:
                    continue
            else:
                if r.result.detect_mode == detect_mode.play:
                    continue
                if option.battle:
                    continue

            filtered.append(r)
        return filtered

    def add(self, result: OneResult) -> bool:
        """リザルト登録用関数。chart_id情報を何も渡さなくても受ける(途中落ちのノーツ数保存用)

        Args:
            result (OneResult): リザルト

        Return:
            bool(True:登録された / False:登録済み等の理由で却下された)
        """
        if result.detect_mode == detect_mode.play:
            self.results.append(result)
            logger.info(
                f"result added! hash:{hash(result)}, len:{len(self.results)}, result:{result}"
            )
            return True
        else:
            if not result.lamp or not result.score:
                logger.warning(f"result rejected (lamp or score missing): {result}")
                return False
            if (result.detect_mode == detect_mode.result) and (
                result.option.valid == False
            ):
                logger.warning(f"result rejected (option is invalid): {result}")
                return False
            if result not in self.results:
                battle = True if result.option and result.option.battle else False
                if result.pre_lamp is None:
                    result.pre_score, result.pre_bp, result.pre_lamp = self.get_best(
                        title=result.title,
                        style=result.play_style,
                        difficulty=result.difficulty,
                        battle=battle,
                        playspeed=result.playspeed,
                        allscratch=result.option.allscratch,
                        regularspeed=result.option.regularspeed,
                    )
                if (
                    result.detect_mode == detect_mode.select
                    and result.pre_score is not None
                ):
                    if not result.is_updated():
                        logger.info(f"select result skipped (no update): {result}")
                        return False
                self.results.append(result)
                logger.info(
                    f"result added! hash:{hash(result)}, len:{len(self.results)}, result:{result}"
                )
                return True
            else:
                return False

    def load(self):
        """保存済みリザルトをロードする"""
        try:
            with bz2.BZ2File("playlog.infdc", "rb", compresslevel=9) as f:
                self.results = pickle.load(f)
        except Exception:
            logger.error(traceback.format_exc())

    def save(self):
        """ファイル出力"""
        with bz2.BZ2File("playlog.infdc", "wb", compresslevel=9) as f:
            pickle.dump(self.results, f)

    def _result_matches_chart(
        self,
        result: OneResult,
        chart_id: str = None,
        title: str = None,
        style: play_style = None,
        difficulty: difficulty = None,
        battle: bool = False,
    ) -> bool:
        """chart_idの完全一致に加え、songinfo更新前後の表記差も同一譜面として扱う。"""
        result_battle = result.option.battle if result.option else False
        if title is not None and style is not None and difficulty is not None:
            if bool(result_battle) != bool(battle):
                return False
            if chart_id and result.chart_id == chart_id:
                return True
        elif chart_id and result.chart_id == chart_id:
            return True
        if title is None or style is None or difficulty is None:
            return False
        return calc_chart_lookup_key(
            result.title, result.play_style, result.difficulty, battle=result_battle
        ) == calc_chart_lookup_key(title, style, difficulty, battle=battle)

    def _search_songinfo_for_result(self, result: OneResult) -> OneSongInfo:
        """保存当時の曲名表記が古くても現在のsonginfoを返す。"""
        return self.song_database.search(
            title=result.title,
            play_style=result.play_style,
            difficulty=result.difficulty,
        )

    def search(
        self,
        title: str = None,
        style: play_style = None,
        difficulty: difficulty = None,
        chart_id: str = None,
        battle: bool = False,
    ) -> List[DetailedResult]:
        """全リザルトの中から指定された譜面のプレーログのみを取り出してリストで返す

        Args:
            title (str, optional): 曲名. Defaults to None.
            play_style (play_style, optional): SP/DPのスタイル. Defaults to None.
            difficulty (difficulty, optional): 譜面難易度. Defaults to None.
            chart_id (str, optional): 譜面ID. Defaults to None.

        Returns:
            List[DetailedResult]: 検索結果(詳細付きリザルトのリスト)
        """
        ret: List[DetailedResult] = []
        key = chart_id
        if title is not None and style is not None and difficulty is not None:
            key = calc_chart_id(title, style, difficulty, battle=battle)
        songinfo = self.song_database.search(
            title=title, play_style=style, difficulty=difficulty
        ) or self.song_database.search(chart_id=key)

        for r in self.results:
            if self._result_matches_chart(r, key, title, style, difficulty, battle):
                detail_songinfo = songinfo or self._search_songinfo_for_result(r)
                detail = DetailedResult(detail_songinfo, r)
                ret.append(detail)
        return ret

    def get_best(
        self,
        title: str = None,
        style: play_style = None,
        difficulty: difficulty = None,
        chart_id: str = None,
        battle: bool = None,
        option: PlayOption = None,
        playspeed: float = None,
        allscratch: bool = False,
        regularspeed: bool = False,
    ) -> List:
        """指定された曲の自己べ(スコア, BP, ランプ)を返す。見つからない場合は0,0を返す。

        Args:
            title (str, optional): 曲名. Defaults to None.
            style (play_style, optional): SP/DP. Defaults to None.
            difficulty (difficulty, optional): 譜面難易度. Defaults to None.
            chart_id (str, optional): 譜面ID. Defaults to None.
            battle (bool, optional): バトルモードの判定に使う. Defaults to None.
            option (PlayOption, optional): 同一オプションのリザルトのみとしたい場合に指定. Defaults to None.
            playspeed (float, optional): 再生速度. Defaults to None.
            allscratch (bool, optional): all-scrかどうか
            regularspeed (bool, optional): regul-speedかどうか

        Returns:
            List[int]: score, bp, lamp
        """
        ret = [0, 99999999, clear_lamp(0)]
        key = chart_id
        if title is not None and style is not None and difficulty is not None:
            key = calc_chart_id(title, style, difficulty, battle=battle)
        if title is not None and style is not None and difficulty is not None:
            results = self.search(
                title=title, style=style, difficulty=difficulty, battle=battle
            )
        else:
            results = self.search(chart_id=key)
        filtered = self._filter_results_for_best(
            results,
            playspeed=playspeed,
            battle=battle,
            allscratch=allscratch,
            regularspeed=regularspeed,
        )
        if not filtered:
            return [None, None, None]
        for r in filtered:
            if option:  # オプション指定がある場合は、arrangeが一致するもののみ通す
                if (
                    option.arrange is not r.result.option.arrange
                    or option.flip is not r.result.option.flip
                    or option.special is not r.result.option.special
                ):
                    continue
            ret[0] = max(ret[0], r.result.score)
            if r.result.judge:
                if not r.result.dead:
                    ret[1] = min(ret[1], r.result.judge.bd + r.result.judge.pr)
            elif r.result.bp is not None:  # 選曲画面から登録したものはこちら
                ret[1] = min(ret[1], r.result.bp)
            ret[2] = clear_lamp(max(ret[2].value, r.result.lamp.value))

        return ret

    def get_monthly_notes(self, target: datetime.datetime = None):
        """その月のノーツ数を算出"""
        if target is None:
            target = datetime.datetime.now()
        ret = 0
        for r in reversed(self.results):
            result_date = datetime.datetime.fromtimestamp(r.timestamp)
            if r.detect_mode != detect_mode.play:
                continue
            if (result_date.month == target.month) and (
                result_date.year == target.year
            ):
                if r.judge:
                    ret += r.judge.notes
            else:
                break
        return ret

    def get_recent_monthly_notes(
        self, target: datetime.datetime = None, months: int = 3
    ) -> List[dict]:
        """targetを含む直近monthsヶ月分のノーツ数を算出"""
        if target is None:
            target = datetime.datetime.now()

        month_keys = []
        year = target.year
        month = target.month
        for _ in range(months):
            month_keys.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1

        totals = {key: 0 for key in month_keys}
        oldest_year, oldest_month = month_keys[-1]

        for r in reversed(self.results):
            if r.detect_mode != detect_mode.play or not r.judge:
                continue

            result_date = datetime.datetime.fromtimestamp(r.timestamp)
            key = (result_date.year, result_date.month)
            if key not in totals and key < (oldest_year, oldest_month):
                break

            if key in totals:
                totals[key] += r.judge.notes

        return [
            {
                "label": f"{year}/{month:02d}",
                "notes": totals[(year, month)],
            }
            for year, month in reversed(month_keys)
        ]

    def get_yearly_notes(self, target: datetime.datetime = None) -> int:
        """target年のノーツ数を算出"""
        if target is None:
            target = datetime.datetime.now()

        ret = 0
        for r in reversed(self.results):
            if r.detect_mode != detect_mode.play or not r.judge:
                continue

            result_date = datetime.datetime.fromtimestamp(r.timestamp)
            if result_date.year < target.year:
                break

            if result_date.year == target.year:
                ret += r.judge.notes

        return ret

    def get_all_best_results(self) -> Dict[tuple, OneBestData]:
        """全譜面のベストリザルトをOneBestDataとして集計（battle有効/無効を別々に集計）
        detect_mode.playのリザルトは除外する。
        playspeedがNoneまたは1.0以外のリザルトは除外する。
        optionはdetect_mode.resultの場合にのみ有効とする。
        bp, lamp, scoreが同点の場合、detect_mode.resultのオプションで上書きする。

        Returns:
            Dict[tuple, OneBestData]: (title, play_style, difficulty, battle)をキーとした辞書
        """
        best_results: Dict[tuple, OneBestData] = {}

        for result in self.results:
            if result.detect_mode == detect_mode.play:
                continue
            if result.playspeed not in (None, 1.0):
                continue
            if result.option.allscratch:
                continue
            if result.option.regularspeed:
                continue
            if type(result.score) is not int:
                continue

            battle = result.option.battle if result.option else None
            key = (result.title, result.play_style, result.difficulty, battle)

            if key not in best_results:
                best = OneBestData()
                best.title = result.title
                best.style = result.play_style
                best.difficulty = result.difficulty
                best.songinfo = self._search_songinfo_for_result(result)
                best_results[key] = best
            else:
                best = best_results[key]

            # ベストスコア更新
            if result.score and (
                not best.best_score_result
                or result.score > best.best_score_result.score
            ):
                best.best_score_result = copy.deepcopy(result)
            elif (
                result.score
                and best.best_score_result
                and result.score == best.best_score_result.score
            ):
                if result.detect_mode == detect_mode.result:
                    best.best_score_result.option = result.option
                if getattr(result, "bpim2", None) is not None:
                    best.best_score_result.bpim2 = result.bpim2
                if getattr(result, "bpim2_arena_averages", None):
                    best.best_score_result.bpim2_arena_averages = result.bpim2_arena_averages

            # 最小BP更新
            current_bp = (
                result.bp if (result.bp is not None and not result.dead) else 99999
            )
            best_bp = (
                best.min_bp_result.bp
                if best.min_bp_result and best.min_bp_result.bp is not None
                else 99999
            )
            if current_bp < best_bp:
                best.min_bp_result = copy.deepcopy(result)
            elif current_bp == best_bp and result.detect_mode == detect_mode.result:
                if best.min_bp_result:
                    best.min_bp_result.option = result.option

            # ベストランプ更新
            if result.lamp:
                if (
                    not best.best_lamp_result
                    or result.lamp.value > best.best_lamp_result.lamp.value
                ):
                    best.best_lamp_result = copy.deepcopy(result)
                elif (
                    result.lamp.value == best.best_lamp_result.lamp.value
                    and result.detect_mode == detect_mode.result
                ):
                    if best.best_lamp_result:
                        best.best_lamp_result.option = result.option

            # 最終プレー日更新
            if not best.last_result or result.timestamp > best.last_result.timestamp:
                best.last_result = result

            # ノーツ数を埋めておく
            if result.notes:
                if best.best_score_result:
                    best.best_score_result.notes = result.notes
                if best.best_lamp_result:
                    best.best_lamp_result.notes = result.notes
                if best.min_bp_result:
                    best.min_bp_result.notes = result.notes

        return best_results

    def get_graph_data(self, start_time: int, end_time: int | None = None) -> dict:
        """本日のノーツ数用データを辞書形式で返す"""
        target = []
        total = Judge()
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.play:
                if self._timestamp_in_range(r.timestamp, start_time, end_time):
                    target.append(r)
                    if r.judge:
                        total += r.judge

        # 現在のスコアレートを計算
        current_score_rate = "0.00%"
        if len(target) > 0:
            latest_result = target[0]
            if (
                hasattr(latest_result, "score")
                and hasattr(latest_result, "notes")
                and latest_result.notes
            ):
                current_score_rate = (
                    f"{latest_result.score / latest_result.notes / 2 * 100:.2f}%"
                )

        data = {
            "start_time": start_time,
            "playcount": len(target),
            "today_notes": total.pg + total.gr + total.gd + total.bd,
            "today_score_rate": f"{total.score_rate * 100:.2f}%",
            "current_score_rate": current_score_rate,
            "today_judge": {
                "pg": total.pg,
                "gr": total.gr,
                "gd": total.gd,
                "bd": total.bd,
                "pr": total.pr,
                "cb": total.cb,
            },
            "judges": [],
        }

        for i, r in enumerate(reversed(target)):
            data["judges"].append(
                {
                    "idx": i + 1,
                    "pg": r.judge.pg,
                    "gr": r.judge.gr,
                    "gd": r.judge.gd,
                    "bd": r.judge.bd,
                    "pr": r.judge.pr,
                    "cb": r.judge.cb,
                }
            )

        return data

    def get_today_updates_data(self, start_time: int, end_time: int | None = None) -> dict:
        """本日のプレー履歴のデータを辞書形式で返す"""
        target: list[tuple[int, OneResult]] = []
        for result_index, r in reversed(list(enumerate(self.results))):
            if r.detect_mode == detect_mode.result:
                if self._timestamp_in_range(r.timestamp, start_time, end_time):
                    target.append((result_index, r))

        items = []
        for result_index, r in target:
            songinfo = self.song_database.search(
                title=r.title, play_style=r.play_style, difficulty=r.difficulty
            )
            detailed_result = DetailedResult(
                songinfo,
                r,
                None,
                songinfo.level if hasattr(songinfo, "level") else None,
            )
            lamp = r.lamp or clear_lamp.noplay

            item = {
                "chart_id": _mobile_chart_id(
                    r.title,
                    r.play_style,
                    r.difficulty,
                    battle=r.option.battle if r.option else False,
                ),
                "lv": str(songinfo.level) if hasattr(songinfo, "level") else "",
                "enable_katate_difficulty_display": bool(
                    self.config and getattr(self.config, "enable_katate_difficulty_display", False)
                ),
                "title": r.title,
                "difficulty": get_chart_name(r.play_style, r.difficulty),
                "notes": r.notes,
                "score": r.score,
                "bp": r.judge.pr + r.judge.bd if r.judge else r.bp,
                "dead": bool(r.dead),
                "lamp": lamp.value,
                "lamp_text": self._lamp_text(lamp),
                "pre_score": r.pre_score if r.pre_score is not None else 0,
                "pre_bp": r.pre_bp if r.pre_bp is not None else 0,
                "pre_lamp": r.pre_lamp.value if r.pre_lamp is not None else 0,
                "pre_lamp_text": self._lamp_text(r.pre_lamp),
                "opt": r.option.__str__() if r.option else "",
                "battle": r.option.battle if r.option else 0,
                "playspeed": r.playspeed if r.playspeed else 1.0,
                "score_rate": r.score / r.notes / 2 if r.notes else 0,
                "timestamp": int(r.timestamp),
            }
            image_url = self._mobile_result_image_url(r)
            if image_url:
                item["image_url"] = image_url
                item["image_id"] = _mobile_result_image_id(result_index, r)

            item.update(_extract_songinfo_fields(songinfo))

            bpim2 = getattr(r, "bpim2", None)
            if bpim2 is not None:
                item["bpi"] = f"{bpim2:.2f}"
                item["bpi_label"] = "BPIM2"
            else:
                bpi = detailed_result.get_local_bpi()
                if bpi is not None:
                    item["bpi"] = f"{bpi:.2f}"
                    item["bpi_label"] = "BPI"

            if detailed_result.score_rate_with_rankdiff:
                item["rankdiff"] = "".join(detailed_result.score_rate_with_rankdiff)
                item["rankdiff0"] = detailed_result.score_rate_with_rankdiff[0]
                item["rankdiff1"] = detailed_result.score_rate_with_rankdiff[1]

            items.append(item)

        return {
            "start_time": start_time,
            "enable_katate_difficulty_display": bool(
                self.config and getattr(self.config, "enable_katate_difficulty_display", False)
            ),
            "items": items,
        }

    def get_today_stats_data(self, start_time: int, end_time: int | None = None) -> dict:
        """today_stats.html用の統計データを生成"""
        now = datetime.datetime.fromtimestamp(end_time) if end_time else datetime.datetime.now()

        # --- playcount, score_rate (get_graph_dataと同等のロジック) ---
        today_target = []
        total_judge = Judge()
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.play:
                if self._timestamp_in_range(r.timestamp, start_time, end_time):
                    today_target.append(r)
                    if r.judge:
                        total_judge += r.judge

        playcount = len(today_target)
        score_rate_str = f"{total_judge.score_rate * 100:.1f}%"

        # --- daily_notes: 直近14日分の日別ノーツ ---
        daily_judges = defaultdict(Judge)
        for r in reversed(self.results):
            if r.detect_mode != detect_mode.play or not r.judge:
                continue
            r_date = datetime.datetime.fromtimestamp(r.timestamp).date()
            days_ago = (now.date() - r_date).days
            if days_ago > 14:
                break
            daily_judges[r_date] += r.judge

        daily_notes = []
        for i in range(14, -1, -1):
            d = now.date() - datetime.timedelta(days=i)
            j = daily_judges.get(d, Judge())
            daily_notes.append(
                {
                    "date": d.strftime("%m/%d"),
                    "pg": j.pg,
                    "gr": j.gr,
                    "gd": j.gd,
                    "bd": j.bd,
                }
            )

        # --- today_level_distribution: 本日のレベル分布 ---
        level_dist = {}
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.result:
                if self._timestamp_in_range(r.timestamp, start_time, end_time):
                    songinfo = self.song_database.search(
                        title=r.title, play_style=r.play_style, difficulty=r.difficulty
                    )
                    lv = (
                        str(songinfo.level)
                        if songinfo and hasattr(songinfo, "level")
                        else "?"
                    )
                    if lv not in level_dist:
                        level_dist[lv] = {"sp": 0, "dp": 0, "battle": 0}
                    is_battle = r.option and r.option.battle
                    if is_battle:
                        level_dist[lv]["battle"] += 1
                    elif r.play_style == play_style.sp:
                        level_dist[lv]["sp"] += 1
                    else:
                        level_dist[lv]["dp"] += 1

        # --- level_stats: 全レベルのランプ/スコアレート統計 ---
        bests = self.get_all_best_results()
        level_stats = {"sp": {}, "dp": {}}

        for (title, style, diff, battle), best in bests.items():
            if battle:
                continue
            if (
                not best.songinfo
                or not hasattr(best.songinfo, "level")
                or not best.songinfo.level
            ):
                continue

            lv = str(best.songinfo.level)
            style_key = "sp" if style == play_style.sp else "dp"

            if lv not in level_stats[style_key]:
                level_stats[style_key][lv] = {
                    "total": 0,
                    "lamps": {
                        "fc": 0,
                        "exh": 0,
                        "hard": 0,
                        "clear": 0,
                        "easy": 0,
                        "assist": 0,
                        "failed": 0,
                    },
                    "scores": {"AAA": 0, "AA": 0, "A": 0, "B_below": 0},
                }

            entry = level_stats[style_key][lv]
            entry["total"] += 1

            # ランプ分類
            lamp = best.lamp
            lamp_key_map = {
                clear_lamp.fc: "fc",
                clear_lamp.exh: "exh",
                clear_lamp.hard: "hard",
                clear_lamp.clear: "clear",
                clear_lamp.easy: "easy",
                clear_lamp.assist: "assist",
                clear_lamp.failed: "failed",
                clear_lamp.noplay: "failed",
            }
            entry["lamps"][lamp_key_map.get(lamp, "failed")] += 1

            # スコアレート分類（songinfo.notesが無い場合はリザルト側のnotesをフォールバック）
            notes = (
                best.songinfo.notes
                if hasattr(best.songinfo, "notes") and best.songinfo.notes
                else best.notes
            )
            if notes and best.best_score > 0:
                rate = best.best_score / (notes * 2)
                if rate >= 16 / 18:
                    entry["scores"]["AAA"] += 1
                elif rate >= 14 / 18:
                    entry["scores"]["AA"] += 1
                elif rate >= 12 / 18:
                    entry["scores"]["A"] += 1
                else:
                    entry["scores"]["B_below"] += 1

        return {
            "date": now.strftime("%Y. %m. %d"),
            "playcount": playcount,
            "score_rate": score_rate_str,
            "daily_notes": daily_notes,
            "monthly_notes": self.get_recent_monthly_notes(now, 12),
            "yearly_notes": {
                "label": f"{now.year}",
                "notes": self.get_yearly_notes(now),
            },
            "today_level_distribution": level_dist,
            "level_stats": level_stats,
        }

    def get_history_cursong_data(
        self,
        title: str,
        style: play_style,
        difficulty: difficulty,
        battle: bool = None,
        playspeed: float = None,
        allscratch: bool = False,
        regularspeed: bool = False,
    ) -> dict:
        """指定された曲のプレーログを辞書形式で返す。websocketでの送信用。"""
        chart_id = calc_chart_id(title, style, difficulty, battle=battle)
        songinfo = self.song_database.search(
            title=title, play_style=style, difficulty=difficulty
        ) or self.song_database.search(chart_id=chart_id)
        results = self.search(
            title=title, style=style, difficulty=difficulty, battle=battle
        )
        best_score = 0
        best_score_opt = None
        detail = None
        best_bp = 99999999
        best_bp_opt = None
        best_lamp = 0
        best_lamp_opt = None
        notes = None  # バグってノーツ数が入っていない場合があるので別処理にする

        filtered = self._filter_results_for_best(
            results,
            playspeed=playspeed,
            battle=battle,
            allscratch=allscratch,
            regularspeed=regularspeed,
        )
        include_legacy_v2_logs = bool(
            self.config and getattr(self.config, "include_legacy_v2_logs", False)
        )
        target = []
        for r in filtered:
            if r.result.detect_mode == detect_mode.result:
                target.append(r)
            elif (
                include_legacy_v2_logs
                and r.result.detect_mode == detect_mode.select
                and r.result.timestamp != 0
            ):
                target.append(r)
            result_notes = _to_int_or_none(r.result.notes)
            if result_notes and not notes:
                notes = result_notes
            result_score = _to_int_or_none(r.result.score)
            if result_score and result_score > best_score:
                best_score = result_score
                best_score_opt = r.result.option
                detail = r
            elif result_score and result_score == best_score and detail:
                current_has_averages = bool(getattr(detail.result, "bpim2_arena_averages", None))
                candidate_has_averages = bool(getattr(r.result, "bpim2_arena_averages", None))
                if candidate_has_averages and not current_has_averages:
                    detail = r
                elif getattr(r.result, "bpim2", None) is not None and getattr(detail.result, "bpim2", None) is None:
                    detail = r
            if r.result.lamp and r.result.lamp.value > best_lamp:
                best_lamp = r.result.lamp.value
                best_lamp_opt = r.result.option
            if r.result.judge:  # リザルト画面からの取得
                if battle:
                    if (
                        not r.result.dead
                        and r.result.judge.pr + r.result.judge.bd < best_bp
                    ):
                        best_bp = r.result.judge.pr + r.result.judge.bd
                        best_bp_opt = r.result.option
                else:
                    if (
                        not r.result.dead
                        and r.result.judge.pr + r.result.judge.bd < best_bp
                    ):
                        best_bp = r.result.judge.pr + r.result.judge.bd
                        best_bp_opt = r.result.option
            else:  # 選曲画面からの取得
                if r.result.bp is not None and r.result.bp < best_bp:
                    best_bp = r.result.bp
                    best_bp_opt = r.result.option

        if not notes and songinfo and getattr(songinfo, "notes", None):
            notes = _to_int_or_none(songinfo.notes)

        if len(results) == 0:
            return {}

        last_played_time = max(r.result.timestamp for r in results)

        data = {
            "lv": str(songinfo.level) if hasattr(songinfo, "level") else "",
            "enable_katate_difficulty_display": bool(
                self.config and getattr(self.config, "enable_katate_difficulty_display", False)
            ),
            "music": title,
            "difficulty": get_chart_name(style, difficulty, battle=battle),
            "playspeed": playspeed if playspeed else 1.0,
            "last_played": str(
                datetime.datetime.fromtimestamp(last_played_time).strftime("%Y/%m/%d")
            ),
            "best_lamp": best_lamp,
            "best_lamp_text": self._lamp_text(clear_lamp(best_lamp)),
            "best_lamp_opt": best_lamp_opt.__str__() if best_lamp_opt else "",
            "best_bp": best_bp,
            "best_bp_opt": best_bp_opt.__str__() if best_bp_opt else "",
            "best_score": best_score,
            "best_score_opt": best_score_opt.__str__() if best_score_opt else "",
            "battle": bool(battle),
        }

        if songinfo and hasattr(songinfo, "bpi_ave") and songinfo.bpi_ave:
            data["bpi_ave"] = f"{songinfo.bpi_ave}"
        if songinfo and hasattr(songinfo, "bpi_top") and songinfo.bpi_top:
            data["bpi_top"] = f"{songinfo.bpi_top}"
        if songinfo and hasattr(songinfo, "bpi_coef") and songinfo.bpi_coef:
            data["bpi_coef"] = f"{songinfo.bpi_coef}"

        if detail:
            detail.result.notes = notes
            if detail.result.notes:
                data["notes"] = notes
                data["best_score_rate"] = best_score / detail.result.notes / 2
                data["best_bp_rate"] = f"{100 * best_bp / detail.result.notes:.2f}"
                if detail.score_rate_with_rankdiff:
                    data["best_rankdiff0"] = detail.score_rate_with_rankdiff[0]
                    data["best_rankdiff1"] = detail.score_rate_with_rankdiff[1]
            bpim2 = getattr(detail.result, "bpim2", None)
            if bpim2 is not None:
                data["best_bpi"] = f"{bpim2:.2f}"
                data["best_bpi_label"] = "BPIM2"
                arena_averages = getattr(detail.result, "bpim2_arena_averages", None)
                if not arena_averages or len(arena_averages) <= 2:
                    refetched = detail.get_bpim2_bpi_detail(force_fetch=True)
                    if refetched and refetched.arena_averages:
                        arena_averages = refetched.arena_averages
                if arena_averages:
                    data["bpi_near_averages"] = [
                        {"rank": avg.rank, "score": avg.avg_ex_score}
                        for avg in arena_averages
                    ]
            elif detail.bpi is not None:
                data["best_bpi"] = f"{detail.bpi:.2f}"
                data["best_bpi_label"] = "BPI"
            if detail.score_rate_with_rankdiff:
                data["rankdiff"] = "".join(detail.score_rate_with_rankdiff)
                data["rankdiff0"] = detail.score_rate_with_rankdiff[0]
                data["rankdiff1"] = detail.score_rate_with_rankdiff[1]

        data.update(_extract_songinfo_fields(songinfo))

        items = []
        for r in reversed(target):
            item = {
                "date": str(
                    datetime.datetime.fromtimestamp(r.result.timestamp).strftime(
                        "%Y/%m/%d"
                    )
                ),
                "lamp": r.result.lamp.value,
                "lamp_text": self._lamp_text(r.result.lamp),
                "score": r.result.score,
                "score_rate": r.result.score / r.result.notes / 2
                if r.result.notes
                else 0,
                "bp": r.result.bp,
                "bprate": r.result.bp / r.result.notes if r.result.notes else 0,
                "pre_score": r.result.pre_score
                if r.result.pre_score is not None
                else 0,
                "pre_lamp": r.result.pre_lamp.value
                if r.result.pre_lamp is not None
                else 0,
                "pre_bp": r.result.pre_bp if r.result.pre_bp is not None else 0,
                "opt": r.result.option.__str__() if r.result.option else "",
            }
            image_url = self._mobile_result_image_url(r.result)
            if image_url:
                item["image_url"] = image_url

            bpim2 = getattr(r.result, "bpim2", None)
            if bpim2 is not None:
                item["bpi"] = f"{bpim2:.2f}"
                item["bpi_label"] = "BPIM2"
            else:
                if r.bpi is not None:
                    item["bpi"] = f"{r.bpi:.2f}"
                    item["bpi_label"] = "BPI"
            if r.score_rate_with_rankdiff:
                item["rankdiff"] = "".join(r.score_rate_with_rankdiff)
                item["rankdiff0"] = r.score_rate_with_rankdiff[0]
                item["rankdiff1"] = r.score_rate_with_rankdiff[1]

            items.append(item)

        data["items"] = items

        # ライバルランキングデータ
        mode = get_chart_name(style, difficulty)
        rival_items = [
            {
                "player": "(ME)",
                "lamp": best_lamp,
                "lamp_text": self._lamp_text(clear_lamp(best_lamp)),
                "score": best_score,
                "bp": best_bp,
                "option": best_score_opt.__str__() if best_score_opt else "",
                "is_me": True,
            }
        ]
        if self.rival_manager:
            for rival_name, entry in self.rival_manager.get_rival_scores(title, mode):
                rival_items.append(
                    {
                        "player": rival_name,
                        "lamp": entry.lamp.value,
                        "lamp_text": self._lamp_text(entry.lamp),
                        "score": entry.score,
                        "bp": entry.bp,
                        "option": entry.option,  # None → HTML側で"?"を表示
                        "is_me": False,
                    }
                )
        rival_items.sort(key=lambda x: (x["score"], x["is_me"]), reverse=True)
        rank = 1
        for i, item in enumerate(rival_items):
            if i > 0 and item["score"] < rival_items[i - 1]["score"]:
                rank = i + 1
            item["rank"] = rank
        data["rival_items"] = rival_items

        return data

    # ─── スマホ向けHTTP API用データ生成 ─────────────────────────────────────

    @staticmethod
    def _timestamp_text(timestamp: int | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
        if not timestamp:
            return ""
        try:
            return datetime.datetime.fromtimestamp(timestamp).strftime(fmt)
        except Exception:
            return ""

    @staticmethod
    def _lamp_text(lamp: clear_lamp | None) -> str:
        return str(lamp) if lamp else str(clear_lamp.noplay)

    @staticmethod
    def _today_start_timestamp() -> int:
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return int(today.timestamp())

    def _mobile_receipt_start_timestamp(self) -> int:
        """receiptで使う開始時刻。アプリ側のオフセット込みtoday範囲を優先する。"""
        for attr in ("today_updates_data", "graph_data", "today_stats_data"):
            data = getattr(self.ws_server, attr, None) if self.ws_server else None
            start_time = _to_int_or_none(data.get("start_time") if isinstance(data, dict) else None)
            if start_time is not None:
                return start_time
        offset_hours = _to_int_or_none(getattr(self.config, "autoload_offset", 0) if self.config else 0) or 0
        return self._today_start_timestamp() - offset_hours * 3600

    def _mobile_app_start_timestamp_with_offset(self) -> int | None:
        start = _to_int_or_none(getattr(self, "app_start_time", None))
        if start is None:
            return None
        offset_hours = _to_int_or_none(getattr(self.config, "autoload_offset", 0) if self.config else 0) or 0
        return start - offset_hours * 3600

    @staticmethod
    def _date_range_timestamps(start_date: str | None, end_date: str | None) -> tuple[int, int] | None:
        try:
            start_dt = datetime.datetime.strptime(str(start_date), "%Y-%m-%d")
            end_dt = datetime.datetime.strptime(str(end_date), "%Y-%m-%d") + datetime.timedelta(days=1)
        except (TypeError, ValueError):
            return None
        if end_dt <= start_dt:
            end_dt = start_dt + datetime.timedelta(days=1)
        return int(start_dt.timestamp()), int(end_dt.timestamp())

    def _mobile_last_play_day_range(self) -> tuple[int, int]:
        latest = None
        for result in reversed(self.results):
            if result.detect_mode in (detect_mode.play, detect_mode.result):
                latest = result.timestamp
                break
        if latest is None:
            latest = int(datetime.datetime.now().timestamp())
        day = datetime.datetime.fromtimestamp(latest).replace(hour=0, minute=0, second=0, microsecond=0)
        return int(day.timestamp()), int((day + datetime.timedelta(days=1)).timestamp())

    def _mobile_receipt_range(
        self,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[int, int | None, str]:
        period = (period or "").lower()
        now = datetime.datetime.now()
        if period == "app_start":
            start = self._mobile_app_start_timestamp_with_offset()
            return start or self._mobile_receipt_start_timestamp(), None, "app_start"
        if period == "last_play":
            start, end = self._mobile_last_play_day_range()
            return start, end, "last_play"
        if period == "week":
            return int((now - datetime.timedelta(days=7)).timestamp()), int(now.timestamp()), "week"
        if period == "month":
            return int((now - datetime.timedelta(days=30)).timestamp()), int(now.timestamp()), "month"
        if period == "year":
            return int((now - datetime.timedelta(days=365)).timestamp()), int(now.timestamp()), "year"
        if period == "custom":
            parsed = self._date_range_timestamps(start_date, end_date)
            if parsed:
                return parsed[0], parsed[1], "custom"
        return self._mobile_receipt_start_timestamp(), None, "default"

    def _mobile_receipt_range_text(self, start_time: int, end_time: int | None, period: str) -> str:
        labels = {
            "app_start": "After app start",
            "last_play": "Last play day",
            "week": "Last 1 week",
            "month": "Last 1 month",
            "year": "Last 1 year",
            "custom": "Custom range",
            "default": "Receipt range",
        }
        start_text = self._timestamp_text(start_time, "%Y-%m-%d %H:%M" if period == "app_start" else "%Y-%m-%d")
        if end_time is None:
            return f"{labels.get(period, period)}: {start_text}-"
        end_date = datetime.datetime.fromtimestamp(end_time) - datetime.timedelta(seconds=1)
        end_text = end_date.strftime("%Y-%m-%d")
        if start_text == end_text:
            return f"{labels.get(period, period)}: {start_text}"
        return f"{labels.get(period, period)}: {start_text} - {end_text}"

    @staticmethod
    def _timestamp_in_range(timestamp: int | float | None, start_time: int, end_time: int | None = None) -> bool:
        value = _to_int_or_none(timestamp)
        if value is None or value < start_time:
            return False
        if end_time is not None and value >= end_time:
            return False
        return True

    def _songinfo_for_result(self, result: OneResult):
        return self.song_database.search(
            title=result.title,
            play_style=result.play_style,
            difficulty=result.difficulty,
        ) or self.song_database.search(chart_id=result.chart_id)

    def _result_level(self, result: OneResult) -> str:
        songinfo = self._songinfo_for_result(result)
        if songinfo and getattr(songinfo, "level", None):
            return str(songinfo.level)
        return str(result.notes or "")

    def _serialize_mobile_best(self, best: OneBestData) -> dict:
        lamp = best.lamp
        best_bp = best.min_bp
        if best_bp >= 99999:
            best_bp = None
        best_score = _to_int_or_none(best.best_score) or 0
        notes = _to_int_or_none(best.notes) or _to_int_or_none(getattr(best.songinfo, "notes", None)) or 0
        score_rate = best_score / (notes * 2) if notes else 0
        bpi = None
        bpi_label = ""
        if best.best_score_result:
            bpim2 = getattr(best.best_score_result, "bpim2", None)
            if notes and not best.best_score_result.notes:
                best.best_score_result.notes = notes
            detail = DetailedResult(best.songinfo, best.best_score_result)
            if bpim2 is not None:
                bpi = f"{bpim2:.2f}"
                bpi_label = "BPIM2"
            else:
                if detail.bpi is not None:
                    bpi = f"{detail.bpi:.2f}"
                    bpi_label = "BPI"
            rankdiff = "".join(detail.score_rate_with_rankdiff) if detail.score_rate_with_rankdiff else ""
        else:
            rankdiff = ""
        data = {
            "chart_id": _mobile_chart_id(best.title, best.style, best.difficulty, battle=best.is_battle),
            "title": best.title,
            "difficulty": best.chart,
            "lv": best.level,
            "score": best_score,
            "bp": best_bp,
            "lamp": lamp.value if lamp else clear_lamp.noplay.value,
            "lamp_text": self._lamp_text(lamp),
            "score_rate": score_rate,
            "rankdiff": rankdiff,
            "bpi": bpi,
            "bpi_label": bpi_label,
            "notes": notes,
            "last_played": best.last_play_date,
            "opt": best.best_score_option,
            "enable_katate_difficulty_display": self._mobile_katate_enabled(),
            "battle": bool(best.is_battle),
        }
        data.update(_extract_songinfo_fields(best.songinfo))
        return data

    def _serialize_mobile_best_safe(self, best: OneBestData) -> dict | None:
        try:
            return self._serialize_mobile_best(best)
        except Exception:
            logger.error(
                "スマホ向け自己ベスト整形エラー: "
                f"{getattr(best, 'title', '')} {getattr(best, 'chart', '')}\n"
                f"{traceback.format_exc()}"
            )
            return None

    def _serialize_mobile_result(self, result: OneResult) -> dict:
        songinfo = self._songinfo_for_result(result)
        detail = DetailedResult(songinfo, result)
        lamp = result.lamp or clear_lamp.noplay
        bpi = None
        bpi_label = ""
        bpim2 = getattr(result, "bpim2", None)
        if bpim2 is not None:
            bpi = f"{bpim2:.2f}"
            bpi_label = "BPIM2"
        elif detail.bpi is not None:
            bpi = f"{detail.bpi:.2f}"
            bpi_label = "BPI"
        bp = result.bp
        if bp is None and result.judge:
            bp = result.judge.bp
        notes = _to_int_or_none(result.notes)
        if not notes and songinfo and getattr(songinfo, "notes", None):
            notes = _to_int_or_none(songinfo.notes)
        score = _to_int_or_none(result.score)
        score_rate = score / (notes * 2) if score is not None and notes else detail.score_rate
        if notes and not result.notes:
            result.notes = notes
            detail.update_details()
        rankdiff = "".join(detail.score_rate_with_rankdiff) if detail.score_rate_with_rankdiff else ""
        data = {
            "chart_id": _mobile_chart_id(
                result.title,
                result.play_style,
                result.difficulty,
                battle=result.option.battle if result.option else False,
            ),
            "title": result.title,
            "difficulty": get_chart_name(result.play_style, result.difficulty, battle=result.option.battle if result.option else False),
            "lv": str(songinfo.level) if songinfo and getattr(songinfo, "level", None) else "",
            "score": score,
            "bp": _to_int_or_none(bp),
            "lamp": lamp.value,
            "lamp_text": self._lamp_text(lamp),
            "score_rate": score_rate,
            "rankdiff": rankdiff,
            "bpi": bpi,
            "bpi_label": bpi_label,
            "notes": notes,
            "date": self._timestamp_text(result.timestamp),
            "opt": str(result.option) if result.option else "",
            "dead": bool(result.dead),
            "enable_katate_difficulty_display": self._mobile_katate_enabled(),
        }
        image_url = self._mobile_result_image_url(result)
        if image_url:
            data["image_url"] = image_url
        data.update(_extract_songinfo_fields(songinfo))
        return data

    def _mobile_result_items(self, results: list[OneResult]) -> list[dict]:
        return [self._serialize_mobile_result(r) for r in results if r.detect_mode == detect_mode.result]

    def _mobile_rank_update_enabled_ranks(self) -> set[str]:
        return {"MAX-", "AAA", "AA"}

    @staticmethod
    def _mobile_reached_rank_name(rate: float, pre_rate: float) -> str | None:
        if rate > 17 / 18 and pre_rate <= 17 / 18:
            return "MAX-"
        if rate > 16 / 18 and pre_rate <= 16 / 18:
            return "AAA"
        if rate > 14 / 18 and pre_rate <= 14 / 18:
            return "AA"
        return None

    def _mobile_rank_achievement_updates(self, items: list[dict]) -> list[dict]:
        enabled = self._mobile_rank_update_enabled_ranks()
        if not enabled:
            return []
        best_by_chart = {}
        for item in items:
            notes = _to_int_or_none(item.get("notes"))
            score = _to_int_or_none(item.get("score"))
            if not notes or score is None:
                continue
            rate = score / (notes * 2)
            pre_score = _to_int_or_none(item.get("pre_score")) or 0
            pre_rate = pre_score / (notes * 2)
            rank_name = self._mobile_reached_rank_name(rate, pre_rate)
            if rank_name not in enabled:
                continue
            row = dict(item)
            row["rank_achievement"] = rank_name
            row["_rank_order"] = {"MAX-": 0, "AAA": 1, "AA": 2}.get(rank_name, 99)
            key = row.get("chart_id") or f"{row.get('title', '')}\0{row.get('difficulty', '')}"
            current = best_by_chart.get(key)
            if (
                current is None
                or row["_rank_order"] < current["_rank_order"]
                or (
                    row["_rank_order"] == current["_rank_order"]
                    and (_to_int_or_none(row.get("timestamp")) or 0) > (_to_int_or_none(current.get("timestamp")) or 0)
                )
            ):
                best_by_chart[key] = row
        rows = list(best_by_chart.values())
        rows.sort(key=lambda item: (item.get("_rank_order", 99), -(_to_int_or_none(item.get("lv")) or 0), item.get("title", "")))
        for row in rows:
            row.pop("_rank_order", None)
        return rows

    def _mobile_play_log_items(self, results: list[OneResult], include_select: bool = False) -> list[dict]:
        allowed_modes = {detect_mode.result}
        if include_select:
            allowed_modes.add(detect_mode.select)
        return [self._serialize_mobile_result(r) for r in results if r.detect_mode in allowed_modes]

    def _mobile_katate_enabled(self) -> bool:
        return bool(self.config and getattr(self.config, "enable_katate_difficulty_display", False))

    @staticmethod
    def _mobile_katate_band_for_best(best: OneBestData):
        return _get_katate_band(getattr(best, "songinfo", None))

    def _mobile_result_image_url(self, result: OneResult) -> str:
        image_path = getattr(result, "image_path", None)
        if not image_path:
            return ""
        try:
            path = Path(image_path)
            if not path.exists() or not path.is_file():
                return ""
        except Exception:
            return ""
        return f"/api/result-images/{int(result.timestamp)}"

    def get_mobile_result_image_path(self, timestamp: int) -> Path | None:
        timestamp = _to_int_or_none(timestamp)
        if timestamp is None:
            return None
        for result in self.results:
            if result.timestamp != timestamp:
                continue
            image_path = getattr(result, "image_path", None)
            if not image_path:
                continue
            try:
                path = Path(image_path).resolve()
                if path.exists() and path.is_file():
                    return path
            except Exception:
                continue
        return None

    def _mobile_bpi_near_averages_for_chart(self, chart_id: str) -> list[dict]:
        if not chart_id:
            return []
        base_chart_id, forced_battle = _split_mobile_chart_id(chart_id)
        if forced_battle:
            return []
        data = self.get_mobile_chart_detail_data(chart_id)
        if not data:
            return []
        return data.get("bpi_near_averages", []) or []

    def _notes_by_date(self) -> dict[str, int]:
        totals = defaultdict(int)
        for result in self.results:
            if result.detect_mode != detect_mode.play or not result.judge:
                continue
            date_key = self._timestamp_text(result.timestamp, "%Y-%m-%d")
            totals[date_key] += result.judge.notes
        return totals

    def _notes_since(self, start_timestamp: int) -> int:
        total = 0
        for result in reversed(self.results):
            if result.timestamp < start_timestamp:
                break
            if result.detect_mode == detect_mode.play and result.judge:
                total += result.judge.notes
        return total

    def get_mobile_folders_data(self) -> dict:
        """スマホビューのトップ階層を返す。"""
        bests = self.get_all_best_results()
        style_defs = [
            ("SP", play_style.sp),
            ("DP", play_style.dp),
        ]
        level_folders = []
        for style_label, style_value in style_defs:
            levels = sorted(
                {
                    _to_int_or_none(best.level)
                    for best in bests.values()
                    if not best.is_battle
                    and best.style == style_value
                    and _to_int_or_none(best.level)
                },
                reverse=True,
            )
            level_folders.extend(
                {
                    "id": f"style/{style_label}/level/{level}",
                    "label": f"{style_label} LEVEL {level}",
                    "count": sum(
                        1
                        for b in bests.values()
                        if not b.is_battle
                        and b.style == style_value
                        and _to_int_or_none(b.level) == level
                    ),
                }
                for level in levels
            )
        dbx_folders = []
        dbx_levels = sorted(
            {
                _to_int_or_none(best.level)
                for best in bests.values()
                if best.is_battle and _to_int_or_none(best.level)
            },
            reverse=True,
        )
        dbx_folders.extend(
            {
                "id": f"dbx/level/{level}",
                "label": f"DBx LEVEL {level}",
                "count": sum(
                    1
                    for b in bests.values()
                    if b.is_battle and _to_int_or_none(b.level) == level
                ),
            }
            for level in dbx_levels
        )
        katate_folders = []
        if self._mobile_katate_enabled():
            for level in (12, 11):
                count = sum(
                    1
                    for best in bests.values()
                    if best.style == play_style.sp
                    and _to_int_or_none(best.level) == level
                    and self._mobile_katate_band_for_best(best)
                )
                if count:
                    katate_folders.append(
                        {
                            "id": f"katate/{level}",
                            "label": f"KATATE LEVEL {level}",
                            "count": count,
                        }
                    )
        result_count = sum(1 for r in self.results if r.detect_mode == detect_mode.result)
        saved_image_count = len(self._mobile_saved_image_results())
        bpi_best_count = len(self._mobile_bpi_best_items())
        receipt_start = self._mobile_receipt_start_timestamp()
        today_notes = _to_int_or_none(self.get_graph_data(receipt_start).get("today_notes")) or 0
        current = self.get_mobile_current_folder_data()
        daily_count = len(self._notes_by_date())
        return {
            "total_best_charts": len(bests),
            "total_results": result_count,
            "today_notes": today_notes,
            "levels": level_folders,
            "dbx": dbx_folders,
            "katate": katate_folders,
            "special": [
                {"id": "history", "label": "PLAY HISTORY", "count": result_count, "count_label": f"{result_count} plays"},
                {"id": "saved-images", "label": "SAVED IMAGES", "count": saved_image_count, "count_label": f"{saved_image_count} images"},
                {"id": "receipt", "label": "RECEIPT", "count": today_notes, "count_label": f"{today_notes:,} notes"},
                {"id": "daily", "label": "DAILY LOG", "count": daily_count, "count_label": f"{daily_count} days"},
                {"id": "current", "label": "CURRENT SONG", "count": len(current.get("items", [])), "count_label": "live"},
                {"id": "bpi-best", "label": "BPI BEST", "count": bpi_best_count, "count_label": f"{bpi_best_count} charts"},
            ],
        }

    def _mobile_bpi_best_items(self) -> list[dict]:
        items = []
        for best in self.get_all_best_results().values():
            if best.style != play_style.sp or best.is_battle:
                continue
            item = self._serialize_mobile_best_safe(best)
            if item is None:
                continue
            bpi = _to_float_or_none(item.get("bpi"))
            if bpi is None:
                continue
            item["_bpi_sort"] = bpi
            items.append(item)
        items.sort(key=lambda item: (-item["_bpi_sort"], item.get("title", ""), item.get("difficulty", "")))
        for item in items:
            item.pop("_bpi_sort", None)
        return items

    def get_mobile_bpi_best_data(self) -> dict:
        items = self._mobile_bpi_best_items()
        return {
            "folder": {"id": "bpi-best", "label": "BPI BEST"},
            "items": items,
            "notes": sum(_to_int_or_none(item.get("notes")) or 0 for item in items),
        }

    def _mobile_saved_image_results(self) -> list[tuple[int, OneResult]]:
        items = []
        for index, result in enumerate(self.results):
            if result.detect_mode != detect_mode.result:
                continue
            image_path = getattr(result, "image_path", None)
            if not image_path:
                continue
            try:
                path = Path(image_path)
                if path.exists() and path.is_file():
                    items.append((index, result))
            except Exception:
                continue
        return items

    def _mobile_result_by_image_id(self, image_id: str) -> OneResult | None:
        try:
            index_text, timestamp_text = str(image_id).split("-", 1)
            index = int(index_text)
            timestamp = int(timestamp_text)
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= len(self.results):
            return None
        result = self.results[index]
        if result.timestamp != timestamp or result.detect_mode != detect_mode.result:
            return None
        image_path = getattr(result, "image_path", None)
        if not image_path:
            return None
        try:
            path = Path(image_path)
            if path.exists() and path.is_file():
                return result
        except Exception:
            return None
        return None

    def get_mobile_saved_images_data(self) -> dict:
        items = []
        for index, result in reversed(self._mobile_saved_image_results()):
            item = self._serialize_mobile_result(result)
            item["image_id"] = _mobile_result_image_id(index, result)
            items.append(item)
        return {
            "folder": {"id": "saved-images", "label": "SAVED IMAGES"},
            "items": items,
            "notes": sum(_to_int_or_none(item.get("notes")) or 0 for item in items),
        }

    def generate_mobile_combined_result_image(self, image_ids: list[str]) -> bytes | None:
        logger.info(f"投稿用画像生成リクエスト: requested={len(image_ids)}, ids={','.join(map(str, image_ids))}")
        results = []
        seen = set()
        for image_id in image_ids:
            if image_id in seen:
                logger.debug(f"投稿用画像生成: 重複IDをスキップ id={image_id}")
                continue
            seen.add(image_id)
            result = self._mobile_result_by_image_id(image_id)
            if result is not None:
                results.append(result)
            else:
                logger.warning(f"投稿用画像生成: リザルト画像IDが見つかりません id={image_id}")
        if not results:
            logger.warning("投稿用画像生成: 有効な画像がありません")
            return None

        results.sort(key=lambda result: (int(getattr(result, "timestamp", 0) or 0), getattr(result, "title", "")))
        logger.info(f"投稿用画像生成開始: {len(results)}枚")
        images = []
        for i, result in enumerate(results):
            try:
                with Image.open(getattr(result, "image_path")) as image:
                    logger.info(
                        f"投稿用画像読み込み: index={i}, path={getattr(result, 'image_path', '')}, "
                        f"size={image.width}x{image.height}, mode={image.mode}"
                    )
                    images.append(image.convert("RGB"))
            except Exception as e:
                logger.error(f"投稿用画像の読み込み失敗: {getattr(result, 'image_path', '')} {e}\n{traceback.format_exc()}")
        if not images:
            logger.warning("投稿用画像生成: 読み込めた画像がありません")
            return None

        count = len(images)
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        if count == 2:
            cols, rows = 2, 1

        cell_width = max(image.width for image in images)
        cell_height = max(image.height for image in images)
        canvas_width = cell_width * cols
        canvas_height = cell_height * rows
        max_side = 4096
        scale = min(1.0, max_side / max(canvas_width, canvas_height))
        if scale < 1.0:
            cell_width = max(1, int(cell_width * scale))
            cell_height = max(1, int(cell_height * scale))
            canvas_width = cell_width * cols
            canvas_height = cell_height * rows
        logger.info(
            f"投稿用画像キャンバス: count={count}, cols={cols}, rows={rows}, "
            f"cell={cell_width}x{cell_height}, canvas={canvas_width}x{canvas_height}, scale={scale:.4f}"
        )

        canvas = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
        if hasattr(Image, "Resampling"):
            resampling_filter = Image.Resampling.LANCZOS
        else:
            resampling_filter = Image.LANCZOS
        for i, image in enumerate(images):
            ratio = min(cell_width / image.width, cell_height / image.height)
            resized = image.resize(
                (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                resampling_filter,
            )
            x = (i % cols) * cell_width + (cell_width - resized.width) // 2
            y = (i // cols) * cell_height + (cell_height - resized.height) // 2
            canvas.paste(resized, (x, y))
            logger.debug(
                f"投稿用画像貼り付け: index={i}, source={image.width}x{image.height}, "
                f"resized={resized.width}x{resized.height}, pos={x},{y}"
            )

        target_size = 4_800_000
        for quality in (90, 86, 82, 78, 74, 70):
            output = BytesIO()
            canvas.save(output, format="JPEG", quality=quality, optimize=True)
            body = output.getvalue()
            output.close()
            if len(body) <= target_size or quality == 70:
                logger.info(f"投稿用画像生成完了: {canvas_width}x{canvas_height}, {len(body)} bytes, quality={quality}")
                return body
        return None

    def get_mobile_level_folder_data(self, level: int, style_text: str | None = None, battle_only: bool = False) -> dict:
        style_value = None
        style_label = ""
        if style_text:
            style_label = style_text.upper()
            style_value = play_style.sp if style_label == "SP" else play_style.dp if style_label == "DP" else None
        bests = [
            best
            for best in self.get_all_best_results().values()
            if _to_int_or_none(best.level) == level
            and (best.is_battle if battle_only else not best.is_battle)
            and (style_value is None or best.style == style_value)
        ]
        bests.sort(key=lambda b: (-( _to_int_or_none(b.best_score) or 0), b.title, b.chart))
        items = [
            item
            for item in (self._serialize_mobile_best_safe(best) for best in bests)
            if item is not None
        ]
        folder_id = f"dbx/level/{level}" if battle_only else f"style/{style_label}/level/{level}" if style_label else f"level/{level}"
        label = f"DBx LEVEL {level}" if battle_only else f"{style_label} LEVEL {level}" if style_label else f"LEVEL {level}"
        return {
            "folder": {"id": folder_id, "label": label},
            "items": items,
            "notes": sum(_to_int_or_none(item.get("notes")) or 0 for item in items),
        }

    def get_mobile_katate_level_folder_data(self, level: int) -> dict:
        if not self._mobile_katate_enabled():
            return {
                "folder": {"id": f"katate/{level}", "label": f"KATATE LEVEL {level}"},
                "items": [],
                "notes": 0,
            }
        bests = [
            best
            for best in self.get_all_best_results().values()
            if best.style == play_style.sp
            and _to_int_or_none(best.level) == level
            and self._mobile_katate_band_for_best(best)
        ]
        by_band: dict[int, list[OneBestData]] = defaultdict(list)
        for best in bests:
            band = _to_int_or_none(self._mobile_katate_band_for_best(best))
            if band is not None:
                by_band[band].append(best)
        items = [
            {
                "id": f"katate/{level}/band/{band}",
                "label": f"{level}-{band}",
                "count": len(by_band[band]),
                "notes": sum(_to_int_or_none(best.notes) or 0 for best in by_band[band]),
            }
            for band in sorted(by_band.keys(), reverse=True)
        ]
        return {
            "folder": {"id": f"katate/{level}", "label": f"KATATE LEVEL {level}"},
            "items": items,
            "notes": sum(item["notes"] for item in items),
            "type": "folder-list",
        }

    def get_mobile_katate_band_folder_data(self, level: int, band: int) -> dict:
        if not self._mobile_katate_enabled():
            items = []
        else:
            bests = [
                best
                for best in self.get_all_best_results().values()
                if best.style == play_style.sp
                and _to_int_or_none(best.level) == level
                and _to_int_or_none(self._mobile_katate_band_for_best(best)) == band
            ]
            bests.sort(key=lambda b: (b.title, b.chart))
            items = [
                item
                for item in (self._serialize_mobile_best_safe(best) for best in bests)
                if item is not None
            ]
        return {
            "folder": {"id": f"katate/{level}/band/{band}", "label": f"KATATE {level}-{band}"},
            "items": items,
            "notes": sum(_to_int_or_none(item.get("notes")) or 0 for item in items),
        }

    def get_mobile_history_data(self, limit: int = 200, offset: int = 0) -> dict:
        limit = max(1, min(1000, int(limit or 200)))
        offset = max(0, int(offset or 0))
        all_results = [r for r in reversed(self.results) if r.detect_mode == detect_mode.result]
        page = all_results[offset : offset + limit]
        return {
            "folder": {"id": "history", "label": "PLAY HISTORY"},
            "total": len(all_results),
            "limit": limit,
            "offset": offset,
            "items": self._mobile_result_items(page),
        }

    def get_mobile_receipt_data(
        self,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        start, end, period_key = self._mobile_receipt_range(period, start_date, end_date)
        range_text = self._mobile_receipt_range_text(start, end, period_key)
        graph_data = self.get_graph_data(start, end)
        updates_data = self.get_today_updates_data(start, end)
        items = updates_data.get("items", [])

        def bpi_value(item):
            difficulty_text = str(item.get("difficulty") or "").upper()
            if difficulty_text.startswith("DP") or difficulty_text.startswith("DB"):
                return None
            return _to_float_or_none(item.get("bpi"))

        def valid_previous_bp(item):
            pre_bp = _to_int_or_none(item.get("pre_bp"))
            return pre_bp is not None and 0 < pre_bp < 99999

        level_distribution = {}
        for item in items:
            lv = str(item.get("lv") or "?")
            if lv not in level_distribution:
                level_distribution[lv] = {"sp": 0, "dp": 0, "battle": 0}
            difficulty_text = str(item.get("difficulty") or "").upper()
            if item.get("battle") or difficulty_text.startswith("DB"):
                level_distribution[lv]["battle"] += 1
            elif difficulty_text.startswith("DP"):
                level_distribution[lv]["dp"] += 1
            else:
                level_distribution[lv]["sp"] += 1

        top_bpi_by_chart = {}
        for item in items:
            value = bpi_value(item)
            if value is None:
                continue
            key = item.get("chart_id") or f"{item.get('title', '')}\0{item.get('difficulty', '')}"
            current = top_bpi_by_chart.get(key)
            if current is None or value > current[0]:
                top_bpi_by_chart[key] = (value, item)

        top_bpi_items = sorted(
            [entry[1] for entry in top_bpi_by_chart.values()],
            key=lambda item: bpi_value(item),
            reverse=True,
        )
        rank_achievement_updates = self._mobile_rank_achievement_updates(items)
        score_updates = [
            item for item in items
            if (_to_int_or_none(item.get("score")) or 0) > (_to_int_or_none(item.get("pre_score")) or 0)
        ]
        lamp_updates_by_chart = {}
        for item in items:
            lamp = _to_int_or_none(item.get("lamp")) or 0
            pre_lamp = _to_int_or_none(item.get("pre_lamp")) or 0
            if lamp <= pre_lamp:
                continue
            key = item.get("chart_id") or f"{item.get('title', '')}\0{item.get('difficulty', '')}"
            current = lamp_updates_by_chart.get(key)
            current_lamp = _to_int_or_none(current.get("lamp")) if current else None
            current_timestamp = _to_int_or_none(current.get("timestamp")) if current else None
            item_timestamp = _to_int_or_none(item.get("timestamp")) or 0
            if (
                current is None
                or lamp > (current_lamp or 0)
                or (lamp == (current_lamp or 0) and item_timestamp > (current_timestamp or 0))
            ):
                lamp_updates_by_chart[key] = item
        lamp_updates = list(lamp_updates_by_chart.values())
        bp_updates = [
            item for item in items
            if not item.get("dead")
            and valid_previous_bp(item)
            and (_to_int_or_none(item.get("bp")) or 99999) < (_to_int_or_none(item.get("pre_bp")) or 99999)
        ]
        current = self.get_mobile_current_folder_data()
        current_detail = current.get("detail")
        top_bpi = top_bpi_items[0].get("bpi") if top_bpi_items else ""
        return {
            "folder": {"id": "receipt", "label": "RECEIPT"},
            "start_time": start,
            "end_time": end,
            "period": period_key,
            "range_text": range_text,
            "start_time_text": self._timestamp_text(start),
            "play_count": graph_data.get("playcount", len(items)),
            "song_count": len(items),
            "today_notes": graph_data.get("today_notes", 0),
            "score_rate": graph_data.get("today_score_rate", "0.00%"),
            "top_bpi": top_bpi,
            "items": items,
            "level_distribution": level_distribution,
            "top_bpi_items": top_bpi_items,
            "rank_achievement_updates": rank_achievement_updates,
            "score_updates": score_updates,
            "lamp_updates": lamp_updates,
            "bp_updates": bp_updates,
            "current_detail": current_detail,
            "rival_items": current_detail.get("rival_items", []) if current_detail else [],
            "tweet": self.get_mobile_tweet_data(start, graph_data, end, period_key, range_text),
            "summary_stats": {
                **self.get_today_stats_data(start, end),
                "range_text": range_text,
            },
        }

    def get_mobile_tweet_data(
        self,
        start_time: int,
        graph_data: dict | None = None,
        end_time: int | None = None,
        period: str | None = None,
        range_text: str | None = None,
    ) -> dict:
        graph_data = graph_data or self.get_graph_data(start_time, end_time)
        judge = graph_data.get("today_judge", {}) if graph_data else {}
        msg = ""
        if period != "app_start" and range_text:
            msg += f"{range_text}\n"
        msg += (
            f"plays:{graph_data.get('playcount', 0)}, "
            f"notes:{_to_int_or_none(graph_data.get('today_notes')) or 0:,}, "
            f"{graph_data.get('today_score_rate', '0.00%')}\n"
        )
        if self.config and getattr(self.config, "enable_judge", False):
            msg += (
                f"(PG:{_to_int_or_none(judge.get('pg')) or 0:,}, "
                f"GR:{_to_int_or_none(judge.get('gr')) or 0:,}, "
                f"GD:{_to_int_or_none(judge.get('gd')) or 0:,}, "
                f"BD:{_to_int_or_none(judge.get('bd')) or 0:,}, "
                f"PR:{_to_int_or_none(judge.get('pr')) or 0:,}, "
                f"CB:{_to_int_or_none(judge.get('cb')) or 0:,})\n"
            )
        app_start_time = _to_int_or_none(getattr(self, "app_start_time", None)) or start_time
        if period == "app_start":
            uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(app_start_time)
            msg += f"uptime: {str(uptime).split('.')[0]}\n"
        if self.config and getattr(self.config, "enable_folder_updates", False):
            msg += self._collect_mobile_tweet_updates(start_time, end_time)
        start_date = datetime.datetime.fromtimestamp(app_start_time)
        msg += f"({start_date.year}/{start_date.month:02d}: {self.get_monthly_notes():,})\n"
        msg += "#INFINITAS_daken_counter\n"
        return {
            "text": msg,
            "url": f"https://twitter.com/intent/tweet?text={urllib.parse.quote(msg)}",
        }

    def _collect_mobile_tweet_updates(self, start_time: int, end_time: int | None = None) -> str:
        today_results = []
        for result in reversed(self.results):
            if result.detect_mode == detect_mode.result:
                if self._timestamp_in_range(result.timestamp, start_time, end_time):
                    today_results.append(result)
        if not today_results:
            return ""

        sp_results = [r for r in today_results if r.play_style == play_style.sp]
        dp_results = [r for r in today_results if r.play_style == play_style.dp]
        has_sp = len(sp_results) > 0
        has_dp = len(dp_results) > 0
        both = has_sp and has_dp

        lines = []
        if has_sp:
            if both:
                lines.append("(SP)")
            lines.extend(self._collect_mobile_tweet_updates_for_style(sp_results))
        if has_dp:
            if both:
                lines.append("(DP)")
            lines.extend(self._collect_mobile_tweet_updates_for_style(dp_results))
        return "\n".join(lines) + "\n" if lines else ""

    def _collect_mobile_tweet_updates_for_style(self, results: list[OneResult]) -> list[str]:
        best_lamp_updates = {}
        for result in results:
            if result.pre_lamp and result.lamp and result.lamp.value > result.pre_lamp.value:
                if (
                    result.chart_id not in best_lamp_updates
                    or result.lamp.value > best_lamp_updates[result.chart_id].lamp.value
                ):
                    best_lamp_updates[result.chart_id] = result

        best_scores = {}
        for result in results:
            notes = _to_int_or_none(result.notes)
            if not notes:
                songinfo = self.song_database.search(chart_id=result.chart_id)
                notes = _to_int_or_none(getattr(songinfo, "notes", None))
            if notes and result.score:
                if result.chart_id not in best_scores or result.score > best_scores[result.chart_id].score:
                    best_scores[result.chart_id] = result

        updates_by_level = {}
        for result in best_lamp_updates.values():
            songinfo = self.song_database.search(chart_id=result.chart_id)
            lv = self._get_mobile_tweet_level_key(songinfo)
            updates_by_level.setdefault(lv, {})
            lamp_name = result.lamp.name.upper()
            updates_by_level[lv][lamp_name] = updates_by_level[lv].get(lamp_name, 0) + 1

        for result in best_scores.values():
            songinfo = self.song_database.search(chart_id=result.chart_id)
            notes = _to_int_or_none(result.notes) or _to_int_or_none(getattr(songinfo, "notes", None))
            if not notes or not result.score:
                continue
            rate = result.score / (notes * 2)
            pre_rate = result.pre_score / (notes * 2) if result.pre_score else 0
            rank_name = None
            if rate > 17 / 18 and pre_rate <= 17 / 18:
                rank_name = "MAX-"
            elif rate > 16 / 18 and pre_rate <= 16 / 18:
                rank_name = "AAA"
            elif rate > 14 / 18 and pre_rate <= 14 / 18:
                rank_name = "AA"
            if rank_name:
                lv = self._get_mobile_tweet_level_key(songinfo)
                updates_by_level.setdefault(lv, {})
                updates_by_level[lv][rank_name] = updates_by_level[lv].get(rank_name, 0) + 1

        display_order = ["EASY", "CLEAR", "HARD", "EXH", "FC", "AA", "AAA", "MAX-"]
        lines = []
        for lv in sorted(updates_by_level.keys()):
            items = updates_by_level[lv]
            parts = [f"{key}+{items[key]}" for key in display_order if key in items]
            parts.extend(f"{key}+{items[key]}" for key in sorted(items.keys()) if key not in display_order)
            if parts:
                lines.append(f"{self._format_mobile_tweet_level_key(lv)} {', '.join(parts)}")
        return lines

    def _get_mobile_tweet_level_key(self, songinfo):
        level = int(songinfo.level) if songinfo and getattr(songinfo, "level", None) else 0
        use_katate = (
            self.config
            and getattr(self.config, "enable_katate_difficulty_display", False)
            and getattr(self.config, "enable_katate_tweet_grouping", False)
            and level in (11, 12)
        )
        if use_katate:
            band = getattr(songinfo, f"katate_{level}", None)
            if band:
                return (level, int(band))
        return (level, 0)

    def _format_mobile_tweet_level_key(self, level_key):
        level, band = level_key
        if not level:
            return "☆?"
        if band:
            return f"☆{level}-{band}"
        return f"☆{level}"

    def _mobile_daily_rows(self) -> list[dict]:
        notes_by_date = self._notes_by_date()
        play_counts = defaultdict(int)
        for result in self.results:
            if result.detect_mode == detect_mode.result:
                play_counts[self._timestamp_text(result.timestamp, "%Y-%m-%d")] += 1
        dates = sorted(set(notes_by_date.keys()) | set(play_counts.keys()), reverse=True)
        return [
            {
                "date": date_key,
                "notes": notes_by_date.get(date_key, 0),
                "play_count": play_counts.get(date_key, 0),
            }
            for date_key in dates
        ]

    def get_mobile_daily_folders_data(self, mode: str = "daily") -> dict:
        mode = (mode or "daily").lower()
        daily_items = self._mobile_daily_rows()
        if mode == "monthly":
            monthly = {}
            for item in daily_items:
                key = item["date"][:7]
                entry = monthly.setdefault(key, {"month": key, "notes": 0, "play_count": 0, "day_count": 0})
                entry["notes"] += item["notes"]
                entry["play_count"] += item["play_count"]
                entry["day_count"] += 1
            items = [monthly[key] for key in sorted(monthly.keys(), reverse=True)]
            return {
                "folder": {"id": "daily", "label": "DAILY LOG"},
                "mode": "monthly",
                "total_notes": sum(item["notes"] for item in daily_items),
                "items": items,
            }
        if mode == "yearly":
            yearly = {}
            for item in daily_items:
                key = item["date"][:4]
                entry = yearly.setdefault(key, {"year": key, "notes": 0, "play_count": 0, "month_count": 0})
                entry["notes"] += item["notes"]
                entry["play_count"] += item["play_count"]
            for entry in yearly.values():
                entry["month_count"] = len(
                    {
                        item["date"][:7]
                        for item in daily_items
                        if item["date"].startswith(entry["year"])
                    }
                )
            items = [yearly[key] for key in sorted(yearly.keys(), reverse=True)]
            return {
                "folder": {"id": "daily", "label": "DAILY LOG"},
                "mode": "yearly",
                "total_notes": sum(item["notes"] for item in daily_items),
                "items": items,
            }
        items = daily_items
        return {
            "folder": {"id": "daily", "label": "DAILY LOG"},
            "mode": "daily",
            "total_notes": sum(item["notes"] for item in daily_items),
            "items": items,
        }

    def get_mobile_monthly_daily_folders_data(self, month_key: str) -> dict:
        items = [
            item
            for item in self._mobile_daily_rows()
            if item["date"].startswith(f"{month_key}-")
        ]
        return {
            "folder": {"id": f"daily/month/{month_key}", "label": month_key},
            "mode": "daily",
            "total_notes": sum(item["notes"] for item in items),
            "items": items,
        }

    def get_mobile_yearly_month_folders_data(self, year_key: str) -> dict:
        daily_items = [
            item
            for item in self._mobile_daily_rows()
            if item["date"].startswith(f"{year_key}-")
        ]
        monthly = {}
        for item in daily_items:
            key = item["date"][:7]
            entry = monthly.setdefault(key, {"month": key, "notes": 0, "play_count": 0, "day_count": 0})
            entry["notes"] += item["notes"]
            entry["play_count"] += item["play_count"]
            entry["day_count"] += 1
        items = [monthly[key] for key in sorted(monthly.keys(), reverse=True)]
        return {
            "folder": {"id": f"daily/year/{year_key}", "label": year_key},
            "mode": "monthly",
            "total_notes": sum(item["notes"] for item in daily_items),
            "items": items,
        }

    def get_mobile_daily_log_data(self, date_key: str) -> dict:
        items = [
            r for r in reversed(self.results)
            if r.detect_mode == detect_mode.result
            and self._timestamp_text(r.timestamp, "%Y-%m-%d") == date_key
        ]
        notes = self._notes_by_date().get(date_key, 0)
        return {
            "folder": {"id": f"daily/{date_key}", "label": date_key},
            "notes": notes,
            "items": self._mobile_result_items(items),
        }

    def get_mobile_current_folder_data(self) -> dict:
        data = self.ws_server.history_cursong_data if self.ws_server else None
        if not data:
            return {"folder": {"id": "current", "label": "CURRENT SONG"}, "items": [], "detail": None}
        title = data.get("music") or data.get("title")
        difficulty_text = data.get("difficulty") or ""
        chart_id = data.get("chart_id")
        if chart_id and (data.get("battle") or str(difficulty_text).upper().startswith("DB")) and not str(chart_id).startswith("dbx:"):
            chart_id = f"dbx:{chart_id}"
        if not chart_id:
            for best in self.get_all_best_results().values():
                if best.title == title and best.chart == difficulty_text:
                    chart_id = _mobile_chart_id(best.title, best.style, best.difficulty, battle=best.is_battle)
                    break
        try:
            lamp_value = int(data.get("best_lamp", 0) or 0)
            lamp_text = self._lamp_text(clear_lamp(lamp_value))
        except Exception:
            lamp_value = 0
            lamp_text = self._lamp_text(clear_lamp.noplay)
        item = {
            "chart_id": chart_id,
            "title": title,
            "difficulty": difficulty_text,
            "lv": data.get("lv", ""),
            "score": data.get("best_score", 0),
            "bp": data.get("best_bp"),
            "lamp": lamp_value,
            "lamp_text": lamp_text,
            "score_rate": data.get("best_score_rate"),
            "notes": data.get("notes"),
            "last_played": data.get("last_played", ""),
            "opt": data.get("best_score_opt", ""),
        }
        detail = dict(data)
        detail["chart_id"] = chart_id
        detail["title"] = title
        if not detail.get("bpi_near_averages") and chart_id:
            detail["bpi_near_averages"] = self._mobile_bpi_near_averages_for_chart(chart_id)
        for rival in detail.get("rival_items", []):
            try:
                rival["lamp_text"] = self._lamp_text(clear_lamp(rival.get("lamp", 0)))
            except Exception:
                rival["lamp_text"] = ""
        for log_item in detail.get("items", []):
            try:
                log_item["lamp_text"] = self._lamp_text(clear_lamp(log_item.get("lamp", 0)))
            except Exception:
                log_item["lamp_text"] = ""
        return {
            "folder": {"id": "current", "label": "CURRENT SONG"},
            "items": [item],
            "detail": detail,
        }

    def get_mobile_chart_detail_data(self, chart_id: str) -> dict | None:
        base_chart_id, forced_battle = _split_mobile_chart_id(chart_id)
        best = None
        candidates = []
        for candidate in self.get_all_best_results().values():
            if forced_battle is not None and bool(candidate.is_battle) != bool(forced_battle):
                continue
            candidate_id = calc_chart_id(candidate.title, candidate.style, candidate.difficulty, battle=candidate.is_battle)
            if candidate_id == base_chart_id:
                candidates.append(candidate)
        if candidates:
            candidates.sort(key=lambda candidate: bool(candidate.is_battle), reverse=bool(forced_battle))
            best = candidates[0]
        if best is not None:
            allowed_modes = {detect_mode.result}
            if best.is_battle:
                allowed_modes.add(detect_mode.select)
            results = [
                detail.result
                for detail in self.search(
                    title=best.title,
                    style=best.style,
                    difficulty=best.difficulty,
                    battle=best.is_battle,
                )
                if detail.result.detect_mode in allowed_modes
            ]
        else:
            results = [detail.result for detail in self.search(chart_id=base_chart_id) if detail.result.detect_mode == detect_mode.result]
        if best is None and not results:
            return None
        title = best.title if best else results[0].title
        style = best.style if best else results[0].play_style
        diff = best.difficulty if best else results[0].difficulty
        battle = best.is_battle if best else (results[0].option.battle if results[0].option else False)
        data = self.get_history_cursong_data(title, style, diff, battle=battle)
        if not data:
            return None
        data["chart_id"] = chart_id
        data["items"] = self._mobile_play_log_items(
            sorted(results, key=lambda r: r.timestamp, reverse=True),
            include_select=bool(battle),
        )
        for item in data.get("rival_items", []):
            try:
                item["lamp_text"] = self._lamp_text(clear_lamp(item.get("lamp", 0)))
            except Exception:
                item["lamp_text"] = ""
        return data

    def get_option_data(self, option: CurrentOption) -> dict:
        """最後に設定したオプションをdictとして出力。WebSocketへの送信用。"""
        if option is None:
            return {
                "option": "",
                "gauge": "",
                "play_style": "",
            }
        data = {
            "option": str(option),  # battle, OFF/OFFとか
            "gauge": str(option.option_gauge) if option.option_gauge else "",  # easyとかexhとか
            "play_style": str(option.play_style.name.upper()) if option.play_style else "",  # SP/DP
        }
        return data

    def write_best_csv(self, csv_path=None):
        header = [
            "LV",
            "Title",
            "mode",
            "Lamp",
            "Score",
            "(rate)",
            "BP",
            "Opt(best score)",
            "Opt(min bp)",
            "Last Played",
        ]
        os.makedirs("out", exist_ok=True)

        # 全曲の自己べを取得
        bests = self.get_all_best_results()

        # 出力先の決定
        if csv_path:
            os.makedirs(csv_path, exist_ok=True)
            output_file = Path(csv_path) / "inf_score.csv"
        else:
            output_file = Path(".") / "inf_score.csv"

        with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)

            for (title_str, style, diff, battle), best in bests.items():
                lv = best.level
                mode = get_chart_name(style, diff)
                if battle:  # DBx
                    mode = "DB" + mode[-1]
                lamp = str(best.lamp)
                score = best.best_score
                bp = best.min_bp
                if bp >= 99999:
                    bp = ""
                best_score_opt = best.best_score_option
                if best_score_opt in ("unknown", "None", "?") or not best_score_opt:
                    best_score_opt = "?"
                if best_score_opt == "REGULAR":
                    if style == play_style.sp:
                        best_score_opt = "OFF"
                    else:
                        best_score_opt = "OFF/OFF"
                min_bp_opt = best.min_bp_option
                if min_bp_opt in ("unknown", "None", "?") or not min_bp_opt:
                    min_bp_opt = "?"
                if min_bp_opt == "REGULAR":
                    if style == play_style.sp:
                        min_bp_opt = "OFF"
                    else:
                        min_bp_opt = "OFF/OFF"
                timestamp = best.last_play_date
                row = [
                    lv,
                    title_str,
                    mode,
                    lamp,
                    score,
                    "",  # rate
                    bp,
                    best_score_opt,
                    min_bp_opt,
                    timestamp,
                ]
                if mode == "":
                    continue
                writer.writerow(row)

    def write_bpi_csv(self, play_style: play_style):
        """bpimが受けられるcsvを出力する。ランプは全てNO PLAYで出す。(CPIに使われないように)"""
        # OK: 12,3395,0,0,200,FAILED,---,
        # NG: 11,3396,0,0,200,FAILED,---
        # OK: 11,3397,0,0,200,FAILED
        #
        # 時刻の更新は必須。
        # レベルは書いてあれば良いっぽい。全部11にしてみるか。
        # 全曲の自己べを取得
        bests = self.get_all_best_results()
        titles = []
        for title, style, diff, battle in bests.keys():
            if battle:
                continue
            if style != play_style:  # SP/DPどちらかのみ
                continue
            titles.append(title)
        titles = list(set(titles))
        out = "バージョン,タイトル,ジャンル,アーティスト,プレー回数,BEGINNER 難易度,BEGINNER スコア,BEGINNER PGreat,BEGINNER Great,BEGINNER ミスカウント,BEGINNER クリアタイプ,BEGINNER DJ LEVEL,NORMAL 難易度,NORMAL スコア,NORMAL PGreat,NORMAL Great,NORMAL ミスカウント,NORMAL クリアタイプ,NORMAL DJ LEVEL,HYPER 難易度,HYPER スコア,HYPER PGreat,HYPER Great,HYPER ミスカウント,HYPER クリアタイプ,HYPER DJ LEVEL,ANOTHER 難易度,ANOTHER スコア,ANOTHER PGreat,ANOTHER Great,ANOTHER ミスカウント,ANOTHER クリアタイプ,ANOTHER DJ LEVEL,LEGGENDARIA 難易度,LEGGENDARIA スコア,LEGGENDARIA PGreat,LEGGENDARIA Great,LEGGENDARIA ミスカウント,LEGGENDARIA クリアタイプ,LEGGENDARIA DJ LEVEL,最終プレー日時\n"
        for t in titles:
            line = "copula,"
            line += t + ","
            line += "TECHNO,SLAKE,0,"
            # beginner, normalは1つもないので埋めておく
            line += "0,0,0,0,---,NO PLAY,---,3,0,0,0,---,NO PLAY,---,"
            if (t, play_style, difficulty.hyper, None) in bests:
                s = bests[(t, play_style, difficulty.hyper, None)]
                line += f"12,{s.best_score},0,0,---,NO PLAY,---,"
            else:
                line += "3,0,0,0,---,NO PLAY,---,"
            if (t, play_style, difficulty.another, None) in bests:
                s = bests[(t, play_style, difficulty.another, None)]
                line += f"12,{s.best_score},0,0,---,NO PLAY,---,"
            else:
                line += "3,0,0,0,---,NO PLAY,---,"
            if (t, play_style, difficulty.leggendaria, None) in bests:
                s = bests[(t, play_style, difficulty.leggendaria, None)]
                line += f"12,{s.best_score},0,0,---,NO PLAY,---,"
            else:
                line += "3,0,0,0,---,NO PLAY,---,"
            now = datetime.datetime.now()
            line += f"{now.year}/{now.month}/{now.day} {now.hour}:{now.minute}\n"
            out += line
        f = open(f"bpi_{play_style.name}.txt", "w", encoding="utf-8")
        f.write(out)

        return titles

    def __str__(self):
        out = ""
        for r in self.results:
            songinfo = self.song_database.search(chart_id=r.chart_id)
            detail = DetailedResult(songinfo, r)
            out += str(detail)
            # out += str(detail) + f', {r.chart_id}, {songinfo}\n'
        return out


if __name__ == "__main__":
    rdb = ResultDatabase()
    chart_id = calc_chart_id("煉獄のエルフェリア", play_style.sp, difficulty.another)
    results = rdb.search(chart_id=chart_id)
    s = rdb.song_database.search(chart_id=chart_id)

    # print(rdb)

    rdb.write_today_updates_xml(0)
