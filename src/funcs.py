from .classes import *
import hashlib
import math
import os
import sys
import re
from PIL import Image
import numpy as np
import imagehash
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.append('infnotebook')
from src.logger import get_logger
logger = get_logger(__name__)

# 各クラスから使う共通の関数をここで定義しておく

# UIの型チェック用
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.ui_jp import UIText

def load_ui_text(config):
    """
    設定に応じて適切な言語ファイルをロード
    
    Args:
        config: Configオブジェクト
    
    Returns:
        UITextクラス
    """
    if config.language == 'en':
        from src.ui_en import UIText
    else:
        from src.ui_jp import UIText
    
    return UIText

def calc_chart_id(title:str, play_style:play_style, difficulty:difficulty):
    """楽曲IDを計算する。曲名、スタイル、難易度をキーとしたsha256とする。"""
    hash = None
    if title and play_style and difficulty:
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

def escape_for_csv(input):
    '''CSVに使えない文字列を変換'''
    out = input
    if 'LOVE2 シュガ' in input:
        out = 'LOVE2 シュガ→'
    return out

_RANK_THRESHOLDS = [
    # (threshold_numerator, rank_name, target_numerator)
    (17, 'MAX', None),  # target_numerator=None means use smax directly
    (15, 'AAA', 16),
    (13, 'AA',  14),
    (11, 'A',   12),
    (9,  'B',   10),
    (7,  'C',   8),
    (5,  'D',   6),
    (3,  'E',   4),
]

def calc_rankdiff(notes, score):
    """ノーツ数をスコアを受け取り、AAA+30みたいな表記をタプルで返す"""
    smax = notes * 2
    if score == smax:
        return ('MAX', '+0')

    for threshold_num, rank_name, target_num in _RANK_THRESHOLDS:
        if score >= math.ceil(threshold_num * smax / 18):
            target_score = smax if target_num is None else math.ceil(target_num * smax / 18)
            diff = f'{score - target_score:+}'
            if diff == '-0':
                diff = '+0'
            return (rank_name, diff)

    return ('F', f'{score:+}')

_PLAY_STYLE_MAP = {
    'SP': play_style.sp,
    'DP': play_style.dp,
}

def convert_play_style(_style) -> play_style | None:
    return _PLAY_STYLE_MAP.get(_style)

_DIFFICULTY_MAP = {
    'BEGINNER': difficulty.beginner, 'B': difficulty.beginner,
    'NORMAL': difficulty.normal,     'N': difficulty.normal,
    'HYPER': difficulty.hyper,       'H': difficulty.hyper,
    'ANOTHER': difficulty.another,   'A': difficulty.another,
    'LEGGENDARIA': difficulty.leggendaria, 'L': difficulty.leggendaria,
}

def convert_difficulty(_difficulty) -> difficulty | None:
    '''難易度の文字列をEnumに変換'''
    return _DIFFICULTY_MAP.get(_difficulty)

_LAMP_MAP = {
    'NOPLAY': clear_lamp.noplay,
    'FAILED': clear_lamp.failed,
    'A-CLEAR': clear_lamp.assist,
    'E-CLEAR': clear_lamp.easy,
    'CLEAR': clear_lamp.clear,
    'H-CLEAR': clear_lamp.hard,
    'EXH-CLEAR': clear_lamp.exh,
    'F-COMBO': clear_lamp.fc,
}

def convert_lamp(_lamp) -> clear_lamp | None:
    '''ランプ用文字列をEnumに変換'''
    return _LAMP_MAP.get(_lamp, clear_lamp.noplay)

_SIDE_MAP = {
    '1P': result_side._1p,
    '2P': result_side._2p,
}

def convert_side(side: str) -> result_side:
    return _SIDE_MAP.get(side)

def cut_rival_area(img:Image, side:result_side) -> Image:
    '''ライバルエリアをカットする'''
    w=1360 # 出力サイズ
    if side == result_side._1p:
        return img.crop((0,0, w,1080))
    else:
        return img.crop((1920-w,0, 1920,1080))
    
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

def add_new_element(root, name, value):
    elem = ET.SubElement(root, name)
    if value:
        elem.text = value
