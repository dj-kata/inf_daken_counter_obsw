# INFINITAS打鍵カウンタ(OBS websocket版)
beatmania IIDX INFINITAS専用の打鍵カウンタです。

SP,DPのどちらにも対応しています。  
リアルタイム判定内訳表示の部分を逐次スキャンし、叩いたノーツ数を算出します。  
その日の各判定(ピカグレ、黄グレ、…)の合計値も表示します。  
(画面の情報を画像処理によって取得しているのみで、リバースエンジニアリングの類ではありません)

その日に打鍵したノーツ数をTwitterに投稿するための機能も備えています。

また、HTMLでリアルタイム表示するためのIFを備えており、OBS配信でも使いやすくなっています。

<img width="900" alt="image" src="https://github.com/user-attachments/assets/756c6650-4a18-496a-b2be-7b2fce05a220" />  
<img width="700" alt="tmp" src="https://github.com/user-attachments/assets/84ca293c-e186-4fe6-a77c-00fd8dc0152b" />
<img width="450" alt="inf_ディスコルディア_SPA_hard_ex3146_bp48_20260327_190654_cut2p" src="https://github.com/user-attachments/assets/e38e492d-4c6c-4145-b4e9-33f0719bae67" />
<img width="700" alt="image" src="https://github.com/user-attachments/assets/e2fc41c6-035f-4a42-8719-7dd19fd85588" />

動作例  
https://youtu.be/6oGS0dvHhGQ

# 動作環境
下記の環境で確認しています。
```
OS: Windows10 64bit(22H2)
CPU: Intel系(i7-12700F)
GPU: NVIDIA系(RTX3050)
ウイルス対策ソフト: Windows Defender
OBS: 29.1.2
```

注意点
- OBS28.0以降でないと動きません。
- 32bitOSでは動作しません。
- 一部の機能はプレー設定(Start->E2)の「判定の数リアルタイム表示」を有効にしないと動きません
- INFINITAS用PCから配信用PCにキャプチャボード経由で映像を送る構成では動きません。

# 本ツールのメリット
## SP,DPの両方に対応
本ツールはDPでも使えます。  
また、1P/2P/DPを自動判別する仕様のため、1日にSP/DPを両方やる人にも対応できます。  
あと、Double Battle系オプション(DBR,DBM,...)にも対応しています。

## 曲中以外(選曲画面など)での打鍵をカウントしない
選曲画面で迷子になる人や空打ちの多い人も安心です。  

## OBSでの配信で使いやすい
OBSのブラウザソースで読み込めるhtmlを同梱しているため、配信のたびに適切な位置にウィンドウを移動する作業が不要です。  
(INFINITASで使っているモニタ内にあるウィンドウはOBSで拾えない)

また、HTMLなので表示部分の見た目をCSSによって自由にカスタマイズできます。  

# 設定方法
こちらの[wiki](https://github.com/dj-kata/inf_daken_counter_obsw/wiki)を参照してください。

リポジトリ内の[説明書サイト原稿](docs/index.md)も順次整備しています。
画像保存の設定は[こちら](docs/image-save.md)、プレビューや更新方法は[作業者向け手順](docs/README.md)を参照してください。

## RANDOM配置認識（SP・Spout）
「ゲーム画面取得」でSpoutを選び、RANDOMレーン配置認識を有効にしてください。
1920×1080のゲーム映像を使い、最初にオプション画面を開いて配置を認識させます。
REGULARまたはMIRRORで譜面データを登録すると、同じ譜面のRANDOM・R-RANDOM配置を解析できます。

検出帯は1P／2P別に上端（ROI内Y）と高さを設定できます。初期値は上端55・高さ20pxです。
高さは1～300pxで、広げすぎると近接ノーツを区別できなくなる場合があります。
検出帯の変更は次のプレーから適用され、変更後の帯でREGULARまたはMIRRORの登録が必要です。
初期値に戻すと、従来の譜面データを再び使えます。

## HTTPサーバからのリザルト画像投稿

HTTPサーバの「RESULT IMAGES」やプレー履歴から、ファイル保存していないリザルトも投稿用画像に選べます。
保持枚数や画像の加工、再起動時の扱いは[画像保存の説明書](docs/image-save.md)を参照してください。

# for developers
環境構築方法は以下。  
Windows版uvのインストールが必要となります。(以下wuvとして記載)
```bash
git clone https://github.com/dj-kata/inf_daken_counter_obsw.git
cd inf_daken_counter_obsw
git clone https://github.com/kaktuswald/inf-notebook.git infnotebook
touch infnotebook/__init__.py

# (Windows版uvを使う)
wuv sync

# inf-notebook実行時に生成される最新のresourcesディレクトリをコピー
cp -a $(inf-notebook-binary-dir)/resources inf_daken_counter_obsw/

make
```

DB更新時、片手難易度表は通常ネットワーク取得せず `misc/katate_difficulty.csv` があればそれを使います。Google SheetsからCSVを手動ダウンロードして以下のどちらかで更新できます。

```bash
python misc/update_db.py --katate-csv misc/katate_difficulty.csv
python misc/update_katate_difficulty.py --input-csv misc/katate_difficulty.csv
```

従来通り片手難易度表をオンライン取得したい場合は `python misc/update_db.py --download-katate` を使います。

# ライセンス
Apache License 2.0に準じるものとします。

非営利・営利問わず配信などに使っていただいて問題ありません。  
クレジット表記等も特に必要ないですが、書いてもらえたら喜びます。

# 連絡先
Twitter: @cold_planet_
