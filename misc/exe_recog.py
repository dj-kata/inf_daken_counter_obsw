import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob

from src.screen_reader import ScreenReader

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
    reader = ScreenReader()
    # for f in glob.glob('debug/select*.png'):
    for f in glob.glob('debug/*.png'):
        reader.update_screen_from_file(f)
        try:
            r = reader.read_result_screen()
            if r:
                print('[RESULT]', r)
            else:
                r2 = reader.read_music_select_screen()
                if r2:
                    print('[SELECT]', r2)
        except:
            # import traceback
            # print(traceback.format_exc())
            continue
        print(reader.is_result(), reader.is_select(), reader.is_endresult(), reader.is_endselect())

        # break # debug


