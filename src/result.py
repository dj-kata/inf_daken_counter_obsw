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
    battle = False
    '''DP時にBATTLEがON 両サイドがSP譜面になる'''
    allscratch = False
    '''ALL-SCRATCHがON'''
    regularspeed = False
    '''REGUL-SPEEDがON'''

    def __init__(self, result_options:ResultOptions=None):
        if result_options is not None:
            self.valid = True
            self.arrange = result_options.arrange
            self.flip = result_options.flip
            self.assist = result_options.assist
            self.battle = result_options.battle
            self.allscratch = result_options.allscratch
            self.regularspeed = result_options.regularspeed

    @property
    def special(self):
        '''保存対象外(特殊配置、allscratch, regularspeed, バトル)'''
        if self.arrange and any(keyword in self.arrange for keyword in ['H-RAN', 'SYMM-RAN', 'SYNC-RAN']):
            return True
        if self.allscratch or self.regularspeed or self.battle:
            return True
        return False

    def __hash__(self):
        return hash((self.arrange, self.flip, self.assist, self.battle, self.allscratch, self.regularspeed))

    def __eq__(self, other):
        if not isinstance(other, PlayOption):
            return False
        return (self.arrange == other.arrange and
                self.flip == other.flip and
                self.assist == other.assist and
                self.battle == other.battle and
                self.allscratch == other.allscratch and
                self.regularspeed == other.regularspeed)

    def convert_from_v2(self, opt_str:str):
        '''v2以前の文字列形式のオプションから復元する。特殊な名前の付いたものを優先的に判定する。'''
        if not opt_str:
            return
        
        if 'BATTLE' in opt_str:
            self.battle = True
        if 'ALL-SCR' in opt_str:
            self.allscratch = True
        if 'REGUL-SPEED' in opt_str:
            self.regularspeed = True
        
        # 記録対象外の判定（v2文字列から復元する場合もプロパティ経由で判定される）
        
        # 残りのオプションをarrange, flip, assistに割り当てる
        temp_opt = opt_str
        if self.battle:
            temp_opt = temp_opt.replace('BATTLE, ', '')
        if self.allscratch:
            temp_opt = temp_opt.replace(', ALL-SCR', '')
        if self.regularspeed:
            temp_opt = temp_opt.replace(', REGUL-SPEED', '')

        if 'FLIP' in temp_opt:
            self.flip = 'FLIP'
            temp_opt = temp_opt.replace(', FLIP', '')
        if 'A-SCR' in temp_opt:
            self.assist = 'A-SCR'
            temp_opt = temp_opt.replace(', A-SCR', '')
        elif 'LEGACY' in temp_opt:
            self.assist = 'LEGACY'
            temp_opt = temp_opt.replace(', LEGACY', '')
        
        # 残りがarrange
        if temp_opt == 'REGULAR':
            self.arrange = None
        elif temp_opt == '?':
            # 不明なオプションはそのままにするか、Noneにするか
            self.arrange = None # 不明な場合は正規として扱う
        else:
            # v2の表記揺れを修正
            if '/' not in temp_opt: # SP
                if temp_opt == 'R-RAN':
                    temp_opt = 'R-RANDOM'
                if temp_opt == 'S-RAN':
                    temp_opt = 'S-RANDOM'
                if temp_opt == 'RAN':
                    temp_opt = 'RANDOM'
                if temp_opt == 'MIR':
                    temp_opt = 'MIRROR'
            self.arrange = temp_opt

    def __str__(self):
        out = '?'
        if self.valid:
            out = ''
            if self.battle:
                out = 'BATTLE, '
            if self.allscratch:
                out += 'ALL-SCR, '
            else:
                if not self.arrange:
                    out += 'REGULAR, '
                else:
                    out += self.arrange + ', '
            if self.regularspeed:
                out += 'REGUL-SPEED, '
            if self.flip:
                out += ', FLIP'
            if self.assist:
                out += f', {self.assist}'
        out = out.replace(', , ', ', ')
        if out[-2:] == ', ':
            out = out[:-2]
        return out
    
class CurrentOption(PlayOption):
    '''オプション画面で選択中のオプション。play_styleやゲージなども覚えておく。'''
    def __init__(self):
        super().__init__()
        self.play_style:play_style = None
        '''SP / DP'''
        self.option_gauge:option_gauge = None
        '''ゲージの種類'''
        self.option_assist:option_assist = None
        '''アシストオプション'''

    def __str__(self):
        if self.option_assist.value > 0:
            out_dict = {
                option_assist.a_scr: 'A-SCR',
                option_assist.legacy: 'LEGACY',
                option_assist.key_assist: 'KEY ASSIST',
                option_assist.any_key: 'ANY KEY',
            }
            self.assist = out_dict[self.option_assist]
        
        base = super().__str__()
        parts = [base]
        # if self.option_gauge:
        #     parts.append(str(self.option_gauge))
        
        return ', '.join(parts)

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
            bool: ランプ、スコア、BPのいずれかが更新されていればTrue。
                  自己ベストが存在しない(初プレー)場合もTrue。
        """
        if self.pre_score is None:
            return True
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
            return f"detect_mode:{self.detect_mode.name}, song:{get_title_with_chart(self.title, self.play_style, self.difficulty)}, score:{self.score}, lamp:{self.lamp.name}, bp:{self.bp}, judge:{self.judge}, dead:{self.dead}, playspeed:{self.playspeed}, option:{self.option}, is_updated:{self.is_updated()}(pre score:{self.pre_score}, bp:{self.pre_bp}, lamp:{self.pre_lamp}), notes:{self.notes}, is_arcade:{self.is_arcade}, timestamp:{datetime.datetime.fromtimestamp(self.timestamp)}"
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
                notes = self.result.notes or self.songinfo.notes
                if not notes:
                    return None
                bpi_coef = self.songinfo.bpi_coef if (self.songinfo.bpi_coef and self.songinfo.bpi_coef > 0) else 1.175
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
        msg += f"result:{self.result}\n"
        msg += f"info:{self.songinfo}\n"
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

class OneBestData:
    """1譜面の自己ベスト情報"""
    def __init__(self):
        self.title: str = ""
        self.style: play_style = play_style.sp
        self.difficulty: difficulty = difficulty.hyper
        self.songinfo = None  # SongInfoオブジェクト
        self.best_score_result: OneResult = None  # ベストスコア時のOneResult
        self.min_bp_result: OneResult = None  # 最小BP時のOneResult
        self.best_lamp_result: OneResult = None  # 最良ランプのOneResult
        self.last_result: OneResult = None  # 最終プレー
    
    @property
    def chart(self) -> str:
        """譜面名 (SPA, SPH, DPA, etc.)"""
        return get_chart_name(self.style, self.difficulty)
    
    @property
    def level(self) -> str:
        """レベル"""
        if self.songinfo and hasattr(self.songinfo, 'level'):
            return str(self.songinfo.level)
        return ""
    
    @property
    def dp_unofficial(self) -> str:
        """非公式難易度"""
        if self.songinfo and hasattr(self.songinfo, 'dp_unofficial'):
            return str(self.songinfo.dp_unofficial)
        return ""
    
    @property
    def lamp(self) -> clear_lamp:
        """最良ランプ"""
        if self.best_lamp_result:
            return self.best_lamp_result.lamp
        return clear_lamp.noplay
    
    @property
    def best_score(self) -> int:
        """ベストスコア"""
        if self.best_score_result:
            return self.best_score_result.score if self.best_score_result.score else 0
        return 0
    
    @property
    def score_rate(self) -> float:
        """スコアレート"""
        if self.best_score_result and self.best_score_result.notes:
            return self.best_score / (self.best_score_result.notes * 2)
        return 0.0
    
    @property
    def min_bp(self) -> int:
        """最小BP"""
        if self.min_bp_result:
            return self.min_bp_result.bp if self.min_bp_result.bp is not None else 99999
        return 99999
    
    @property
    def best_score_option(self) -> str:
        """ベストスコア時のオプション"""
        if self.best_score_result and self.best_score_result.option:
            return str(self.best_score_result.option)
        return ""
    
    @property
    def min_bp_option(self) -> str:
        """最小BP時のオプション"""
        if self.min_bp_result and self.min_bp_result.option:
            return str(self.min_bp_result.option)
        return ""
    
    @property
    def last_play_date(self) -> str:
        """最終プレー日"""
        if self.last_result:
            return datetime.datetime.fromtimestamp(self.last_result.timestamp).strftime('%Y-%m-%d %H:%M')
        return ""
    
    @property
    def notes(self) -> int:
        """ノーツ数"""
        # ベストスコア時のノーツ数を優先
        if self.best_score_result and self.best_score_result.notes:
            return self.best_score_result.notes
        if self.min_bp_result and self.min_bp_result.notes:
            return self.min_bp_result.notes
        if self.best_lamp_result and self.best_lamp_result.notes:
            return self.best_lamp_result.notes
        return 0
    
    @property
    def is_battle(self):
        """battleオプションありかどうか"""
        if self.best_score_result and self.best_score_result.option:
            return self.best_score_result.option.battle
        return None