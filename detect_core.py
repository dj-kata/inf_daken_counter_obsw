import numpy as np
from PIL import Image
import imagehash, os
import logging, logging.handlers
mdigit_vals = [20910,3570,9945,8925,8160,9945,12240,7140,11730,12495]
mdigit_vals = [20910,8415,19635,18615,17085,20655,23205,13515,24225,23205]

os.makedirs('log', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

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

def get_update_area(img:Image, valid_playside):
    """リザルト画面に対し、各エリアが更新されているかどうかを確認する。

    Args:
        img (PIL.Image): ゲーム画面
        valid_playside (str): プレーサイドの判定結果

    Returns:
        [bool,bool,bool,bool]: ランプ、DJLEVEL、SCORE、MISSCOUNTが更新されているかどうか
    """
    ret = []
    #hash_target = imagehash.average_hash(Image.open('layout/update.png'))
    hash_target = imagehash.hex_to_hash('00ffff0000ffeffc')
    if ('1p' in valid_playside) or (valid_playside == 'dp-l'):
        for i in range(4):
            tmp = imagehash.average_hash(img.crop((521,417+68*i,555,438+68*i))) # TODO
            ret.append((hash_target - tmp)<10)
    else:
        for i in range(4):
            tmp = imagehash.average_hash(img.crop((1871,417+68*i,1905,438+68*i)))
            ret.append((hash_target - tmp)<10)
    #logger.debug(f"valid_playside={valid_playside}, ret={ret}")
    return ret

def has_rival_area(img:Image):
    """リザルト画像を入力し、ライバル欄があるかどうかを判定

    Args:
        img (Image): ゲーム画面

    Returns:
        str or None: 1p,2p,Noneのいずれか
    """
    ret = None
    hash_target = imagehash.hex_to_hash('fffffff040000000')
    hashl = imagehash.average_hash(img.crop((489,272,489+64,272+68)))
    hashr = imagehash.average_hash(img.crop((1829,272,1829+64,272+68)))
    if abs(hashl-hash_target)<5:
        ret = '2p'
    elif abs(hashr-hash_target)<5:
        ret = '1p'
    #logger.debug(f"ret={ret}")
    return ret

def mosaic_rival_area(img:Image, playside:str) -> Image:
    """リザルト画面を入力し、ライバル情報をぼかした画像を出力

    Args:
        img (Image): ゲーム画面
        playside (str): どっち側のリザルトか(1p/2p)

    Returns:
        Image: 処理後のリザルト画像
    """
    img_array = np.array(img)
    if playside == '1p': # ライバルエリアが右側
        sx=1375
        det_rival_sx = 42
        rival_name_sx = 226
    elif playside == '2p': # ライバルエリアが左側
        sx=35
        det_rival_sx = 1392
        rival_name_sx = 1576
    sy=270
    ex=sx+456
    ey=sy+618
    rivalarea = img.crop((sx,sy,ex,ey))
    rivalarea = rivalarea.resize((45,61))
    rivalarea = rivalarea.resize((456,618))
    rival_array = np.array(rivalarea)
    img_array[sy:ey, sx:ex] = rival_array

    # 挑戦状エリアの処理
    ### TODO 挑戦状日時の部分をひろうと、撃破とかのエフェクトが重なるのでライバル名のところに変更
    hash_target = imagehash.hex_to_hash('00007f7f7f7f1400')
    hash = imagehash.average_hash(img.crop((827,854,926,876)))
    if abs(hash - hash_target) < 5:
        mailarea = img.crop((875,777,987,799))
        mailarea = mailarea.resize((11,2))
        mailarea = mailarea.resize((112,22))
        mail_array = np.array(mailarea)
        img_array[777:799, 875:987] = mail_array
    ## ターゲット名も隠す(ライバルの名前が入っている可能性があるため)
    hash_target = imagehash.hex_to_hash('00ffff000000ffff')
    hash = imagehash.average_hash(img.crop((det_rival_sx,690,det_rival_sx+15,699)))
    if abs(hash - hash_target) < 5: # ターゲットがライバル
        targetarea = img.crop((rival_name_sx,690,rival_name_sx+82,707))
        targetarea = targetarea.resize((8,2))
        targetarea = targetarea.resize((82,20))
        img_array[687:707, rival_name_sx:rival_name_sx+82] = targetarea
    return Image.fromarray(img_array)

def trim_main_area(img:Image, playside:str) -> Image:
    """スコア情報と曲名だけ切り取る

    Args:
        img (Image): リザルト画面
        playside (str): 1p,2p

    Returns:
        Image: 処理後の画像
    """
    if playside == '1p': # ライバルエリアが右側
        sx=0
    elif playside == '2p': # ライバルエリアが左側
        sx=1919-1353
    return img.crop((sx,0, sx+1353,1080))

def is_select(img:Image) -> bool:
    """選曲画面かどうかを判定し、判定結果(True/False)を返す

    Args:
        img (PIL.Image): ゲーム画面

    Returns:
        bool: 選曲画面であればTrue
    """
    ret = False

    hash_target = imagehash.hex_to_hash('007e7e5e5a7e7c00')
    img_1p = img.crop((466,1000,466+27,1000+27))
    h_1p = imagehash.average_hash(img_1p)
    img_2p = img.crop((1422,1000,1422+27,1000+27))
    h_2p = imagehash.average_hash(img_2p)
    ret = ((hash_target - h_1p) < 10) or ((hash_target - h_2p) < 10)
    #logger.debug(f"ret = {ret}")

    return ret

### リザルト画面かどうかを判定し、判定結果(True/False)を返す
def is_result(img):
    ret = False

    hash_target = imagehash.average_hash(Image.open('layout/is_result.png'))
    tmpl = imagehash.average_hash(img.crop((20,28,60,58)))
    tmpr = imagehash.average_hash(img.crop((1860,28,1900,58)))
    ret = ((hash_target - tmpl) < 10) or ((hash_target - tmpr) < 10)
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
        print('is_select:', is_select(img),',is_result:', is_result(img),',end_select:', detect_endselect(img),',end_result:', detect_endresult(img))
        result_playside = has_rival_area(img)
        if type(result_playside)==str:
            tmp = mosaic_rival_area(img, result_playside)
            tmp = trim_main_area(tmp, result_playside)
            tmp.save('debug/hoge.png')
        #print(detect_playside(img))
        #print(detect_judge(img, 'dp-l'))
    #detect_judge(img, '2p-l')
    #img = Image.open('debug/play1_sp.png')
    #detect_judge(img, '2p-l')
