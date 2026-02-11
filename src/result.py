# 単体検証: wuv run python -m src.result
from .classes import *
from .funcs import *
from .songinfo import *
from .logger import get_logger
from .config import Config
logger = get_logger(__name__)
import os
import sys
import datetime
import bz2, pickle
import traceback
import logging
import logging, logging.handlers
import math
import csv
import asyncio
import threading
import os
from pathlib import Path
from typing import List
# リザルト用のクラスを定義

sys.path.append('infnotebook')
from result import ResultOptions

class PlayOption():
    """プレイオプション用のクラス。inf-notebook側が None==正規 となっていて非常に使いづらいので変えている。"""
    valid = False
    '''有効かどうか。選曲画面ではオプションが読めないのでFalseに倒す。'''
    arrange = None
    '''配置オプション'''
    flip = None
    '''DPオンリー 左右の譜面が入れ替わる'''
    assist = None
    '''A-SCR or LEGACY(オプション画面の構造上兼ねられない点に注意)'''
    battle = None
    '''DP時にBATTLEがON 両サイドがSP譜面になる'''
    special = None
    '''集計対象とすべきでないスコアのフラグ。H-RAN or BATTLEの場合にTrueとなる。'''

    def __init__(self, option:ResultOptions=None):
        if option:
            self.valid = True
            self.arrange: str = option.arrange
            self.flip: str = option.flip
            self.assist: str = option.assist
            self.battle: bool = option.battle

    @property
    def special(self) -> bool:
        """特殊オプション判定（自動計算）"""
        if not self.arrange:
            return self.battle

        special_keywords = ['H-RAN', 'BATTLE', 'SYMM-RAN', 'SYNC-RAN']
        return any(keyword in self.arrange for keyword in special_keywords) or self.battle

    def convert_from_v2(self, opt:str):
        '''v2の文字列形式でのオプションをv3用に変換してインスタンスに直接書き込む。'''
        self.valid = True
        if opt == None: # 正規
            self.arrange = None
        elif opt == '?':
            self.valid = False # 不明だったやつは不明にしておく
        else:
            if 'H-RAN' in opt:
                self.special = True
            if 'BATTLE' in opt:
                self.special = True
            if 'SYNC-RAN' in opt:
                self.special = True
            if 'SYMM-RAN' in opt:
                self.special = True
            if opt.startswith('BATTLE'): # battle有効時はフラグを立てる
                self.battle = True
                opt = opt.split('BATTLE, ')[-1]
            if 'FLIP' in opt: # flip有効時は消す
                self.flip = 'FLIP'
                opt = opt.replace(', FLIP', '')
            if 'A-SCR' in opt:
                self.assist = 'A-SCR'
                opt = opt.replace(', A-SCR', '')
            if 'LEGACY' in opt:
                self.assist = 'LEGACY'
                opt = opt.replace(', LEGACY', '')

            if '/' not in opt: # sp
                if opt == 'R-RAN':
                    opt = 'R-RANDOM'
                if opt == 'S-RAN':
                    opt = 'S-RANDOM'
                if opt == 'RAN':
                    opt = 'RANDOM'
                if opt == 'MIR':
                    opt = 'MIRROR'
            self.arrange = opt

    def __hash__(self):
        return hash((self.valid, self.arrange, self.flip, self.assist, self.battle, self.special))

    def __eq__(self, other):
        if not isinstance(other, PlayOption):
            return False
        return (self.valid == other.valid and
                self.arrange == other.arrange and
                self.flip == other.flip and
                self.assist == other.assist and
                self.battle == other.battle and
                self.special == other.special)
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __str__(self):
        out = 'unknown'
        if self.valid:
            if self.battle:
                out += 'BATTLE, '
            if not self.arrange:
                out = 'REGULAR'
            else:
                out = self.arrange
            if self.flip:
                out += ',FLIP'
            if self.assist:
                out += f',{self.assist}'
        return out

class OneResult:
    """1曲分のリザルトを表すクラス。ファイルへの保存用。"""
    def __init__(self,
                    title:str,
                    play_style:play_style,
                    difficulty:difficulty,
                    lamp:clear_lamp,
                    timestamp:int,
                    playspeed:float | None,
                    option:PlayOption,
                    detect_mode:detect_mode,
                    is_arcade:bool=False,
                    judge:Judge=None,
                    score:int=None,
                    bp:int=None,
                    pre_score:int=0,
                    pre_lamp:clear_lamp=clear_lamp.noplay,
                    pre_bp:int=99999999,
                    notes:int=None,
                    dead:bool=None,
                    average_release:average_release=None,
                ):
        self.title = title
        '''曲名'''
        self.play_style = play_style
        '''SP/DP'''
        self.difficulty = difficulty
        '''譜面難易度'''
        self.chart_id  = calc_chart_id(title, play_style, difficulty)
        """楽曲ID。無効なIDも設定可能とする"""
        self.judge     = judge
        """判定内訳"""

        self.detect_mode = detect_mode
        '''登録時のモード。曲数・ノーツ数の計算はselectからのもののみ利用。'''

        self.score = score
        '''現在のスコア'''
        self.bp = bp
        '''現在のBP'''
        self.pre_score = pre_score
        '''現在のランプ'''
        self.pre_lamp = pre_lamp
        '''現在のスコア'''
        self.pre_bp = pre_bp
        '''現在のBP'''
        if judge: # 判定がある場合はこちら(打鍵カウンタv2のデータは上だけで受ける)
            self.score = judge.score
            self.bp    = judge.bp
        self.lamp      = lamp
        self.timestamp = timestamp
        self.option    = option
        self.playspeed = playspeed
        self.is_arcade = is_arcade
        self.notes     = notes
        '''ノーツ数。リザルト画面からの場合は埋め込む。'''
        self.dead      = dead
        self.average_release = average_release
        '''平均リリース時間のログ。Otoge Input Viewerと連携する時のために準備している。'''

    def is_updated(self) -> bool:
        """更新があるかどうかを返す

        Returns:
            bool: ランプ、スコア、BPのいずれかが更新されていればTrue
        """
        ret = False
        ret = True if self.pre_score and self.score > self.pre_score else ret
        ret = True if self.pre_lamp and self.lamp.value > self.pre_lamp.value else ret
        ret = True if self.bp and not self.pre_bp else ret
        ret = True if self.bp and self.pre_bp and self.bp < self.pre_bp else ret
        return ret
        
    def __eq__(self, other):
        if not isinstance(other, OneResult):
            return False
        # 同一リザルトとみなす条件を絞り込む (例: ID、ランプ、スコア、オプションが同じなら同一)
        return (self.chart_id == other.chart_id and
                self.lamp == other.lamp and
                self.timestamp == other.timestamp and
                self.playspeed == other.playspeed and
                self.option == other.option and
                self.is_arcade == other.is_arcade and
                self.judge == other.judge and
                self.score == other.score and
                self.bp == other.bp and
                self.dead == other.dead and
                # self.pre_score == other.pre_score and
                # self.pre_lamp == other.pre_lamp and
                # self.pre_bp == other.pre_bp and
                self.detect_mode == other.detect_mode
        )
    
    def __lt__(self, other):
        '''日付順にソートできるようにする'''
        return self.timestamp < other.timestamp

    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        # 後日全く同じ判定内訳のリザルトを出したときに困るので、やはりtimestampは必須かも
        return hash((self.chart_id, self.lamp.value, self.timestamp, self.playspeed, self.option, self.is_arcade, self.judge, self.score, self.bp, self.dead))

    def __str__(self):
        """主要情報の文字列を出力。ログ用"""
        if self.lamp and self.score:
            return f"detect_mode:{self.detect_mode.name}, song:{get_title_with_chart(self.title, self.play_style, self.difficulty)}, score:{self.score}, bp:{self.bp}, judge:{self.judge}, lamp:{self.lamp.name}, dead:{self.dead}, playspeed:{self.playspeed}, option:{self.option}, is_updated:{self.is_updated()}(pre score:{self.pre_score}, bp:{self.pre_bp}, lamp:{self.pre_lamp}), notes:{self.notes}, is_arcade:{self.is_arcade}, timestamp:{datetime.datetime.fromtimestamp(self.timestamp)}"
        else:
            return "not a result data!"

class DetailedResult():
    """1曲分のリザルトを表すクラス。スコアレート、BPIなどの詳細な情報を含む。ResultDatabase側からOneSongInfoを受け取る。"""
    def __init__(self,
                    songinfo:OneSongInfo,
                    result:OneResult,
                    result_side:result_side=None,
                    level:int=None,
                ):
        """コンストラクタ。ResultDatabase側でsonginfoとresultを与えて初期化する。"""
        self.result = result
        '''OneResultの部分'''
        self.songinfo = songinfo
        '''曲情報'''

        self.result_side = result_side
        '''1P/2Pどちら側であるか'''
        self.level = level
        '''inf-notebook側で認識したレベル'''

        self.score_rate = None
        """スコアレート(0.0-1.0; float)"""
        self.score_rate_with_rankdiff = None
        """ランク差分付きのスコアレート(F+0 - MAX+0; str)"""
        self.bpi = None
        """BPIの値"""
        self.update_details()
        self.bpi = self.get_bpi()

    def update_details(self):
        """詳細情報を算出"""
        if self.result.notes and self.result.score:
            self.score_rate = self.result.score / self.result.notes / 2
            self.score_rate_with_rankdiff = calc_rankdiff(notes=self.result.notes, score=self.result.score)

    def pgf(self, score_rate:float, notes:int):
        """BPI計算用。入力スコアレートに対して許容されるKG率を求める。

        Args:
            score_rate (float): 目標スコアレート
            notes (int): その曲のノーツ数。理論値が出ている曲の場合に必要。

        Returns:
            float: 何ノーツに1回黄グレを出してよいか
        """
        if score_rate == 1:
            return notes*2
        else:
            return 1 + (score_rate - 0.5) / (1 - score_rate)

    def get_bpi(self) -> float:
        """BPIを計算して返す。XMLにそのまま渡す都合上返り値は文字型なので注意。

        Args:
            key (str): 譜面名。title___SPAのような形式。
            best_score (int): 自己べのEXスコア

        Returns:
            str: フォーマット後BPIもしくは??(未定義の場合)
        """
        bpi = None
        try:
            if self.songinfo and self.result.score and self.songinfo.bpi_ave:
                notes = self.result.notes
                bpi_coef = self.songinfo.bpi_coef if self.songinfo.bpi_coef>0 else 1.175
                s = self.result.score
                m = notes*2
                z = self.songinfo.bpi_top
                k = self.songinfo.bpi_ave
                sl = self.pgf(s/m, notes)
                kl = self.pgf(k/m, notes)
                zl = self.pgf(z/m, notes)
                sd = sl/kl
                zd = zl/kl
                # logger.debug(f"s={s},m={m},z={z},k={k},sl={sl},kl={kl},zl={zl}")
                # logger.debug(f"sd={sd:.3f}; zd={zd:.3f}; bpi_coef={bpi_coef}")
                if s > k:
                    bpi = (100 * (math.log(sd)**bpi_coef)) / (math.log(zd)**bpi_coef)
                else:
                    bpi = max((-100 * ((-math.log(sd))**bpi_coef)) / (math.log(zd)**bpi_coef),-15.0)
        except:
            pass
            # logger.error(traceback.format_exc())
        return bpi

    def __str__(self):
        """主要情報の文字列を出力。ログ用(overrided)"""
        msg = f"=== DetailedResult === \nchart:{get_title_with_chart(self.result.title, self.result.play_style, self.result.difficulty)}\n"
        msg += f"info:{self.songinfo}\n"
        msg += f"result:{self.result}\n"
        if self.score_rate_with_rankdiff:
            if self.result.judge:
                msg += f"({''.join(self.score_rate_with_rankdiff)}, {self.result.judge.score_rate*100:.2f}%)"
            else:
                msg += f"({''.join(self.score_rate_with_rankdiff)})"
        msg += f", detect_mode:{self.result.detect_mode}, judge:[{self.result.judge}]"
        if self.bpi:
            msg += f", BPI: {self.bpi}, "
        if self.result_side:
            msg += f", side: {self.result_side.name[1:]}"
        msg += 'level:{self.level}'
        return msg
        
    def __eq__(self, other):
        if not isinstance(other, DetailedResult):
            return False
        return (self.result == other.result)

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
    def broadcast_graph_data(self, start_time: int):
        """グラフデータをWebSocketで配信"""
        if self.ws_server is None:
            return
        
        try:
            data = self.get_graph_data(start_time)
            self.ws_server.update_graph_data(data)
        except Exception as e:
            logger.error(f"グラフデータ配信エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def broadcast_today_updates_data(self, start_time: int):
        """本日の更新データをWebSocketで配信"""
        if self.ws_server is None:
            return
        
        try:
            data = self.get_today_updates_data(start_time)
            self.ws_server.update_today_updates_data(data)
        except Exception as e:
            logger.error(f"更新データ配信エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def broadcast_history_cursong_data(self, title: str, style, difficulty, 
                                       battle: bool = None, playspeed: float = None):
        """履歴データをWebSocketで配信"""
        if self.ws_server is None:
            return
        
        try:
            data = self.get_history_cursong_data(title, style, difficulty, battle, playspeed)
            self.ws_server.update_history_cursong_data(data)
        except Exception as e:
            logger.error(f"履歴データ配信エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
                result.pre_score,result.pre_bp,result.pre_lamp = self.get_best(title=result.title, style=result.play_style, difficulty=result.difficulty, battle=battle)
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
        except:
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
        battle=TrueかつDPの場合はDBx系のみ検索対象とする。optionが空でない場合は同一オプションのみ検索対象とする。

        Args:
            title (str, optional): _description_. Defaults to None.
            style (play_style, optional): _description_. Defaults to None.
            difficulty (difficulty, optional): _description_. Defaults to None.
            chart_id (str, optional): _description_. Defaults to None.
            battle (bool, optional): DBx系の判定に使う、Defaults to False.
            option (PlayOption, optional): 同一オプションのリザルトのみとしたい場合に指定、Defaults to False.

        Returns:
            List[int]: score, bp, lamp
        """
        ret = [0,99999999,clear_lamp(0)]
        key = chart_id
        if title is not None and style is not None and difficulty is not None:
            key = calc_chart_id(title, style, difficulty)
        results = self.search(chart_id=key)
        for r in results:
            if r.result.detect_mode == detect_mode.play: # 途中落ちの判定ができないため使わない
                continue
            if playspeed != r.result.playspeed: # 再生速度が異なる場合は落とす。選曲画面から呼ぶ場合は等速しか対象にしないので存在確認はしない。
                continue
            if style == play_style.dp:
                if battle: # 検索対象がDBxの場合
                    if r.result.option and not r.result.option.battle:
                        continue
                else: # 検索対象が非DBxの場合
                    if r.result.option and r.result.option.battle:
                        continue
            if option: # オプション指定がある場合は、arrangeが一致するもののみ通す
                if option.arrange is not r.option.arrange or option.flip is not r.option.flip or option.special is not r.option.special:
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
                'pre_score': r.pre_score,
                'pre_bp': r.pre_bp,
                'pre_lamp': r.pre_lamp.value,
                'opt': r.option.__str__() if r.option else "",
                'playspeed': r.playspeed if r.playspeed else 1.0,
                'score_rate': r.score / r.notes / 2 if r.notes else 0
            }
            
            if songinfo:
                item['dp_unofficial_lv'] = str(songinfo.dp_unofficial) if hasattr(songinfo, 'dp_unofficial') and songinfo.dp_unofficial else ""
                item['sp_12hard'] = songinfo.sp12_hard.__str__() if hasattr(songinfo, 'sp12_hard') and songinfo.sp12_hard else ""
                item['sp_12clear'] = songinfo.sp12_clear.__str__() if hasattr(songinfo, 'sp12_clear') and songinfo.sp12_clear else ""
                item['sp_11hard'] = songinfo.sp11_hard.__str__() if hasattr(songinfo, 'sp11_hard') and songinfo.sp11_hard else ""
                item['sp_11clear'] = songinfo.sp11_clear.__str__() if hasattr(songinfo, 'sp11_clear') and songinfo.sp11_clear else ""
            
            if detailed_result.bpi:
                item['bpi'] = f"{detailed_result.bpi:.2f}"
            
            if detailed_result.score_rate_with_rankdiff:
                item['rankdiff'] = ''.join(detailed_result.score_rate_with_rankdiff)
                item['rankdiff0'] = detailed_result.score_rate_with_rankdiff[0]
                item['rankdiff1'] = detailed_result.score_rate_with_rankdiff[1]
            
            items.append(item)
        
        return {'items': items}
    
    
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
        
        target = []
        for r in results:
            if r.result.option and r.result.option.special:
                continue
            if r.result.playspeed != playspeed:
                continue
            if r.result.detect_mode == detect_mode.play:
                continue
            if battle and style == play_style.dp and r.result.option.battle != battle:
                continue
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
            'best_score_opt': best_score_opt.__str__() if best_score_opt else ""
        }
        
        if songinfo and hasattr(songinfo, 'bpi_ave') and songinfo.bpi_ave:
            data['bpi_ave'] = f"{songinfo.bpi_ave}"
        if songinfo and hasattr(songinfo, 'bpi_top') and songinfo.bpi_top:
            data['bpi_top'] = f"{songinfo.bpi_top}"
        if songinfo and hasattr(songinfo, 'bpi_coef') and songinfo.bpi_coef:
            data['bpi_coef'] = f"{songinfo.bpi_coef}"
        
        if detail:
            detail.result.notes = notes
            detail.bpi = detail.get_bpi() # ノース数などが入っていない場合におかしくなるので、一応計算し直す
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
        
        if songinfo:
            data['dp_unofficial_lv'] = str(songinfo.dp_unofficial) if hasattr(songinfo, 'dp_unofficial') else ""
            data['sp_12hard'] = songinfo.sp12_hard.__str__() if hasattr(songinfo, 'sp12_hard') and songinfo.sp12_hard else ""
            data['sp_12clear'] = songinfo.sp12_clear.__str__() if hasattr(songinfo, 'sp12_clear') and songinfo.sp12_clear else ""
            data['sp_11hard'] = songinfo.sp11_hard.__str__() if hasattr(songinfo, 'sp11_hard') and songinfo.sp11_hard else ""
            data['sp_11clear'] = songinfo.sp11_clear.__str__() if hasattr(songinfo, 'sp11_clear') and songinfo.sp11_clear else ""
        
        items = []
        for r in reversed(target):
            item = {
                'date': str(datetime.datetime.fromtimestamp(r.result.timestamp).strftime('%Y/%m/%d')),
                'lamp': r.result.lamp.value,
                'score': r.result.score,
                'score_rate': r.result.score / r.result.notes / 2 if r.result.notes else 0,
                'bp': r.result.bp,
                'bprate': r.result.bp / r.result.notes if r.result.notes else 0,
                'pre_score': r.result.pre_score,
                'pre_lamp': r.result.pre_lamp.value,
                'pre_bp': r.result.pre_bp,
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

    def write_best_csv(self):
        header = ['LV', 'Title', 'mode', 'Lamp', 'Score', '(rate)', 'BP', 'Opt(best score)', 'Opt(min bp)', 'Last Played']
        os.makedirs('out', exist_ok=True)

        # 全曲の自己べを取得
        bests = self.get_all_best_results()

        with open(Path('.')/'inf_score.csv', 'w') as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)

            for key,value in zip(bests.keys(), bests.values()):
                row = []
                lv = ''
                title = escape_for_csv(key[0])
                mode = get_chart_name(key[1], key[2])
                if key[3]: # DBx
                    mode = 'DB' + mode[-1]
                lamp = value['best_lamp'].__str__()
                score = value['best_score']
                best_score_opt = value['best_score_option'].__str__()
                if best_score_opt in ('unknown', 'None') or not best_score_opt:
                    best_score_opt = '?'
                bp = value['min_bp']
                if bp == 99999999:
                    bp = ''
                min_bp_opt = value['min_bp_option'].__str__()
                if min_bp_opt in ('unknown', 'None') or not min_bp_opt:
                    min_bp_opt = '?'
                timestamp = datetime.datetime.fromtimestamp(value['last_play_timestamp'])
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