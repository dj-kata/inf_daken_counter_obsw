"""座標など固定のデータをここに記載
"""
from src.classes import *

judge_digits = [20910,8415,19635,18615,17085,20655,23205,13515,24225,23205]

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

class PosJudge:
    '''詳細判定部分の座標を返すクラス。'''
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