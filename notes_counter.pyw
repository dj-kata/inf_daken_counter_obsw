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
import copy
from bs4 import BeautifulSoup
from obssocket import OBSSocket
from PIL import Image, ImageFilter

### 固定値
SWNAME = 'INFINITAS打鍵カウンタ'
SWVER  = 'v2.0'

width  = 1280
height = 720
digit_vals = [43860,16065,44880,43095,32895,43605,46920,28050,52020,49215]
mdigit_vals = [9690,3570,9945,8415,7650,9945,10965,6885,10710,11475]
mdigit_vals = [10965,3570,9945,8925,8160,9945,12240,7140,11730,12495] # 10/5に急に変わった？
savefile   = 'settings.json'
FONT = ('Meiryo',12)
FONTs = ('Meiryo',8)

imgpath = 'C:\\Users\\katao\\OneDrive\\デスクトップ\\hoge.png'

if len(sys.argv) > 1:
    savefile = sys.argv[1]

class DakenCounter:
    def __init__(self, savefile=savefile):
    ### グローバル変数
        self.stop_thread = False # メインスレッドを強制停止するために使う
        self.window      = False
        self.savefile    = savefile
        self.load_settings()
        self.obs = OBSSocket('localhost', 4455, 'panipaninoakuma', 'INFINITAS', imgpath)

    def load_settings(self):
        default_val = {'target_srate':'72%', 'sleep_time':'1.0',
        'plays':'0','total_score':'0', 'run_on_boot':False, 'reset_on_boot':False, 'lx':0, 'ly':0,
        'series_query':'#[number]','judge':[0,0,0,0,0,0], 'playopt':'OFF'}
        ret = {}
        try:
            with open(self.savefile) as f:
                ret = json.load(f)
                print(f"設定をロードしました。\n")
        except Exception as e:
            print(e)
            print(f"有効な設定ファイルなし。デフォルト値を使います。")

        ### 後から追加した値がない場合にもここでケア
        for k in default_val.keys():
            if not k in ret.keys():
                print(f"{k}が設定ファイル内に存在しません。デフォルト値({default_val[k]}を登録します。)")
                ret[k] = default_val[k]
        self.settings = ret
        return ret

    def save_settings(self):
        with open(self.savefile, 'w') as f:
            json.dump(self.settings, f, indent=2)

    # icon用
    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # デバッグ用、現在設定している座標の画像を切り出してファイルに保存。
    def get_screen_all(self): 
        print(f"10秒後にキャプチャ画像をtest.bmpに保存します。")
        print(f"また、全モニタの画像をwhole.bmpに保存します。")
        print(f"test.bmpがINFINITASで使うモニタとなっていることを確認してください。")
        time.sleep(10)
        print(f"\n10秒経過。キャプチャを実行します。")
        sc = self.obs.save_screenshot()

    ### プレイサイド検出を行う
    def detect_playside(self):
        ret = False
        target = ['1p-l', '1p-r', '2p-l', '2p-r', '1p_nograph', '2p_nograph', 'dp-l', 'dp-r'] # BGA表示エリアの位置
        for t in target:
            det = self.detect_judge(t)
            if det[0] == '0':
                ret = t
        return ret

    ### オプション検出を行う
    def detect_option(self):
        playopt = False
        self.obs.save_screenshot()
        whole = Image.open(imgpath)
        flip = ''
        left = False
        right = False
        assist = ''
        gauge = False
        battle = ''
        ### オプション画面かどうかを検出
        px0 = whole.getpixel((43,33)) == (255,0,0,255)
        px1 = whole.getpixel((44,424)) == (0xff,0x4f,0xbb,255)
        px2 = whole.getpixel((114,645)) == (0xff,0x4f,0xbb,255)
        px_dp = whole.getpixel((1070,345)) == (0x0,0x29,0x32,255)
        px_sp = whole.getpixel((905,358)) == (0x0,0x29,0x32,255)

        if px0 and px1 and px2 and (px_sp or px_dp): # オプション画面かどうか
            flip_off   = whole.getpixel((932,200)) == (0xff,0x6c,0x0,255)
            flip_on    = whole.getpixel((932,230)) == (0xff,0x6c,0x0,255)

            isbattle = whole.getpixel((148,536)) != (0xff,0xff,0xff,255) # 白かどうかをみる、白ならオフ
            hran   = whole.getpixel((167,555)) != (0xff,0xff,0xff,255) # 白かどうかをみる、白ならオフ

            if isbattle:
                battle = 'BATTLE, '

            if px_dp: # DP
                normal    = whole.getpixel((683,390)) == (0xff, 0x6c, 0x0,255)
                a_easy    = whole.getpixel((742,422)) != (0, 0, 0,255)
                easy      = whole.getpixel((683,456)) == (0xff, 0x6c, 0x0,255)
                hard      = whole.getpixel((683,489)) == (0xff, 0x6c, 0x0,255)
                ex_hard   = whole.getpixel((682,522)) == (0xff, 0x6c, 0x0,255)
                for pix,val in zip([normal,a_easy,easy,hard,ex_hard],['NORMAL','A-EASY','EASY','HARD', 'EX-HARD']):
                    if pix:
                        gauge = val

                left_off     = whole.getpixel((390,390)) == (0xff, 0x6c, 0x0, 255)
                left_ran     = whole.getpixel((390,422)) == (0xff, 0x6c, 0x0, 255)
                left_rran    = whole.getpixel((384,455)) == (0xff, 0x6c, 0x0, 255)
                left_sran    = whole.getpixel((384,489)) == (0xff, 0x6c, 0x0, 255)
                left_mirror  = whole.getpixel((390,520)) == (0xff, 0x6c, 0x0, 255)

                right_off     = whole.getpixel((536,390)) == (0xff, 0x6c, 0x0, 255)
                right_ran     = whole.getpixel((536,422)) == (0xff, 0x6c, 0x0, 255)
                right_rran    = whole.getpixel((530,455)) == (0xff, 0x6c, 0x0, 255)
                right_sran    = whole.getpixel((530,489)) == (0xff, 0x6c, 0x0, 255)
                right_mirror  = whole.getpixel((536,520)) == (0xff, 0x6c, 0x0, 255)

                sync_ran      = whole.getpixel((394,554)) == (0xff, 0x6c, 0x0, 255)
                symm_ran      = whole.getpixel((394,585)) == (0xff, 0x6c, 0x0, 255)

                assist_off    = whole.getpixel((830,390)) == (0xff, 0x6c, 0x0, 255)
                assist_as     = whole.getpixel((858,426)) == (0xff, 0x6c, 0x0, 255)
                assist_legacy = whole.getpixel((880,489)) == (0xff, 0x6c, 0x0, 255)

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
                normal    = whole.getpixel((524,390)) == (0xff, 0x6c, 0x0, 255)
                a_easy    = whole.getpixel((582,422)) != (0, 0, 0, 255)
                easy      = whole.getpixel((524,456)) == (0xff, 0x6c, 0x0, 255)
                hard      = whole.getpixel((524,489)) == (0xff, 0x6c, 0x0, 255)
                ex_hard   = whole.getpixel((518,522)) == (0xff, 0x6c, 0x0, 255)
                for pix,val in zip([normal,a_easy,easy,hard,ex_hard],['NORMAL','A-EASY','EASY','HARD', 'EX-HARD']):
                    if pix:
                        gauge = val

                right_off     = whole.getpixel((375,391)) == (0xff, 0x6c, 0x0, 255)
                right_ran     = whole.getpixel((375,424)) == (0xff, 0x6c, 0x0, 255)
                right_rran    = whole.getpixel((369,457)) == (0xff, 0x6c, 0x0, 255)
                right_sran    = whole.getpixel((369,489)) == (0xff, 0x6c, 0x0, 255)
                right_mirror  = whole.getpixel((375,520)) == (0xff, 0x6c, 0x0, 255)

                assist_off    = whole.getpixel((680,390)) == (0xff, 0x6c, 0x0, 255)
                assist_as     = whole.getpixel((699,426)) == (0xff, 0x6c, 0x0, 255)
                assist_legacy = whole.getpixel((720,489)) == (0xff, 0x6c, 0x0, 255)
                # 右手
                sran_str = 'S-RAN'
                if hran:
                    sran_str = 'H-RAN'
                for pix,val in zip([right_off,right_ran,right_rran,right_mirror,right_sran],['OFF','RAN','R-RAN','MIR',sran_str]):
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
    def get_judge_img(self, playside):
        self.obs.save_screenshot()
        img = Image.open(imgpath)
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
    def detect_judge(self, playside):
        sc,digits = self.get_judge_img(playside)
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
                #if (playside == '2p-r') and (val>0):
                #    print(f"val={val}, tmp(det)={tmp}")
            #if (playside == '2p-r') and (line!=''):
            #    print(f"line={line}")
            ret.append(line)
        return ret

    ### 無限ループにする(終了時は上から止める)
    ### 曲の開始・終了を数字から検出し、境界処理を行う
    ### 曲中は検出したスコアをprintする
    def detect_top(self, sleep_time):
        pre_det = ''
        pre_judge = ['0','0','0','0','0','0']
        pre_score = 0
        stop_local = False
        playside = False
        self.playopt = '' # 曲開始タイミングとオプション検出タイミングは一致しないため、最後の値を覚えておく
        self.gauge   = ''
        print(f'スコア検出スレッド開始。')
        while True:
            while True: # 曲開始までを検出
                #print('test')
                try:
                    playside = self.detect_playside()
                    tmp_playopt, tmp_gauge = self.detect_option()
                    if tmp_playopt and tmp_gauge:
                        if self.playopt != tmp_playopt:
                            self.window.write_event_value('-PLAYOPT-', tmp_playopt)
                        if self.gauge != tmp_gauge:
                            self.window.write_event_value('-GAUGE-', tmp_gauge)
                        self.playopt = tmp_playopt
                        self.gauge = tmp_gauge
                        self.gen_opt_xml(self.playopt, self.gauge) # 常時表示オプションを書き出す
                    if playside: # 曲頭を検出
                        print(f'曲開始を検出しました。\nEXスコア取得開始。mode={playside.upper()}')
                        self.gen_opt_xml(playopt, gauge, True) # 常時表示+曲中のみデータの書き出し
                        break
                except Exception as e:
                    stop_local = True
                    print(f'スクリーンショットに失敗しました。{e}')
                    self.window.write_event_value('-SCRSHOT_ERROR-', " ")
                    break
                if self.stop_thread:
                    stop_local = True
                    break
                #time.sleep(sleep_time)
                time.sleep(0.3) # オプション取得のためにここは短くしたほうがよさそう？

            if stop_local:
                break

            while True: # 曲中の処理
                det = self.detect_judge(playside)
                try:
                    score = int(det[0])+int(det[1])+int(det[2])
                    self.window.write_event_value('-THREAD-', f"cur {score} {det[0]} {det[1]} {det[2]} {det[3]} {det[4]} {det[5]}")
                    pre_score = score
                    pre_judge = det
                except ValueError: # intに変換できない数値を検出&暗転の両方を見る
                    self.obs.save_screenshot()
                    tmp = Image.open(imgpath)
                    topleft = tmp.crop((0,0,120,120))
                    #print(np.array(topleft).sum(), np.array(topleft).shape)
                    if np.array(topleft).sum()==120*120*255: # alpha=255の分を考慮
                        self.window.write_event_value('-ENDSONG-', f"{pre_score} {playopt}")
                        self.window.write_event_value('-THREAD-', f"end {pre_score} {pre_judge[0]} {pre_judge[1]} {pre_judge[2]} {pre_judge[3]} {pre_judge[4]} {pre_judge[5]}")
                        print(f'曲終了を検出しました。 => {pre_score}')
                        self.gen_opt_xml(playopt, gauge) # 曲中のみデータの削除
                        break

                time.sleep(sleep_time)

    def gen_notes_xml(self, cur,today, plays, notes_ran, notes_battle, judge):
        srate = 0.0
        if judge[0]+judge[1]+judge[2]+judge[5] > 0:
            srate = (judge[0]*2+judge[1])/(judge[0]+judge[1]+judge[2]+judge[5])*50
        f = codecs.open('data.xml', 'w', 'utf-8')
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
    <Items>
        <playcount>{plays}</playcount>
        <cur_notes>{cur}</cur_notes>
        <today_notes>{today}</today_notes>
        <notes_ran>{notes_ran}</notes_ran>
        <notes_battle>{notes_battle}</notes_battle>
        <pg>{judge[0]}</pg>
        <gr>{judge[1]}</gr>
        <gd>{judge[2]}</gd>
        <bd>{judge[3]}</bd>
        <pr>{judge[4]}</pr>
        <cb>{judge[5]}</cb>
        <score_rate>{srate:.1f}</score_rate>
    </Items>''')
        f.close()

    def gen_opt_xml(self, opt, in_gauge, onSong=False): # onSong: 曲開始時の呼び出し時にTrue->曲中のみ文字列を設定
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

    def parse_url(self, url):
        ret = False
        if re.search('www.youtube.com.*v=', url):
            ret = re.sub('.*v=', '', url)
        elif re.search('livestreaming\Z', url):
            ret = url.split('/')[-2]
        return ret

    def write_series_xml(self, series, basetitle):
        print(f"series.xmlを更新しました => {series}\n")
        f=codecs.open('series.xml', 'w', 'utf-8')
        f.write(f'''<?xml version="1.0" encoding="utf-8"?>
    <Items>
        <series>{series}</series>
        <basetitle>{basetitle}</basetitle>
    </Items>''')
        f.close()
    def get_ytinfo(self, url):
        liveid = self.parse_url(url)
        ret = False
        if liveid:
            regular_url = f"https://www.youtube.com/watch?v={liveid}"
            r = requests.get(regular_url)
            soup = BeautifulSoup(r.text,features="html.parser")
            title = re.sub(' - YouTube\Z', '', soup.find('title').text)
            #print(f"liveid = {liveid}")
            print(f"配信タイトル:\n{title}\n")
            print(f"ツイート用:\n{title}\n{regular_url}\n")
            print(f"コメント欄用:\nhttps://www.youtube.com/live_chat?is_popout=1&v={liveid}\n")

            encoded_title = urllib.parse.quote(f"{title}\n{regular_url}\n")
            webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_title}")
            ret = title
        else:
            print('無効なURLです\n')
        return ret

    def gui_ytinfo(self, default_query='#[number]'):
        sg.theme('SystemDefault')
        FONT = ('Meiryo',12)
        ico=self.ico_path('icon.ico')
        right_click_menu = ['&Right', ['貼り付け']]
        layout = [
            [sg.Text("YoutubeLive URL(配信、スタジオ等)", font=FONT)],
            [sg.Input("", font=FONT, key='youtube_url', size=(50,1),right_click_menu=right_click_menu)],
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
                title = self.get_ytinfo(url)
                if title:
                    series = ''
                    if re.search(query, title):
                        series = re.search(query, title).group()
                    basetitle = re.sub('【[^【】]*】', '', title.replace(series, ''))
                    self.write_series_xml(series, basetitle)
                    window.close()
                    break
            elif ev == '貼り付け':
                try:
                    clipboard_text = window["youtube_url"].Widget.clipboard_get()
                    insert_pos = window["youtube_url"].Widget.index("insert")
                    window["youtube_url"].Widget.insert(insert_pos, clipboard_text)
                except:
                    pass

        return default_query

    def gui_setting(self): # GUI設定
        if self.window:
            self.window.close()
        sg.theme('SystemDefault')

    def gui_info(self): #情報表示用
        self.mode = 'info'
        if self.window:
            self.window.close()
        layout = [
            [sg.Text(f'{SWNAME}', font=FONT)],
            [sg.Text(f'version: {SWVER}', font=FONT)],
            [sg.Text(f'')],
            [sg.Text(f'author: かたさん (@cold_planet_)')],
            [sg.Text(f'https://github.com/dj-kata/inf_daken_counter_obsw', enable_events=True, key="URL https://github.com/dj-kata/inf_daken_counter_obsw", font=('Meiryo', 10, 'underline'))],
            [sg.Button('OK', key='btn_close_info', font=FONT)],
        ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window(f"{SWNAME}について", layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico,location=(self.settings['lx'], self.settings['ly']), size=(400,220))

    def gui_main(self): # GUI設定
        self.mode = 'main'
        if self.window:
            self.window.close()

        sg.theme('SystemDefault')
        menuitems = [['ファイル',['設定',]],['ヘルプ',[f'{SWNAME}について']]]
        layout = [
            [sg.Menubar(menuitems, key='menu')],
            [sg.Button('start', key='start', font=FONT, size=(27,1)), sg.Button('reset', key='reset', font=FONT), sg.Button('tweet', key='tweet', font=FONT), sg.Button('test', key='test_screenshot', font=FONT)],
            [sg.Text('plays:', font=FONT), sg.Text('0', key='plays', font=FONT)
            ,sg.Text(' ', font=FONT, size=(5,1))
            ,sg.Checkbox("起動時に即start", default=False, font=FONT, key='run_on_boot')
            ,sg.Checkbox("start時にreset", default=False, font=FONT, key='reset_on_boot')
            ],
            [sg.Text("ノーツ数 ", font=FONT),sg.Text("cur:", font=FONT),sg.Text("0", key='cur',font=FONT, size=(7,1)),sg.Text("Total:", font=FONT),sg.Text("0", key='today',font=FONT)],
            [sg.Text('PG:',font=FONTs),sg.Text('0',key='judge0',font=FONTs),sg.Text('GR:',font=FONTs),sg.Text('0',key='judge1',font=FONTs),sg.Text('GD:',font=FONTs),sg.Text('0',key='judge2',font=FONTs),sg.Text('BD:',font=FONTs),sg.Text('0',key='judge3',font=FONTs),sg.Text('PR:',font=FONTs),sg.Text('0',key='judge4',font=FONTs),sg.Text('CB:',font=FONTs),sg.Text('0',key='judge5',font=FONTs)],
            [sg.Text("ゲージ:", font=FONT),sg.Text(" ", key='gauge',font=FONT),sg.Text('平均スコアレート:',font=FONT),sg.Text('0 %',key='srate',font=FONT)],
            [sg.Text("option:", font=FONT),sg.Text(" ", key='playopt',font=FONT)],
            [sg.Output(size=(63,8), key='output', font=('Meiryo',9))] # ここを消すと標準出力になる
            ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window('打鍵カウンタ for INFINITAS', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico,location=(self.settings['lx'], self.settings['ly']))
        self.window['run_on_boot'].update(self.settings['run_on_boot'])
        self.window['reset_on_boot'].update(self.settings['reset_on_boot'])
        self.window['today'].update(value=f"{self.today_notes}")
        self.window['plays'].update(value=f"{self.today_plays}")
        for i in range(6):
            self.window[f'judge{i}'].update(value=self.judge[i])
        self.window['srate'].update(value=f"{self.srate:.2f} %")
        self.window['playopt'].update(value=self.settings['playopt'])

    def main(self):
        # 設定をもとにGUIの値を変更
        SLEEP_TIME = float(self.settings['sleep_time'])

        self.today_notes = int(self.settings['total_score'])
        self.today_plays = int(self.settings['plays'])
        self.playopt     = self.settings['playopt']
        self.judge       = self.settings['judge']
        self.srate       = 0.0
        if self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5] > 0:
            self.srate = (self.judge[0]*2+self.judge[1])/(self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5])*50
        self.gui_main()
        self.notes_ran = 0
        self.notes_battle  = 0
        pre_cur = 0
        running = self.settings['run_on_boot'] # 実行中かどうかの区別に使う。スレッド停止用のstop_threadとは役割が違うので注意
        th = False

        if self.settings['run_on_boot']: # 起動後即開始設定の場合
            print('自動起動設定が有効です。')
            if self.settings['reset_on_boot']:
                self.today_notes = 0
                self.today_plays = 0
                self.notes_ran = 0
                self.notes_battle  = 0
                self.judge = [0,0,0,0,0,0]
            running = True
            th = threading.Thread(target=self.detect_top, args=(SLEEP_TIME,), daemon=True)
            self.gen_notes_xml(0,self.today_notes,self.today_plays, self.notes_ran, self.notes_battle, self.judge)
            th.start()
            self.window['start'].update("stop")

        while True:
            ev, val = self.window.read()
            #print(f"event='{ev}', values={val}")
            # 設定を最新化
            if self.settings and val and self.mode=='main': # 起動後、そのまま何もせずに終了するとvalが拾われないため対策している
                # 今日のノーツ数とか今日の回数とかはここに記述しないこと(resetボタンを押すと即反映されてしまうため)
                self.settings['lx'] = self.window.current_location()[0]
                self.settings['ly'] = self.window.current_location()[1]
                self.settings['run_on_boot'] = val['run_on_boot'] # TODO KeyErrorが出ているが原因が分かっていない
                self.settings['reset_on_boot'] = val['reset_on_boot']
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'btn_close_info'):
                if self.mode == 'info':
                    self.gui_main()
                else:
                    self.save_settings()
                    break
            elif ev.startswith('start'):
                running = not running
                if running:
                    if self.settings['reset_on_boot']:
                        print('自動リセット設定が有効です。')
                        self.today_notes = 0
                        self.today_plays = 0
                        self.notes_ran = 0
                        self.notes_battle = 0
                        self.judge = [0,0,0,0,0,0]
                    th = threading.Thread(target=self.detect_top, args=(SLEEP_TIME,), daemon=True)
                    self.gen_notes_xml(0,self.today_notes,self.today_plays, self.notes_ran, self.notes_battle, self.judge)
                    th.start()
                    self.window['start'].update("stop")
                else:
                    self.stop_thread = True
                    th.join()
                    self.stop_thread = False
                    print(f'スコア検出スレッド終了。')
                    self.window['start'].update("start")
            elif ev.startswith('reset'):
                print(f'プレイ回数と合計スコアをリセットします。')
                self.today_plays  = 0
                self.today_notes  = 0
                self.notes_ran    = 0
                self.notes_battle = 0
                self.window['today'].update(value=f"0")
                self.window['plays'].update(value=f"0")
                for i in range(6):
                    self.window[f"judge{i}"].update(value='0')
            elif ev.startswith('test_screenshot'):
                th_scshot = threading.Thread(target=self.get_screen_all, daemon=True)
                th_scshot.start()
            elif ev.startswith('tweet'):
                cur_notes = today_notes
                srate = 0.0
                if judge[0]+judge[1]+judge[2]+judge[5] > 0:
                    srate = (judge[0]*2+judge[1])/(judge[0]+judge[1]+judge[2]+judge[5])*50
                msg = f"今日は{today_plays:,}曲プレイし、{cur_notes:,}ノーツ叩きました。\n"
                msg += f'(PG:{judge[0]:,}, GR:{judge[1]:,}, GD:{judge[2]:,}, BD:{judge[3]:,}, PR:{judge[4]:,}, CB:{judge[5]:,})\n'
                msg += f'(スコアレート: {srate:.1f}%)\n'
                msg += '#INFINITAS_daken_counter'
                encoded_msg = urllib.parse.quote(msg)
                webbrowser.open(f"https://twitter.com/intent/tweet?text={encoded_msg}")
            elif ev == '-GAUGE-':
                self.window['gauge'].update(value=val[ev])
            elif ev == '-PLAYOPT-':
                self.window['playopt'].update(value=val[ev])
            elif ev == '-THREAD-':
                dat = val[ev].split(' ')
                cmd = dat[0]
                cur = int(dat[1])
                tmp_today_notes = cur+self.today_notes
                self.window['today'].update(value=f"{tmp_today_notes}")
                try:
                    tmp_judge = [judge[i]+int(dat[2+i]) for i in range(6)] # 前の曲までの値judge[i]に現在の曲の値dat[2+i]を加算したもの
                except:
                    print(f'error!!! datの値が不正?, dat={dat}')
                    tmp_judge = copy.copy(judge)

                for i in range(6):
                    self.window[f"judge{i}"].update(value=tmp_judge[i])
                self.srate = 0.0
                if tmp_judge[0]+tmp_judge[1]+tmp_judge[2]+tmp_judge[5] > 0:
                    self.srate = (tmp_judge[0]*2+tmp_judge[1])/(tmp_judge[0]+tmp_judge[1]+tmp_judge[2]+tmp_judge[5])*50
                self.window['srate'].update(value=f"{self.srate:.2f} %")
                if cmd == 'end':
                    self.today_plays += 1
                    self.today_notes += pre_cur
                    self.window['today'].update(value=f"{self.today_notes}")
                    for i in range(6):
                        try:
                            judge[i] += int(dat[2+i])
                        except ValueError:
                            print(f'{i}番目の値の取得に失敗。skipします。')
                            judge[i] = tmp_judge[i]

                self.window['cur'].update(value=f"{cur}")
                self.window['plays'].update(value=f"{today_plays}")
                ### スコアなどのセーブデータはここで更新(安全なresetとさせるため)
                self.settings['plays'] = today_plays
                self.settings['total_score'] = tmp_today_notes
                self.settings['judge'] = tmp_judge
                self.gen_notes_xml(cur,tmp_today_notes,self.today_plays, self.notes_ran, self.notes_battle, tmp_judge)
                pre_cur = cur
            elif ev == '-ENDSONG-': # TODO 将来的にコマンドを分けたい
                dat = val[ev].split(' ')
                score = int(dat[0])
                #self.option = val[ev][len(dat[0])+1:]
                if 'BATTLE' in self.playopt:
                    notes_battle += cur
                elif ('RAN / RAN' in self.playopt) or ('S-RAN / S-RAN' in self.playopt) or ('H-RAN / H-RAN' in self.playopt): # 両乱だけ数えるか片乱だけ数えるか未定
                    notes_ran += cur
            elif ev == '-SCRSHOT_ERROR-':
                self.stop_thread = True
                th.join()
                self.stop_thread = False
                #print(f"th.is_alive:{th.is_alive()}")
                print(f"スコア検出スレッドが異常終了しました。再スタートします。")
                th = threading.Thread(target=self.detect_top, args=(SLEEP_TIME,), daemon=True)
                th.start()
            elif ev == 'Y:89':
                #print('隠しコマンド')
                #url = sg.popup_get_text('YoutubeLiveのURL(Studioでも可)を入力してください。', 'Youtube準備用コマンド')
                q = self.gui_ytinfo(self.settings['series_query'])
                self.settings['series_query'] = q
                #get_ytinfo(url)
            elif ev in ("コピー"):
                # try - except で弾かれたとき用に、バックアップの値を用意しておく
                backup = self.window["output"].Widget.clipboard_get()
                self.window["output"].Widget.clipboard_clear()
                try:
                    selected_text = self.window["output"].Widget.selection_get()
                    self.window["output"].Widget.clipboard_append(selected_text)
                except:
                    self.window["output"].Widget.clipboard_append(backup)
                    pass

            elif ev in ('btn_setting', '設定'):
                self.gui_setting()

            elif ev  == f'{SWNAME}について':
                self.gui_info()

            elif ev.startswith('URL '): # URLをブラウザで開く;info用
                url = ev.split(' ')[1]
                webbrowser.open(url)

if __name__ == '__main__':
    a = DakenCounter()
    a.main()
