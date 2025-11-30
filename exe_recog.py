#import recog
import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
from screenshot import Screenshot,open_screenimage
from recog import Recognition as recog
from resources import resource

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
    if len(sys.argv) < 2:
        print('')
    else:
        filename = sys.argv[1]
        screen = open_screenimage(sys.argv[1])
        img = Image.open(sys.argv[1])
        result = recog.get_result(screen)

        np_value = np.array(img.crop((48,135,1188,952)))
        musicname = recog.MusicSelect.get_musicname(np_value)
        print('musicname:',musicname)

        print(result.informations.music)
        print(result.informations.play_mode, result.informations.difficulty, result.informations.level, result.informations.notes)
        print(f"opt arrange:{result.details.options.arrange}, flip:{result.details.options.flip}, battle:{result.details.options.battle}, assist:{result.details.options.assist}, special:{result.details.options.special}, playspeed:{result.informations.playspeed}")
        print(f'sc:{result.details.score.current}, lamp:{result.details.clear_type.current}')

