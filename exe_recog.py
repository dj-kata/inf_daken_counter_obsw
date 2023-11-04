from recog import *
import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash

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
        #'informations': (slice(628, 706), slice(410, 870)),
        img = Image.open(filename)
        #play_side = recog.get_play_side(np.array(img))
        play_side = 'DP'
        # TODO define.pyのsliceをそのまま渡せるように修正したい
        #title = img.crop((410,633,870,704)) # 旧方式
        title = img.crop((410,628,870,706)) # 新方式
        #title = title.convert('L')
        title_np = np.array(title)
        print(title_np.shape)
        a = recog.get_informations(title_np)
        if a.music == None:
            img_mono = img.convert('L')
            pic_info = img.crop((410,633,870,704))
            a.music  = recog.get_music(np.array(pic_info))
        # 1p, 2pをケアする必要がある TODO
        score = img.crop((905,192,905+350,192+293))
        score = np.array(score)
        b = recog.get_details(score)
        #gen_ocr_result(a, b)
        print(a.music, a.difficulty)
        print(play_side)
        print(f"opt arrange:{b.options.arrange}, flip:{b.options.flip}, battle:{b.options.battle}, assist:{b.options.assist}, special:{b.options.special}")

        # x(2p): 133-210
        # y 1st: 199-216, 2nd:279-296, ...

        # ライバル名のhash
        #for i in range(6):
        #    tmp = imagehash.average_hash(img.crop((133,199+80*i,210,216+80*i)))
        #    print(f"{i}: {tmp}")
