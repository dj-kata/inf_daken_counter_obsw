from enum import Enum
from src.logger import logger
from typing import List

class clear_lamp(Enum):
    """クリアランプを表すための列挙型クラス"""
    noplay = 0
    """未プレイ"""
    failed = 1
    """未クリア"""
    assist = 2
    """アシストクリア。60%のゲージや皿オートなどを使う場合はすべてこちらになる。"""
    easy   = 3
    """イージークリア"""
    clear  = 4
    """ノマゲ"""
    hard   = 5
    """ハード"""
    exh     = 6
    """エクハ"""
    fc     = 7
    """フルコンボ"""

class play_style(Enum):
    """SP/DPのどれであるかを表す列挙型クラス。DBxはここでは考慮しない。"""
    sp  = 0
    """シングルプレイ"""
    dp  = 1
    """ダブルプレイ"""

class result_side(Enum):
    '''1P/2Pのどちらであるかを表す列挙型クラス。リザルト画面で使う。'''
    _1p = 0
    '''1p側'''
    _2p = 1
    '''2p側'''

class difficulty(Enum):
    """難易度を表すクラス"""
    beginner    = 0
    """ビギナー譜面。SPのみ。"""
    normal      = 1
    """ノーマル譜面"""
    hyper       = 2
    """ハイパー譜面"""
    another     = 3
    """アナザー譜面"""
    leggendaria = 4
    """はか譜面"""

class Judge:
    """判定内訳を格納するクラス"""
    def __init__(self, pg:int, gr:int, gd:int, bd:int, pr:int, cb:int):
        self.pg = pg
        """ピカグレ"""
        self.gr = gr
        """黄グレ"""
        self.gd = gd
        """Good"""
        self.bd = bd
        """Bad"""
        self.pr = pr
        """Poor(見逃し+空)"""
        self.cb = cb
        """ComboBreak"""
        self.kpr = pr-cb
        """空プア。自動計算される。"""

        self.score = pg*2 + gr
        self.bp = bd+pr

        if self.cb < self.bd:
            logger.info(f"cb < badなので補正します。(リザルト画面での認識ミス?)")
            self.cb = self.bp

    @classmethod
    def from_list(cls, data: List[str]):
        """
        read_play_screenの出力をそのまま受けるためのファクトリメソッド
        Judge.from_list(data) で呼び出せる
        """
        tmp = list(map(int, data))
        # *tmp でリストを展開してメインのコンストラクタに渡す
        return cls(*tmp)

    def get_score_rate(self) -> float:
        """現在の判定内訳に対するスコアレートを計算"""
        notes = self.pg+self.gr+self.gd+self.bd+self.pr-self.cb
        if notes == 0:
            return 0.0
        else:
            max_score = notes*2
            cur_score = self.pg*2+self.gr
            return cur_score / max_score
        
    def sum(self) -> int:
        '''CB以外の判定値の合計を返す。CB補正用'''
        return self.pg + self.gr + self.gd + self.bd + self.pr

    def __str__(self):
        return f"PG:{self.pg}, GR:{self.gr}, GD:{self.gd}, BD:{self.bd}, PR:{self.pr}, CB:{self.cb},  score:{self.score}, bp:{self.bp},  rate:{self.get_score_rate()}"

class detect_mode(Enum):
    """検出モード用のEnum"""
    init = 0
    '''初期状態'''
    play = 1
    '''プレー画面'''
    select = 2
    '''選曲画面'''
    result = 3
    '''リザルト画面'''

class play_mode(Enum):
    """プレー画面のモード用Enum"""
    sp_1p_l = 0
    '''1P側、グラフが左'''
    sp_1p_r = 1
    '''1P側、グラフが右'''
    sp_1p_nograph = 2
    '''1P側、グラフなし'''
    sp_2p_l = 3
    '''2P側、グラフが左'''
    sp_2p_r = 4
    '''2P側、グラフが右'''
    sp_2p_nograph = 5
    '''2P側、グラフなし'''
    dp_l = 6
    '''DP、グラフが左'''
    dp_r = 7
    '''DP、グラフが右'''