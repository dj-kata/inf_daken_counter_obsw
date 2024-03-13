import numpy as np
from PIL import Image
import imagehash
mdigit_vals = [10965,3570,9945,8925,8160,9945,12240,7140,11730,12495]

### 判定部分の切り出し
def get_judge_img(img, playside):
    if playside == '1p-l':
        x=414
        y=647
    elif playside == '1p-r':
        x=694
        y=647
    elif playside == '2p-l':
        x=570
        y=647
    elif playside == '2p-r':
        x=850
        y=647
    elif playside == '1p_nograph':
        x=383
        y=649
    elif playside == '2p_nograph':
        x=881
        y=649
    elif playside == 'dp-l':
        x=176
        y=600
    elif playside == 'dp-r':
        x=1089
        y=600
    sc = img.crop((x,y,x+38,y+57))
    d = []
    for j in range(6): # pg～prの5つ
        tmp_sec = []
        for i in range(4): # 4文字
            DW = 8
            DH = 7
            DSEPA = 2
            tmp = np.array(sc.crop((i*(DW+DSEPA),10*j,(i+1)*DW+i*DSEPA,10*j+DH)))
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
                if val == mdigit_vals[2]: # 2,5がひっくり返しただけで合計値が同じなのでケア
                    if dd[2,1] == 255:
                        tmp = '5'
                    else:
                        tmp = '2'
                else:
                    tmp = str(mdigit_vals.index(val))
            line += tmp 
        ret.append(line)
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
