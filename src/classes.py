from enum import Enum

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

    def __str__(self):
        return f"PG:{self.pg}, GR:{self.gr}, GD:{self.gd}, BD:{self.bd}, PR:{self.pr}, CB:{self.cb},  score:{self.score}, bp:{self.bp}"
