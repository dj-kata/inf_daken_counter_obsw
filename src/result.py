# 単体検証: wuv run python -m src.result
from .classes import *
from .funcs import *
from .songinfo import *
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

os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

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

    def __init__(self, option=None):
        if option:
            self.valid = True
            self.arrange: str = option.arrange
            self.flip: str = option.flip
            self.assist: str = option.assist
            self.battle: bool = option.battle
            self.special: bool = (option.arrange is not None and 'H-RAN' in option.arrange) or self.battle
    def __init__(self, arrange:str=None, flip:str=None, assist:str=None, battle:bool=None):
        self.valid = True
        self.arrange = arrange
        self.flip = flip
        self.assist = assist
        self.battle = battle
        self.special = (arrange is not None and 'H-RAN' in arrange) or self.battle

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
                    chart_id:str,
                    lamp:clear_lamp,
                    timestamp:int,
                    playspeed:float | None,
                    option:PlayOption,
                    is_arcade:bool=False,
                    judge:Judge=None,
                    score:int=None,
                    bp:int=None,
                    dead:bool=None,
                ):
        self.chart_id  = chart_id
        """楽曲ID。無効なIDも設定可能とする(選曲画面から登録した場合)。"""
        self.judge     = judge
        if judge:
            self.score = judge.score
            self.bp    = judge.bp
        else: # 判定内訳がない場合も受ける(打鍵カウンタv2のデータなど)
            self.score = score
            self.bp    = bp
        self.lamp      = lamp
        self.timestamp = timestamp
        self.option    = option
        self.playspeed = playspeed
        self.is_arcade = is_arcade
        self.dead      = dead
        
    def disp_all(self):
        """全attrsを表示"""
        print(self.__dict__)

    def __str__(self):
        """主要情報の文字列を出力。ログ用"""
        if self.lamp and self.score:
            return f"chart_id:{self.chart_id}, score:{self.score}, bp:{self.bp}, lamp:{self.lamp.name}, dead:{self.dead}, playspeed:{self.playspeed}, option:{self.option}, is_arcade:{self.is_arcade}, timestamp:{self.timestamp}"
        else:
            return "not a result data!"

class DetailedResult(OneResult):
    """1曲分のリザルトを表すクラス。スコアレート、BPIなどの詳細な情報を含む。ResultDatabase側からOneSongInfoを受け取る。"""
    def __init__(self,
                    songinfo:OneSongInfo,
                    result:OneResult,
                ):
        """コンストラクタ。ResultDatabase側でsonginfoとresultを与えて初期化する。"""
        self.songinfo = songinfo
        super().__init__(chart_id=result.chart_id,
                         judge=result.judge,
                         lamp=result.lamp,
                         timestamp=result.timestamp,
                         playspeed=result.playspeed,
                         option=result.option,
                         is_arcade=result.is_arcade,
                         score=result.score,
                         bp=result.bp,
                         dead=result.dead,
                        )

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
        if self.songinfo is None:
            return super().__str__()
        else:
            msg = f"chart:{self.songinfo.title}({self.songinfo.play_style.name.upper()}{self.songinfo.difficulty.name[0].upper()}), "
            msg += f""
            msg += f"score: {self.score}({''.join(self.score_rate_with_rankdiff)}, {self.score_rate*100:.2f}%), "
            if self.bpi:
                msg += f"BPI: {self.bpi}, "
            msg += f"bp: {self.bp}, lamp: {self.lamp.name}, option: {self.option}, timestamp:{self.timestamp}\n"
            return msg

class ResultDatabase:
    """全リザルトを保存するためのクラス"""
    def __init__(self):
        self.song_database = SongDatabase()
        """曲情報クラスのインスタンス。検索用。"""
        self.results:List[OneResult] = []
        """全リザルトが格納されるリスト。OneResultが1エントリとなる。"""
        self.load()
        self.save()

    def add(self, judge:Judge, lamp:clear_lamp, option:PlayOption,
            title:str=None, play_style:play_style=None, difficulty:difficulty=None, _chart_id:str=None,
            playspeed=None
        ):
        """リザルト登録用関数。chart_id情報を何も渡さなくても受ける(途中落ちのノーツ数保存用)

        Args:
            judge (Judge): 判定内訳
            lamp (clear_lamp): クリアランプ
            option (PlayOption): プレーオプション
            title (str, optional): 曲名. Defaults to None.
            play_style (play_style, optional): SP/DP. Defaults to None.
            difficulty (difficulty, optional): 譜面難易度. Defaults to None.
            _chart_id (str, optional): 譜面ID. Defaults to None.
            playspeed (_type_, optional): プレー速度. Defaults to None.
        """
        timestamp = int(datetime.datetime.now().timestamp())
        if _chart_id:
            chart_id = _chart_id
        elif title is not None and play_style is not None and difficulty is not None:
            chart_id = calc_chart_id(title, play_style, difficulty)
        else: # chart_id不明(途中落ちなどの判定内訳も拾っておく)
            chart_id = None
        result = OneResult(chart_id=chart_id, judge=judge, lamp=lamp, timestamp=timestamp, option=option, playspeed=playspeed)
        logger.info(f"result added! ({result})")
        self.results.append(result)

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
                title:str=None, play_style:play_style=None, difficulty:difficulty=None, chart_id:str=None,
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
        if chart_id:
            key = chart_id
        elif title is not None and play_style is not None and difficulty is not None:
            key = calc_chart_id(title, play_style, difficulty)
        songinfo = self.song_database.search(key)

        for r in self.results:
            if r.chart_id == key:
                detail = DetailedResult(songinfo, r)
                ret.append(detail)
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