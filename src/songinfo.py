from classes import *
from funcs import *
import os
import bz2, pickle
import traceback
import logging
import logging, logging.handlers

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

class OneSongInfo:
    """1譜面分の曲情報を表すクラス"""
    def __init__(self,
                    title:str,
                    play_style:play_style,
                    difficulty:difficulty,
                    level:int,
                    notes:int,
                    version:int=None,
                    min_bpm:int=None,
                    max_bpm:int=None,
                    rader_notes:float=None,
                    rader_peak:float=None,
                    rader_scratch:float=None,
                    rader_soflan:float=None,
                    rader_charge:float=None,
                    rader_chord:float=None,
                    sp12_hard:str=None,
                    sp12_clear:str=None,
                    sp11_hard:str=None,
                    sp11_clear:str=None,
                    cpi_easy:float=None,
                    cpi_clear:float=None,
                    cpi_hard:float=None,
                    cpi_exh:float=None,
                    cpi_fc:float=None,
                    katate_12:int=None,
                    katate_11:int=None,
                    bpi_ave:int=None,
                    bpi_top:int=None,
                    bpi_coef:float=None,
                    dp_unofficial:str=None,
                    dp_ereter_easy:str=None,
                    dp_ereter_hard:str=None,
                    dp_ereter_exh:str=None,
                ):
        self.title          = title
        """曲名。inf-notebookから貰うものをここにつける"""
        self.play_style     = play_style
        """SP/DP"""
        self.difficulty     = difficulty
        """難易度"""
        self.level          = level
        """譜面のLevel(1-12)"""
        self.notes          = notes
        """ノーツ数"""
        self.version        = version
        """収録バージョン。INF初出はなるべくINFとしたい。(inf=99999999にする)"""
        self.min_bpm        = min_bpm
        self.max_bpm        = max_bpm
        # ノーツレーダー
        self.rader_notes    = rader_notes
        self.rader_peak     = rader_peak
        self.rader_scratch  = rader_scratch
        self.rader_soflan   = rader_soflan
        self.rader_charge   = rader_charge
        self.rader_chord    = rader_chord
        # 非公式の難易度
        self.sp12_hard      = sp12_hard
        self.sp12_clear     = sp12_clear
        self.sp11_hard      = sp11_hard
        self.sp11_clear     = sp11_clear
        self.cpi_easy       = cpi_easy
        self.cpi_clear      = cpi_clear
        self.cpi_hard       = cpi_hard
        self.cpi_exh        = cpi_exh
        self.cpi_fc         = cpi_fc
        self.katate_12      = katate_12
        self.katate_11      = katate_11
        self.bpi_ave        = bpi_ave
        """BPI計算用 皆伝平均"""
        self.bpi_top        = bpi_top
        """BPI計算用 歴代全1"""
        self.bpi_coef       = bpi_coef
        """BPI計算用 補正係数"""
        self.dp_unofficial  = dp_unofficial
        """DP非公式難易度"""
        self.dp_ereter_easy = dp_ereter_easy
        self.dp_ereter_hard = dp_ereter_hard
        self.dp_ereter_exh  = dp_ereter_exh
        # その他
        self.chart_id       = calc_chart_id(title, play_style, difficulty)
        """譜面毎に割り当てるID"""

    def disp(self):
        """内部情報を表示"""
        print(self.__dict__)

class SongDatabase:
    """全曲の情報を保持するクラス。検索もできる。"""
    def __init__(self):
        self.songs = []
        """曲情報(OneSongInfo)を格納するリスト"""
        self.load()
        self.save()

    def get(self, chart_id:str) -> OneSongInfo:
        """指定されたchart_idに対応する曲情報を返す。見つからない場合はNoneを返す。"""
        ret = None
        for s in self.songs:
            if chart_id == s.chart_id:
                ret = s
                break
        return ret

    def load(self):
        """pklファイルから曲情報を読み出す"""
        try:
            with bz2.BZ2File('songinfo.infdc', 'rb', compresslevel=9) as f:
                self.songs = pickle.load(f)
        except:
            logger.error(traceback.format_exc())

    def save(self):
        """曲情報をpklへ書き出す"""
        with bz2.BZ2File('songinfo.infdc', 'wb', compresslevel=9) as f:
            pickle.dump(self.songs, f)


if __name__ == '__main__':
    a = OneSongInfo('AA', play_style.sp, difficulty.another, 12, 1834)
    a.disp()
    a = OneSongInfo('AA -rebuild-', play_style.sp, difficulty.another, 12, 1834)
    a.disp()