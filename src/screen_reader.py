import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

import cv2

sys.path.append('infnotebook')
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource
from define import Define as define

from src.classes import *
from src.result import *
from src.define import *
from src.logger import logger

class ScreenReader:
    """ゲーム画面を読むためのクラス。ループの先頭でupdate_screenを叩いてから使うこと。"""
    def __init__(self):
        self.songinfo = SongDatabase()
        self.screen = None
        self.last_title_result = None
        self.last_title_select = None

    def update_screen_from_file(self, _file:str):
        self.screen = open_screenimage(_file)

    def update_screen(self, screen):
        self.screen = screen

    def read_judge_from_result(self, side:result_side) -> Judge:
        """リザルト画面から判定部分を読み取る"""
        img = self.screen.original
        out = []
        # for item in ['pg', 'gr', 'gd', 'bd', 'pr', 'cb']:
        for item in ['pg', 'gr', 'gd', 'bd', 'pr']:
            line = ''
            for idx in range(4):
                digit = img.crop(PosResultJudge.get(side, item, idx))

                fn = lambda x: 255 if x > 220 else 0
                digit_mono = digit.convert('L').point(fn, mode='1')
                # digit.save(f"hoge_{['pg', 'gr', 'gd', 'bd', 'pr', 'cb'].index(item)}{item}_{idx}.png")
                hash = imagehash.phash(digit_mono)
                # print(item, idx, hash)
                for i,h in enumerate(hash_digits):
                    hash_target = imagehash.hex_to_hash(h)
                    if abs(hash - hash_target) < 10:
                        if i in (0,8): # 0:198, 
                            d_sum = np.sum(np.array(digit_mono))
                            if d_sum > 215:
                                line += '8'
                            else:
                                line += str(i)
                        else:
                            line += str(i)
                        break
            out.append(line)
        out.append('0')
        ret = Judge.from_list(out)
        return ret

    def read_result_screen(self) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        try:
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
                judge = self.read_judge_from_result(convert_side(result.play_side))

                judge_sum = judge.sum()
                if judge_sum >= notes: # 完走した場合はCBを正確に計算
                    cb = bp - (judge_sum - notes)
                    judge.cb = cb
                else: # 途中落ちの場合残りノーツを見逃しとして足しておく
                    judge.pr += (notes - judge_sum)

                result = OneResult(chart_id=chart_id, lamp=lamp, timestamp=timestamp, playspeed=playspeed, option=option,
                                   judge=judge,score=score,bp=bp, dead=result.dead)
                ret = DetailedResult(songinfo=songinfo, result=result)
                self.last_title_result = title
        except:
            return None
        return ret

    def read_music_select_screen(self) -> DetailedResult:
        """pngファイルを入力してDetailedResultを返す"""
        ret = None
        np_value = self.screen.np_value[define.musicselect_trimarea_np]
        title = recog.MusicSelect.get_musicname(np_value)
        if title:
            self.last_title_select = title
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
        
    def read_play_screen(self, mode:play_mode):
        """プレー画面から判定を取得"""
        try:
            judge = self.detect_judge(mode)
            return Judge.from_list(judge)
        except:
            print(traceback.format_exc())
            return None

    ### 判定部分の切り出し
    def get_judge_img(self, playside:play_mode):
        img = self.screen.original
        # 判定内訳部分のみを切り取る
        sc = img.crop(PosPlayJudge.get(playside))
        d = []
        for j in range(6): # pg～prの5つ
            tmp_sec = []
            for i in range(4): # 4文字
                W = 11
                H = 11
                DSEPA = 3
                HSEPA = 5
                sx = i*(W+DSEPA)
                ex = sx+W
                sy = j*(H+HSEPA)
                ey = sy+H
                tmp = np.array(sc.crop((sx,sy,ex,ey)))
                tmp_sec.append(tmp)
            d.append(tmp_sec)
        return np.array(sc), d

    ### プレー画面から判定内訳を取得
    def detect_judge(self, playside):
        sc,digits = self.get_judge_img(playside)
        ret = []
        for jj in digits: # 各判定、ピカグレー>POORの順
            line = ''
            for d in jj:
                dd = d[:,:,2]
                dd = (dd>100)*255
                val = dd.sum()
                tmp = '?'
                if val == 0:
                    tmp  = '' # 従来スペースを入れていたが、消しても動く?
                elif val in judge_digits:
                    if val == judge_digits[6]: # 6,9がひっくり返しただけで合計値が同じなのでケア
                        if dd[8,0] == 0:
                            tmp = '9'
                        else:
                            tmp = '6'
                    else:
                        tmp = str(judge_digits.index(val))
                line += tmp 
            ret.append(line)
        return ret

    def detect_playside(self) -> play_mode:
        '''プレイサイド検出を行う'''
        ret = None
        for mode in play_mode:
            det = self.detect_judge(mode)
            if det[0] == '0':
                ret = mode
        return ret

    def is_select(self) -> bool:
        """選曲画面かどうかを判定し、判定結果(True/False)を返す
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

    def is_result(self) -> bool:
        """リザルト画面かどうかを判定し、判定結果を返す
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
    
    def is_play(self) -> play_mode | None:
        """プレー画面かどうかを判定し、判定結果を返す

        Returns:
            play_mode | None: 判定結果。どのモードかも返すようにする。
        """
        ret = None
        img = self.screen.original

        hash_target = imagehash.hex_to_hash('105f487f5effb700')
        for mode in play_mode:
            tmp = imagehash.average_hash(img.crop(PosIsPlay.get(mode)))
            judge = (hash_target - tmp) < 10
            # x = img.crop(PosIsPlay.get(mode)).save(f'hoge{mode.value}.png')
            if judge:
                return mode
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
