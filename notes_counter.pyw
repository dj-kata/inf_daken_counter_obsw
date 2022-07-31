import pyautogui as pgui
import PySimpleGUI as sg
import numpy as np
import os, sys, re
import time
import keyboard
import threading
import math
import codecs
import json

### 固定値
width  = 1280
height = 720
digit_vals = [43860,16065,44880,43095,32895,43605,46920,28050,52020,49215]
savefile   = 'settings.json'

### グローバル変数
today_total = 0
stop_thread = False # メインスレッドを強制停止するために使う

def load_settings():
    # default値を先にセットしておく
    ret = {}
    try:
        with open(savefile) as f:
            ret = json.load(f)
            print(f"設定をロードしました。")
    except Exception:
        ret['target_srate'] = '72%'
        ret['sx'] = '0'
        ret['sy'] = '0'
        ret['sleep_time'] = '1.0'
        ret['run_on_boot'] = False
        print(f"有効な設定ファイルなし。デフォルト値を使います。")

    return ret

def save_settings(settings):
    with open(savefile, 'w') as f:
        json.dump(settings, f, indent=2)

# icon用
def ico_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# デバッグ用、現在設定している座標の画像を切り出してファイルに保存。
def get_screen_all(sx,sy,_w,_h): 
    print(f"設定された左上座標({sx},{sy})から{width}x{height}だけ切り出した画像をtest.pngに保存します。")
    print(f"INFINITASで使うモニタとなっていることを確認してください。")
    sc = pgui.screenshot(region=(sx,sy,_w,_h))
    sc.save('test.png')

### スコア部分の切り出し
def get_score_img(sx,sy,playside):
    if playside == '1P':
        sc = pgui.screenshot(region=(sx+113,sy+650,105,15)) # 1P
    elif playside == '2P':
        sc = pgui.screenshot(region=(sx+1064,sy+650,105,15)) # 2P
    else: # DP
        sc = pgui.screenshot(region=(sx+350,sy+588,105,15)) # DP
    #sc.save('score.png')
    d = []
    for i in range(4):
        DW = 24
        DH = 15
        DSEPA = 3
        d.append(sc.crop((i*DW+i*DSEPA,0,(i+1)*DW+i*DSEPA,DH)))
        #d[-1].save(f"d{i}.png")
    return np.array(sc), d

### キーボード操作用関数(未使用)
### 曲開始時にOBSのシーンを切り替えたりできそうだな～と思って一応用意している
def send_key(cmd):
    pgui.typewrite(cmd)

def push_key(cmd):
    pgui.keyDown(cmd)

def release_key(cmd):
    pgui.keyUp(cmd)

### プレイサイド検出を行う
def detect_playside(sx,sy):
    ret = False
    target = ['1P', '2P', 'DP']
    for t in target:
        det = detect_digit(t, sx, sy)
        if det == '   0':
            ret = t
    return ret

### スコアのデジタル数字を読む関数
### ビットマップの緑チャンネルの合計値で判別している
def detect_digit(playside, sx, sy):
    sc,digits = get_score_img(sx,sy,playside)
    ret = ''
    for d in digits:
        res = '?'
        a = np.array(d)[:,:,1]
        a = (a>180)*255
        wsum = a.sum()

        # 推定部
        if wsum == 0:
            res = ' '
        elif wsum in digit_vals:
            res = digit_vals.index(wsum)
        ret += str(res)
    return ret

### 無限ループにする(終了時は上から止める)
### 曲の開始・終了を数字から検出し、境界処理を行う
### 曲中は検出したスコアをprintする
def detect_top(window, sx, sy, sleep_time):
    pre_det = ''
    playside = False
    print(f'スコア検出スレッド開始。inf=({sx},{sy})')
    while True:
        while True:
            playside = detect_playside(sx,sy)
            global stop_thread
            if playside: # 曲頭を検出
                print(f'曲開始を検出しました。\nEXスコア取得開始。mode={playside}')
                break
            if stop_thread:
                break
            time.sleep(sleep_time)

        if stop_thread:
            break

        while True:
            det = detect_digit(playside, sx, sy)
            try:
                score = int(det)
                window.write_event_value('-THREAD-', f"cur {score}")
                pre_score = score
            except ValueError: #暗転
                window.write_event_value('-THREAD-', f"end {pre_score}")
                print(f'曲終了を検出しました。 => {pre_score}')
                break

            time.sleep(sleep_time)
    
def gen_html(cur,today_score, cur_notes,today_notes,plays):
    f = codecs.open('data.xml', 'w', 'utf-8')
    f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<Items>
    <playcount>{plays}</playcount>
    <cur>{cur}</cur>
    <cur_notes>{cur_notes}</cur_notes>
    <today_score>{today_score}</today_score>
    <today_notes>(推定: {today_notes} notes)</today_notes>
</Items>''')
    f.close()

def gui():
    # GUI設定
    sg.theme('DarkAmber')
    FONT = ('Meiryo',16)
    srate_cand = ['50%','66%','72%'] + [f"{i}%" for i in range(77,101)]
    layout = [
        [sg.Text("target", font=FONT)
        ,sg.Combo(srate_cand, key='target_srate',font=FONT,default_value="72%",readonly=True)
        ,sg.Text('INFINITAS sx:', font=FONT), sg.Input('2560', key='sx', font=FONT, size=(5,1))
        ,sg.Text('sy:', font=FONT), sg.Input('0', key='sy', font=FONT, size=(5,1))
        ],
        [sg.Button('start', key='start', font=FONT, size=(35,1)), sg.Button('test', key='test_screenshot', font=FONT)],
        [sg.Text('plays:', font=FONT), sg.Text('0', key='today_plays', font=FONT), sg.Text(' ', font=FONT, size=(15,1))
        ,sg.Checkbox("起動時に即startする", default=False, font=FONT, key='run_on_boot')
        ],
        [sg.Text("EXスコア        ", font=FONT),sg.Text("cur:", font=FONT),sg.Text("0", key='cur_score',font=FONT, size=(7,1)),sg.Text("Total:", font=FONT),sg.Text("0", key='today_score',font=FONT)],
        [sg.Text("推定ノーツ数   ", font=FONT),sg.Text("cur:", font=FONT),sg.Text("0", key='cur_notes',font=FONT, size=(7,1)),sg.Text("Total:", font=FONT),sg.Text("0", key='today_notes',font=FONT)],
        [sg.Output(size=(51,5), font=('Meiryo',12))] # ここを消すと標準出力になる
        ]
    ico=ico_path('icon.ico')
    window = sg.Window('打鍵カウンタ for INFINITAS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico)

    # 設定のロード
    settings = load_settings()

    # 設定をもとにGUIの値を変更
    window['target_srate'].update(value=settings['target_srate'])
    window['sx'].update(value=settings['sx'])
    window['sy'].update(value=settings['sy'])
    window['run_on_boot'].update(settings['run_on_boot'])
    SLEEP_TIME = float(settings['sleep_time'])


    # カウントした値は現状起動時にリセットとしている
    # 保存するかどうかは仕様をよく考えてから
    today_score = 0
    today_plays = 0
    pre_cur = 0
    pre_cur_notes = 0
    running = settings['run_on_boot'] # 実行中かどうかの区別に使う。スレッド停止用のstop_threadとは役割が違うので注意
    th = False

    if settings['run_on_boot']: # 起動後即開始設定の場合
        print('自動起動設定が有効です。')
        running = True
        sx = int(settings['sx'])
        sy = int(settings['sy'])
        th = threading.Thread(target=detect_top, args=(window, sx, sy, SLEEP_TIME), daemon=True)
        th.start()
        window['start'].update("stop")

    while True:
        ev, val = window.read()
        if settings and val: # 起動後、そのまま何もせずに終了するとvalが拾われないため対策している
            settings['target_srate'] = val['target_srate']
            settings['sx'] = val['sx']
            settings['sy'] = val['sy']
            settings['run_on_boot'] = val['run_on_boot']
        if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-'):
            save_settings(settings)
            break
        elif ev.startswith('start'):
            running = not running
            if running:
                sx = int(val['sx'])
                sy = int(val['sy'])
                th = threading.Thread(target=detect_top, args=(window, sx, sy, SLEEP_TIME), daemon=True)
                th.start()
                window['start'].update("stop")
            else:
                global stop_thread
                stop_thread = True
                th.join()
                stop_thread = False
                print(f'スコア検出スレッド終了。')
                window['start'].update("start")
        elif ev.startswith('test_screenshot'):
            get_screen_all(int(val['sx']), int(val['sy']), width, height)
        elif ev == '-THREAD-':
            dat = val[ev].split(' ')
            cmd = dat[0]
            cur = int(dat[1])
            srate = int(val['target_srate'][:-1])
            cur_notes = math.ceil(cur / 2 / (srate/100))
            tmp_today_notes = math.ceil((cur+today_score) / 2 / (srate/100))
            if cmd == 'cur':
                window['today_score'].update(value=f"{today_score + cur}")
                tmp_today_score = today_score + cur
            elif cmd == 'end':
                today_plays += 1
                today_score += pre_cur
                tmp_today_score = today_score
                window['today_score'].update(value=f"{today_score}")
            window['cur_score'].update(value=f"{cur}")
            window['cur_notes'].update(value=f"{cur_notes}")
            window['today_notes'].update(value=f"{tmp_today_notes}")
            window['today_plays'].update(value=f"{today_plays}")
            gen_html(cur,tmp_today_score,cur_notes,tmp_today_notes,today_plays)
            pre_cur = cur
            pre_cur_notes = cur_notes

if __name__ == '__main__':
    gui()
