from datetime import datetime
import os
from logging import getLogger
from PIL import Image
import re

logger_child_name = 'result'

logger = getLogger().getChild(logger_child_name)
logger.debug('loaded result.py')

from gui.general import get_imagevalue

results_basepath = 'results'
filtereds_basepath = 'filtered'

adjust_length = 94

class ResultInformations():
    def __init__(self, play_mode, difficulty, level, notes, music):
        self.play_mode = play_mode
        self.difficulty = difficulty
        self.level = level
        self.notes = notes
        self.music = music

class ResultValues():
    def __init__(self, best, current, new):
        self.best = best
        self.current = current
        self.new = new

class ResultDetails():
    def __init__(self, graphtype, options, clear_type, dj_level, score, miss_count, graphtarget):
        self.graphtype = graphtype
        self.options = options
        self.clear_type = clear_type
        self.dj_level = dj_level
        self.score = score
        self.miss_count = miss_count
        self.graphtarget = graphtarget

class ResultOptions():
    def __init__(self, arrange, flip, assist, battle):
        self.arrange = arrange
        self.flip = flip
        self.assist = assist
        self.battle = battle
        self.special = (arrange is not None and 'H-RAN' in arrange) or self.battle

class Result():
    def __init__(self, informations, play_side, rival, dead, details):
        self.informations = informations
        self.play_side = play_side
        self.rival = rival
        self.dead = dead
        self.details = details

        now = datetime.now()
        self.timestamp = f"{now.strftime('%Y%m%d-%H%M%S')}"
    
    def has_new_record(self):
        return any([
            self.details.clear_type.new,
            self.details.dj_level.new,
            self.details.score.new,
            self.details.miss_count.new
        ])

def result_save(image, music, timestamp, musicname_right=False):
    """リザルト画像をファイル保存する

    Args:
        image (Image): 対象の画像(PIL.Image)
        music (str): 曲名
        timestamp (str): リザルトを記録したときのタイムスタンプ
        musicname_right (bool, optional): 曲名をファイル名の後尾にする. Defaults to False.

    Returns:
        str: 成功した場合はファイル名を返す
    """
    if not os.path.exists(results_basepath):
        os.mkdir(results_basepath)

    filename = generate_resultfilename(music, timestamp, musicname_right)
    filepath = os.path.join(results_basepath, filename)
    if os.path.exists(filepath):
        return None
    
    image.save(filepath)

    return filename

def result_savefiltered(image, music, timestamp, musicname_right=False):
    """ライバル欄にぼかしを入れたリザルト画像をファイル保存する

    Args:
        image (Image): 対象の画像(PIL.Image)
        music (str): 曲名
        timestamp (str): リザルトを記録したときのタイムスタンプ
        musicname_right (bool, optional): 曲名をファイル名の後尾にする. Defaults to False.

    Returns:
        str: 成功した場合はファイル名を返す
    """
    if not os.path.exists(filtereds_basepath):
        os.mkdir(filtereds_basepath)

    filename = generate_resultfilename(music, timestamp, musicname_right)
    filepath = os.path.join(filtereds_basepath, filename)
    if os.path.exists(filepath):
        return None
    
    image.save(filepath)

    return filename

def generate_resultfilename(music, timestamp, musicname_right=False):
    """保存ファイル名を作る

    Args:
        music (str): 曲名
        timestamp (str): リザルトを記録したときのタイムスタンプ
        musicname_right (bool, optional): 曲名をファイル名の後尾にする. Defaults to False.

    Returns:
        str: ファイル名
    """
    if music is None:
        return f"{timestamp}.jpg"

    music_convert=re.sub(r'[\\|/|:|*|?|.|"|<|>|/|]', '', music)
    adjustmented = music_convert if len(music_convert) < adjust_length else f'{music_convert[:adjust_length]}..'
    if not musicname_right:
        return f"{adjustmented}_{timestamp}.jpg"
    else:
        return f"{timestamp}_{adjustmented}.jpg"

def get_resultimage(music, timestamp):
    """リザルト画像をファイルから取得する

    最も古い形式はタイムスタンプのみのファイル名。
    曲名がファイル名の左側にあるときも右側にあるときもある。
    全パターンでファイルの有無を確認する。

    Args:
        music (str): 曲名
        timestamp (str): リザルトを記録したときのタイムスタンプ

    Returns:
        bytes: PySimpleGUIに渡すデータ
    """
    filename = generate_resultfilename(music, timestamp)
    filepath = os.path.join(results_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    filename = generate_resultfilename(music, timestamp, True)
    filepath = os.path.join(results_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    filename = generate_resultfilename(None, timestamp)
    filepath = os.path.join(results_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    return None

def get_filteredimage(music, timestamp):
    """ぼかしの入ったリザルト画像をファイルから取得する

    最も古い形式はタイムスタンプのみのファイル名。
    曲名がファイル名の左側にあるときも右側にあるときもある。
    全パターンでファイルの有無を確認する。

    Args:
        music (str): 曲名
        timestamp (str): リザルトを記録したときのタイムスタンプ

    Returns:
        bytes: PySimpleGUIに渡すデータ
    """
    filename = generate_resultfilename(music, timestamp)
    filepath = os.path.join(filtereds_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    filename = generate_resultfilename(music, timestamp, True)
    filepath = os.path.join(filtereds_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    filename = generate_resultfilename(None, timestamp)
    filepath = os.path.join(filtereds_basepath, filename)
    if os.path.isfile(filepath):
        return Image.open(filepath)
    
    return None
