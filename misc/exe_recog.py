import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

from src.screen_reader import ScreenReader
from src.logger import get_logger
from src.result import *
from src.classes import *
from src.config import Config
from src.funcs import *
logger = get_logger('exe_recog')

def gen_ocr_result(info, playdata):
    out = []
    out.append(info.level)
    out.append(info.music)
    if info.difficulty != None:
        out.append(info.play_mode+info.difficulty[0])
    else:
        out.append(None)
    out.append(info.notes)
    out.append(playdata.dj_level.best)
    out.append(playdata.dj_level.current)
    out.append(playdata.clear_type.best)
    out.append(playdata.clear_type.current)
    out.append(playdata.score.best)
    out.append(playdata.score.current)
    out.append(playdata.miss_count.best)
    out.append(playdata.miss_count.current)
    with open('./tmp.pkl', 'wb') as f:
        pickle.dump(out, f)

if __name__ == '__main__':
    logger.info('start')
    rdb = ResultDatabase()
    reader = ScreenReader()
    for f in glob.glob('debug/0126/*.png'):
        reader.update_screen_from_file(f)
        logger.info(f'file={f}')
        if reader.is_result():
            r = reader.read_result_screen()
            if r:
                logger.info(f'[RESULT] {r}')
                # rdb.add(r.result)
    rdb.save()

    write_notescount_xml(15, Judge(), Judge())
    rdb.write_today_updates_xml(0)
    # r = rdb.search('Mira', play_style.sp, difficulty.another)[0]