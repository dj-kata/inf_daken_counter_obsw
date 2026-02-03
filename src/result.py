# 単体検証: wuv run python -m src.result
from .classes import *
from .funcs import *
from .songinfo import *
from .logger import get_logger
logger = get_logger(__name__)
import datetime
import os
import bz2, pickle
import traceback
import logging
import logging, logging.handlers
import math
import sys
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
    '''A-SCR or LEGACY'''
    battle = None
    '''DP時にBATTLEがON 両サイドがSP譜面になる'''
    special = None
    '''H-RAN or BATTLE'''

    def __init__(self, option:ResultOptions=None):
        if option:
            self.valid = True
            self.arrange: str = option.arrange
            self.flip: str = option.flip
            self.assist: str = option.assist
            self.battle: bool = option.battle
            self.special: bool = (option.arrange is not None and 'H-RAN' in option.arrange) or self.battle

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
            if not self.arrange:
                out = 'REGULAR'
            else:
                out = self.arrange
            if self.flip:
                out += ',FLIP'
            if self.assist:
                out += f',{self.assist}'
            if self.battle:
                out += ',BATTLE'
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
                    is_arcade:bool=False,
                    judge:Judge=None,
                    score:int=None,
                    bp:int=None,
                    pre_score:int=0,
                    pre_lamp:clear_lamp=clear_lamp.noplay,
                    pre_bp:int=99999999,
                    dead:bool=None,
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
        self.dead      = dead

    def is_updated(self) -> bool:
        """更新があるかどうかを返す

        Returns:
            bool: ランプ、スコア、BPのいずれかが更新されていればTrue
        """
        ret = False
        ret = True if self.pre_score and self.score > self.pre_score else ret
        ret = True if self.pre_lamp and self.lamp.value > self.pre_lamp.value else ret
        ret = True if self.pre_bp and self.bp < self.pre_bp else ret
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
                self.dead == other.dead
        )
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        # 後日全く同じ判定内訳のリザルトを出したときに困るので、やはりtimestampは必須かも
        return hash((self.chart_id, self.lamp, self.timestamp, self.playspeed, self.option, self.is_arcade, self.judge, self.score, self.bp, self.dead))

    def __str__(self):
        """主要情報の文字列を出力。ログ用"""
        if self.lamp and self.score:
            return f"song:{get_title_with_chart(self.title, self.play_style, self.difficulty)}, score:{self.score}, bp:{self.bp}, judge:{self.judge}, lamp:{self.lamp.name}, dead:{self.dead}, playspeed:{self.playspeed}, option:{self.option}, is_arcade:{self.is_arcade}, timestamp:{datetime.datetime.fromtimestamp(self.timestamp)}"
        else:
            return "not a result data!"

class DetailedResult():
    """1曲分のリザルトを表すクラス。スコアレート、BPIなどの詳細な情報を含む。ResultDatabase側からOneSongInfoを受け取る。"""
    def __init__(self,
                    songinfo:OneSongInfo,
                    result:OneResult,
                    result_side:result_side=None,
                    notes:int=None,
                    level:int=None,
                ):
        """コンストラクタ。ResultDatabase側でsonginfoとresultを与えて初期化する。"""
        self.result = result
        '''OneResultの部分'''
        self.songinfo = songinfo
        '''曲情報'''

        self.result_side = result_side
        '''1P/2Pどちら側であるか'''
        self.notes = notes
        '''inf-notebook側で認識したノーツ数'''
        self.level = level
        '''inf-notebook側で認識したレベル'''

        self.score_rate = None
        """スコアレート(0.0-1.0; float)"""
        self.score_rate_with_rankdiff = None
        """ランク差分付きのスコアレート(F+0 - MAX+0; str)"""
        self.bpi = None
        """BPIの値"""
        self.update_details()

    def update_details(self):
        """詳細情報を算出"""
        if self.songinfo and self.songinfo.notes and self.score:
            self.score_rate = self.score / self.songinfo.notes / 2
            self.score_rate_with_rankdiff = calc_rankdiff(notes=self.songinfo.notes, score=self.score)
            self.bpi = self.get_bpi()

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

    def get_bpi(self) -> str:
        """BPIを計算して返す。XMLにそのまま渡す都合上返り値は文字型なので注意。

        Args:
            key (str): 譜面名。title___SPAのような形式。
            best_score (int): 自己べのEXスコア

        Returns:
            str: フォーマット後BPIもしくは??(未定義の場合)
        """
        bpi = '??'
        try:
            if self.songinfo and self.score:
                notes = self.songinfo.notes
                bpi_coef = self.songinfo.bpi_coef if self.songinfo.bpi_coef>0 else 1.175
                s = self.score
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
                    bpi = f"{(100 * (math.log(sd)**bpi_coef)) / (math.log(zd)**bpi_coef):.2f}"
                else:
                    bpi = f"{max((-100 * (-math.log(sd)**bpi_coef)) / (math.log(zd)**bpi_coef),-15):.2f}"
        except:
            logger.error(traceback.format_exc())
        return bpi
    def __str__(self):
        """主要情報の文字列を出力。ログ用(overrided)"""
        msg = f"chart:{get_title_with_chart(self.result.title, self.result.play_style, self.result.difficulty)}"
        msg += f", score: {self.result.score}"
        if self.notes:
            msg += f"/{2*self.notes}"
        if self.score_rate_with_rankdiff:
            msg += f"({''.join(self.score_rate_with_rankdiff)}, {self.result.score_rate*100:.2f}%)"
        msg += f", judge:[{self.result.judge}]"
        if self.bpi:
            msg += f", BPI: {self.bpi}, "
        if self.result_side:
            msg += f", side: {self.result_side.name[1:]}"
        msg += f", bp: {self.result.bp}, lamp: {self.result.lamp.name}, option: {self.result.option}, timestamp:{self.result.timestamp}\n"
        return msg
        
    def __eq__(self, other):
        if not isinstance(other, DetailedResult):
            return False
        return (self.result == other.result)
class ResultDatabase:
    """全リザルトを保存するためのクラス"""
    def __init__(self):
        self.song_database = SongDatabase()
        """曲情報クラスのインスタンス。検索用。"""
        self.results:List[OneResult] = []
        """全リザルトが格納されるリスト。OneResultが1エントリとなる。"""
        self.load()
        self.save()

    def add(self, result:OneResult) -> bool:
        """リザルト登録用関数。chart_id情報を何も渡さなくても受ける(途中落ちのノーツ数保存用)

        Args:
            result (OneResult): リザルト

        Return:
            bool(True:登録された / False:登録済み等の理由で却下された)
        """
        if result not in self.results:
            self.results.append(result)
            logger.info(f"result added! hash:{hash(result)}, len:{len(self.results)}, result:{result}")
            return True
        else:
            return False

    def __str__(self):
        out = ''
        for r in self.results:
            songinfo = self.song_database.search(r.chart_id)
            detail = DetailedResult(songinfo, r)
            out += str(detail)
        return out
    
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
        songinfo = self.song_database.search(key)

        for r in self.results:
            if r.chart_id == key:
                detail = DetailedResult(songinfo, r)
                ret.append(detail)
        return ret
    
    def get_best(self,
                title:str=None, style:play_style=None, difficulty:difficulty=None, chart_id:str=None,
                battle:bool=False,option:PlayOption=None
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
    
if __name__ == '__main__':
    db = ResultDatabase()
    a = OneSongInfo('THE BRAVE MUST DIE', play_style.sp, difficulty.another, 12, 2075)
    a.bpi_top = 4135
    a.bpi_ave = 3442
    a.bpi_coef = 0.746675
    db.song_database.songs.append(a)
    a = OneSongInfo('KAMAITACHI', play_style.sp, difficulty.leggendaria, 12, 2000)
    db.song_database.songs.append(a)
    j = Judge(pg=1561, gr=414, gd=94, bd=3, pr=9, cb=6)
    db.add(judge=j, lamp=clear_lamp.exh, option=PlayOption(arrange='RANDOM'), title='THE BRAVE MUST DIE', play_style=play_style.sp, difficulty=difficulty.another)
    j = Judge(pg=750, gr=320, gd=33, bd=11, pr=20, cb=45)
    db.add(judge=j, lamp=clear_lamp.failed, option='')
    b = db.search('THE BRAVE MUST DIE', play_style.sp, difficulty.another)
    print(b[0])