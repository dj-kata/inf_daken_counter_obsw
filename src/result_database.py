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
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
import copy
import threading


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
        self.mobile_http_server.start()

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
            server_running = self.mobile_http_server is not None
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
                if r.result.detect_mode != detect_mode.result:
                    continue
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
        if chart_id and result.chart_id == chart_id:
            return True
        if title is None or style is None or difficulty is None:
            return False
        result_battle = result.option.battle if result.option else False
        if bool(result_battle) != bool(battle):
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
                if best.best_lamp_result:
                    best.best_lamp_result.notes = result.notes
                if best.min_bp_result:
                    best.min_bp_result.notes = result.notes

        return best_results

    def get_graph_data(self, start_time: int) -> dict:
        """本日のノーツ数用データを辞書形式で返す"""
        target = []
        total = Judge()
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.play:
                if r.timestamp >= start_time:
                    target.append(r)
                    if r.judge:
                        total += r.judge
                else:
                    break

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

    def get_today_updates_data(self, start_time: int) -> dict:
        """本日のプレー履歴のデータを辞書形式で返す"""
        target: List[OneResult] = []
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.result:
                if r.timestamp >= start_time:
                    target.append(r)
                else:
                    break

        items = []
        for r in target:
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
                "chart_id": calc_chart_id(
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
            }

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

    def get_today_stats_data(self, start_time: int) -> dict:
        """today_stats.html用の統計データを生成"""
        now = datetime.datetime.now()

        # --- playcount, score_rate (get_graph_dataと同等のロジック) ---
        today_target = []
        total_judge = Judge()
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.play:
                if r.timestamp >= start_time:
                    today_target.append(r)
                    if r.judge:
                        total_judge += r.judge
                else:
                    break

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
                if r.timestamp >= start_time:
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
                else:
                    break

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
            "battle": best_score_opt.battle if best_score_opt else 0,
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
        notes = _to_int_or_none(best.notes) or 0
        score_rate = best_score / (notes * 2) if notes else 0
        return {
            "chart_id": calc_chart_id(best.title, best.style, best.difficulty, battle=best.is_battle),
            "title": best.title,
            "difficulty": best.chart,
            "lv": best.level,
            "score": best_score,
            "bp": best_bp,
            "lamp": lamp.value if lamp else clear_lamp.noplay.value,
            "lamp_text": self._lamp_text(lamp),
            "score_rate": score_rate,
            "notes": notes,
            "last_played": best.last_play_date,
            "opt": best.best_score_option,
        }

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
        return {
            "chart_id": result.chart_id,
            "title": result.title,
            "difficulty": get_chart_name(result.play_style, result.difficulty, battle=result.option.battle if result.option else False),
            "lv": str(songinfo.level) if songinfo and getattr(songinfo, "level", None) else "",
            "score": score,
            "bp": _to_int_or_none(bp),
            "lamp": lamp.value,
            "lamp_text": self._lamp_text(lamp),
            "score_rate": score_rate,
            "bpi": bpi,
            "bpi_label": bpi_label,
            "notes": notes,
            "date": self._timestamp_text(result.timestamp),
            "opt": str(result.option) if result.option else "",
            "dead": bool(result.dead),
        }

    def _mobile_result_items(self, results: list[OneResult]) -> list[dict]:
        return [self._serialize_mobile_result(r) for r in results if r.detect_mode == detect_mode.result]

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
                    if best.style == style_value and _to_int_or_none(best.level)
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
                        if b.style == style_value and _to_int_or_none(b.level) == level
                    ),
                }
                for level in levels
            )
        result_count = sum(1 for r in self.results if r.detect_mode == detect_mode.result)
        today_notes = self._notes_since(self._today_start_timestamp())
        current = self.get_mobile_current_folder_data()
        daily_count = len(self._notes_by_date())
        return {
            "total_best_charts": len(bests),
            "total_results": result_count,
            "today_notes": today_notes,
            "levels": level_folders,
            "special": [
                {"id": "history", "label": "PLAY HISTORY", "count": result_count, "count_label": f"{result_count} plays"},
                {"id": "receipt", "label": "RECEIPT", "count": today_notes, "count_label": f"{today_notes:,} notes"},
                {"id": "daily", "label": "DAILY LOG", "count": daily_count, "count_label": f"{daily_count} days"},
                {"id": "current", "label": "CURRENT SONG", "count": len(current.get("items", [])), "count_label": "live"},
            ],
        }

    def get_mobile_level_folder_data(self, level: int, style_text: str | None = None) -> dict:
        style_value = None
        style_label = ""
        if style_text:
            style_label = style_text.upper()
            style_value = play_style.sp if style_label == "SP" else play_style.dp if style_label == "DP" else None
        bests = [
            best
            for best in self.get_all_best_results().values()
            if _to_int_or_none(best.level) == level
            and (style_value is None or best.style == style_value)
        ]
        bests.sort(key=lambda b: (-( _to_int_or_none(b.best_score) or 0), b.title, b.chart))
        items = [
            item
            for item in (self._serialize_mobile_best_safe(best) for best in bests)
            if item is not None
        ]
        folder_id = f"style/{style_label}/level/{level}" if style_label else f"level/{level}"
        label = f"{style_label} LEVEL {level}" if style_label else f"LEVEL {level}"
        return {
            "folder": {"id": folder_id, "label": label},
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

    def get_mobile_receipt_data(self) -> dict:
        start = self._mobile_receipt_start_timestamp()
        graph_data = self.get_graph_data(start)
        updates_data = self.get_today_updates_data(start)
        items = updates_data.get("items", [])

        def bpi_value(item):
            return _to_float_or_none(item.get("bpi"))

        def valid_previous_bp(item):
            pre_bp = _to_int_or_none(item.get("pre_bp"))
            return pre_bp is not None and 0 < pre_bp < 99999

        top_bpi_items = sorted(
            [item for item in items if bpi_value(item) is not None],
            key=lambda item: bpi_value(item),
            reverse=True,
        )[:20]
        score_updates = [
            item for item in items
            if (_to_int_or_none(item.get("score")) or 0) > (_to_int_or_none(item.get("pre_score")) or 0)
        ]
        lamp_updates = [
            item for item in items
            if (_to_int_or_none(item.get("lamp")) or 0) > (_to_int_or_none(item.get("pre_lamp")) or 0)
        ]
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
            "start_time_text": self._timestamp_text(start),
            "play_count": graph_data.get("playcount", len(items)),
            "song_count": len(items),
            "today_notes": graph_data.get("today_notes", 0),
            "score_rate": graph_data.get("today_score_rate", "0.00%"),
            "top_bpi": top_bpi,
            "items": items[:20],
            "top_bpi_items": top_bpi_items,
            "score_updates": score_updates,
            "lamp_updates": lamp_updates,
            "bp_updates": bp_updates,
            "current_detail": current_detail,
            "rival_items": current_detail.get("rival_items", []) if current_detail else [],
        }

    def get_mobile_daily_folders_data(self) -> dict:
        notes_by_date = self._notes_by_date()
        play_counts = defaultdict(int)
        for result in self.results:
            if result.detect_mode == detect_mode.result:
                play_counts[self._timestamp_text(result.timestamp, "%Y-%m-%d")] += 1
        dates = sorted(set(notes_by_date.keys()) | set(play_counts.keys()), reverse=True)
        items = [
            {
                "date": date_key,
                "notes": notes_by_date.get(date_key, 0),
                "play_count": play_counts.get(date_key, 0),
            }
            for date_key in dates
        ]
        return {
            "folder": {"id": "daily", "label": "DAILY LOG"},
            "total_notes": sum(notes_by_date.values()),
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
        if not chart_id:
            for best in self.get_all_best_results().values():
                if best.title == title and best.chart == difficulty_text:
                    chart_id = calc_chart_id(best.title, best.style, best.difficulty, battle=best.is_battle)
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
        best = None
        for candidate in self.get_all_best_results().values():
            candidate_id = calc_chart_id(candidate.title, candidate.style, candidate.difficulty, battle=candidate.is_battle)
            if candidate_id == chart_id:
                best = candidate
                break
        results = [detail.result for detail in self.search(chart_id=chart_id) if detail.result.detect_mode == detect_mode.result]
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
        data["items"] = self._mobile_result_items(sorted(results, key=lambda r: r.timestamp, reverse=True))
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
