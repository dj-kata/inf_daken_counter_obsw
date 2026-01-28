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
    @classmethod
    def get(self, mode:play_mode):
        '''モードに対するJUDGEの文字の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        if mode == play_mode.sp_1p_l:
            x = 596
            y = 943
        elif mode == play_mode.sp_1p_r:
            x = 1013
            y = 943
        elif mode == play_mode.sp_1p_nograph:
            x = 642
            y = 943
        elif mode == play_mode.sp_2p_l:
            x = 834
            y = 943
        elif mode == play_mode.sp_2p_r:
            x = 1251
            y = 943
        elif mode == play_mode.sp_2p_nograph:
            x = 1206
            y = 943
        elif mode == play_mode.dp_l:
            x = 244
            y = 872
        elif mode == play_mode.dp_r:
            x = 1607
            y = 872
        return (x, y, x+74, y+16)

class PosPlayJudge:
    '''プレー画面における詳細判定部分の座標を返すクラス。'''
    @classmethod
    def get(self, mode:play_mode):
        '''モードに対する判定部分の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        x = 0
        y = 0
        if mode == play_mode.sp_1p_l:
            x = 632
            y = 969
        elif mode == play_mode.sp_1p_r:
            x = 1049
            y = 969
        elif mode == play_mode.sp_1p_nograph:
            x = 678
            y = 969
        elif mode == play_mode.sp_2p_l:
            x = 852
            y = 969
        elif mode == play_mode.sp_2p_r:
            x = 1269
            y = 969
        elif mode == play_mode.sp_2p_nograph:
            x = 1223
            y = 969
        elif mode == play_mode.dp_l:
            x = 262
            y = 898
        elif mode == play_mode.dp_r:
            x = 1643
            y = 898
        return (x, y, x+53, y+91)

class PosResultJudge:
    '''Result画面における詳細判定部分の座標を返すクラス。'''
    items = ['pg', 'gr', 'gd', 'bd', 'pr', 'cb']
    @classmethod
    def get(self, mode:result_side, item:str, idx:int):
        '''モードに対する判定部分の位置を返す。img.crop()でそのまま使えるようにtupleで返す。'''
        item_idx = self.items.index(item)
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
    