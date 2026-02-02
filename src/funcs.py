from .classes import *
import hashlib
import math
import sys
import re
from PIL import Image
import numpy as np
import imagehash

sys.path.append('infnotebook')
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource
from define import Define as define
from src.logger import get_logger
logger = get_logger(__name__)

# 各クラスから使う共通の関数をここで定義しておく

def calc_chart_id(title:str, play_style:play_style, difficulty:difficulty):
    """楽曲IDを計算する。曲名、スタイル、難易度をキーとしたsha256とする。"""
    key = title + play_style.name + difficulty.name
    hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return hash

def get_chart_name(play_style:play_style, difficulty:difficulty):
    """SPA,DPLのような難易度部分のみの文字列を出力"""
    if play_style and difficulty:
        return f"{play_style.name.upper()}{difficulty.name.upper()[0]}"
    else:
        return ''
    
def get_title_with_chart(title:str, play_style:play_style, difficulty:difficulty) -> str:
    """AA (SPA)のような表示用のタイトル文字列を出力

    Args:
        title (str): 曲名
        play_style (play_style): SP/DP
        difficulty (difficulty): 譜面難易度

    Returns:
        str: snow storm (SPL)のような文字列
    """
    if title and play_style and difficulty:
        return f"{title} ({get_chart_name(play_style, difficulty)})"
    else:
        return title
    
def escape_for_filename(input):
    '''Windowsのファイル名に使えない文字列を消す'''
    invalid_chars = r'[\\/:*?"<>|]'
    safe_name = re.sub(invalid_chars, '', input)
    return safe_name
    
def escape_for_xml(input):
    '''XMLに使えない文字列を変換'''
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

def convert_play_style(_style) -> play_style|None:
    if _style == 'SP':
        return play_style.sp
    elif _style == 'DP':
        return play_style.dp
    else:
        return None

def convert_difficulty(_difficulty) -> difficulty|None:
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

def convert_lamp(_lamp) -> clear_lamp|None:
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
    else:
        lamp = None
    return lamp

def convert_side(side:str) -> result_side:
    ret = None
    if side == "1P":
        ret = result_side._1p
    elif side == "2P":
        ret = result_side._2p
    return ret

def cut_rival_area(img:Image, side:result_side) -> Image:
    '''ライバルエリアをカットする'''
    w=560 # ライバルエリアの幅
    if side == result_side._1p:
        return img.crop((0,0, 1920-w,1080))
    else:
        return img.crop((w,0, 1920,1080))
    
def mosaic_rival_area(img:Image, side:result_side) -> Image:
    '''ライバルエリアをぼかす'''
    img_array = np.array(img)
    if side == result_side._1p: # ライバルエリアが右側
        sx=1375
    else:
        sx=35
    sy=270
    ex=sx+456
    ey=sy+618
    rivalarea = img.crop((sx,sy,ex,ey))
    rivalarea = rivalarea.resize((45,61))
    rivalarea = rivalarea.resize((456,618))
    rival_array = np.array(rivalarea)
    img_array[sy:ey, sx:ex] = rival_array
    return Image.fromarray(img_array)

def mosaic_other_rival_names(img:Image, side:result_side) -> Image:
    '''挑戦状及びターゲットスコアにおけるライバル名を隠す'''
    img_array = np.array(img)
    if side == result_side._1p: # ライバルエリアが右側
        det_rival_sx = 42
        rival_name_sx = 226
    else:
        det_rival_sx = 1392
        rival_name_sx = 1576
    # # 挑戦状エリアの処理
    # ### TODO 挑戦状日時の部分をひろうと、撃破とかのエフェクトが重なるのでライバル名のところに変更
    hash_target = imagehash.hex_to_hash('00007f7f7f7f1400')
    hash = imagehash.average_hash(img.crop((827,854,926,876)))
    if abs(hash - hash_target) < 5:
        mailarea = img.crop((875,777,987,799))
        mailarea = mailarea.resize((11,2))
        mailarea = mailarea.resize((112,22))
        mail_array = np.array(mailarea)
        img_array[777:799, 875:987] = mail_array
    ## ターゲット名も隠す(ライバルの名前が入っている可能性があるため)
    hash_target = imagehash.hex_to_hash('00ffff000000ffff')
    hash = imagehash.average_hash(img.crop((det_rival_sx,690,det_rival_sx+15,699)))
    if abs(hash - hash_target) < 5: # ターゲットがライバル
        targetarea = img.crop((rival_name_sx,690,rival_name_sx+82,707))
        targetarea = targetarea.resize((8,2))
        targetarea = targetarea.resize((82,20))
        img_array[687:707, rival_name_sx:rival_name_sx+82] = targetarea
    return Image.fromarray(img_array)