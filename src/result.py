# リザルト関連のデータモデル: PlayOption, OneResult, DetailedResult
from .classes import *
from .funcs import *
from .songinfo import *
import datetime
import math
import sys

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
            # special は @property で自動計算されるため、ここでの代入は不要
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

    def __str__(self):
        out = '?'
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

    @property
    def chart_id(self) -> str:
        """楽曲ID（自動計算）"""
        return calc_chart_id(self.title, self.play_style, self.difficulty)

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
        self.update_details()

    @property
    def bpi(self) -> float:
        """BPI(自動計算)"""
        return self.get_bpi()

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
        except Exception:
            pass
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
