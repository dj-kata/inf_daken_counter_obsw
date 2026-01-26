from classes import *
import hashlib
import math

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
