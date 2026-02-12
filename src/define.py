"""座標など固定のデータをここに記載
"""
from src.classes import *

judge_digits = [20910,8415,19635,18615,17085,20655,23205,13515,24225,23205]
hash_digits = [
    'a800800080002000', # 0
    '9966666666666666', # 1
    'fc01d75481017faf', # 2
    'a100d500d4002d00', # 3
    'a9fe2f80d03f29d0', # 4
    'fdfa82abd50028f8', # 5
    'f45480aa85ab7faa', # 6
    'a9d4d48181557d7d', # 7
    'a800800080002800', # 8
    'a1fed501d4bd2dc0', # 9
]

class PosIsPlay:
    _COORDS = {
        play_mode.sp_1p_l:       (596,  943),
        play_mode.sp_1p_r:       (1013, 943),
        play_mode.sp_1p_nograph: (642,  943),
        play_mode.sp_2p_l:       (834,  943),
        play_mode.sp_2p_r:       (1251, 943),
        play_mode.sp_2p_nograph: (1206, 943),
        play_mode.dp_l:          (244,  872),
        play_mode.dp_r:          (1607, 872),
    }

    @classmethod
    def get(cls, mode: play_mode):
        '''モードに対するJUDGEの文字の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        x, y = cls._COORDS[mode]
        return (x, y, x + 74, y + 16)

class PosPlayJudge:
    '''プレー画面における詳細判定部分の座標を返すクラス。'''
    _COORDS = {
        play_mode.sp_1p_l:       (632,  969),
        play_mode.sp_1p_r:       (1049, 969),
        play_mode.sp_1p_nograph: (678,  969),
        play_mode.sp_2p_l:       (852,  969),
        play_mode.sp_2p_r:       (1269, 969),
        play_mode.sp_2p_nograph: (1223, 969),
        play_mode.dp_l:          (262,  898),
        play_mode.dp_r:          (1643, 898),
    }

    @classmethod
    def get(cls, mode: play_mode):
        '''モードに対する判定部分の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        x, y = cls._COORDS[mode]
        return (x, y, x + 53, y + 91)

class PosResultJudge:
    '''Result画面における詳細判定部分の座標を返すクラス。'''
    items = ['pg', 'gr', 'gd', 'bd', 'pr', 'cb']
    @classmethod
    def get(cls, mode: result_side, item: str, idx: int):
        '''モードに対する判定部分の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        item_idx = cls.items.index(item)
        if mode == result_side._1p:
            if item_idx <= 4:
                x = 392 + 28*idx
                y = 788 + 28*item_idx
            else: # combo break
                x = 423 + 28*idx
                y = 981
        elif mode == result_side._2p:
            if item_idx <= 4:
                x = 1741 + 28*idx
                y = 788 + 28*item_idx
            else: # combo break
                x = 1773 + 28*idx
                y = 981
        return (x, y, x+23, y+15)
