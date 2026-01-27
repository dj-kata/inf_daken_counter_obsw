import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

# sys.path.append('old')
sys.path.append('infnotebook')
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource
from define import Define as define

from src.result import *

class ScreenReader:
    """プレー画面を読むためのクラス"""
    def __init__(self):
        self.songinfo = SongDatabase()

    def read_result_screen(self, _file:str) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        screen = open_screenimage(_file)
        ret = None
        result = recog.get_result(screen)
        if result:
            title = result.informations.music
            style = convert_play_style(result.informations.play_mode)
            level = result.informations.level
            notes = result.informations.notes
            option = result.details.options
            playspeed = result.informations.playspeed
            score = result.details.score.current
            bp = result.details.miss_count.current
            diff = convert_difficulty(result.informations.difficulty)
            lamp = convert_lamp(result.details.clear_type.current)
            chart_id = calc_chart_id(title=title, play_style=style, difficulty=diff)
            songinfo = self.songinfo.search(chart_id)
            timestamp = int(datetime.datetime.now().timestamp())
            result = OneResult(chart_id=chart_id, lamp=lamp, timestamp=timestamp, playspeed=playspeed, option=option,
                               judge=None,score=score,bp=bp)
            ret = DetailedResult(songinfo=songinfo, result=result)
        return ret

    def read_music_select_screen(self, _file:str) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        screen = open_screenimage(_file)
        ret = None
        np_value = screen.np_value[define.musicselect_trimarea_np]
        title = recog.MusicSelect.get_musicname(np_value)
        if title:
            diff = convert_difficulty(recog.MusicSelect.get_difficulty(np_value))
            lamp = convert_lamp(recog.MusicSelect.get_cleartype(np_value))
            score = recog.MusicSelect.get_score(np_value)
            bp = recog.MusicSelect.get_misscount(np_value)
            style = convert_play_style(recog.MusicSelect.get_playmode(np_value))
            chart_id = calc_chart_id(title=title, play_style=style, difficulty=diff)
            songinfo = self.songinfo.search(chart_id)
            timestamp = int(datetime.datetime.now().timestamp())
            result = OneResult(chart_id=chart_id, lamp=lamp, timestamp=timestamp, playspeed=None, option=PlayOption(None),
                               judge=None,score=score,bp=bp)
            ret = DetailedResult(songinfo=songinfo, result=result)
        return ret
        