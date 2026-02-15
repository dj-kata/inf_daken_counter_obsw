# ResultDatabase - リザルトの永続化・検索・配信を担当
from .classes import *
from .funcs import *
from .songinfo import *
from .result import PlayOption, OneResult, DetailedResult
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
from typing import List


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
    for attr, key in [('dp_unofficial', 'dp_unofficial_lv'),
                       ('sp12_hard', 'sp_12hard'), ('sp12_clear', 'sp_12clear'),
                       ('sp11_hard', 'sp_11hard'), ('sp11_clear', 'sp_11clear'),
                       ('dp_ereter_easy', 'dp_ereter_easy'), ('dp_ereter_hard', 'dp_ereter_hard'),
                       ('dp_ereter_exh', 'dp_ereter_exh')]:
        val = getattr(songinfo, attr, None)
        fields[key] = str(val) if val else ""
    return fields

class ResultDatabase:
    """全リザルトを保存するためのクラス"""
    def __init__(self, config:Config=None):
        self.song_database = SongDatabase()
        """曲情報クラスのインスタンス。検索用。"""
        self.results:List[OneResult] = []
        """全リザルトが格納されるリスト。OneResultが1エントリとなる。"""

        # WebSocketサーバー関連の初期化
        self.config = config
        self.ws_server = None
        self.ws_loop = None
        self.ws_thread = None

        # configが渡された場合のみWebSocketサーバーを起動
        if config is not None:
            self._init_websocket_server()
            # WebSocket設定をCSSファイルに書き込み
            self._write_websocket_config()

        self.load()
        self.save()

    def _write_websocket_config(self):
        """WebSocketポート番号をCSSファイルに書き込む"""
        try:
            os.makedirs('out', exist_ok=True)

            css_content = f"""/* WebSocket設定 - 自動生成ファイル */
    :root {{
        --websocket-port: {self.config.websocket_data_port};
    }}
    """

            css_path = Path('out') / 'websocket.css'
            with open(css_path, 'w', encoding='utf-8') as f:
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
        self.ws_thread = threading.Thread(target=self._start_websocket_loop, daemon=True)
        self.ws_thread.start()

        # WebSocketサーバーの起動
        self.ws_server = DataWebSocketServer(self.config.websocket_data_port)
        self.ws_server.start(self.ws_loop)

        logger.info(f"WebSocketサーバー起動: ポート {self.config.websocket_data_port}")

    def _start_websocket_loop(self):
        """WebSocket用イベントループをスレッドで実行"""
        import asyncio
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_forever()

    def shutdown_servers(self):
        """サーバーを停止（アプリケーション終了時に呼び出す）"""
        if self.ws_server:
            self.ws_server.stop()
        if self.ws_loop:
            self.ws_loop.call_soon_threadsafe(self.ws_loop.stop)
        logger.info("WebSocketサーバーを停止しました")

    def update_websocket_port(self, port: int):
        """WebSocketポート番号を更新"""
        if self.config:
            self.config.websocket_data_port = port
            self._write_websocket_config()  # CSSファイルを更新
            logger.info(f"WebSocketポート更新: {port}")

    @_ws_broadcast('update_graph_data')
    def broadcast_graph_data(self, start_time: int):
        """グラフデータをWebSocketで配信"""
        return self.get_graph_data(start_time)

    @_ws_broadcast('update_today_updates_data')
    def broadcast_today_updates_data(self, start_time: int):
        """本日の更新データをWebSocketで配信"""
        return self.get_today_updates_data(start_time)

    @_ws_broadcast('update_history_cursong_data')
    def broadcast_history_cursong_data(self, title: str, style, difficulty,
                                       battle: bool = None, playspeed: float = None):
        """履歴データをWebSocketで配信"""
        return self.get_history_cursong_data(title, style, difficulty, battle, playspeed)

    @_ws_broadcast('update_today_stats_data')
    def broadcast_today_stats_data(self, start_time: int):
        """統計データをWebSocketで配信"""
        return self.get_today_stats_data(start_time)

    _SPECIAL_ARRANGE_KEYWORDS = ['H-RAN', 'SYMM-RAN', 'SYNC-RAN']

    def _filter_results_for_best(self, results: List[DetailedResult],
                                  playspeed: float = None, battle: bool = False
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
                if any(kw in r.result.option.arrange for kw in self._SPECIAL_ARRANGE_KEYWORDS):
                    continue

            if playspeed is not None:
                # playspeed指定時: 同一playspeedの detect_mode.result のみ
                if r.result.playspeed != playspeed:
                    continue
                if r.result.detect_mode != detect_mode.result:
                    continue
            elif battle:
                # battle時: battle=True の detect_mode.result のみ
                if not (r.result.option and r.result.option.battle):
                    continue
                if r.result.detect_mode != detect_mode.result:
                    continue
            else:
                # 通常: playspeed=None かつ battleでない detect_mode.result / detect_mode.select
                if r.result.playspeed is not None:
                    continue
                if r.result.option and r.result.option.battle:
                    continue

            filtered.append(r)
        return filtered

    def add(self, result:OneResult) -> bool:
        """リザルト登録用関数。chart_id情報を何も渡さなくても受ける(途中落ちのノーツ数保存用)

        Args:
            result (OneResult): リザルト

        Return:
            bool(True:登録された / False:登録済み等の理由で却下された)
        """
        if result.detect_mode==detect_mode.play:
            self.results.append(result)
            logger.info(f"result added! hash:{hash(result)}, len:{len(self.results)}, result:{result}")
            return True
        else:
            if result not in self.results:
                battle = True if result.option and result.option.battle else False
                result.pre_score,result.pre_bp,result.pre_lamp = self.get_best(title=result.title, style=result.play_style, difficulty=result.difficulty, battle=battle, playspeed=result.playspeed)
                self.results.append(result)
                logger.info(f"result added! hash:{hash(result)}, len:{len(self.results)}, result:{result}")
                return True
            else:
                return False

    def load(self):
        """保存済みリザルトをロードする"""
        try:
            with bz2.BZ2File('playlog.infdc', 'rb', compresslevel=9) as f:
                self.results = pickle.load(f)
        except Exception:
            logger.error(traceback.format_exc())

    def save(self):
        '''ファイル出力'''
        with bz2.BZ2File('playlog.infdc', 'wb', compresslevel=9) as f:
            pickle.dump(self.results, f)

    def search(self,
                title:str=None, style:play_style=None, difficulty:difficulty=None, chart_id:str=None,
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
        ret:List[DetailedResult] = []
        key = chart_id
        if title is not None and style is not None and difficulty is not None:
            key = calc_chart_id(title, style, difficulty)
        songinfo = self.song_database.search(chart_id=key)

        for r in self.results:
            if r.chart_id == key:
                detail = DetailedResult(songinfo, r)
                ret.append(detail)
        return ret

    def get_best(self,
                title:str=None, style:play_style=None, difficulty:difficulty=None, chart_id:str=None,
                battle:bool=None,option:PlayOption=None,playspeed:float=None
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

        Returns:
            List[int]: score, bp, lamp
        """
        ret = [0,99999999,clear_lamp(0)]
        key = chart_id
        if title is not None and style is not None and difficulty is not None:
            key = calc_chart_id(title, style, difficulty)
        results = self.search(chart_id=key)
        filtered = self._filter_results_for_best(results, playspeed=playspeed, battle=battle)
        if not filtered:
            return [None, None, None]
        for r in filtered:
            if option: # オプション指定がある場合は、arrangeが一致するもののみ通す
                if option.arrange is not r.result.option.arrange or option.flip is not r.result.option.flip or option.special is not r.result.option.special:
                    continue
            ret[0] = max(ret[0], r.result.score)
            if r.result.judge:
                ret[1] = min(ret[1], r.result.judge.bd + r.result.judge.pr)
            elif r.result.bp: # 選曲画面から登録したものはこちら
                ret[1] = min(ret[1], r.result.bp)
            ret[2] = clear_lamp(max(ret[2].value, r.result.lamp.value))

        return ret

    def get_monthly_notes(self, target:datetime.datetime=None):
        '''その月のノーツ数を算出'''
        if target is None:
            target = datetime.datetime.now()
        ret = 0
        for r in self.results:
            result_date = datetime.datetime.fromtimestamp(r.timestamp)
            if r.detect_mode != detect_mode.play:
                continue
            if (result_date.month == target.month) and (result_date.year == target.year):
                if r.judge:
                    ret += r.judge.notes
            else:
                break
        return ret

    def get_all_best_results(self):
        """全譜面のベストリザルトを集計（battle有効/無効を別々に集計）

        Returns:
            dict: (title, play_style, difficulty, battle)のtupleをキーとした辞書。
                  各要素は以下のキーを持つ辞書:
                - best_score: ベストスコア
                - best_score_option: ベストスコア時のオプション
                - min_bp: 最小BP
                - min_bp_option: 最小BP時のオプション
                - last_play_timestamp: 最終プレー日のタイムスタンプ
                - best_lamp: ベストランプ
        """
        best_results = {}

        for result in self.results:
            # battleの判定
            battle = result.option.battle if result.option else None

            # キーをtupleで作成
            key = (result.title, result.play_style, result.difficulty, battle)

            # 初期化
            if key not in best_results:
                best_results[key] = {
                    'best_score': 0,
                    'best_score_option': None,
                    'min_bp': 99999999,
                    'min_bp_option': None,
                    'last_play_timestamp': 0,
                    'best_lamp': clear_lamp(0),
                }

            entry = best_results[key]

            # ノーツ数を記録（リザルトから取得）
            if result.notes and not entry.get('notes'):
                entry['notes'] = result.notes

            # ベストスコア更新
            if result.score and result.score > entry['best_score']:
                entry['best_score'] = result.score
                entry['best_score_option'] = result.option

            # 最小BP更新
            bp = None
            if result.judge:
                bp = result.judge.bd + result.judge.pr
            elif result.bp:
                bp = result.bp

            if bp is not None and bp < entry['min_bp']:
                entry['min_bp'] = bp
                entry['min_bp_option'] = result.option

            # 最終プレー日更新
            if result.timestamp > entry['last_play_timestamp']:
                entry['last_play_timestamp'] = result.timestamp

            # ベストランプ更新
            if result.lamp and result.lamp.value > entry['best_lamp'].value:
                entry['best_lamp'] = result.lamp

        return best_results

    def get_graph_data(self, start_time:int) -> dict:
        '''本日のノーツ数用データを辞書形式で返す'''
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
            if hasattr(latest_result, 'score') and hasattr(latest_result, 'notes') and latest_result.notes:
                current_score_rate = f"{latest_result.score / latest_result.notes / 2 * 100:.2f}%"

        data = {
            'playcount': len(target),
            'today_notes': total.pg + total.gr + total.gd + total.bd,
            'today_score_rate': f"{total.score_rate*100:.2f}%",
            'current_score_rate': current_score_rate,
            'today_judge': {
                'pg': total.pg,
                'gr': total.gr,
                'gd': total.gd,
                'bd': total.bd,
                'pr': total.pr,
                'cb': total.cb
            },
            'judges': []
        }

        for i, r in enumerate(reversed(target)):
            data['judges'].append({
                'idx': i + 1,
                'pg': r.judge.pg,
                'gr': r.judge.gr,
                'gd': r.judge.gd,
                'bd': r.judge.bd,
                'pr': r.judge.pr,
                'cb': r.judge.cb
            })

        return data


    def get_today_updates_data(self, start_time:int) -> dict:
        """本日のプレー履歴のデータを辞書形式で返す"""
        target:List[OneResult] = []
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.result:
                if r.timestamp >= start_time:
                    target.append(r)
                else:
                    break

        items = []
        for r in target:
            songinfo = self.song_database.search(title=r.title, play_style=r.play_style, difficulty=r.difficulty)
            detailed_result = DetailedResult(songinfo, r, None, songinfo.level if hasattr(songinfo, 'level') else None)

            item = {
                'lv': str(songinfo.level) if hasattr(songinfo, 'level') else "",
                'title': r.title,
                'difficulty': get_chart_name(r.play_style, r.difficulty),
                'notes': r.notes,
                'score': r.score,
                'bp': r.judge.pr + r.judge.bd if r.judge else r.bp,
                'lamp': r.lamp.value,
                'pre_score': r.pre_score if r.pre_score is not None else 0,
                'pre_bp': r.pre_bp if r.pre_bp is not None else 0,
                'pre_lamp': r.pre_lamp.value if r.pre_lamp is not None else 0,
                'opt': r.option.__str__() if r.option else "",
                'battle': r.option.battle if r.option else 0,
                'playspeed': r.playspeed if r.playspeed else 1.0,
                'score_rate': r.score / r.notes / 2 if r.notes else 0
            }

            item.update(_extract_songinfo_fields(songinfo))

            if detailed_result.bpi:
                item['bpi'] = f"{detailed_result.bpi:.2f}"

            if detailed_result.score_rate_with_rankdiff:
                item['rankdiff'] = ''.join(detailed_result.score_rate_with_rankdiff)
                item['rankdiff0'] = detailed_result.score_rate_with_rankdiff[0]
                item['rankdiff1'] = detailed_result.score_rate_with_rankdiff[1]

            items.append(item)

        return {'items': items}


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
            daily_notes.append({
                'date': d.strftime('%m/%d'),
                'pg': j.pg,
                'gr': j.gr,
                'gd': j.gd,
                'bd': j.bd,
            })

        # --- today_level_distribution: 本日のレベル分布 ---
        level_dist = {}
        for r in reversed(self.results):
            if r.detect_mode == detect_mode.result:
                if r.timestamp >= start_time:
                    songinfo = self.song_database.search(
                        title=r.title, play_style=r.play_style, difficulty=r.difficulty
                    )
                    lv = str(songinfo.level) if songinfo and hasattr(songinfo, 'level') else '?'
                    if lv not in level_dist:
                        level_dist[lv] = {'sp': 0, 'dp': 0, 'battle': 0}
                    is_battle = r.option and r.option.battle
                    if is_battle:
                        level_dist[lv]['battle'] += 1
                    elif r.play_style == play_style.sp:
                        level_dist[lv]['sp'] += 1
                    else:
                        level_dist[lv]['dp'] += 1
                else:
                    break

        # --- level_stats: 全レベルのランプ/スコアレート統計 ---
        bests = self.get_all_best_results()
        level_stats = {'sp': {}, 'dp': {}}

        for (title, style, diff, battle), value in bests.items():
            if battle:
                continue
            songinfo = self.song_database.search(
                title=title, play_style=style, difficulty=diff
            )
            if not songinfo or not hasattr(songinfo, 'level') or not songinfo.level:
                continue

            lv = str(songinfo.level)
            style_key = 'sp' if style == play_style.sp else 'dp'

            if lv not in level_stats[style_key]:
                level_stats[style_key][lv] = {
                    'total': 0,
                    'lamps': {
                        'fc': 0, 'exh': 0, 'hard': 0, 'clear': 0,
                        'easy': 0, 'assist': 0, 'failed': 0,
                    },
                    'scores': {'AAA': 0, 'AA': 0, 'A': 0, 'B_below': 0},
                }

            entry = level_stats[style_key][lv]
            entry['total'] += 1

            # ランプ分類
            lamp = value['best_lamp']
            lamp_key_map = {
                clear_lamp.fc: 'fc', clear_lamp.exh: 'exh',
                clear_lamp.hard: 'hard', clear_lamp.clear: 'clear',
                clear_lamp.easy: 'easy', clear_lamp.assist: 'assist',
                clear_lamp.failed: 'failed', clear_lamp.noplay: 'failed',
            }
            entry['lamps'][lamp_key_map.get(lamp, 'failed')] += 1

            # スコアレート分類（songinfo.notesが無い場合はリザルト側のnotesをフォールバック）
            notes = songinfo.notes if hasattr(songinfo, 'notes') and songinfo.notes else value.get('notes')
            if notes and value['best_score'] > 0:
                rate = value['best_score'] / (notes * 2)
                if rate >= 16 / 18:
                    entry['scores']['AAA'] += 1
                elif rate >= 14 / 18:
                    entry['scores']['AA'] += 1
                elif rate >= 12 / 18:
                    entry['scores']['A'] += 1
                else:
                    entry['scores']['B_below'] += 1

        return {
            'date': now.strftime('%Y. %m. %d'),
            'playcount': playcount,
            'score_rate': score_rate_str,
            'daily_notes': daily_notes,
            'today_level_distribution': level_dist,
            'level_stats': level_stats,
        }

    def get_history_cursong_data(self, title:str, style:play_style, difficulty:difficulty,
                                 battle:bool=None, playspeed:float=None) -> dict:
        """指定された曲のプレーログを辞書形式で返す。websocketでの送信用。"""
        songinfo = self.song_database.search(title=title, play_style=style, difficulty=difficulty)
        results = self.search(title=title, style=style, difficulty=difficulty)
        best_score = 0
        best_score_opt = None
        detail = None
        best_bp = 99999999
        best_bp_opt = None
        best_lamp = 0
        best_lamp_opt = None
        notes = None # バグってノーツ数が入っていない場合があるので別処理にする

        filtered = self._filter_results_for_best(results, playspeed=playspeed, battle=battle)
        target = []
        for r in filtered:
            if r.result.detect_mode == detect_mode.result:
                target.append(r)
            if r.result.notes and not notes:
                notes = r.result.notes
            if r.result.score > best_score:
                best_score = r.result.score
                best_score_opt = r.result.option
                detail = r
            if r.result.lamp.value > best_lamp:
                best_lamp = r.result.lamp.value
                best_lamp_opt = r.result.option
            if r.result.judge:
                if not r.result.dead and r.result.judge.pr + r.result.judge.bd < best_bp:
                    best_bp = r.result.judge.pr + r.result.judge.bd
                    best_bp_opt = r.result.option
            else:
                if r.result.bp and r.result.bp < best_bp:
                    best_bp = r.result.bp
                    best_bp_opt = r.result.option

        if len(results) == 0:
            return {}

        last_played_time = results[0].result.timestamp

        data = {
            'lv': str(songinfo.level) if hasattr(songinfo, 'level') else "",
            'music': title,
            'difficulty': get_chart_name(style, difficulty),
            'playspeed':playspeed if playspeed else 1.0,
            'last_played': str(datetime.datetime.fromtimestamp(last_played_time).strftime('%Y/%m/%d')),
            'best_lamp': best_lamp,
            'best_lamp_opt': best_lamp_opt.__str__() if best_lamp_opt else "",
            'best_bp': best_bp,
            'best_bp_opt': best_bp_opt.__str__() if best_bp_opt else "",
            'best_score': best_score,
            'best_score_opt': best_score_opt.__str__() if best_score_opt else "",
            'battle': best_score_opt.battle if best_score_opt else 0,
        }

        if songinfo and hasattr(songinfo, 'bpi_ave') and songinfo.bpi_ave:
            data['bpi_ave'] = f"{songinfo.bpi_ave}"
        if songinfo and hasattr(songinfo, 'bpi_top') and songinfo.bpi_top:
            data['bpi_top'] = f"{songinfo.bpi_top}"
        if songinfo and hasattr(songinfo, 'bpi_coef') and songinfo.bpi_coef:
            data['bpi_coef'] = f"{songinfo.bpi_coef}"

        if detail:
            detail.result.notes = notes
            if detail.result.notes:
                data['notes'] = notes
                data['best_score_rate'] = best_score / detail.result.notes / 2
                data['best_bp_rate'] = f"{100*best_bp / detail.result.notes:.2f}"
                if detail.score_rate_with_rankdiff:
                    data['best_rankdiff0'] = detail.score_rate_with_rankdiff[0]
                    data['best_rankdiff1'] = detail.score_rate_with_rankdiff[1]
            if detail.bpi:
                data['best_bpi'] = f"{detail.bpi:.2f}"
            if detail.score_rate_with_rankdiff:
                data['rankdiff'] = ''.join(detail.score_rate_with_rankdiff)
                data['rankdiff0'] = detail.score_rate_with_rankdiff[0]
                data['rankdiff1'] = detail.score_rate_with_rankdiff[1]

        data.update(_extract_songinfo_fields(songinfo))

        items = []
        for r in reversed(target):
            item = {
                'date': str(datetime.datetime.fromtimestamp(r.result.timestamp).strftime('%Y/%m/%d')),
                'lamp': r.result.lamp.value,
                'score': r.result.score,
                'score_rate': r.result.score / r.result.notes / 2 if r.result.notes else 0,
                'bp': r.result.bp,
                'bprate': r.result.bp / r.result.notes if r.result.notes else 0,
                'pre_score': r.result.pre_score if r.result.pre_score is not None else 0,
                'pre_lamp': r.result.pre_lamp.value if r.result.pre_lamp is not None else 0,
                'pre_bp': r.result.pre_bp if r.result.pre_bp is not None else 0,
                'opt': r.result.option.__str__() if r.result.option else ""
            }

            if r.bpi:
                item['bpi'] = f"{r.bpi:.2f}"
            if r.score_rate_with_rankdiff:
                item['rankdiff'] = ''.join(r.score_rate_with_rankdiff)
                item['rankdiff0'] = r.score_rate_with_rankdiff[0]
                item['rankdiff1'] = r.score_rate_with_rankdiff[1]

            items.append(item)

        data['items'] = items
        return data

    def write_best_csv(self, csv_path=None):
        header = ['LV', 'Title', 'mode', 'Lamp', 'Score', '(rate)', 'BP', 'Opt(best score)', 'Opt(min bp)', 'Last Played']
        os.makedirs('out', exist_ok=True)

        # 全曲の自己べを取得
        bests = self.get_all_best_results()

        # 出力先の決定
        if csv_path:
            os.makedirs(csv_path, exist_ok=True)
            output_file = Path(csv_path) / 'inf_score.csv'
        else:
            output_file = Path('.') / 'inf_score.csv'

        with open(output_file, 'w') as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)

            for key,value in zip(bests.keys(), bests.values()):
                row = []
                lv = ''
                title = escape_for_csv(key[0])
                mode = get_chart_name(key[1], key[2])
                if key[3]: # DBx
                    mode = 'DB' + mode[-1]
                lamp = str(value['best_lamp'])
                score = value['best_score']
                bp = value['min_bp']
                if bp == 99999999:
                    bp = ''
                best_score_opt = value['best_score_option'].__str__()
                if best_score_opt in ('unknown', 'None') or not best_score_opt:
                    best_score_opt = '?'
                if best_score_opt == 'REGULAR':
                    if key[1] == play_style.sp:
                        best_score_opt = 'OFF'
                    else:
                        best_score_opt = 'OFF/OFF'
                min_bp_opt = value['min_bp_option'].__str__()
                if min_bp_opt in ('unknown', 'None') or not min_bp_opt:
                    min_bp_opt = '?'
                if min_bp_opt == 'REGULAR':
                    if key[1] == play_style.sp:
                        min_bp_opt = 'OFF'
                    else:
                        min_bp_opt = 'OFF/OFF'
                timestamp = datetime.datetime.fromtimestamp(value['last_play_timestamp']).strftime('%Y/%m/%d %H:%M')
                row = [
                    lv,
                    title,
                    mode,
                    lamp,
                    score,
                    '', # rate
                    bp,
                    best_score_opt,
                    min_bp_opt,
                    timestamp
                ]
                if mode == '':
                    logger.debug(f'mode is None, skipped!, row={row}')
                    continue
                writer.writerow(row)

    def write_bpi_csv(self, play_style:play_style):
        '''bpimが受けられるcsvを出力する。ランプは全てNO PLAYで出す。(CPIに使われないように)'''
        # OK: 12,3395,0,0,200,FAILED,---,
        # NG: 11,3396,0,0,200,FAILED,---
        # OK: 11,3397,0,0,200,FAILED
        #
        # 時刻の更新は必須。
        # レベルは書いてあれば良いっぽい。全部11にしてみるか。
        # 全曲の自己べを取得
        bests = self.get_all_best_results()
        titles = []
        for k in bests.keys():
            title, style, diff, battle = k
            if battle:
                continue
            if style != play_style: # SP/DPどちらかのみ
                continue
            titles.append(title)
        titles = list(set(titles))
        out = 'バージョン,タイトル,ジャンル,アーティスト,プレー回数,BEGINNER 難易度,BEGINNER スコア,BEGINNER PGreat,BEGINNER Great,BEGINNER ミスカウント,BEGINNER クリアタイプ,BEGINNER DJ LEVEL,NORMAL 難易度,NORMAL スコア,NORMAL PGreat,NORMAL Great,NORMAL ミスカウント,NORMAL クリアタイプ,NORMAL DJ LEVEL,HYPER 難易度,HYPER スコア,HYPER PGreat,HYPER Great,HYPER ミスカウント,HYPER クリアタイプ,HYPER DJ LEVEL,ANOTHER 難易度,ANOTHER スコア,ANOTHER PGreat,ANOTHER Great,ANOTHER ミスカウント,ANOTHER クリアタイプ,ANOTHER DJ LEVEL,LEGGENDARIA 難易度,LEGGENDARIA スコア,LEGGENDARIA PGreat,LEGGENDARIA Great,LEGGENDARIA ミスカウント,LEGGENDARIA クリアタイプ,LEGGENDARIA DJ LEVEL,最終プレー日時\n'
        for t in titles:
            line = 'copula,'
            line += t + ','
            line += 'TECHNO,SLAKE,0,'
            # beginner, normalは1つもないので埋めておく
            line += '0,0,0,0,---,NO PLAY,---,3,0,0,0,---,NO PLAY,---,'
            if (t, play_style, difficulty.hyper, None) in bests.keys():
                s = bests[(t, play_style, difficulty.hyper, None)]
                line += f"12,{s['best_score']},0,0,---,NO PLAY,---,"
            else:
                line += '3,0,0,0,---,NO PLAY,---,'
            if (t, play_style, difficulty.another, None) in bests.keys():
                s = bests[(t, play_style, difficulty.another, None)]
                line += f"12,{s['best_score']},0,0,---,NO PLAY,---,"
            else:
                line += '3,0,0,0,---,NO PLAY,---,'
            if (t, play_style, difficulty.leggendaria, None) in bests.keys():
                s = bests[(t, play_style, difficulty.leggendaria, None)]
                line += f"12,{s['best_score']},0,0,---,NO PLAY,---,"
            else:
                line += '3,0,0,0,---,NO PLAY,---,'
            now = datetime.datetime.now()
            line += f"{now.year}/{now.month}/{now.day} {now.hour}:{now.minute}\n"
            out += line
        f = open(f'bpi_{play_style.name}.txt', 'w', encoding='utf-8')
        f.write(out)

        return titles

    def __str__(self):
        out = ''
        for r in self.results:
            songinfo = self.song_database.search(chart_id=r.chart_id)
            detail = DetailedResult(songinfo, r)
            out += str(detail)
            # out += str(detail) + f', {r.chart_id}, {songinfo}\n'
        return out

if __name__ == '__main__':
    rdb = ResultDatabase()
    chart_id = calc_chart_id('煉獄のエルフェリア', play_style.sp, difficulty.another)
    results = rdb.search(chart_id=chart_id)
    s = rdb.song_database.search(chart_id=chart_id)

    # print(rdb)

    rdb.write_today_updates_xml(0)
