# INFINITAS打鍵カウンタ(OBS websocket版)
beatmania IIDX INFINITAS専用の打鍵カウンタです。

SP,DPのどちらにも対応しています。  
リアルタイム判定内訳表示の部分を逐次スキャンし、叩いたノーツ数を算出します。  
その日の各判定(ピカグレ、黄グレ、…)の合計値も表示します。  
(画面の情報を画像処理によって取得しているのみで、リバースエンジニアリングの類ではありません)

その日に打鍵したノーツ数をTwitterに投稿するための機能も備えています。

また、HTMLでリアルタイム表示するためのIFを備えており、OBS配信でも使いやすくなっています。

主な機能はこちらの動画で紹介しています。  
https://www.youtube.com/watch?v=1LSqYLQKDjU

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
- OBS28.0以降でないと動きません。OBS27以前を使いたい方は、[前のバージョン](https://github.com/dj-kata/inf_daken_counter)をお使いください。
- 32bitOSでは動作しません。
- プレー設定(Start->E2)の「判定の数リアルタイム表示」を有効にしないと動きません
- INFINITAS用PCから配信用PCにキャプチャボード経由で映像を送る構成では動きません。
- プレーログの保存は打鍵カウンタ終了時に行います。起動したままだとスコアビューワに反映できません。

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
こちらの[wiki](https://github.com/dj-kata/inf_daken_counter_obsw/wiki/%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参照してください。

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

# ライセンス
Apache License 2.0に準じるものとします。

非営利・営利問わず配信などに使っていただいて問題ありません。  
クレジット表記等も特に必要ないですが、書いてもらえたら喜びます。

# 連絡先
Twitter: @cold_planet_
