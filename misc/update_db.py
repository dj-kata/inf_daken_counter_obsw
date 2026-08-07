import sys
import argparse
import pickle
import os
import shutil
from pathlib import Path
from PIL import Image
import numpy as np
import imagehash
import glob
import gzip
import urllib.request, json, requests
from bs4 import BeautifulSoup
try:
    from . import update_katate_difficulty
except ImportError:
    import update_katate_difficulty

from src.screen_reader import ScreenReader
from src.logger import get_logger
from src.result_database import ResultDatabase
from src.classes import * 
from src.config import Config
from src.songinfo import *
logger = get_logger('convert_db')

OUT_DIR = Path('out')


def get_pkl_path(filename):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pkl_path = OUT_DIR / filename
    legacy_path = Path(filename)
    if not pkl_path.exists() and legacy_path.exists():
        shutil.copy2(legacy_path, pkl_path)
    return pkl_path


def load_pickle_or_empty(pkl_path:Path, label:str):
    if not pkl_path.exists():
        print(f"{pkl_path} not found; skipping {label}.")
        return {}
    with open(pkl_path, 'rb') as f:
        return pickle.load(f)


def str_to_bool(value):
    if isinstance(value, bool):
        return value
    value = value.lower()
    if value in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if value in ('0', 'false', 'no', 'n', 'off'):
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--download',
        nargs='?',
        const=True,
        default=False,
        type=str_to_bool,
        help='download source data before generating local pkl caches',
    )
    parser.add_argument(
        '--legacy-bpi',
        action='store_true',
        help='embed cached legacy BPI Manager v1 definitions for local fallback',
    )
    parser.add_argument(
        '--skip-katate',
        action='store_true',
        help='skip updating katate difficulty after songinfo generation',
    )
    return parser.parse_args()


with gzip.open('infnotebook/resources/informations4.1.res', 'rb') as f:
    detect = pickle.load(f) # bpim, notes
titles = detect['music']['musics'] # inf-notebook側の曲名リスト

with gzip.open('infnotebook/resources/musictable1.2.res', 'rb') as f:
    mt = pickle.load(f) # bpim, notes
versions = mt['versions'] # 1st&substream, 2nd style,...などのキー
levels = mt['levels'] # SP/DP, 1-12
leggendarias = mt['leggendarias'] # SP/DP
beginners = mt['beginners'] #(list)

def get_ereter_dp(download=False):
    """ereter.netからDP統計データ(EC/HC/EXH diff)を取得する

    Returns:
        dict: key=(title, play_style.dp, difficulty), value={'easy':float, 'hard':float, 'exh':float}
    """
    pkl_path = get_pkl_path('ereter_dp.pkl')
    if download:
        try:
            url = 'https://ereter.net/iidxsongs/analytics/perlevel/'
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=30)
            res.raise_for_status()
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, features='html.parser')
            table = soup.find('table')
            if table is None:
                raise ValueError('ereter table not found')
            rows = table.find_all('tr')
            ret = {}
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                title_text = cols[1].get_text(' ', strip=True)
                # "Kailua (ANOTHER)" -> title="Kailua", diff="ANOTHER"
                # 末尾の (DIFFICULTY) を分離
                paren_idx = title_text.rfind('(')
                if paren_idx == -1:
                    continue
                title = title_text[:paren_idx].strip()
                diff_str = title_text[paren_idx+1:].rstrip(')')
                diff = convert_difficulty(diff_str)
                if diff is None:
                    continue
                try:
                    ec = parse_ereter_diff(cols[2])
                    hc = parse_ereter_diff(cols[3])
                    exh = parse_ereter_diff(cols[4])
                except ValueError:
                    continue
                ret[(title, play_style.dp, diff)] = {'easy': ec, 'hard': hc, 'exh': exh}
            with open(pkl_path, 'wb') as f:
                pickle.dump(ret, f)
            print(f"ereter DP: {len(ret)} charts scraped")
        except Exception as e:
            print(f"ereter DP download failed; using cached data if available: {e}")
    return load_pickle_or_empty(pkl_path, 'ereter DP data')

def parse_ereter_diff(cell):
    """ereterの★表記から数値だけを取り出す。sort-valueがあればそれを優先する。"""
    value = cell.get('sort-value')
    if value is None:
        value = cell.get_text(strip=True).replace('★', '').strip()
    return round(float(value), 1)

def get_bpim_data(download=False):
    """BPI Managerの旧ローカル定義データを読み込む

    Args:
        songs (dict): 曲リストの辞書。keyが曲名。

    Returns:
        ret (dict): BPIM定義情報。key: 曲名___SPAのような形式, value: 
    """
    pkl_path = get_pkl_path('bpi.pkl')
    if download:
        print("Legacy BPIM download is disabled; BPIM2 is calculated at runtime.")
    return load_pickle_or_empty(pkl_path, 'legacy local BPI data')

def get_sp12_unofficial(download=False):
    pkl_path = get_pkl_path('sp12.pkl')
    if download:
        try:
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

            with open(pkl_path, 'wb') as f:
                pickle.dump(sp12, f)
        except Exception as e:
            print(f"SP12 unofficial download failed; using cached data if available: {e}")
    return load_pickle_or_empty(pkl_path, 'SP12 unofficial data')

def set_sp12unofficial(titles:list, sdb:SongDatabase, conv_unof_infn:dict):
    '''12地力表のデータを登録'''
    ########           12地力表          ##########
    not_found = []
    for s in titles: # inf-notebookの曲名
        title = s['music']
        tmp_d =s['difficulty']
        if tmp_d == 'HYPER':
            diff = difficulty.hyper
        elif tmp_d == 'ANOTHER':
            diff = difficulty.another
        elif tmp_d == 'LEGGENDARIA':
            diff = difficulty.leggendaria

        existing = sdb.search(title=title, play_style=play_style.sp, difficulty=diff)
        candidate_titles = []
        if existing and existing.sp12_title:
            candidate_titles.append(existing.sp12_title)
        candidate_titles.append(title)
        if (title, play_style.sp, diff) in conv_unof_infn:
            candidate_titles.append(conv_unof_infn[(title, play_style.sp, diff)])
        candidate_titles = list(dict.fromkeys(candidate_titles))

        matched_title = next(
            (
                candidate_title for candidate_title in candidate_titles
                if (candidate_title, play_style.sp, diff) in sp12
            ),
            None,
        )

        if matched_title is not None: # 地力表側との照合
            new = OneSongInfo(
                title = title,
                play_style = play_style.sp,
                difficulty=diff,
                level=12,
                sp12_clear = sp12[(matched_title,play_style.sp,diff)]['clear'],
                sp12_hard = sp12[(matched_title,play_style.sp,diff)]['hard'],
                sp12_title = matched_title,
            )
            add_preserving_existing(sdb, new)
        else:
            new = OneSongInfo(
                title = title,
                play_style = play_style.sp,
                difficulty=diff,
                level=12,
            )
            add_preserving_existing(sdb, new)
            not_found.append((title, play_style.sp, diff))
    return not_found

def get_dp_unofficial(conv, download=False):
    '''DP非公式難易度表の取得'''
    pkl_path = get_pkl_path('dp_unofficial.pkl')
    vers = ['RA', 'ROOT', 'SINO', 'CB', 'DJT', 'sub', 'HERO', 'HSKY', 'CH', '4th'
        , 'PEN', 'SIR', '1st', '2nd', '5th', '6th', '7th', '8th', '9th', '10th'
        , 'GOLD', 'RED', 'COP', 'EMP', 'BIS',  'TRI', 'LC', 'DD', 'RDT', 'SPD']
    def parse_lv_table(res):
        ret = {}
        soup = BeautifulSoup(res, features='html.parser')
        div = soup.find_all('div')[8:-1]
        for i,d in enumerate(div):
            dat = d.text.split('\n')
            if dat[0] == '曲情報なし':
                continue
            unofficial_lv = dat[1].strip()
            for l in dat[2:-1]:
                if l[:-4] in conv.keys():
                    tmp = conv[l[:-4]]
                    # (DD)とかを消す処理
                    for v in vers:
                        if tmp[-len(v)-3:] == f" ({v})":
                            tmp = tmp[:-len(v)-3]
                    title = (tmp, play_style.dp , convert_difficulty(l[-2]))
                else:
                    tmp = l[:-4]
                    # (DD)とかを消す処理
                    for v in vers:
                        if tmp[-len(v)-3:] == f" ({v})":
                            tmp = tmp[:-len(v)-3]
                    title = (tmp, play_style.dp , convert_difficulty(l[-2]))
                ret[title] = unofficial_lv
        return ret
    if download:
        try:
            session = requests.session()
            url = 'https://zasa.sakura.ne.jp/dp/rank.php'
            songdb = {}
            # 古い順に実行すればOK。同じkeyが即上書きとすれば最新の難易度だけ残る。
            for ver in list(range(1,31)):
                print(f"ver = {ver}")
                data={'env':f'a{ver:02d}0', 'submit':'表示', 'cat':'0', 'mode':'m1', 'offi':'0'}
                r = session.post(url, data=data)
                dic = parse_lv_table(r.text)
                songdb.update(dic)
            with open(pkl_path, 'wb') as f:
                pickle.dump(songdb, f)
        except Exception as e:
            print(f"DP unofficial download failed; using cached data if available: {e}")
    return load_pickle_or_empty(pkl_path, 'DP unofficial data')

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
        add_preserving_existing(sdb, new)

def preserve_songinfo(existing:OneSongInfo, new:OneSongInfo):
    """既存DBにしかない手入力/旧キャッシュ由来の補助情報を引き継ぐ。"""
    if existing is None:
        return new

    preserve_attrs = [
        'notes',
        'version',
        'music_pack',
        'min_bpm',
        'max_bpm',
        'rader_notes',
        'rader_peak',
        'rader_scratch',
        'rader_soflan',
        'rader_charge',
        'rader_chord',
        'sp12_hard',
        'sp12_clear',
        'sp12_title',
        'sp11_hard',
        'sp11_clear',
        'cpi_easy',
        'cpi_clear',
        'cpi_hard',
        'cpi_exh',
        'cpi_fc',
        'katate_12',
        'katate_11',
        'bpim2_title',
        'dp_unofficial',
        'dp_ereter_easy',
        'dp_ereter_hard',
        'dp_ereter_exh',
    ]
    for attr in preserve_attrs:
        if getattr(new, attr, None) is None:
            setattr(new, attr, getattr(existing, attr, None))
    return new

def add_preserving_existing(sdb:SongDatabase, new:OneSongInfo):
    existing = sdb.search(
        title=new.title,
        play_style=new.play_style,
        difficulty=new.difficulty,
    )
    sdb.add(preserve_songinfo(existing, new))

def set_bpim(bpi:dict, sdb:SongDatabase, conv:dict=None):
    '''SongDatabaseにBPI Manager用データを埋め込む。見つからなかった曲一覧を返す'''
    not_found = []
    if not bpi:
        return not_found
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

args = parse_args() if __name__ == '__main__' else argparse.Namespace(download=False)
download = args.download

sp12 = get_sp12_unofficial(download=download)
bpi = get_bpim_data(download=download) if getattr(args, 'legacy_bpi', False) else {}

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

conv_dp ={
    "†渚の小悪魔ラヴリィ〜レイディオ†(II":"†渚の小悪魔ラヴリィ～レイディオ†(II",
    "かげぬい 〜 Ver.BENIBOTAN":"かげぬい ～ Ver.BENIBOTAN",
    "カゴノトリ〜弐式〜":"カゴノトリ～弐式～",
    "キャトられ♥恋はモ〜モク":"キャトられ恋はモ～モク",
    "ギョギョっと人魚♨爆婚ブライダル":"ギョギョっと人魚 爆婚ブライダル",
    "クルクル☆ラブ〜Opioid Pepti":"クルクル☆ラブ～Opioid Pepti",
    'ピアノ協奏曲第1番"蠍火"':"ピアノ協奏曲第１番”蠍火”",
    "フェティッシュペイパー〜脇の汗回転ガール":"フェティッシュペイパー ～脇の汗回転ガール～",
    'ワルツ第17番 ト短調"大犬のワルツ"':"ワルツ第17番 ト短調”大犬のワルツ”",
    "全力 SPECIAL VACATION!":"全力 SPECIAL VACATION!",
    "共犯ヘヴンズコード":"共犯へヴンズコード",
    "夕焼け 〜Fading Day〜":"夕焼け ～Fading Day～",
    "太陽〜T・A・I・Y・O〜":"太陽～T・A・I・Y・O～",
    "恋する☆宇宙戦争っ!!":"恋する☆宇宙戦争っ！！",
    "旋律のドグマ〜Misérables〜":"旋律のドグマ～Miserables～",
    "焱影":"火影",
    "花吹雪 〜 IIDX LIMITED 〜":"花吹雪 ～ IIDX LIMITED ～",
    "草原の王女-奇跡を辿って-":"草原の王女-軌跡を辿って-",
    "表裏一体！？怪盗いいんちょの悩み♥":"表裏一体！？怪盗いいんちょの悩み",
    "超!!遠距離らぶ♡メ〜ル":"超!!遠距離らぶメ～ル",
    "野球の遊び方 そしてその歴史 〜決定版〜":"野球の遊び方 そしてその歴史 ～決定版～",
    "麗 〜うらら〜":"麗 ～うらら～",
    '100% minimoo-G':'100％ minimoo-G',
    '19,November':'19，November',
    '50th Memorial Songs -二人の時 〜under the cherry blossoms〜-':'50th Memorial Songs -二人の時 ～under the cherry blossoms～-',
    'A MINSTREL 〜 ver. short-scape 〜':'A MINSTREL ～ ver. short-scape ～',
    'Amor De Verão':'Amor De Verao',
    'Apocalypse 〜dirge of swans〜':'Apocalypse ～dirge of swans～',
    'BALLAD FOR YOU〜想いの雨〜':'BALLAD FOR YOU～想いの雨～',
    'Be Rock U(1998 burst style)':'Be Rock U (1998 burst style)',
    'Best Of Me':'Best of Me',
    'Blind Justice 〜Torn souls, Hurt Faiths〜':'Blind Justice ～Torn souls， Hurt Faiths ～',
    'BLO§OM':'BLOSSOM',
    'CaptivAte2〜覚醒〜':'CaptivAte2～覚醒～',
    'CaptivAte〜浄化〜':'CaptivAte～浄化～',
    'CaptivAte〜裁き〜':'CaptivAte～裁き～',
    'CaptivAte〜裁き〜(SUBLIME TECHNO MIX)':'CaptivAte～裁き～(SUBLIME TECHNO MIX)',
    'CaptivAte〜誓い〜':'CaptivAte～誓い～',
    'CaptivAte2 〜覚醒〜':'CaptivAte2～覚醒～',
    'CaptivAte 〜浄化〜':'CaptivAte～浄化～',
    'CaptivAte 〜裁き〜':'CaptivAte～裁き～',
    'CaptivAte 〜裁き〜(SUBLIME TECHNO MIX)':'CaptivAte～裁き～(SUBLIME TECHNO MIX)',
    'CaptivAte 〜誓い〜':'CaptivAte～誓い～',
    'City Never Sleeps (IIDX EDITION)':'City Never Sleeps (IIDX Edition)',
    'CODE:Ø':'CODE:0',
    'CROSSROAD 〜Left Story〜':'CROSSROAD ～Left Story～',
    'DEATH†ZIGOQ〜怒りの高速爆走野郎〜':'DEATH†ZIGOQ ～怒りの高速爆走野郎～',
    'DENJIN AKATSUKINITAORERU-SF PureAnalogSynth Mix-':'DENJIN AKATSUKINI TAORERU -SF PureAnalogSynth Mix-',
    'DM STAR〜関西 energy style〜':'DM STAR～関西 energy style～',
    'DORNWALD 〜Junge〜':'DORNWALD ～Junge～',
    'Double♥♥Loving Heart':'Double Loving Heart',
    'e-motion 2003 -romantic extra-':'e-motion 2003  -romantic extra-',
    'Eine Haube 〜聖地の果てにあるもの〜':'Eine Haube ～聖地の果てにあるもの～',
    'Geirskögul':'Geirskogul',
    'i feel...':'i feel ...',
    'LETHEBOLG 〜双神威に斬り咲けり〜':'LETHEBOLG ～双神威に斬り咲けり～',
    'Light and Cyber･･･':'Light and Cyber…',
    'London Affairs Beckoned WithMoney Loved By Yellow Papers.':'London Affairs Beckoned With Money Loved By Yellow Papers.',
    'LOVE AGAIN TONIGHT〜for Mellisa mix〜':'LOVE AGAIN TONIGHT～for Mellisa mix～',
    'Love♡km':'Love km',
    'LOVE♡SHINE':'LOVE SHINE',
    'Mächö Mönky':'Macho Monky',
    'never...':'never…',
    'PARANOIA MAX〜DIRTY MIX〜':'PARANOIA MAX～DIRTY MIX～',
    'PARANOiA 〜HADES〜':'PARANOiA ～HADES～',
    'Programmed Sun (xac Antarctic Ocean mix)':'Programmed Sun(xac Antarctic Ocean mix)',
    'Präludium':'Praludium',
    'quell〜the seventh slave〜':'quell～the seventh slave～',
    "Raison d'être〜交差する宿命〜":"Raison d'etre～交差する宿命～",
    'Raspberry♥Heart(English version)':'Raspberry Heart(English version)',
    'spiral galaxy -L.E.D. STYLESPREADING PARTICLE BEAM MIX-':'spiral galaxy -L.E.D. STYLE SPREADING PARTICLE BEAM MIX-',
    'Sweet Sweet♥Magic':'Sweet Sweet Magic',
    'The Sealer 〜ア・ミリアとミリアの民〜':'The Sealer ～ア・ミリアとミリアの民～',
    'Time to Empress':'Time To Empress',
    'Turii 〜Panta rhei〜':'Turii ～Panta rhei～',
    'ULTiM∧TE':'ＵＬＴｉＭΛＴＥ',
    'Winning Eleven9 Theme (IIDX EDITION)':'Winning Eleven9 Theme(IIDX EDITION)',
    'XENON II 〜TOMOYUKIの野望〜':'XENON II ～TOMOYUKIの野望～',
    'ZETA〜素数の世界と超越者〜':'ZETA～素数の世界と超越者～',
    '¡Viva!':'!Viva!',
    'ÆTHER':'ATHER',
    'Übertreffen':'Ubertreffen',
    'Ōu Legends':'Ou Legends',
    '全力 SPECIAL VACATION!! 〜限りある休日〜': '全力 SPECIAL VACATION!! ～限りある休日～',
    '†渚の小悪魔ラヴリィ〜レイディオ†(IIDX EDIT)':'†渚の小悪魔ラヴリィ～レイディオ†(IIDX EDIT)',
    'かげぬい 〜 Ver.BENIBOTAN 〜':'かげぬい ～ Ver.BENIBOTAN ～',
    'クルクル☆ラブ〜Opioid Peptide MIX〜':'クルクル☆ラブ～Opioid Peptide MIX～',
    'フェティッシュペイパー〜脇の汗回転ガール〜':'フェティッシュペイパー ～脇の汗回転ガール～',
    'L.F.O.':'L.F.O',
    "Raison d'être～交差する宿命～":"Raison d'etre～交差する宿命～",
    'カゴノトリ ～弐式～':'カゴノトリ～弐式～',
    'ZETA ～素数の世界と超越者～':'ZETA～素数の世界と超越者～',
    'era (nostal mix)':'era (nostalmix)',
    'DISAPPEAR feat. Koyomin':'DISAPPEAR feat. koyomin',
    'Χ-DEN':'X-DEN',
    'Anisakis -somatic mutation type "Forza"-':'Anisakis -somatic mutation type"Forza"-'
}

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

# DP非公式難易度
dp = get_dp_unofficial(conv_dp, download=download)

dp_not_found = []
for k in dp:
    title, style, diff = k
    chart_id = calc_chart_id(title, style, diff)
    if sdb.search(chart_id = chart_id):
        sdb.songs[chart_id].dp_unofficial = float(dp[k])
    else:
        dp_not_found.append(k)

# DP ereter難易度 (EC/HC/EXH diff)
ereter = get_ereter_dp(download=download)

conv_ereter = {
    # ereter側の曲名: inf-notebook側の曲名
}
ereter_not_found = []
for k in ereter:
    title, style, diff = k
    song = sdb.search(title=title, play_style=style, difficulty=diff)
    if song is None and title in conv_ereter:
        song = sdb.search(title=conv_ereter[title], play_style=style, difficulty=diff)
    if song:
        song.dp_ereter_easy = ereter[k]['easy']
        song.dp_ereter_hard = ereter[k]['hard']
        song.dp_ereter_exh = ereter[k]['exh']
    else:
        ereter_not_found.append(k)
print(f"ereter not found: {len(ereter_not_found)}")
for e in ereter_not_found:
    print(f"  {e}")

sdb.save()
if getattr(args, 'skip_katate', False):
    print("skipping katate difficulty update")
else:
    print("updating katate difficulty...")
    update_katate_difficulty.main([])
