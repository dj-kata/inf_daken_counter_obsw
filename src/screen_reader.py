import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

sys.path.append('infnotebook')
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource
from define import Define as define

from src.classes import *
from src.result import *

class ScreenReader:
    """ゲーム画面を読むためのクラス。ループの先頭でupdate_screenを叩いてから使うこと。"""
    def __init__(self):
        self.songinfo = SongDatabase()
        self.screen = None

    def update_screen_from_file(self, _file:str):
        self.screen = open_screenimage(_file)

    def update_screen(self, screen):
        self.screen = screen

    def read_result_screen(self) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        ret = None
        result = recog.get_result(self.screen)
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

    def read_music_select_screen(self) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        ret = None
        np_value = self.screen.np_value[define.musicselect_trimarea_np]
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
        
    def is_select(self) -> bool:
        """選曲画面かどうかを判定し、判定結果(True/False)を返す

        Args:
            img (PIL.Image): ゲーム画面

        Returns:
            bool: 選曲画面であればTrue
        """
        ret = False
        img = self.screen.original

        hash_target = imagehash.hex_to_hash('007e7e5e5a7e7c00')
        img_1p = img.crop((466,1000,466+27,1000+27))
        h_1p = imagehash.average_hash(img_1p)
        img_2p = img.crop((1422,1000,1422+27,1000+27))
        h_2p = imagehash.average_hash(img_2p)
        ret = ((hash_target - h_1p) < 10) or ((hash_target - h_2p) < 10)
        # キーボードプレイの場合
        hash_target = imagehash.hex_to_hash('003c3c3c3c3c3c00')
        img_1p = img.crop((60,980,60+34,980+47))
        h_1p = imagehash.average_hash(img_1p)
        img_2p = img.crop((1860,980,1860+34,980+47))
        h_2p = imagehash.average_hash(img_2p)
        ret |= ((hash_target - h_1p) < 10) or ((hash_target - h_2p) < 10)
        #logger.debug(f"ret = {ret}")

        return ret

    def is_result(self):
        """リザルト画面かどうかを判定し、判定結果を返す

        Args:
            img (PIL.Image): キャプチャ画像

        Returns:
            bool: Trueならimgがリザルト画面である
        """
        ret = False
        img = self.screen.original

        hash_target = imagehash.hex_to_hash('e0e0fc063c62e2c3')
        tmpl = imagehash.average_hash(img.crop((20,28,60,58)))
        tmpr = imagehash.average_hash(img.crop((1860,28,1900,58)))
        ret = ((hash_target - tmpl) < 10) or ((hash_target - tmpr) < 10)
        #logger.debug(f"ret = {ret}")

        return ret

    def is_endselect(self):
        """選曲画面の終了時かどうかを判定"""
        img = self.screen.original
        tmp = imagehash.average_hash(img.crop((0,0,1920,380)))
        hash_target = imagehash.hex_to_hash('000018082c3fbffe')
        ret = (hash_target - tmp) < 10
        return ret

    def is_endresult(self):
        """リザルト画面の終了時かどうかを判定"""
        img = self.screen.original
        tmp = imagehash.average_hash(img)
        hash_target = imagehash.hex_to_hash('f86060d8f8783cfc')
        ret = (hash_target - tmp) < 10
        #logger.debug(f"ret = {ret}")
        return ret
