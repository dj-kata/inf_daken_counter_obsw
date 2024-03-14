import numpy as np
from PIL import Image
import imagehash
mdigit_vals = [20910,3570,9945,8925,8160,9945,12240,7140,11730,12495]
mdigit_vals = [20910,8415,19635,18615,17085,20655,23205,13515,24225,23205]

### 判定部分の切り出し
def get_judge_img(img, playside):
    # x,yはPGの4桁目(一番左)の左上座標としている
    if playside == '1p-l':
        x=632
        y=969
    elif playside == '1p-r':
        x=1049
        y=969
    elif playside == '2p-l':
        x=852
        y=969
    elif playside == '2p-r':
        x=1269
        y=969
    elif playside == '1p_nograph':
        x=678
        y=969
    elif playside == '2p_nograph':
        x=1223
        y=969
    elif playside == 'dp-l':
        x=262
        y=898
    elif playside == 'dp-r':
        x=1643
        y=898
    # 判定内訳部分のみを切り取る
    sc = img.crop((x,y,x+53,y+91))
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
def detect_judge(img, playside):
    sc,digits = get_judge_img(img, playside)
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
            elif val in mdigit_vals:
                if val == mdigit_vals[6]: # 6,9がひっくり返しただけで合計値が同じなのでケア
                    if dd[8,0] == 0:
                        tmp = '9'
                    else:
                        tmp = '6'
                else:
                    tmp = str(mdigit_vals.index(val))
            line += tmp 
        ret.append(line)
    return ret

### プレイサイド検出を行う
def detect_playside(img):
    ret = False
    target = ['1p-l', '1p-r', '2p-l', '2p-r', '1p_nograph', '2p_nograph', 'dp-l', 'dp-r'] # BGA表示エリアの位置
    for t in target:
        det = detect_judge(img, t)
        if det[0] == '0':
            ret = t
    return ret
    
### 選曲画面かどうかを判定し、判定結果(True/False)を返す
def detect_select(img):
    ret = False

    hash_target = imagehash.average_hash(Image.open('layout/is_select.png'))
    tmp = imagehash.average_hash(img.crop((272,982,272+62,982+58)))
    ret = (hash_target - tmp) < 10
    #logger.debug(f"ret = {ret}")

    return ret

### 選曲画面の終了判定
def detect_endselect(img):
    tmp = imagehash.average_hash(img.crop((0,0,1920,380)))
    img = Image.open('layout/endselect.png') #.crop((550,1,750,85))
    hash_target = imagehash.average_hash(img)
    ret = (hash_target - tmp) < 10
    return ret

### リザルト画面の終了判定
def detect_endresult(img):
    tmp = imagehash.average_hash(img)
    img2 = Image.open('layout/endresult.png')
    hash_target = imagehash.average_hash(img2)
    ret = (hash_target - tmp) < 10
    #logger.debug(f"ret = {ret}")
    return ret

if __name__ == '__main__':
    import sys
    for f in sys.argv[1:]:
        img = Image.open(f)
        print(f)
        print('is_select:', detect_select(img))
        print('end_select:', detect_endselect(img))
        print('end_result:', detect_endresult(img))
        print(detect_playside(img))
        print(detect_judge(img, 'dp-l'))
    img = Image.open('debug/play0_sp_all0.png')
    print(detect_playside(img))
    #detect_judge(img, '2p-l')
    #img = Image.open('debug/play1_sp.png')
    #detect_judge(img, '2p-l')
