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
    for f in glob.glob('debug/select*.png'):
        filename = f
        screen = open_screenimage(f)
        img = Image.open(f)
        np_value = np.array(img)
        try:
            result = recog.get_result(screen)
        except:
            continue
        if result:
            print(f'file:{f}, musicname:{result.informations.music}', end='')
            print(result.informations.play_mode, result.informations.difficulty, result.informations.level, result.informations.notes)
            if result.details.options:
                print(f"opt arrange:{result.details.options.arrange}, flip:{result.details.options.flip}, battle:{result.details.options.battle}, assist:{result.details.options.assist}, special:{result.details.options.special}, playspeed:{result.informations.playspeed}", end='')
            else:
                print("options: None", end='')
            print(f'sc:{result.details.score.current}, lamp:{result.details.clear_type.current}')

        np_value = screen.np_value[define.musicselect_trimarea_np]
        musicselect = recog.MusicSelect.get_musicname(np_value)
        if musicselect:
            print(f"[SELECT] file:{f}, title: {musicselect}, {recog.MusicSelect.get_difficulty(np_value)}, {recog.MusicSelect.get_cleartype(np_value)}, {recog.MusicSelect.get_score(np_value)}, {recog.MusicSelect.get_misscount(np_value)}")


