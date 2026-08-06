# リザルト関連のデータモデル: PlayOption, OneResult, DetailedResult
from .classes import *
from .funcs import *
from .songinfo import *
from .logger import get_logger
import datetime
from dataclasses import dataclass
import json
import math
import sys
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = get_logger(__name__)

sys.path.append('infnotebook')
from result import ResultOptions
try:
    from bpim2 import bpim2_getchartbpi, bpim2_savecache
except Exception:
    bpim2_getchartbpi = None
    bpim2_savecache = None

BPIM2_API_URL = 'https://bpi2.poyashi.me/api/v1/bpi/calc'
BPIM2_TIMEOUT_SEC = 2.0
BPIM2_NEGATIVE_CACHE_TTL_SEC = 600.0
_BPIM2_POSITIVE_CACHE = {}
_BPIM2_NEGATIVE_CACHE = {}


@dataclass
class BpiArenaAverage:
    rank: str
    avg_ex_score: int


@dataclass
class BpiDetail:
    value: Optional[float] = None
    source: str = 'local'
    arena_averages: Optional[list[BpiArenaAverage]] = None

    @property
    def label(self) -> str:
        return 'BPIM2' if self.source == 'bpim2' else 'BPI'

    @property
    def arena_average_text(self) -> Optional[str]:
        if not self.arena_averages:
            return None
        return ' / '.join(f"{avg.rank} avg {avg.avg_ex_score}" for avg in self.arena_averages)


def _difficulty_to_bpim2_name(diff:difficulty) -> Optional[str]:
    names = {
        difficulty.hyper: 'HYPER',
        difficulty.another: 'ANOTHER',
        difficulty.leggendaria: 'LEGGENDARIA',
    }
    return names.get(diff)


def _nearest_arena_averages(arena_averages:dict, score:int) -> list[BpiArenaAverage]:
    averages = []
    for rank, data in arena_averages.items():
        avg_ex_score = data.get('avgExScore') if isinstance(data, dict) else None
        if avg_ex_score is None:
            continue
        avg_ex_score = _to_int_or_none(avg_ex_score)
        if not avg_ex_score:
            continue
        averages.append(BpiArenaAverage(rank=rank, avg_ex_score=math.floor(avg_ex_score)))
    rank_order = {'A1': 1, 'A2': 2, 'A3': 3, 'A4': 4, 'A5': 5}
    averages.sort(key=lambda avg: rank_order.get(avg.rank, 99))
    if len(averages) <= 2:
        return averages

    if score >= averages[0].avg_ex_score:
        return averages[:2]
    if score <= averages[-1].avg_ex_score:
        return [averages[-1], averages[-2]]

    for high, low in zip(averages, averages[1:]):
        if high.avg_ex_score >= score >= low.avg_ex_score:
            return [high, low]

    averages.sort(key=lambda avg: abs(avg.avg_ex_score - score))
    return averages[:2]


def _extract_arena_averages(data: dict, score:int) -> list[BpiArenaAverage]:
    """BPIM2 APIレスポンスから近いランク平均を取り出す。"""
    metadata = data.get('metadata') or {}
    candidates = [
        metadata.get('arenaAverages'),
        metadata.get('rankAverages'),
        data.get('arenaAverages'),
        data.get('rankAverages'),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            averages = _nearest_arena_averages(candidate, score)
            if averages:
                return averages
    return []


def _fetch_bpim2_bpi(title:str, diff_name:str, score:int) -> Optional[BpiDetail]:
    now = datetime.datetime.now().timestamp()
    cache_key = (title, diff_name, score)
    cached_result = _BPIM2_POSITIVE_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    cached_until = _BPIM2_NEGATIVE_CACHE.get(cache_key)
    can_try_direct_api = not (cached_until and cached_until > now)
    if cached_until and can_try_direct_api:
        _BPIM2_NEGATIVE_CACHE.pop(cache_key, None)

    if can_try_direct_api:
        params = urlencode({
            'title': title,
            'difficulty': diff_name,
            'exScore': score,
        })
        req = Request(f'{BPIM2_API_URL}?{params}', headers={'User-Agent': 'inf-daken-counter-obsw/0.1'})
        try:
            with urlopen(req, timeout=BPIM2_TIMEOUT_SEC) as res:
                body = res.read().decode('utf-8')
            data = json.loads(body)
        except Exception:
            _BPIM2_NEGATIVE_CACHE[cache_key] = now + BPIM2_NEGATIVE_CACHE_TTL_SEC
        else:
            bpi = data.get('bpi')
            if bpi is not None:
                arena_averages = _extract_arena_averages(data, score)
                result = BpiDetail(value=float(bpi), source='bpim2', arena_averages=arena_averages)
                _BPIM2_POSITIVE_CACHE[cache_key] = result
                return result
            _BPIM2_NEGATIVE_CACHE[cache_key] = now + BPIM2_NEGATIVE_CACHE_TTL_SEC

    if bpim2_getchartbpi is not None:
        bpi = bpim2_getchartbpi(title, diff_name, score)
        if bpi is not None:
            result = BpiDetail(value=float(bpi), source='bpim2')
            _BPIM2_POSITIVE_CACHE[cache_key] = result
            return result

    return None


def _to_int_or_none(value) -> Optional[int]:
    """文字列/数値のどちらで来てもintへ寄せる。変換不能ならNone。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
                    bpim2:float=None,
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
        self.bpim2 = bpim2
        '''BPIM2 APIから取得したBPI値。未取得または未対応の場合はNone。'''

    def is_updated(self) -> bool:
        """更新があるかどうかを返す

        Returns:
            bool: ランプ、スコア、BPのいずれかが更新されていればTrue。
                  自己ベストが存在しない(初プレー)場合もTrue。
        """
        if self.pre_score is None:
            return True
        ret = False
        if type(self.score) is not int or type(self.bp) is not int or type(self.lamp) is not clear_lamp:
            return False
        ret = True if self.score is not None and self.pre_score is not None and self.score > self.pre_score else ret
        ret = True if self.lamp is not None and self.pre_lamp is not None and self.lamp.value > self.pre_lamp.value else ret
        ret = True if self.bp is not None and self.pre_bp is None else ret
        ret = True if self.bp is not None and self.pre_bp is not None and self.bp < self.pre_bp else ret
        return ret

    @property
    def chart_id(self) -> str:
        """楽曲ID（自動計算）"""
        battle = self.option.battle if self.option else False
        return calc_chart_id(self.title, self.play_style, self.difficulty, battle=battle)

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
        self._bpi_detail = None
        self.update_details()

    @property
    def bpi(self) -> float:
        """BPI(自動計算)"""
        return self.get_bpi()

    @property
    def bpi_detail(self) -> BpiDetail:
        """BPI値と取得元、BPIM2補足情報を返す。"""
        return self.get_bpi_detail()

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
        return self.get_local_bpi()

    def get_local_bpi(self) -> Optional[float]:
        """外部APIを使わず、従来のローカル定義だけでBPIを計算する。"""
        return self._get_local_bpi()

    def get_bpi_detail(self) -> BpiDetail:
        if self._bpi_detail is not None:
            return self._bpi_detail

        saved_bpim2 = getattr(self.result, 'bpim2', None)
        if saved_bpim2 is not None:
            self._bpi_detail = BpiDetail(value=saved_bpim2, source='bpim2')
            return self._bpi_detail

        bpim2 = self._get_bpim2_bpi_detail()
        if bpim2 and bpim2.value is not None:
            self.result.bpim2 = bpim2.value
            self._bpi_detail = bpim2
            return self._bpi_detail

        self._bpi_detail = BpiDetail(value=self._get_local_bpi(), source='local')
        return self._bpi_detail

    def get_bpim2_bpi_detail(self, force_fetch: bool=False) -> Optional[BpiDetail]:
        """BPIM2のBPI詳細を返す。force_fetch=Trueなら保存済み値があっても現在曲1件だけ再取得する。"""
        saved_bpim2 = getattr(self.result, 'bpim2', None)
        if saved_bpim2 is not None and not force_fetch:
            return BpiDetail(value=saved_bpim2, source='bpim2')

        bpim2 = self._get_bpim2_bpi_detail()
        if bpim2 and bpim2.value is not None:
            self.result.bpim2 = bpim2.value
            return bpim2
        if saved_bpim2 is not None:
            return BpiDetail(value=saved_bpim2, source='bpim2')
        return None

    def _get_bpim2_bpi_detail(self) -> Optional[BpiDetail]:
        try:
            if not (self.result and self.result.score is not None):
                return None
            if self.result.play_style != play_style.sp:
                return None
            songinfo_level = _to_int_or_none(getattr(self.songinfo, 'level', None))
            detail_level = _to_int_or_none(self.level)
            level = songinfo_level or detail_level
            if level is None or level < 11:
                return None
            diff_name = _difficulty_to_bpim2_name(self.result.difficulty)
            if not diff_name:
                return None
            score = int(self.result.score)
            if score < 0:
                return None
            songinfo_notes = _to_int_or_none(getattr(self.songinfo, 'notes', None))
            result_notes = _to_int_or_none(self.result.notes)
            notes = result_notes or songinfo_notes
            if notes and score > notes * 2:
                return None
            title = (getattr(self.songinfo, 'bpim2_title', None)
                     or getattr(self.songinfo, 'title', None)
                     or self.result.title)
            if not title:
                return None
            return _fetch_bpim2_bpi(title, diff_name, score)
        except Exception as e:
            logger.debug(f"BPIM2 BPI取得エラー ({self.result.title}): {e}")
            return None

    def _get_local_bpi(self) -> Optional[float]:
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
        bpi = self.get_local_bpi()
        if bpi is not None:
            msg += f", BPI: {bpi}, "
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
        return get_chart_name(self.style, self.difficulty, battle=self.is_battle)
    
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
        for result in (self.best_score_result, self.min_bp_result, self.best_lamp_result, self.last_result):
            if result and result.option:
                return result.option.battle
        return False
