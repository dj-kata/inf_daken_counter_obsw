import sys
import pickle
import os
from PIL import Image
import numpy as np
import imagehash
import glob
import urllib, json, requests

from src.screen_reader import ScreenReader
from src.logger import get_logger
from src.result import ResultDatabase
from src.classes import * 
from src.config import Config
from src.songinfo import *
logger = get_logger('convert_db')

with open('resources/informations4.0.res', 'rb') as f:
    detect = pickle.load(f) # bpim, notes
titles = detect['music']['musics'] # inf-notebook側の曲名リスト

with open('resources/musictable1.1.res', 'rb') as f:
    mt = pickle.load(f) # bpim, notes
versions = mt['versions'] # 1st&substream, 2nd style,...などのキー
levels = mt['levels'] # SP/DP, 1-12
leggendarias = mt['leggendarias'] # SP/DP
beginners = mt['beginners'] #(list)

with open('noteslist.pkl', 'rb') as f:
    noteslist = pickle.load(f) # bpim, notes
# with open('sp_12jiriki.pkl', 'rb') as f:
    # sp12 = pickle.load(f) # hard/clear
with open('dp_unofficial.pkl', 'rb') as f:
    dp12 = pickle.load(f) # title

def get_bpim_data(download=False):
    """BPI Managerの定義データを取得して整理する

    Args:
        songs (dict): 曲リストの辞書。keyが曲名。

    Returns:
        ret (dict): BPIM定義情報。key: 曲名___SPAのような形式, value: 
    """
    if download:
        res = requests.get('https://bpim.msqkn310.workers.dev/release') # 定義ファイルのURL
        ret_json = json.loads(res.text)

        ret = {}

        for s in ret_json['body']:
            title = s['title']
            lvidx = int(s['difficulty'])
            diff = '???'
            style = play_style.sp
            if lvidx == 10: # spl
                style = play_style.sp
                diff = difficulty.leggendaria
            elif lvidx == 11: # dpl
                diff = 'DPL'
                style = play_style.dp
                diff = difficulty.leggendaria
            elif lvidx == 3: # sph
                diff = 'SPH'
                style = play_style.sp
                diff = difficulty.hyper
            elif lvidx == 4: # spa
                diff = 'SPA'
                style = play_style.sp
                diff = difficulty.another
            elif lvidx == 8: # dph
                diff = 'DPH'
                style = play_style.dp
                diff = difficulty.hyper
            elif lvidx == 9: # dpa
                style = play_style.dp
                diff = difficulty.another

            wr = int(s['wr'])
            avg = int(s['avg'])
            notes = int(s['notes'])
            coef = -1
            if 'coef' in s.keys():
                coef = s['coef']
            ret[(title,style,diff)] = {
                'wr':wr,
                'avg':avg,
                'notes':notes,
                'coef':coef,
            }
        with open('bpi.pkl', 'wb') as f:
            pickle.dump(ret, f)
    with open('bpi.pkl', 'rb') as f:
        ret = pickle.load(f)

    return ret

def get_sp12_unofficial(download=False):
    if download:
        url = 'https://sp12.iidx.app/api/v1/sheets'
        headers = { "User-Agent" :  "Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)" }
        req = urllib.request.Request(url, None, headers)
        tmp = urllib.request.urlopen(req).read()

        tmp_sp12 = json.loads(tmp)['sheets']
        unoff_conv = {
            '地力S+':19,
            '個人差S+':18,
            '地力S':17,
            '個人差S':16,
            '地力A+':15,
            '個人差A+':14,
            '地力A':13,
            '個人差A':12,
            '地力B+':11,
            '個人差B+':10,
            '地力B':9,
            '個人差B':8,
            '地力C':7,
            '個人差C':6,
            '地力D':5,
            '個人差D':4,
            '地力E':3,
            '個人差E':2,
            '地力F':1,
            '難易度未定':0,
        }
        sp12 = {} # (title, play_style.sp, difficulty)をキーとする
        for s in tmp_sp12:
            title = s['title']
            diff = difficulty.another
            if '[H]' == s['title'][-3:]:
                title = s['title'][:-3]
                diff = difficulty.hyper
            if '[A]' == s['title'][-3:]:
                title = s['title'][:-3]
                diff = difficulty.another
            if '†' == s['title'][-1]:
                title = s['title'][:-1]
                diff = difficulty.leggendaria
            if 'n_clear_string' in s.keys():
                clear = s['n_clear_string']
            if 'clear_string' in s.keys():
                clear = s['clear_string']
            hard = s['hard_string']
            print(s, title, clear, hard)
            clear = unofficial_difficulty(unoff_conv[clear])
            hard = unofficial_difficulty(unoff_conv[hard])
            sp12[(title,play_style.sp,diff)] = {'title':title, 'difficulty':diff, 'clear':clear, 'hard':hard}

        with open('sp12.pkl', 'wb') as f:
            pickle.dump(sp12, f)
    with open('sp12.pkl', 'rb') as f:
        sp12 = pickle.load(f)
    return sp12

def set_sp12unofficial(titles:list, sdb:SongDatabase, conv_unof_infn:dict):
    '''12地力表のデータを登録'''
    ########           12地力表          ##########
    for s in titles: # inf-notebookの曲名
        title = s['music']
        tmp_d =s['difficulty']
        if tmp_d == 'HYPER':
            diff = difficulty.hyper
        elif tmp_d == 'ANOTHER':
            diff = difficulty.another
        elif tmp_d == 'LEGGENDARIA':
            diff = difficulty.leggendaria
        if (title, play_style.sp, diff) in sp12.keys(): # 地力表側との照合
            new = OneSongInfo(
                title = title,
                play_style = play_style.sp,
                difficulty=diff,
                level=12,
                sp12_clear = sp12[(title,play_style.sp,diff)]['clear'],
                sp12_hard = sp12[(title,play_style.sp,diff)]['hard'],
                sp12_title = title,
            )
            sdb.add(new)
        elif (title, play_style.sp, diff) in conv_unof_infn.keys():
            new_title = conv_unof_infn[(title, play_style.sp, diff)]
            new = OneSongInfo(
                title = title,
                play_style = play_style.sp,
                difficulty=diff,
                level=12,
                sp12_clear = sp12[(new_title,play_style.sp,diff)]['clear'],
                sp12_hard = sp12[(new_title,play_style.sp,diff)]['hard'],
                sp12_title = title,
            )
            sdb.add(new)
        else:
            new = OneSongInfo(
                title = title,
                play_style = play_style.sp,
                difficulty=diff,
                level=12,
            )
            sdb.add(new)
            not_found.append((title, play_style.sp, diff))
    return not_found

def set_lvall(style:play_style, lv:int, titles:dict, sdb:SongDatabase):
    '''指定レベルの曲を全て追加。特にチェックをしない'''
    for s in titles[style.name.upper()][str(lv)]: # inf-notebookの曲名
        title = s['music']
        tmp_d =s['difficulty']
        if tmp_d == 'HYPER':
            diff = difficulty.hyper
        elif tmp_d == 'ANOTHER':
            diff = difficulty.another
        elif tmp_d == 'LEGGENDARIA':
            diff = difficulty.leggendaria
        elif tmp_d == 'BEGINNER':
            diff = difficulty.beginner
        elif tmp_d == 'NORMAL':
            diff = difficulty.normal
        elif tmp_d == 'HYPER':
            diff = difficulty.hyper
        new = OneSongInfo(
            title = title,
            play_style = style,
            difficulty=diff,
            level=lv,
        )
        sdb.add(new)

def set_bpim(bpi:dict, sdb:SongDatabase, conv:dict=None):
    '''SongDatabaseにBPI Manager用データを埋め込む。見つからなかった曲一覧を返す'''
    not_found = []
    for k in bpi.keys():
        if sdb.search(title=k[0], play_style=k[1], difficulty=k[2]):
            chart_id = calc_chart_id(k[0], k[1], k[2])
            sdb.songs[chart_id].bpi_top = bpi[k]['wr']
            sdb.songs[chart_id].bpi_ave = bpi[k]['avg']
            sdb.songs[chart_id].bpi_coef = bpi[k]['coef']
            sdb.songs[chart_id].notes = bpi[k]['notes']
            sdb.songs[chart_id].bpi_title = k[0]
        elif conv and k[0] in conv.keys() and sdb.search(title=conv[k[0]], play_style=k[1], difficulty=k[2]):
            chart_id = calc_chart_id(conv[k[0]], k[1], k[2])
            sdb.songs[chart_id].bpi_top = bpi[k]['wr']
            sdb.songs[chart_id].bpi_ave = bpi[k]['avg']
            sdb.songs[chart_id].bpi_coef = bpi[k]['coef']
            sdb.songs[chart_id].notes = bpi[k]['notes']
            sdb.songs[chart_id].bpi_title = k[0]
        else:
            not_found.append(k)
    return not_found

sp12 = get_sp12_unofficial()
bpi = get_bpim_data()

diff_str = ['BEGINNER', 'NORMAL', 'HYPER', 'ANOTHER', 'LEGGENDARIA']
for style in play_style:
    for lv in [11,12]:
        for s in levels[style.name.upper()][str(lv)]:
            diff = difficulty(diff_str.index(s.get('difficulty')))
            # print(f"lv{lv}, title={s.get('music')}, style={style}, diff={diff}")

sdb = SongDatabase()
not_found = []
conv_unof_infn = {
    ('uan',play_style.sp,difficulty.another):'uen',
    ('火影',play_style.sp,difficulty.another):'焱影',
    ('旋律のドグマ～Miserables～',play_style.sp,difficulty.another):'旋律のドグマ ～Misérables～'
}

########           BPI          ##########
not_found_sp12 = set_sp12unofficial(levels['SP']['12'], sdb, conv_unof_infn)
set_lvall(play_style.sp, 11, levels, sdb)
set_lvall(play_style.dp, 12, levels, sdb)
set_lvall(play_style.dp, 11, levels, sdb)

conv_bpi ={
    # "": "A MINSTREL ～ ver. short-scape ～", # SPL
    # "": "Cross Fire", # SPA
    "Rave*it!! Rave*it!! ": "Rave*it!! Rave*it!!", # SPA
    # "uen": "uan", # SPA
    # "": "1116", # SPA
    # "": "CALL", # SPL
    # "": "Plea Per Phase", # SPA
    "POLKAMAИIA": "POLKAMANIA", # SPA
    "ZEИITH": "ZENITH", # SPA
}
not_found_bpi = set_bpim(bpi=bpi, sdb=sdb, conv=conv_bpi)

print(sdb)

# songdbのSP11,12でBPI情報がないものを抽出; DPは需要が不明なので真面目にやらない
# i=0
# for s in sdb.filter(play_style=play_style.sp):
#     if s.bpi_ave is None:
#         i+=1
#         print(f'    "": "{s.title}", # {get_chart_name(s.play_style, s.difficulty)}')


print(f"len not_found_sp12:{len(not_found_sp12)}")
# print(f"len not_found_bpi:{i}")

# ACと譜面が違う曲を補正
chart_id = calc_chart_id('New Castle Legions', play_style.sp, difficulty.another)
print(sdb.search(chart_id))
# sdb.songs[chart_id].bpi_ave=None
# sdb.songs[chart_id].bpi_top=None
# sdb.songs[chart_id].bpi_title=None
# sdb.songs[chart_id].bpi_coef=None
# sdb.songs[chart_id].level = 11

# 10以下も登録
for i in range(1, 11):
    set_lvall(play_style.sp, i, levels, sdb)
    set_lvall(play_style.dp, i, levels, sdb)

sdb.save()