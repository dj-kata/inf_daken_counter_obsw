from .classes import *
import hashlib
import math
import sys

sys.path.append('infnotebook')
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource
from define import Define as define

# 各クラスから使う共通の関数をここで定義しておく

def calc_chart_id(title:str, play_style:play_style, difficulty:difficulty):
    """楽曲IDを計算する。曲名、スタイル、難易度をキーとしたsha256とする。"""
    key = title + play_style.name + difficulty.name
    hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return hash
    
def escape_for_xml(self, input):
    return input.replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')

def calc_rankdiff(notes, score):
    """ノーツ数をスコアを受け取り、AAA+30みたいな表記をタプルで返す"""
    target,diff = ('', '') # AAA, -50 みたいな結果を返す
    smax = notes*2
    if score == smax:
        target,diff = ('MAX', '+0')
    elif score >= math.ceil(17*smax/18):
        target,diff = ('MAX', f"{score-smax:+}")
    elif score >= math.ceil(15*smax/18):
        aaa = math.ceil(smax*16/18)
        target,diff = ('AAA', f'{score - aaa:+}')
    elif score >= math.ceil(13*smax/18):
        aa = math.ceil(smax*14/18)
        target,diff = ('AA', f'{score - aa:+}')
    elif score >= math.ceil(11*smax/18):
        a = math.ceil(smax*12/18)
        target,diff = ('A', f'{score - a:+}')
    elif score >= math.ceil(9*smax/18):
        tmp = math.ceil(smax*10/18)
        target,diff = ('B', f'{score - tmp:+}')
    elif score >= math.ceil(7*smax/18):
        tmp = math.ceil(smax*8/18)
        target,diff = ('C', f'{score - tmp:+}')
    elif score >= math.ceil(5*smax/18):
        tmp = math.ceil(smax*6/18)
        target,diff = ('D', f'{score - tmp:+}')
    elif score >= math.ceil(3*smax/18):
        tmp = math.ceil(smax*4/18)
        target,diff = ('E', f'{score - tmp:+}')
    else:
        target,diff = ('F', f'{score:+}')
    if diff == '-0':
        diff = '+0'

    return target,diff

def convert_play_style(_style):
    if _style == 'SP':
        return play_style.sp
    elif _style == 'DP':
        return play_style.dp

def convert_difficulty(_difficulty):
    diff = None
    if _difficulty == 'BEGINNER':
        diff = difficulty.beginner
    elif _difficulty == 'NORMAL':
        diff = difficulty.normal
    elif _difficulty == 'HYPER':
        diff = difficulty.hyper
    elif _difficulty == 'ANOTHER':
        diff = difficulty.another
    elif _difficulty == 'LEGGENDARIA':
        diff = difficulty.leggendaria
    return diff

def convert_lamp(_lamp):
    lamp = None
    if _lamp == 'NOPLAY':
        lamp = clear_lamp.noplay
    elif _lamp == 'FAILED':
        lamp = clear_lamp.failed
    elif _lamp == 'A-CLEAR':
        lamp = clear_lamp.assist
    elif _lamp == 'E-CLEAR':
        lamp = clear_lamp.easy
    elif _lamp == 'CLEAR':
        lamp = clear_lamp.clear
    elif _lamp == 'H-CLEAR':
        lamp = clear_lamp.hard
    elif _lamp == 'EXH-CLEAR':
        lamp = clear_lamp.exh
    elif _lamp == 'F-COMBO':
        lamp = clear_lamp.fc
    return lamp