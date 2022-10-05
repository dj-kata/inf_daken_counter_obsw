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
import webbrowser, urllib, requests
from bs4 import BeautifulSoup

### 固定値
width  = 1280
height = 720
digit_vals = [43860,16065,44880,43095,32895,43605,46920,28050,52020,49215]
mdigit_vals = [9690,3570,9945,8415,7650,9945,10965,6885,10710,11475]
savefile   = 'settings.json'

if len(sys.argv) > 1:
    savefile = sys.argv[1]

### グローバル変数
today_total = 0
stop_thread = False # メインスレッドを強制停止するために使う

def load_settings():
    default_val = {'target_srate':'72%', 'sx':'0','sy':'0', 'sleep_time':'1.0',
    'plays':'0','total_score':'0', 'run_on_boot':False, 'reset_on_boot':False, 'lx':0, 'ly':0,
    'series_query':'#[number]','judge':[0,0,0,0,0,0]}
    ret = {}
    try:
        with open(savefile) as f:
            ret = json.load(f)
            print(f"設定をロードしました。\n")
    except Exception:
        print(f"有効な設定ファイルなし。デフォルト値を使います。")

    ### 後から追加した値がない場合にもここでケア
    for k in default_val.keys():
        if not k in ret.keys():
            print(f"{k}が設定ファイル内に存在しません。デフォルト値({default_val[k]}を登録します。)")
            ret[k] = default_val[k]

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
    print(f"10秒後に設定された左上座標({sx},{sy})から{width}x{height}だけ切り出した画像をtest.bmpに保存します。")
    print(f"また、全モニタの画像をwhole.bmpに保存します。")
    print(f"test.bmpがINFINITASで使うモニタとなっていることを確認してください。")
    time.sleep(10)
    print(f"\n10秒経過。キャプチャを実行します。")
    sc = pgui.screenshot(region=(sx,sy,_w,_h))
    sc.save('test.bmp')
    sc = pgui.screenshot()
    sc.save('whole.bmp')

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
    target = ['1p-l', '1p-r', '2p-l', '2p-r', 'dp-l', 'dp-r'] # BGA表示エリアの位置
    for t in target:
        det = detect_judge(t, sx, sy)
        if det[0] == '0':
            ret = t
    return ret

### オプション検出を行う
def detect_option(sx, sy):
    playopt = False
    whole = pgui.screenshot(region=(sx,sy,1280,720))
    flip = ''
    left = False
    right = False
    assist = ''
    gauge = False
    battle = ''
    ### オプション画面かどうかを検出
    px0 = whole.getpixel((43,33)) == (255,0,0)
    px1 = whole.getpixel((44,424)) == (0xff,0x4f,0xbb)
    px2 = whole.getpixel((114,645)) == (0xff,0x4f,0xbb)
    px_dp = whole.getpixel((1070,345)) == (0x0,0x29,0x32)
    px_sp = whole.getpixel((905,358)) == (0x0,0x29,0x32)

    if px0 and px1 and px2 and (px_sp or px_dp): # オプション画面かどうか
        flip_off   = whole.getpixel((932,200)) == (0xff,0x6c,0x0)
        flip_on    = whole.getpixel((932,230)) == (0xff,0x6c,0x0)
        
        isbattle = whole.getpixel((148,514)) != (0xff,0xff,0xff) # 白かどうかをみる、白ならオフ
        hran   = whole.getpixel((167,534)) != (0xff,0xff,0xff) # 白かどうかをみる、白ならオフ
    
        if isbattle:
            battle = 'BATTLE, '

        if px_dp: # DP
            normal    = whole.getpixel((683,390)) == (0xff, 0x6c, 0x0)
            a_easy    = whole.getpixel((742,422)) != (0, 0, 0)
            easy      = whole.getpixel((683,456)) == (0xff, 0x6c, 0x0)
            hard      = whole.getpixel((683,489)) == (0xff, 0x6c, 0x0)
            ex_hard   = whole.getpixel((682,522)) == (0xff, 0x6c, 0x0)
            for pix,val in zip([normal,a_easy,easy,hard,ex_hard],['NORMAL','A-EASY','EASY','HARD', 'EX-HARD']):
                if pix:
                    gauge = val

            left_off     = whole.getpixel((390,390)) == (0xff, 0x6c, 0x0)
            left_ran     = whole.getpixel((390,422)) == (0xff, 0x6c, 0x0)
            left_rran    = whole.getpixel((384,455)) == (0xff, 0x6c, 0x0)
            left_sran    = whole.getpixel((384,489)) == (0xff, 0x6c, 0x0)
            left_mirror  = whole.getpixel((390,520)) == (0xff, 0x6c, 0x0)
        
            right_off     = whole.getpixel((536,390)) == (0xff, 0x6c, 0x0)
            right_ran     = whole.getpixel((536,422)) == (0xff, 0x6c, 0x0)
            right_rran    = whole.getpixel((530,455)) == (0xff, 0x6c, 0x0)
            right_sran    = whole.getpixel((530,489)) == (0xff, 0x6c, 0x0)
            right_mirror  = whole.getpixel((536,520)) == (0xff, 0x6c, 0x0)
        
            sync_ran      = whole.getpixel((394,554)) == (0xff, 0x6c, 0x0)
            symm_ran      = whole.getpixel((394,585)) == (0xff, 0x6c, 0x0)

            assist_off    = whole.getpixel((830,390)) == (0xff, 0x6c, 0x0)
            assist_as     = whole.getpixel((858,426)) == (0xff, 0x6c, 0x0)
            assist_legacy = whole.getpixel((880,489)) == (0xff, 0x6c, 0x0)

            if flip_on:
                flip = ', FLIP'
            sran_str = 'S-RAN'
            if hran:
                sran_str = 'H-RAN'
            # 左手
            for pix,val in zip([left_off,left_ran,left_rran,left_mirror,left_sran],['OFF','RAN','R-RAN','MIR', sran_str]):
                if pix:
                    left = val
            # 右手
            for pix,val in zip([right_off,right_ran,right_rran,right_mirror,right_sran],['OFF','RAN','R-RAN','MIR', sran_str]):
                if pix:
                    right = val
            if isbattle:
                if sync_ran:
                    left = ' '
                    right = 'SYNC-RAN'
                elif symm_ran:
                    left = ' '
                    right = 'SYMM-RAN'
            # アシスト
            for pix,val in zip([assist_off, assist_as, assist_legacy],['', ', A-SCR', ', LEGACY']):
                if pix:
                    assist += val

            if left and right: # オプション画面のスライド中にバグるのを防ぐため
                if battle and (symm_ran or sync_ran):
                    playopt = f"{battle}{right}{assist}"
                else:
                    playopt = f"{battle}{left} / {right}{flip}{assist}"

        else: # SP
            normal    = whole.getpixel((524,390)) == (0xff, 0x6c, 0x0)
            a_easy    = whole.getpixel((582,422)) != (0, 0, 0)
            easy      = whole.getpixel((524,456)) == (0xff, 0x6c, 0x0)
            hard      = whole.getpixel((524,489)) == (0xff, 0x6c, 0x0)
            ex_hard   = whole.getpixel((518,522)) == (0xff, 0x6c, 0x0)
            for pix,val in zip([normal,a_easy,easy,hard,ex_hard],['NORMAL','A-EASY','EASY','HARD', 'EX-HARD']):
                if pix:
                    gauge = val

            right_off     = whole.getpixel((375,391)) == (0xff, 0x6c, 0x0)
            right_ran     = whole.getpixel((375,424)) == (0xff, 0x6c, 0x0)
            right_rran    = whole.getpixel((369,457)) == (0xff, 0x6c, 0x0)
            right_sran    = whole.getpixel((369,489)) == (0xff, 0x6c, 0x0)
            right_mirror  = whole.getpixel((375,520)) == (0xff, 0x6c, 0x0)

            assist_off    = whole.getpixel((680,390)) == (0xff, 0x6c, 0x0)
            assist_as     = whole.getpixel((699,426)) == (0xff, 0x6c, 0x0)
            assist_legacy = whole.getpixel((720,489)) == (0xff, 0x6c, 0x0)
            # 右手
            for pix,val in zip([right_off,right_ran,right_rran,right_mirror,right_sran],['OFF','RAN','R-RAN','MIR','S-RAN']):
                if pix:
                    right = val
            # アシスト
            for pix,val in zip([assist_off, assist_as, assist_legacy],['', ', A-SCR', ', LEGACY']):
                if pix:
                    assist += val
            if right: # オプション画面のスライド中にバグるのを防ぐため
                playopt = f"{right}{assist}"
    return playopt, gauge

### 判定部分の切り出し
def get_judge_img(playside,sx,sy):
    if playside == '1p-l':
        sc = pgui.screenshot(region=(sx+113,sy+647,38,57)) #TODO
    elif playside == '1p-r':
        sc = pgui.screenshot(region=(sx+113,sy+647,38,57)) #TODO
    elif playside == '2p-l':
        sc = pgui.screenshot(region=(sx+571,sy+647,38,57))
    elif playside == '2p-r':
        sc = pgui.screenshot(region=(sx+871,sy+647,38,57)) #TODO
    elif playside == 'dp-l':
        sc = pgui.screenshot(region=(sx+164,sy+600,38,57)) #TODO
    elif playside == 'dp-r':
        sc = pgui.screenshot(region=(sx+1089,sy+600,38,57))
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
def detect_judge(playside, sx, sy):
    sc,digits = get_judge_img(playside,sx,sy)
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

### 無限ループにする(終了時は上から止める)
### 曲の開始・終了を数字から検出し、境界処理を行う
### 曲中は検出したスコアをprintする
def detect_top(window, sx, sy, sleep_time):
    global stop_thread
    pre_det = ''
    stop_local = False
    playside = False
    playopt = '' # 曲開始タイミングとオプション検出タイミングは一致しないため、最後の値を覚えておく
    gauge   = ''
    print(f'スコア検出スレッド開始。inf=({sx},{sy})')
    while True:
        while True: # 曲開始までを検出
            #print('test')
            try:
                playside = detect_playside(sx,sy)
                tmp_playopt, tmp_gauge = detect_option(sx, sy)
                if tmp_playopt and tmp_gauge:
                    if playopt != tmp_playopt:
                        window.write_event_value('-PLAYOPT-', tmp_playopt)
                    if gauge != tmp_gauge:
                        window.write_event_value('-GAUGE-', tmp_gauge)
                    playopt = tmp_playopt
                    gauge = tmp_gauge
                    gen_opt_xml(playopt, gauge) # 常時表示オプションを書き出す
                if playside: # 曲頭を検出
                    print(f'曲開始を検出しました。\nEXスコア取得開始。mode={playside.upper()}')
                    gen_opt_xml(playopt, gauge, True) # 常時表示+曲中のみデータの書き出し
                    break
            except Exception as e:
                stop_local = True
                print(f'スクリーンショットに失敗しました。{e}')
                window.write_event_value('-SCRSHOT_ERROR-', " ")
                break
            if stop_thread:
                stop_local = True
                break
            #time.sleep(sleep_time)
            time.sleep(0.3) # オプション取得のためにここは短くしたほうがよさそう？

        if stop_local:
            break

        while True: # 曲中の処理
            det = detect_judge(playside, sx,sy)
            try:
                score = int(det[0])+int(det[1])+int(det[2])
                window.write_event_value('-THREAD-', f"cur {score} {det[0]} {det[1]} {det[2]} {det[3]} {det[4]} {det[5]}")
                pre_score = score
                pre_judge = det
            except ValueError: # intに変換できない数値を検出&暗転の両方を見る
                topleft = pgui.screenshot(region=(sx,sy,120,120))
                if np.array(topleft).sum() == 0:
                    window.write_event_value('-ENDSONG-', f"{pre_score} {playopt}")
                    window.write_event_value('-THREAD-', f"end {pre_score} {pre_judge[0]} {pre_judge[1]} {pre_judge[2]} {pre_judge[3]} {pre_judge[4]} {pre_judge[5]}")
                    print(f'曲終了を検出しました。 => {pre_score}')
                    gen_opt_xml(playopt, gauge) # 曲中のみデータの削除
                    break

            time.sleep(sleep_time)
    print(f'スコア検出スレッド終了。')
    
def gen_notes_xml(cur,today, plays, notes_ran, notes_battle, judge):
    srate = 0.0
    if judge[0]+judge[1]+judge[2]+judge[5] > 0:
        srate = (judge[0]*2+judge[1])/(judge[0]+judge[1]+judge[2]+judge[5])*50
    f = codecs.open('data.xml', 'w', 'utf-8')
    f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<Items>
    <playcount>{plays:,}</playcount>
    <cur_notes>{cur:,}</cur_notes>
    <today_notes>{today:,}</today_notes>
    <notes_ran>{notes_ran:,}</notes_ran>
    <notes_battle>{notes_battle:,}</notes_battle>
    <pg>{judge[0]:,}</pg>
    <gr>{judge[1]:,}</gr>
    <gd>{judge[2]:,}</gd>
    <bd>{judge[3]:,}</bd>
    <pr>{judge[4]:,}</pr>
    <cb>{judge[5]:,}</cb>
    <score_rate>{srate:.1f}</score_rate>
</Items>''')
    f.close()

def gen_opt_xml(opt, in_gauge, onSong=False): # onSong: 曲開始時の呼び出し時にTrue->曲中のみ文字列を設定
    gauge = f"<{re.sub('-', '', in_gauge.lower())}>{in_gauge}</{re.sub('-', '', in_gauge.lower())}>"

    f = codecs.open('option.xml', 'w', 'utf-8')
    opt_dyn = ''
    gauge_dyn = ''
    if onSong:
        opt_dyn = 'opt: opt'
        gauge_dyn = f"<{re.sub('-', '', in_gauge.lower())}_dyn>{in_gauge}</{re.sub('-', '', in_gauge.lower())}_dyn>"


    f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<Items>
    <option>{opt}</option>
    <opt_dyn>{opt_dyn}</opt_dyn>
    {gauge}
    {gauge_dyn}
</Items>''')
    f.close()

def parse_url(url):
    ret = False
    if re.search('www.youtube.com.*v=', url):
        ret = re.sub('.*v=', '', url)
    elif re.search('livestreaming\Z', url):
        ret = url.split('/')[-2]
    return ret

def write_series_xml(series):
    print(f"series.xmlを更新しました => {series}\n")
    f=codecs.open('series.xml', 'w', 'utf-8')
    f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<Items>
    <series>{series}</series>
</Items>''')
    f.close()
def get_ytinfo(url):
    liveid = parse_url(url)
    ret = False
    if liveid:
        regular_url = f"https://www.youtube.com/watch?v={liveid}"
        r = requests.get(regular_url)
        soup = BeautifulSoup(r.text,features="html.parser")
        title = re.sub(' - YouTube\Z', '', soup.find('title').text)
        #print(f"liveid = {liveid}")
        print(f"配信タイトル:\n{title}\n")
        print(f"コメント欄用:\nhttps://www.youtube.com/live_chat?is_popout=1&v={liveid}\n")
        print(f"ツイート用:\n{title}\n{regular_url}\n")

        encoded_title = urllib.parse.quote(f"{title}\n{regular_url}\n")
        webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_title}")
        ret = title
    else:
        print('無効なURLです\n')
    return ret

def gui_ytinfo(default_query='#[number]'):
    sg.theme('DarkAmber')
    FONT = ('Meiryo',12)
    ico=ico_path('icon.ico')
    layout = [
        [sg.Text("YoutubeLive URL(配信、スタジオ等)", font=FONT)],
        [sg.Input("", font=FONT, key='youtube_url', size=(50,1))],
        [sg.Text("シリーズ文字列の検索クエリ(例: #[number] [number]日目等)", font=FONT)],
        [sg.Input(default_query, font=FONT, key='series_query', size=(20,1))],
        [sg.Button('go', size=(10,1))]
    ]
    window = sg.Window('YoutubeLive準備用ツール(隠しコマンド)', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico)
    window['youtube_url'].bind('<Return>', '_Enter')
    window['series_query'].bind('<Return>', '_Enter')
    while True:
        ev, val = window.read()
        #print(f"event='{ev}', values={val}")
        default_query = val['series_query']
        # 設定を最新化
        if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-'):
            print('キャンセルされました。')
            window.close()
            break
        elif ev in ('go', 'youtube_url_Enter', 'series_query_Enter'):
            url = val['youtube_url']
            query = val['series_query'].replace('[number]', '[0-9０-９]+')
            title = get_ytinfo(url)
            if title:
                series = ''
                if re.search(query, title):
                    series = re.search(query, title).group()
                write_series_xml(series)
                window.close()
                break
    return default_query

def gui(): # GUI設定
    # 設定のロード
    settings = load_settings()

    sg.theme('DarkAmber')
    FONT = ('Meiryo',12)
    FONTs = ('Meiryo',8)
    layout = [
        [sg.Text('INFINITAS sx:', font=FONT), sg.Input('2560', key='sx', font=FONT, size=(5,1))
        ,sg.Text('sy:', font=FONT), sg.Input('0', key='sy', font=FONT, size=(5,1))
        ],
        [sg.Button('start', key='start', font=FONT, size=(27,1)), sg.Button('reset', key='reset', font=FONT), sg.Button('tweet', key='tweet', font=FONT), sg.Button('test', key='test_screenshot', font=FONT)],
        [sg.Text('plays:', font=FONT), sg.Text('0', key='plays', font=FONT)
        ,sg.Text(' ', font=FONT, size=(5,1))
        ,sg.Checkbox("起動時に即start", default=False, font=FONT, key='run_on_boot')
        ,sg.Checkbox("start時にreset", default=False, font=FONT, key='reset_on_boot')
        ],
        [sg.Text("ノーツ数 ", font=FONT),sg.Text("cur:", font=FONT),sg.Text("0", key='cur',font=FONT, size=(7,1)),sg.Text("Total:", font=FONT),sg.Text("0", key='today',font=FONT)],
        [sg.Text('PG:',font=FONTs),sg.Text('0',key='judge0',font=FONTs),sg.Text('GR:',font=FONTs),sg.Text('0',key='judge1',font=FONTs),sg.Text('GD:',font=FONTs),sg.Text('0',key='judge2',font=FONTs),sg.Text('BD:',font=FONTs),sg.Text('0',key='judge3',font=FONTs),sg.Text('PR:',font=FONTs),sg.Text('0',key='judge4',font=FONTs),sg.Text('CB:',font=FONTs),sg.Text('0',key='judge5',font=FONTs)],
        [sg.Text("option:", font=FONT),sg.Text(" ", key='playopt',font=FONT, ),sg.Text("ゲージ:", font=FONT),sg.Text(" ", key='gauge',font=FONT),sg.Text('平均スコアレート:',font=FONT),sg.Text('0 %',key='srate',font=FONT)],
        [sg.Output(size=(63,8), font=('Meiryo',9))] # ここを消すと標準出力になる
        ]
    ico=ico_path('icon.ico')
    window = sg.Window('打鍵カウンタ for INFINITAS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico,location=(settings['lx'], settings['ly']))

    # 設定をもとにGUIの値を変更
    window['sx'].update(value=settings['sx'])
    window['sy'].update(value=settings['sy'])
    window['run_on_boot'].update(settings['run_on_boot'])
    window['reset_on_boot'].update(settings['reset_on_boot'])
    SLEEP_TIME = float(settings['sleep_time'])

    today_notes = int(settings['total_score'])
    today_plays = int(settings['plays'])
    window['today'].update(value=f"{today_notes}")
    window['plays'].update(value=f"{today_plays}")
    judge = settings['judge']
    for i in range(6):
        window[f'judge{i}'].update(value=judge[i])
    srate = 0.0
    if judge[0]+judge[1]+judge[2]+judge[5] > 0:
        srate = (judge[0]*2+judge[1])/(judge[0]+judge[1]+judge[2]+judge[5])*50
    window['srate'].update(value=f"{srate:.2f} %")
    notes_ran = 0
    notes_battle  = 0
    pre_cur = 0
    running = settings['run_on_boot'] # 実行中かどうかの区別に使う。スレッド停止用のstop_threadとは役割が違うので注意
    th = False
    global stop_thread

    if settings['run_on_boot']: # 起動後即開始設定の場合
        print('自動起動設定が有効です。')
        if settings['reset_on_boot']:
            today_notes = 0
            today_plays = 0
            notes_ran = 0
            notes_battle  = 0
        running = True
        sx = int(settings['sx'])
        sy = int(settings['sy'])
        th = threading.Thread(target=detect_top, args=(window, sx, sy, SLEEP_TIME), daemon=True)
        th.start()
        window['start'].update("stop")

    while True:
        ev, val = window.read()
        #print(f"event='{ev}', values={val}")
        # 設定を最新化
        if settings and val: # 起動後、そのまま何もせずに終了するとvalが拾われないため対策している
            # 今日のノーツ数とか今日の回数とかはここに記述しないこと(resetボタンを押すと即反映されてしまうため)
            settings['sx'] = val['sx']
            settings['sy'] = val['sy']
            settings['lx'] = window.current_location()[0]
            settings['ly'] = window.current_location()[1]
            settings['run_on_boot'] = val['run_on_boot']
            settings['reset_on_boot'] = val['reset_on_boot']
        if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-'):
            save_settings(settings)
            break
        elif ev.startswith('start'):
            running = not running
            if running:
                if settings['reset_on_boot']:
                    print('自動リセット設定が有効です。')
                    today_notes = 0
                    today_plays = 0
                    notes_ran = 0
                    notes_battle = 0
                    judge = [0,0,0,0,0,0]
                sx = int(val['sx'])
                sy = int(val['sy'])
                th = threading.Thread(target=detect_top, args=(window, sx, sy, SLEEP_TIME), daemon=True)
                th.start()
                window['start'].update("stop")
            else:
                stop_thread = True
                th.join()
                stop_thread = False
                print(f'スコア検出スレッド終了。')
                window['start'].update("start")
        elif ev.startswith('reset'):
            print(f'プレイ回数と合計スコアをリセットします。')
            today_plays  = 0
            today_notes  = 0
            notes_ran    = 0
            notes_battle = 0
            window['today'].update(value=f"0")
            window['plays'].update(value=f"0")
            for i in range(6):
                window[f"judge{i}"].update(value='0')
        elif ev.startswith('test_screenshot'):
            th_scshot = threading.Thread(target=get_screen_all, args=(int(val['sx']), int(val['sy']), width, height), daemon=True)
            th_scshot.start()
        elif ev.startswith('tweet'):
            cur_notes = today_notes
            msg = f"今日は{today_plays:,}曲プレイし、{cur_notes:,}ノーツ叩きました。\n#INFINITAS_daken_counter"
            encoded_msg = urllib.parse.quote(msg)
            webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")
        elif ev == '-GAUGE-':
            window['gauge'].update(value=val[ev])
        elif ev == '-PLAYOPT-':
            window['playopt'].update(value=val[ev])
        elif ev == '-THREAD-':
            dat = val[ev].split(' ')
            cmd = dat[0]
            cur = int(dat[1])
            tmp_today_notes = cur+today_notes
            window['today'].update(value=f"{tmp_today_notes}")
            try:
                tmp_judge = [judge[i]+int(dat[2+i]) for i in range(6)] # 前の曲までの値judge[i]に現在の曲の値dat[2+i]を加算したもの
            except:
                print(f'error!!! datの値が不正?, dat={dat}')
                tmp_judge = judge[i]

            for i in range(6):
                window[f"judge{i}"].update(value=tmp_judge[i])
            srate = 0.0
            if judge[0]+judge[1]+judge[2]+judge[5] > 0:
                srate = (tmp_judge[0]*2+tmp_judge[1])/(tmp_judge[0]+tmp_judge[1]+tmp_judge[2]+tmp_judge[5])*50
            window['srate'].update(value=f"{srate:.2f} %")
            if cmd == 'end':
                today_plays += 1
                today_notes += pre_cur
                window['today'].update(value=f"{today_notes}")
                for i in range(6):
                    judge[i] += int(dat[2+i])
            window['cur'].update(value=f"{cur}")
            window['plays'].update(value=f"{today_plays}")
            ### スコアなどのセーブデータはここで更新(安全なresetとさせるため)
            settings['plays'] = today_plays
            settings['total_score'] = tmp_today_notes
            settings['judge'] = tmp_judge
            gen_notes_xml(cur,tmp_today_notes,today_plays, notes_ran, notes_battle, tmp_judge)
            pre_cur = cur
        elif ev == '-ENDSONG-': # TODO 将来的にコマンドを分けたい
            dat = val[ev].split(' ')
            score = int(dat[0])
            option = val[ev][len(dat[0])+1:]
            if 'BATTLE' in option:
                notes_battle += cur
            elif 'RAN / RAN' in option: # 両乱だけ数えるか片乱だけ数えるか未定
                notes_ran += cur
        elif ev == '-SCRSHOT_ERROR-':
            stop_thread = True
            th.join()
            stop_thread = False
            #print(f"th.is_alive:{th.is_alive()}")
            print(f"スコア検出スレッドが異常終了しました。再スタートします。")
            sx = int(val['sx'])
            sy = int(val['sy'])
            th = threading.Thread(target=detect_top, args=(window, sx, sy, SLEEP_TIME), daemon=True)
            th.start()
        elif ev == 'Y:89':
            #print('隠しコマンド')
            #url = sg.popup_get_text('YoutubeLiveのURL(Studioでも可)を入力してください。', 'Youtube準備用コマンド')
            q = gui_ytinfo(settings['series_query'])
            settings['series_query'] = q
            #get_ytinfo(url)

if __name__ == '__main__':
    gui()
