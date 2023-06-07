#!/usr/bin/python3
# bemaniwikiの曲一覧から、各楽曲パックに含まれるSP12/DP12の曲数を算出
import pandas as pd
import pickle
from bs4 import BeautifulSoup
import requests
from collections import defaultdict
#url = 'http://bemaniwiki.com/index.php?beatmania%20IIDX%20INFINITAS/%C1%B4%B6%CA%A5%EA%A5%B9%A5%C8'
url = 'https://bemaniwiki.com/index.php?beatmania+IIDX+INFINITAS/%C1%ED%A5%CE%A1%BC%A5%C4%BF%F4%A5%EA%A5%B9%A5%C8'

req = requests.get(url)
soup = BeautifulSoup(req.text, 'html.parser')

df = pd.read_html(url)

# bemaniwikiの表の曲名をsongsに登録
songs = defaultdict(list)
for tr in soup.find_all('tr'):
    numtd = len(tr.find_all('td'))
    if numtd in (11,9):
        tmp = tr.find_all('td')
        title = tmp[0].text
        for sc in tmp[1:8]:
            try:
                songs[title].append(int(sc.text))
            except:
                songs[title].append(0)

# music4.0.jsonとの整合性確認
# AETHERやMacho Monkyなどが表記ゆれの関係になっている。
with open('resources/informations2.0.res', 'rb') as f:
    js = pickle.load(f)

ocr_title = js['music']['musics']

conv ={
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
}

# 一度置換候補を抽出
to_change = []
for s in songs.keys():
    if s in conv.keys():
        to_change.append(s)
# songs(現在:bemaniwikiの曲名リスト)のうち、inf-notebookと違う曲名のものを置換
# 表記ゆれを置換
for c in to_change:
    conv_k = conv[c]
    songs[conv_k] = songs[c]
    del songs[c]

not_found = sorted(sorted([k for k in songs.keys() if not k in ocr_title]), key=str.lower)
not_found_from_ocr = sorted(sorted([k for k in ocr_title if not k in songs.keys()]), key=str.lower)

print('見つからなかった曲')
for s in not_found_from_ocr:
    print(s)

with open('noteslist.pkl', 'wb') as f:
    pickle.dump(songs, f)

print('\n->noteslist.pkl updated!')