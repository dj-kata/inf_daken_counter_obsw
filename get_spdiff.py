#!/usr/bin/python3
import urllib, json, requests, pickle

url = 'https://sp12.iidx.app/api/v1/sheets'

tmp = urllib.request.urlopen(url).read()
diffs = json.loads(tmp)['sheets']

out = {}
diff_hard = {}
diff_clear = {}

conv ={
    "カゴノトリ〜弐式〜":"カゴノトリ～弐式～",
    "キャトられ♥恋はモ〜モク":"キャトられ恋はモ～モク",
    'ピアノ協奏曲第1番"蠍火"':"ピアノ協奏曲第１番”蠍火”",
    'ワルツ第17番 ト短調"大犬のワルツ"':"ワルツ第17番 ト短調”大犬のワルツ”",
    "恋する☆宇宙戦争っ!!":"恋する☆宇宙戦争っ！！",
    "旋律のドグマ〜Misérables〜":"旋律のドグマ～Miserables～",
    "焱影":"火影",
    "表裏一体！？怪盗いいんちょの悩み♥":"表裏一体！？怪盗いいんちょの悩み",
    'DEATH†ZIGOQ〜怒りの高速爆走野郎〜':'DEATH†ZIGOQ ～怒りの高速爆走野郎～',
    'DORNWALD 〜Junge〜':'DORNWALD ～Junge～',
    'Mächö Mönky':'Macho Monky',
    'PARANOiA 〜HADES〜':'PARANOiA ～HADES～',
    'quell〜the seventh slave〜':'quell～the seventh slave～',
    'spiral galaxy -L.E.D. STYLESPREADING PARTICLE BEAM MIX-':'spiral galaxy -L.E.D. STYLE SPREADING PARTICLE BEAM MIX-',
    'Ōu Legends':'Ou Legends',
    "†渚の小悪魔ラヴリィ〜レイディオ†(II":"†渚の小悪魔ラヴリィ～レイディオ†(II",
    '†渚の小悪魔ラヴリィ〜レイディオ†(IIDX EDIT)':'†渚の小悪魔ラヴリィ～レイディオ†(IIDX EDIT)',
}

for song in diffs:
    title = song['title']
    if title[-3:] == '[H]':
        title = title[:-3] + '___SPH'
    elif title[-3:] == '[A]':
        title = title[:-3] + '___SPA'
    elif title[-1] == '†':
        title = title[:-1] + '___SPL'
    else:
        if title in conv.keys():
            title = conv[title]
        title = title + '___SPA'
    diff_hard[title] = song['hard']
    diff_clear[title] = song['n_clear']

with open('resources/informations2.0.res', 'rb') as f:
    js = pickle.load(f)

ocr_title = js['music']['musics']
not_found = sorted(sorted([k for k in diff_hard.keys() if not k in ocr_title]), key=str.lower)
not_found_from_ocr = sorted(sorted([k for k in ocr_title if not k in diff_hard.keys()]), key=str.lower)

spdiff = {}
spdiff['hard'] = diff_hard
spdiff['clear'] = diff_clear
with open('sp_12jiriki.pkl', 'wb') as f:
    pickle.dump(spdiff, f)