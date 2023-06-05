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
from tkinter import filedialog
import datetime
import imagehash
from daken_logger import DakenLogger
from log_manager import LogManager
import pickle
from pathlib import Path
from recog import *
from manage_output import *
import logging, logging.handlers
import traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    './dbg.log',
    encoding='utf-8',
    maxBytes=1024*1024*20,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)

#hdl2 = logging.StreamHandler(sys.stdout)
#hdl2.setLevel(logging.INFO)
#hdl2_formatter = logging.Formatter('%(message)s')
#hdl2.setFormatter(hdl2_formatter)
#logger.addHandler(hdl2)

### TODO
# スコアは差分を送るんじゃなくて、best、cur両方を送ってHTML側で計算させる?
# loggerの利用

### 固定値
SWNAME = 'INFINITAS打鍵カウンタ'
SWVER  = 'v2.0.11'

width  = 1280
height = 720
digit_vals = [43860,16065,44880,43095,32895,43605,46920,28050,52020,49215]
mdigit_vals = [10965,3570,9945,8925,8160,9945,12240,7140,11730,12495]
savefile   = 'settings.json'
FONT = ('Meiryo',12)
FONTs = ('Meiryo',8)

if len(sys.argv) > 1:
    savefile = sys.argv[1]

class DakenCounter:
    def __init__(self, savefile=savefile):
    ### グローバル変数
        self.stop_thread = False # メインスレッドを強制停止するために使う
        self.window      = False
        try:
            with open('noteslist.pkl', 'rb') as f:
                self.noteslist = pickle.load(f)
        except:
            self.noteslist   = False
        self.difflist = ['SPB', 'SPN', 'SPH', 'SPA', 'DPN', 'DPH', 'DPA']
        self.savefile    = savefile
        self.alllogfile  = './alllog.pkl'
        self.alllog      = []
        self.dict_alllog = {}
        self.todaylog    = []
        self.write_today_update_xml()
        self.load_alllog()
        self.load_settings()
        self.valid_playside = ''
        self.startdate = False # 最後にスレッドを開始した日付を記録。打鍵ログ保存用
        self.imgpath = os.path.dirname(__file__) + '\\tmp.png'
        try:
            self.obs = OBSSocket(self.settings['host'], self.settings['port'], self.settings['passwd'], self.settings['obs_source'], self.imgpath)
        except:
            self.obs = False
            print('obs socket error!')
            pass

    def load_settings(self):
        default_val = {'target_srate':'72%', 'sleep_time':'1.0',
        'plays':'0','total_score':'0', 'run_on_boot':False, 'reset_on_boot':False, 'lx':0, 'ly':0,
        'series_query':'#[number]','judge':[0,0,0,0,0,0], 'playopt':'OFF',
        'host':'localhost', 'port':'4444', 'passwd':'', 'obs_source':'INFINITAS',
        'autosave_lamp':False,'autosave_djlevel':False,'autosave_score':False,'autosave_bp':False,'autosave_dbx':'no',
        'autosave_dir':'','autosave_always':False, 'autosave_mosaic':False, 'todaylog_always_push':True,
        'todaylog_dbx_always_push':True,
        'obs_scene':'', 'obs_itemid_history_cursong':False, 'obs_itemid_today_result':False, 'obs_scenename_history_cursong':'', 'obs_scenename_today_result':''
        }
        ret = {}
        try:
            with open(self.savefile) as f:
                ret = json.load(f)
                print(f"設定をロードしました。\n")
        except Exception as e:
            logger.debug(traceback.format_exc())
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

    def load_alllog(self):
        try: 
            with open(self.alllogfile, 'rb') as f:
                self.alllog = pickle.load(f)
        except Exception as e:
            print('プレーログファイル(alllog.pkl)を作成します。')
            with open(self.alllogfile, 'wb') as f:
                pickle.dump([], f)
        for s in self.alllog:
            key = f"{s[1]}({s[2]})"
            if not key in self.dict_alllog.keys():
                self.dict_alllog[key] = []
            self.dict_alllog[key].append(s)
    
    def save_alllog(self):
        with open(self.alllogfile, 'wb') as f:
            pickle.dump(self.alllog, f)

    def save_dakenlog(self):
        tmp = DakenLogger()
        if self.today_plays > 0:
            tmp.add(self.startdate, self.today_plays, self.judge)
            tmp.save()

    def gen_weekly_graph(self):
        tmp = DakenLogger()
        tmp.gen_entire_graph()
        print('graph generated')

    # icon用
    def ico_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    # デバッグ用、現在設定している座標の画像を切り出してファイルに保存。
    def get_screen_all(self): 
        print(f"10秒後にキャプチャ画像をtest.pngに保存します。")
        time.sleep(10)
        print(f"\n10秒経過。キャプチャを実行します。")
        imgpath = os.path.dirname(__file__) + '\\test.png'
        sc = self.obs.save_screenshot_dst(imgpath)
        print(f'-> {imgpath}')

    def save_result(self, result):
        img = Image.open(self.imgpath)
        now = datetime.datetime.now()
        fmtnow = format(now, "%Y%m%d_%H%M%S")
        dst = f"{self.settings['autosave_dir']}/infinitas_{fmtnow}.png"
        if result != False:
            title = result[1]
            for ch in ('\\', '/', ':', '*', '?', '"', '<', '>', '|'):
                title = title.replace(ch, '')
            title = f"{title[:120]}_{result[2]}"
            lamp  = result[7].replace('-', '')
            score = f'ex{result[9]}'
            bp    = ''
            with_scratch = ''
            if result[11] != None:
                bp = f'_bp{result[11]}'
            if not 'A-SCR' in self.playopt:
                with_scratch='皿あり'
            if ('BATTLE, MIR / OFF' in self.playopt) or ('BATTLE, OFF / MIR' in self.playopt):
                title+=f'_{with_scratch}DBM'
            elif ('BATTLE, RAN / RAN' in self.playopt):
                title+=f'_{with_scratch}DBR'
            elif ('BATTLE, S-RAN / S-RAN' in self.playopt):
                title+=f'_{with_scratch}DBSR'
            elif ('BATTLE' in self.playopt):
                title+=f'_{with_scratch}DB'
            dst = f"{self.settings['autosave_dir']}/inf_{title}_{lamp}_{score}{bp}_{fmtnow}.png"
        print(f"自動保存します。 -> {dst})")
        if self.settings['autosave_mosaic']: # TODO ライバルエリアがあるかどうかを判定する
            rival_1p = 0
            rival_2p = 0
            for y in range(6):
                sc = img.crop((1215,195+y*80,1255,203+y*80))
                rival_1p += np.array(sc).sum()
                sc = img.crop((360,195+y*80,400,203+y*80))
                rival_2p += np.array(sc).sum()
            logger.debug(f"sum 1p,2p = {rival_1p:,}, {rival_2p:,}")
            result_threshold = 542400
        
            # ライバル欄があるかどうかの判定
            rival_mode = 'none'
            if rival_1p == result_threshold:
                rival_mode = '1p'
            elif rival_2p == result_threshold:
                rival_mode = '2p'

            # ライバルのモザイク処理
            img_array = np.array(img)
            self.obs.save_screenshot_dst(dst)
            if rival_mode == '1p': # ライバルエリアが右側
                rivalarea = img.crop((877,180,1212,655))
                rivalarea = rivalarea.resize((33,47))
                rivalarea = rivalarea.resize((335,475))
                rival_array = np.array(rivalarea)
                img_array[180:655, 877:1212] = rival_array
            elif rival_mode == '2p': # ライバルエリアが左側
                rivalarea = img.crop((22,180,357,655))
                rivalarea = rivalarea.resize((33,47))
                rivalarea = rivalarea.resize((335,475))
                rival_array = np.array(rivalarea)
                img_array[180:655, 22:357] = rival_array
            # 挑戦状エリアの処理
            if img.getpixel((540,591)) == (0,0,0,255):
                mailarea = img.crop((577,513,677,533))
                mailarea = mailarea.resize((10,2))
                mailarea = mailarea.resize((100,20))
                mail_array = np.array(mailarea)
                img_array[513:533, 577:677] = mail_array
            # ターゲット名も隠す(ライバルの名前が入っている可能性があるため)
            if ('1p' in self.valid_playside) or (self.valid_playside == 'dp-l'):
                targetarea = img.crop((29,456,241,476))
                targetarea = targetarea.resize((21,2))
                targetarea = targetarea.resize((212,20))
                img_array[456:476, 29:241] = targetarea
            else:
                targetarea = img.crop((910,456,1122,476))
                targetarea = targetarea.resize((21,2))
                targetarea = targetarea.resize((212,20))
                img_array[456:476, 910:1122] = targetarea

            out = Image.fromarray(img_array)
            out.save(dst)
        else: # ライバル欄を隠さない場合
            self.obs.save_screenshot_dst(dst)

    def autosave_result(self, result):
        ret = False
        isAlways  = (self.settings['autosave_always'])
        if result != False:
            img = Image.open(self.imgpath)

            update_area = []
            hash_target = imagehash.average_hash(Image.open('layout/update.png'))
            if ('1p' in self.valid_playside) or (self.valid_playside == 'dp-l'):
                for i in range(4):
                    tmp = imagehash.average_hash(img.crop((355,258+48*i,385,288+48*i)))
                    update_area.append(hash_target - tmp)

            else:
                for i in range(4):
                    tmp = imagehash.average_hash(img.crop((1235,258+48*i,1265,288+48*i)))
                    update_area.append(hash_target - tmp)

            if not 'BATTLE' in self.playopt:
                #print(f"update_area = {update_area}")
                isLamp    = (self.settings['autosave_lamp'])    and (update_area[0] < 10)
                isDjlevel = (self.settings['autosave_djlevel']) and (update_area[1] < 10)
                isScore   = (self.settings['autosave_score'])   and (update_area[2] < 10)
                isBp      = (self.settings['autosave_bp'])      and (update_area[3] < 10)
                # 左上にミッション進捗が出ていないかどうか
                isMissionEnd = img.getpixel((20,15)) != (44,61,77, 255)
                # 獲得bitと所持bitのwindowが出ていないかどうか
                tmp = np.array(img.crop((100,30,180,110)))
                tmp[:,:][-1] = 0
                isBitwindowEnd = tmp.sum() != 1914960

                if isLamp or isDjlevel or isScore or isBp or isAlways:
                    if isMissionEnd and isBitwindowEnd:
                        self.save_result(result)
                        ret = True
            else: # DBM, DBRなど
                lamp_table = ['NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO']
                if (self.settings['autosave_dbx'] == 'always') or ((self.settings['autosave_dbx'] == 'clear') and (lamp_table.index(result[7]) >= 2)) or isAlways:
                    self.save_result(result)
                    ret = True

        return ret
    
    ### 自動保存用ディレクトリ内の画像からDBを作成する
    # TODO 検索用キー配列を作成してから、
    def read_result_from_pic(self):
        paths = list(Path(self.settings['autosave_dir']).glob(r'*.png'))
        keys  = [self.alllog[i][1]+'___'+self.alllog[i][-1] for i in range(len(self.alllog))]
        cnt_add = 0
        cnt_edit = 0
        list_added = []
        for f in paths:
            if ('infinitas' in str(f).lower()) or ('inf_' in str(f)):
                try:
                    logger.debug(f)
                    result = self.ocr(f, onplay=False)
                    if result:
                        tmp_key = result[1]+'___'+result[-1]
                        judge = tmp_key in keys
                        print(f"{result[-1]} {result[1]}({result[2]}) - {result[7]}, score:{result[9]:,}, bp:{result[11]}")
                        logger.debug(f"judge:{judge}, file={f}, result={result}")
                        if not judge:
                            self.alllog.append(result)
                            logger.debug(f'===> added! ({f})')
                            cnt_add += 1
                            list_added.append(result)
                        else: # 同一リザルトが存在する場合、上書き
                            if self.alllog[keys.index(tmp_key)] != result:
                                self.alllog[keys.index(tmp_key)] = result
                                cnt_edit += 1
                except Exception:
                    logger.debug(traceback.format_exc())
        print(f"過去リザルトの登録完了。{cnt_add:,}件追加、{cnt_edit:,}件修正 -> 全{len(self.alllog):,}件")
        self.window.write_event_value('-OCR_FROM_IMG_END-', " ")

    ### プレイサイド検出を行う
    def detect_playside(self):
        ret = False
        target = ['1p-l', '1p-r', '2p-l', '2p-r', '1p_nograph', '2p_nograph', 'dp-l', 'dp-r'] # BGA表示エリアの位置
        for t in target:
            det = self.detect_judge(t)
            if det[0] == '0':
                ret = t
        if ret:
            self.valid_playside = ret # 最後に検出した有効なプレイサイドを覚えておく
        return ret
    
    def convert_option(self, opt, fumen):
        ret = '?'
        if opt != None:
            if opt.arrange == None:
                if fumen.startswith('SP'):
                    ret = 'OFF'
                elif fumen.startswith('DP'):
                    ret = 'OFF / OFF' 
            else:
                ret = opt.arrange.replace('/', ' / ')
            if opt.battle:
                ret = f"BATTLE, {ret}"
            if opt.flip != None:
                ret = f"{ret}, FLIP"
            if opt.assist != None:
                ret = f"{ret}, {opt.assist}"
            logger.debug(f"arrange:{opt.arrange}, battle:{opt.battle}, flip:{opt.flip}, assist:{opt.assist}, fumen:{fumen} ===> ret:{ret}")
        return ret

    # リザルト画像pngを受け取って、スコアツールの1entryとして返す
    def ocr(self, pic, onplay=True):
        ret = False
        tmp = []
        img = Image.open(pic)
        pic_info = np.array(img.crop((410,628,870,706)))
        info = recog.get_informations(pic_info)
        if onplay:
            if ('2p' in self.valid_playside) or (self.valid_playside == 'dp-r'):
                pic_playdata = np.array(img.crop((905,192,905+350,192+293)))
            else:
                pic_playdata = np.array(img.crop((25,192,25+350,192+293)))
        else: # 過去の画像から抽出している場合はrecogの機能で抽出しておく
            play_side = recog.get_play_side(np.array(img))
            if '2P' == play_side:
                pic_playdata = np.array(img.crop((905,192,905+350,192+293)))
            else:
                pic_playdata = np.array(img.crop((25,192,25+350,192+293)))
        playdata     = recog.get_details(pic_playdata)
        # 新方式がNGの場合、旧方式で曲名認識
        if info.music == None:
            img_mono   = img.convert('L')
            pic_info   = img_mono.crop((410,633,870,704))
            info.music = recog.get_music(pic_info)
        is_valid = (info.music!=None) and (info.level!=None) and (info.play_mode!=None) and (info.difficulty!=None) and (playdata.dj_level.current!=None) and (playdata.clear_type.current!=None) and (playdata.score.current!=None)
        #logger.debug(info.music, info.level, info.play_mode, info.difficulty, playdata.clear_type.current, playdata.dj_level.current, playdata.score.current)
        if is_valid:
            tmp.append(info.level)
            tmp.append(info.music)
            if info.difficulty != None:
                tmp.append(info.play_mode+info.difficulty[0])
            else:
                tmp.append(None)
            tmp.append(info.notes)
            tmp.append(playdata.dj_level.best)
            tmp.append(playdata.dj_level.current)
            tmp.append(playdata.clear_type.best)
            tmp.append(playdata.clear_type.current)
            tmp.append(playdata.score.best)
            if 'H-RAN' in self.playopt:
                # H乱の場合もEXスコアを出しておく(本日のノーツ数加算の都合)
                tmp.append(self.tmp_judge[0]*2+self.tmp_judge[1]) 
            else:
                tmp.append(playdata.score.current)
            tmp.append(playdata.miss_count.best)
            if 'BATTLE' in self.playopt:
                tmp.append(self.tmp_judge[3]+self.tmp_judge[4])
            else:
                tmp.append(playdata.miss_count.current)
            ts = os.path.getmtime(pic)
            dt = datetime.datetime.fromtimestamp(ts)
            if onplay:
                tmp.append(self.playopt)
            else:
                tmp.append(self.convert_option(playdata.options, tmp[2]))
            # タイムスタンプはpngの作成日時を使っている。
            # こうすると、過去のリザルトから読む場合もプレー中に読む場合も共通化できる
            tmp.append(dt.strftime('%Y-%m-%d-%H-%M'))
            ret = tmp
            if self.noteslist != False: # ノーツリストがある場合
                if tmp[2] != None:
                    notes = self.noteslist[info.music][self.difflist.index(tmp[2])]
                    if 'BATTLE' in tmp[-2]:
                        notes = 2 * self.noteslist[info.music][self.difflist.index(tmp[2].replace('DP','SP'))]
                    if tmp[3] != notes:
                        logger.debug(f"ノーツ数不一致エラー。判定失敗とみなします。notes={notes:,}, tmp[3]={tmp[3]:,}")
                        ret = False
        return ret

    ### オプション検出を行う
    def detect_option(self):
        playopt = False
        #self.obs.save_screenshot()
        whole = Image.open(self.imgpath)
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
        img = Image.open(self.imgpath)
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
            ret.append(line)
        return ret

    ### 選曲画面かどうかを判定し、判定結果(True/False)を返す
    def detect_select(self):
        ret = False

        img = Image.open(self.imgpath)
        hash_target = imagehash.average_hash(Image.open('layout/e4.png'))
        tmp = imagehash.average_hash(img.crop((358,90,358+24,90+24)))
        ret = (hash_target - tmp) < 10
        #logger.debug(f"ret = {ret}")

        return ret
    
    ### リザルト画面の終了判定
    def detect_endresult(self):
        img = Image.open(self.imgpath)
        tmp = imagehash.average_hash(img)
        img = Image.open('layout/endresult.png')
        hash_target = imagehash.average_hash(img)
        ret = (hash_target - tmp) < 10
        #logger.debug(f"ret = {ret}")
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
        flg_autosave = True # その曲で自動保存を使ったかどうか, autosaveが成功したらTrue、曲終了時にリセット
        is_pushed_to_alllog = True
        self.startdate = datetime.datetime.now().strftime("%Y/%m/%d")
        self.obs.disable_source(self.settings['obs_scenename_today_result'], self.settings['obs_itemid_today_result'])
        self.obs.disable_source(self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'])
        tmp_stats = ManageStats(date=self.startdate, todaylog=self.todaylog, judge=self.judge, plays=self.today_plays)
        print(f'スコア検出スレッド開始。')
        while True:
            while True: # 曲開始までを検出
                try:
                    self.obs.save_screenshot()
                    playside = self.detect_playside()
                    tmp_playopt, tmp_gauge = self.detect_option()
                    if not flg_autosave:
                        try:
                            result = self.ocr(self.imgpath)
                            flg_autosave = self.autosave_result(result)
                        except Exception as e:
                            logger.debug(traceback.format_exc())
                    if self.detect_endresult(): # リザルト画面を抜けた後の青い画面
                        self.obs.disable_source(self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'])
                    if self.detect_select() and len(self.todaylog) > 0: # 選曲画面
                        is_pushed_to_alllog = True
                        self.obs.enable_source(self.settings['obs_scenename_today_result'], self.settings['obs_itemid_today_result'])
                        self.obs.disable_source(self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'])
                    else: # 選曲画面じゃなくなった(選曲中レイヤの停止用)
                        self.obs.disable_source(self.settings['obs_scenename_today_result'], self.settings['obs_itemid_today_result'])
                    if not is_pushed_to_alllog:
                        try:
                            result = self.ocr(self.imgpath)
                            if result != False:
                                self.todaylog.append(result)
                                self.alllog.append(result)
                                key = f"{result[1]}({result[2]})"
                                if not key in self.dict_alllog.keys():
                                    self.dict_alllog[key] = []
                                self.dict_alllog[key].append(result)
                                is_pushed_to_alllog = True
                                print(f"{result[1]}({result[2]}) - {result[7]},score:{result[9]:,},")
                                logger.debug(f'result = {result}')
                                self.write_today_update_xml()
                                self.write_history_cursong_xml(result)
                                self.obs.enable_source(self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'])
                                logger.debug('')
                                tmp_stats.update(self.todaylog, self.judge, self.today_plays)
                                logger.debug('')
                                tmp_stats.write_stats_to_xml()
                                logger.debug('')
                        except Exception as e:
                            logger.debug(traceback.format_exc())

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
                        self.gen_opt_xml(self.playopt, self.gauge, True) # 常時表示+曲中のみデータの書き出し
                        break
                except Exception as e: # 今の構成になってから、このtry文がそもそも不要かもしれない TODO
                    logger.debug(traceback.format_exc())
                    stop_local = True
                    print(f'スクリーンショットに失敗しました。{e}')
                    self.window.write_event_value('-SCRSHOT_ERROR-', " ")
                    if self.obs == False:
                        stop_local = True
                    elif not self.obs.active: # obsインスタンスがあっても、OBSが落ちていたら止める
                        stop_local = True
                    break
                if self.stop_thread:
                    stop_local = True
                    break
                #time.sleep(sleep_time)
                time.sleep(0.3) # オプション取得のためにここは短くしたほうがよさそう？

            if stop_local:
                break
            
            self.obs.disable_source(self.settings['obs_scenename_today_result'], self.settings['obs_itemid_today_result'])
            self.obs.disable_source(self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'])

            pre_success = True # 前の検出サイクルに取得が成功したかどうか
            while True: # 曲中の処理
                self.obs.save_screenshot()
                det = self.detect_judge(playside)
                try:
                    score = int(det[0])+int(det[1])+int(det[2])
                    self.window.write_event_value('-THREAD-', f"cur {score} {det[0]} {det[1]} {det[2]} {det[3]} {det[4]} {det[5]}")
                    pre_score = score
                    pre_judge = det
                    pre_success = True
                except Exception:
                    if not pre_success: # 2回連続でスコア取得に失敗したら曲中モードから出る
                        is_pushed_to_alllog = False # OCR起動フラグを立てる
                        self.window.write_event_value('-ENDSONG-', f"{pre_score} {self.playopt}")
                        self.window.write_event_value('-THREAD-', f"end {pre_score} {pre_judge[0]} {pre_judge[1]} {pre_judge[2]} {pre_judge[3]} {pre_judge[4]} {pre_judge[5]}")
                        print(f'曲終了を検出しました。 => {pre_score}')
                        self.gen_opt_xml(self.playopt, self.gauge) # 曲中のみデータの削除
                        flg_autosave = False
                        break
                    pre_success = False
                if self.stop_thread:
                    stop_local = True
                    break
                time.sleep(sleep_time)

            if stop_local:
                break

        print('detect_top end')

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
            opt_dyn = f'opt: {opt}'
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

    def escape_for_xml(self, input):
        return input.replace('&', '&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&apos;')

    def write_history_cursong_xml(self, result):
        with open('history_cursong.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Results>\n")
            f.write(f'    <lv>{result[0]}</lv>\n')
            f.write(f'    <music>{self.escape_for_xml(result[1])}</music>\n')
            f.write(f'    <difficulty>{result[2]}</difficulty>\n')
            key = f"{result[1]}({result[2]})"
            logger.debug(f"key={key}")
            for s in reversed(self.dict_alllog[key]): # 過去のプレー履歴のループ,sが1つのresultに相当
                logger.debug(f"s = {s}")
                bp = s[11]
                if len(s) != 14: # フォーマットがおかしい場合は飛ばす
                    continue
                if bp == None: # 昔のリザルトに入っていない可能性を考えて一応例外処理している
                    bp = '?'
                if 'BATTLE' in self.playopt: # 現在DBx系オプションの場合、単曲履歴もDBxのリザルトのみを表示
                    if 'BATTLE' in s[-2]: # DBxのリザルトのみ抽出
                        f.write('    <item>\n')
                        f.write(f'        <date>{s[-1][2:10]}</date>\n')
                        f.write(f'        <lamp>{s[7]}</lamp>\n')
                        f.write(f'        <score>{s[9]}</score>\n')
                        f.write(f'        <opt>{s[-2]}</opt>\n')
                        f.write(f'        <bp>{bp}</bp>\n')
                        f.write('    </item>\n')
                else: # 現在のオプションがDBx系ではない
                    if not 'BATTLE' in s[-2]: # DBx''以外''のリザルトのみ抽出
                        f.write('    <item>\n')
                        f.write(f'        <date>{s[-1][2:10]}</date>\n')
                        f.write(f'        <lamp>{s[7]}</lamp>\n')
                        f.write(f'        <score>{s[9]}</score>\n')
                        f.write(f'        <opt>{s[-2]}</opt>\n')
                        f.write(f'        <bp>{bp}</bp>\n')
                        f.write('    </item>\n')
            f.write('</Results>\n')
            logger.debug(f"end")

    def write_today_update_xml(self):
        with open('today_update.xml', 'w', encoding='utf-8') as f:
            f.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<Results>\n")
            lamp_table = ['NO PLAY', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO']
            for s in reversed(self.todaylog):
                logger.debug(f"s = {s}")
                lamp = ''
                score = ''
                if ('BATTLE' in s[-2]): # DBx系
                    if (lamp_table.index(s[7]) >= 2) or self.settings['todaylog_dbx_always_push']:
                        lamp = s[7]
                elif ('H-RAN' in s[-2]):
                    if self.settings['todaylog_always_push']: # 更新時のみランプを送信
                        lamp = s[7]
                        score = s[9]
                else:
                    if (lamp_table.index(s[7]) > lamp_table.index(s[6])) or self.settings['todaylog_always_push']: # 更新時のみランプを送信
                        lamp = s[7]
                    if (s[9] > s[8]) or self.settings['todaylog_always_push']: # 更新時のみスコアを送信
                        score = f'{s[9]-s[8]:+}'
                bp = s[11]
                if bp == None: # 昔のリザルトに入っていない可能性を考えて一応例外処理している
                    bp = '?'
                if (lamp != '') or (score != ''):
                    f.write('<item>\n')
                    f.write(f'    <lv>{s[0]}</lv>\n')
                    f.write(f'    <title>{self.escape_for_xml(s[1])}</title>\n')
                    f.write(f'    <difficulty>{s[2]}</difficulty>\n')
                    f.write(f'    <lamp>{lamp}</lamp>\n')
                    f.write(f'    <score>{score}</score>\n')
                    f.write(f'    <opt>{s[-2]}</opt>\n')
                    f.write(f'    <bp>{bp}</bp>\n') # DB系で使うためにbpも送っておく
                    f.write('</item>\n')
            f.write('</Results>\n')
            logger.debug(f"end")

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
        window = sg.Window('YoutubeLive準備用ツール', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico)
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
                    basetitle = title.replace(series, '')
                    basetitle = re.sub('【[^【】]*】', '', basetitle)
                    basetitle = re.sub('\[[^\[\]]*]', '', basetitle)
                    self.write_series_xml(series, basetitle.strip())
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

    def gui_setting(self):
        self.mode = 'setting'
        if self.window:
            self.window.close()
        #print(self.settings)
        layout_obs = [
            [sg.Text('OBS host: ', font=FONT), sg.Input(self.settings['host'], font=FONT, key='input_host', size=(20,20))],
            [sg.Text('OBS websocket port: ', font=FONT), sg.Input(self.settings['port'], font=FONT, key='input_port', size=(10,20))],
            [sg.Text('OBS websocket password', font=FONT), sg.Input(self.settings['passwd'], font=FONT, key='input_passwd', size=(20,20), password_char='*')],
            #[sg.Text('OBS websocket password: ', font=FONT), sg.Input(self.settings['passwd'], font=FONT, key='input_passwd', size=(20,20))],
            [sg.Text('INFINITAS用ソース名: ', font=FONT, tooltip='OBSでINFINITASを表示するのに使っているゲームソースの名前を入力してください。'), sg.Input(self.settings['obs_source'], font=FONT, key='input_obs_source', size=(20,20))],
        ]
        layout_autosave = [
            [sg.Text('リザルト自動保存先フォルダ', font=FONT), sg.Button('変更', key='btn_autosave_dir')],
            [sg.Text(self.settings['autosave_dir'], key='txt_autosave_dir')],
            [
                sg.Checkbox('更新に関係なく常時保存する',self.settings['autosave_always'],key='chk_always', enable_events=True),
                sg.Checkbox('ライバルの名前を隠す',self.settings['autosave_mosaic'],key='chk_mosaic', enable_events=True)
            ],
            [sg.Text('リザルト自動保存用設定 (onになっている項目の更新時に保存)', font=FONT)],
            [sg.Checkbox('クリアランプ',self.settings['autosave_lamp'],key='chk_lamp', enable_events=True)
            ,sg.Checkbox('DJ Level',self.settings['autosave_djlevel'], key='chk_djlevel', enable_events=True)
            ,sg.Checkbox('スコア', self.settings['autosave_score'], key='chk_score', enable_events=True)
            ,sg.Checkbox('ミスカウント', self.settings['autosave_bp'], key='chk_bp', enable_events=True)
            ],
            [sg.Text('DBx系リザルト(DBM,DBR等)自動保存用設定', font=FONT)],
            [
                sg.Radio('しない', group_id='dbx', default=(self.settings['autosave_dbx']=='no'), key='radio_dbx_no'),
                sg.Radio('常時', group_id='dbx', default=(self.settings['autosave_dbx']=='always'), key='radio_dbx_always'),
                sg.Radio('A-CLEAR以上の場合のみ', group_id='dbx', default=(self.settings['autosave_dbx']=='clear'), key='radio_dbx_clear'),
            ]
        ]
        layout_ocr = [
            [sg.Text('本日の履歴の更新:', font=FONT), sg.Radio(text='常時', group_id='1', default=self.settings['todaylog_always_push'], font=FONT, key='todaylog_always_push'), sg.Radio(text='更新時のみ', group_id='1', default=not self.settings['todaylog_always_push'], font=FONT)],
            [sg.Text('DBx系の履歴の更新:', font=FONT),sg.Radio(text='常時', group_id='2', default=self.settings['todaylog_dbx_always_push'], font=FONT, key='todaylog_dbx_always_push'), sg.Radio(text='クリア時のみ', group_id='2', default=not self.settings['todaylog_dbx_always_push'], font=FONT)],
            [sg.Text('INFINITAS用シーン名:', font=FONT), sg.Input(self.settings['obs_scene'], font=FONT, key="input_obs_scene", size=(20,1))],
            [sg.Button('保存したリザルト画像からスコアデータに反映する', key='btn_ocr_from_savedir', tooltip='リザルト画像の数によってはかなり時間がかかります。')],
        ]
        layout = [
            [sg.Frame('OBS設定', layout=layout_obs, title_color='#000044')],
            [sg.Frame('リザルト自動保存設定', layout=layout_autosave, title_color='#000044')],
            [sg.Frame('OCR(リザルト文字認識)設定', layout=layout_ocr, title_color='#000044')],
            [sg.Button('close', key='btn_close_setting', font=FONT)],
            ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window(f'{SWNAME} - 設定', layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico,location=(self.settings['lx'], self.settings['ly']))
        if self.settings['autosave_always']:
            self.window['chk_lamp'].update(disabled=True)
            self.window['chk_djlevel'].update(disabled=True)
            self.window['chk_score'].update(disabled=True)
            self.window['chk_bp'].update(disabled=True)
            self.window['radio_dbx_no'].update(disabled=True)
            self.window['radio_dbx_always'].update(disabled=True)
            self.window['radio_dbx_clear'].update(disabled=True)

    def gui_graph(self): # グラフ作成用
        self.mode = 'graph'
        if self.window:
            self.window.close()
        layout = [
            [sg.Text(f'')],
            [sg.Button('OK', key='btn_close_graph', font=FONT)],
        ]
        ico=self.ico_path('icon.ico')
        self.window = sg.Window(f"{SWNAME}", layout, grab_anywhere=True,return_keyboard_events=True,resizable=False,finalize=True,enable_close_attempted_event=True,icon=ico,location=(self.settings['lx'], self.settings['ly']), size=(400,220))

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
        menuitems = [['ファイル',['設定','配信を告知する','グラフ作成']],['ヘルプ',[f'{SWNAME}について']]]
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
            [sg.Output(size=(63,8), key='output', font=('Meiryo',9))],
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
            logger.info('自動起動設定が有効です。')
            self.window.refresh()
            print('自動起動設定が有効です。')
            if self.settings['reset_on_boot']:
                self.today_notes = 0
                self.today_plays = 0
                self.notes_ran = 0
                self.notes_battle  = 0
                self.srate = 0
                self.judge = [0,0,0,0,0,0]
                self.tmp_judge = [0,0,0,0,0,0] # 最後の曲の判定を覚えておく(DBxのBP記録用)
                self.window['srate'].update(value=f"{self.srate:.2f} %")
                self.window['today'].update(value=f"0")
                self.window['plays'].update(value=f"0")
                for i in range(6):
                    self.window[f"judge{i}"].update(value='0')
            running = True
            th = threading.Thread(target=self.detect_top, args=(SLEEP_TIME,), daemon=True)
            self.gen_notes_xml(0,self.today_notes,self.today_plays, self.notes_ran, self.notes_battle, self.judge)
            th.start()
            self.window['start'].update("stop")

        while True:
            ev, val = self.window.read()
            #logger.debug(f"ev={ev}")
            # 設定を最新化
            if self.settings and val: # 起動後、そのまま何もせずに終了するとvalが拾われないため対策している
                if self.mode == 'main':
                    # 今日のノーツ数とか今日の回数とかはここに記述しないこと(resetボタンを押すと即反映されてしまうため)
                    self.settings['lx'] = self.window.current_location()[0]
                    self.settings['ly'] = self.window.current_location()[1]
                    self.settings['run_on_boot'] = val['run_on_boot']
                    self.settings['reset_on_boot'] = val['reset_on_boot']
                elif self.mode == 'setting':
                    #self.settings['lx'] = self.window.current_location()[0]
                    #self.settings['ly'] = self.window.current_location()[1]
                    self.settings['host'] = val['input_host']
                    self.settings['port'] = val['input_port']
                    self.settings['obs_scene'] = val['input_obs_scene']
                    if self.obs != False:
                        self.settings['obs_scenename_history_cursong'], self.settings['obs_itemid_history_cursong'] = self.obs.search_itemid(self.settings['obs_scene'], 'history_cursong')
                        self.settings['obs_scenename_today_result'], self.settings['obs_itemid_today_result'] = self.obs.search_itemid(self.settings['obs_scene'], 'today_result')
                    self.settings['todaylog_always_push'] = val['todaylog_always_push']
                    self.settings['todaylog_dbx_always_push'] = val['todaylog_dbx_always_push']
                    self.settings['passwd'] = val['input_passwd']
                    self.settings['obs_source'] = val['input_obs_source']
                    self.settings['autosave_lamp'] = val['chk_lamp']
                    self.settings['autosave_djlevel'] = val['chk_djlevel']
                    self.settings['autosave_score'] = val['chk_score']
                    self.settings['autosave_bp'] = val['chk_bp']
                    self.settings['autosave_always'] = val['chk_always']
                    self.settings['autosave_mosaic'] = val['chk_mosaic']
                    if val['chk_always']:
                        self.window['chk_lamp'].update(disabled=True)
                        self.window['chk_djlevel'].update(disabled=True)
                        self.window['chk_score'].update(disabled=True)
                        self.window['chk_bp'].update(disabled=True)
                        self.window['radio_dbx_no'].update(disabled=True)
                        self.window['radio_dbx_always'].update(disabled=True)
                        self.window['radio_dbx_clear'].update(disabled=True)
                    else:
                        self.window['chk_lamp'].update(disabled=False)
                        self.window['chk_djlevel'].update(disabled=False)
                        self.window['chk_score'].update(disabled=False)
                        self.window['chk_bp'].update(disabled=False)
                        self.window['radio_dbx_no'].update(disabled=False)
                        self.window['radio_dbx_always'].update(disabled=False)
                        self.window['radio_dbx_clear'].update(disabled=False)
                    if val['radio_dbx_no']:
                        self.settings['autosave_dbx'] = 'no'
                    elif val['radio_dbx_always']:
                        self.settings['autosave_dbx'] = 'always'
                    else:
                        self.settings['autosave_dbx'] = 'clear'
            if ev in (sg.WIN_CLOSED, 'Escape:27', '-WINDOW CLOSE ATTEMPTED-', 'btn_close_info', 'btn_close_setting'):
                if self.mode == 'main':
                    self.save_alllog()
                    self.save_settings()
                    self.save_dakenlog()
                    logger.info('終了します')
                    break
                else:
                    if self.mode == 'setting':
                        if self.obs:
                            self.obs.close()
                        del self.obs
                        try:
                            self.obs = OBSSocket(self.settings['host'], self.settings['port'], self.settings['passwd'], self.settings['obs_source'], self.imgpath)
                        except:
                            self.obs = False
                            print('obs socket error!')
                            pass
                    self.gui_main()
            elif ev.startswith('start'):
                running = not running
                if running:
                    if self.settings['reset_on_boot']:
                        print('自動リセット設定が有効です。')
                        self.today_notes = 0
                        self.today_plays = 0
                        self.notes_ran = 0
                        self.notes_battle  = 0
                        self.srate = 0
                        self.judge = [0,0,0,0,0,0]
                        self.tmp_judge = [0,0,0,0,0,0] # 最後の曲の判定を覚えておく(DBxのBP記録用)
                        self.window['srate'].update(value=f"{self.srate:.2f} %")
                        self.window['today'].update(value=f"0")
                        self.window['plays'].update(value=f"0")
                        for i in range(6):
                            self.window[f"judge{i}"].update(value='0')

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
                self.today_notes = 0
                self.today_plays = 0
                self.notes_ran = 0
                self.notes_battle = 0
                self.judge = [0,0,0,0,0,0]
                self.tmp_judge = [0,0,0,0,0,0]
                self.srate = 0
                self.window['srate'].update(value=f"{self.srate:.2f} %")
                self.window['today'].update(value=f"0")
                self.window['plays'].update(value=f"0")
                for i in range(6):
                    self.window[f"judge{i}"].update(value='0')
            elif ev.startswith('test_screenshot'):
                th_scshot = threading.Thread(target=self.get_screen_all, daemon=True)
                th_scshot.start()
            elif ev.startswith('tweet'):
                srate = 0.0
                if self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5] > 0:
                    srate = (self.judge[0]*2+self.judge[1])/(self.judge[0]+self.judge[1]+self.judge[2]+self.judge[5])*50
                msg = f"今日は{self.today_plays:,}曲プレイし、{self.today_notes:,}ノーツ叩きました。\n"
                msg += f'(PG:{self.judge[0]:,}, GR:{self.judge[1]:,}, GD:{self.judge[2]:,}, BD:{self.judge[3]:,}, PR:{self.judge[4]:,}, CB:{self.judge[5]:,})\n'
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
                    tmp_judge = [self.judge[i]+int(dat[2+i]) for i in range(6)] # 前の曲までの値judge[i]に現在の曲の値dat[2+i]を加算したもの
                    self.tmp_judge = [int(dat[2+i]) for i in range(6)]
                except:
                    print(f'error!!! datの値が不正?, dat={dat}')
                    tmp_judge = copy.copy(self.judge)

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
                            self.judge[i] += int(dat[2+i])
                        except ValueError:
                            print(f'{i}番目の値の取得に失敗。skipします。')
                            self.judge[i] = tmp_judge[i]

                self.window['cur'].update(value=f"{cur}")
                self.window['plays'].update(value=f"{self.today_plays}")
                ### スコアなどのセーブデータはここで更新(安全なresetとさせるため)
                self.settings['plays'] = self.today_plays
                self.settings['total_score'] = tmp_today_notes
                self.settings['judge'] = tmp_judge
                self.gen_notes_xml(cur,tmp_today_notes,self.today_plays, self.notes_ran, self.notes_battle, tmp_judge)
                pre_cur = cur
            elif ev == '-ENDSONG-':
                dat = val[ev].split(' ')
                score = int(dat[0])
                #self.option = val[ev][len(dat[0])+1:]
                if 'BATTLE' in self.playopt:
                    self.notes_battle += cur
                elif ('RAN / RAN' in self.playopt) or ('S-RAN / S-RAN' in self.playopt) or ('H-RAN / H-RAN' in self.playopt): # 両乱だけ数えるか片乱だけ数えるか未定
                    self.notes_ran += cur
                logger.debug(f'self.playopt = {self.playopt},  dat = {dat}')
                logger.debug(f'self.notes_ran = {self.notes_ran:,}, self.notes_battle = {self.notes_battle:,}')
            elif ev == '-SCRSHOT_ERROR-':
                self.stop_thread = True
                th.join()
                self.stop_thread = False
                running = not running
                if self.mode == 'main':
                    self.window['start'].update("start")
                print(f"スコア検出スレッドが異常終了しました。")
            elif ev in ('Y:89', '配信を告知する'):
                #url = sg.popup_get_text('YoutubeLiveのURL(Studioでも可)を入力してください。', 'Youtube準備用コマンド')
                q = self.gui_ytinfo(self.settings['series_query'])
                self.settings['series_query'] = q
                #get_ytinfo(url)
            elif ev == 'グラフ作成':
                log_manager = LogManager(self.settings)
                log_manager.main()

            elif ev == "コピー":
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

            elif ev == 'btn_autosave_dir':
                tmp = filedialog.askdirectory()
                if tmp != '':
                    self.settings['autosave_dir'] = tmp
                    self.window['txt_autosave_dir'].update(tmp)

            elif ev  == 'btn_ocr_from_savedir': # リザルト画像フォルダからスコアを抽出。スコア一覧の初期値生成用
                th_read_result = threading.Thread(target=self.read_result_from_pic, daemon=True)
                self.playopt = '?' # 画像からオプションが取得できなさそうなので、不明にしておく
                pre_len_alllog = len(self.alllog)
                th_read_result.start()

            elif ev == '-OCR_FROM_IMG_END-':
                th_read_result.join()
                self.playopt = self.settings['playopt']

            elif ev  == f'{SWNAME}について':
                self.gui_info()

            elif ev.startswith('URL '): # URLをブラウザで開く;info用
                url = ev.split(' ')[1]
                webbrowser.open(url)

if __name__ == '__main__':
    a = DakenCounter()
    a.main()
