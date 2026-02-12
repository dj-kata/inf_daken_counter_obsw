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
from src.result_database import ResultDatabase
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
    config = Config()
    rdb = ResultDatabase(config = config)
    reader = ScreenReader()
    # for f in glob.glob('debug/0126/*.png'):
    #     # logger.info(f'file={f}')
    #     reader.update_screen_from_file(f)
    #     if reader.is_result():
    #         r = reader.read_result_screen()
    #         if r:
    #             # logger.info(f'[RESULT] {r}')
    #             r.result.timestamp = os.path.getmtime(f)
    #             rdb.add(r.result)
    # rdb.save()
    # print(len(rdb.results))

    # print(rdb)

    print(f'len = {len(rdb.results)}')

    # rdb.write_best_csv()
    a = rdb.get_all_best_results()
    rdb.write_best_csv()

    import time
    # a = rdb.results[-1]
    # a.play_style = play_style.dp
    # a.chart_id = (a.title, a.play_style, a.difficulty)
    # rdb.results[-1] = a
    rdb.broadcast_today_updates_data(datetime.datetime.now().timestamp() - 96*3600)
    rdb.broadcast_history_cursong_data('AA', play_style.sp, difficulty.another)
    # time.sleep(5)
    # rdb.broadcast_history_cursong_data('Lords Of The Roundtable', play_style.sp, difficulty.another, playspeed=0.95)
    # rdb.broadcast_history_cursong_data('Carmina', play_style.sp, difficulty.another)
    # rdb.broadcast_graph_data(datetime.datetime.now().timestamp()-4*3600)
    time.sleep(4)

    rdb.shutdown_servers()
