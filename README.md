# 概要
beatmania IIDX INFINITAS専用の打鍵カウンタです。

SP,DPのどちらにも対応しています。  
コントローラからの入力ではなく、画面上のEXスコアを取得する方式を取っています。  
あらかじめ設定した目標スコアレートをもとに、EXスコアから叩いたノーツ数を推定します。

HTMLでリアルタイム表示するためのIFを備えており、OBSでの配信で使いやすくなっています。

# 動作環境
下記の環境で確認しています。
```
OS: Windows10 64bit(21H2)
CPU: Intel系(i7-12700F)
GPU: NVIDIA系(RTX3050)
ウイルス対策ソフト: Windows Defender
```

注意点
- 32bitOSでは動作しません。
- スクリーンショットを封じてくる系のウイルス対策ソフト(カスペルスキー他多数)がいる環境では恐らく動きません

# 本ツールのメリット
## SP,DPの両方に対応
本ツールはDPでも使えます。  
また、1P/2P/DPを自動判別する仕様のため、1日にSP/DPを両方やる人にも対応できます。  
あと、DBMにも対応しています(内部的にはDP扱い)。

## 曲中以外(選曲画面など)での打鍵をカウントしない
EXスコアベースなので、選曲画面で迷子になる人や空打ちの多い人も安心です。  
1日の目標をEXスコアベースにするのも良いかもしれません。

## OBSでの配信で使いやすい
OBSのブラウザソースで読み込めるhtmlを同梱しているため、配信のたびに適切な位置にウィンドウを移動する作業が不要です。  
(INFINITASで使っているモニタ内にあるウィンドウはOBSで拾えない)

また、HTMLなので表示部分の見た目をCSSによって自由にカスタマイズできます。  
(以下にCSSのサンプルも記載しています)

# インストール方法
[リリースページ](https://github.com/dj-kata/inf_daken_counter/releases)から最新版のパッケージ(.zip)をダウンロードし、好きなフォルダに解凍してください。

# ファイル一覧
|ファイル名|説明|
|---|---|
|notes_counter.exe|ツール本体|
|autoload.html|OBSで読み込むHTMLファイル|
|data.xml|自動生成されるスコア情報|
|settings.json|ツール本体の設定ファイル。|
|README.txt|本説明書|
|icon.ico|アイコンファイル。多分無くても動くが一応入れている。|
|LICENSE|ライセンス情報|

# 使い方
## notes_counter.exeの使い方
1. notes_counter.exeを起動する。
2. INFINITASで使うモニタの位置を設定する。(一番左のモニタの左上を(0,0)としてsx,syに設定)
3. 目標とするスコアレートを設定する。1日の平均スコアレートを入れるのが良いと思います。スコアレートが高いほどEXスコアに対する推定ノーツ数が少なくなります。
4. startをクリックする。(```起動時に即start```にチェックすると、次回以降はスキップ可能)
5. INFINITASをプレーする。

resetをクリックするとカウンタ(プレー回数・合計EXスコア)をリセットできます。  
また、```start時にreset```にチェックしておくと、start後にカウンタを自動でリセットします。  
(resetを押しても即座に設定ファイルから消えるようにはしていません。間違えて押してしまった場合は、すぐにnotes_counter.exeを終了すればカウント値を元に戻せます。)  
![image](https://user-images.githubusercontent.com/61326119/182029142-f7eb1ad2-ba5e-4b0d-9ea1-ea109ceddbca.png)

tweetをクリックすると、その時点でのプレー曲数・推定ノーツ数をTwitterに投稿できます。  
(ブラウザが開きます)

### ゲーム画面位置の設定について
正しいモニタが設定されているかの確認のために、Testボタンが使えます。  

Testボタンを押すと、設定された左上座標から1280×720だけ切り取った画像をtest.pngに保存します。  
test.pngを見て正しいモニタから取得できていることを確認してください。

作者の環境(2560×1440のモニタ3枚が横に並んでいて、真ん中のモニタでプレイしている)では、```sx:2560, sy:0```を設定します。

## OBSへの設定方法
1. ソースの追加 -> ブラウザを選択する。好きな名前を付けてOK。  
![image](https://user-images.githubusercontent.com/61326119/182008724-44d2711d-fb3e-4e32-b1f1-9fa95b8ed751.png)
2. 1.で作成したブラウザソースをダブルクリックする。
3. ローカルファイルのチェックを入れ、同梱のautoload.htmlを選択する。
4. 幅1200、高さ600ぐらいに設定する。(Alt+ドラッグでトリミングできるので小さすぎなければ適当で良いです)
5. 必要に応じて以下のようなカスタムCSSを設定する。

```
body { 

background-color: rgba(0, 0, 50, 0.8);
margin: 10px;
padding: 20px;
overflow: hidden;
font-family:"Meiryo";
color:#2196F3;   
font-size: 64px;
color: #fff;
text-shadow: 6px 6px 0 #000,
             -2px 2px 0 #000,
             2px -2px 0 #000,
             -2px -2px 0 #000;
}
```

![image](https://user-images.githubusercontent.com/61326119/182008763-7ff255a4-890b-4fe8-9b00-4cf9b1bed0aa.png)

# AMDのCPU(Ryzenなど)をお使いの方向け
AMDのCPU(Ryzenなど)を搭載したPCではかなり重くなってしまうようです。  
このような方は、Windows版Pythonをインストールし、  
```python -m pip install pyautogui PySimpleGUI numpy keyboard```  
した上で[ソースコード](https://github.com/dj-kata/inf_daken_counter/archive/refs/heads/main.zip)内のnotes_counter.pywをダブルクリックして実行してください。  

# その他
設定ファイル(settings.json)がない場合は起動時に生成されます。  
設定がおかしくなった場合は起動前にsettings.jsonを削除すればリセットできます。

スコア取得開始後はdata.xmlにデータが逐次書き込まれます。

(わかる人向け)ソースコードから実行する場合は、Windows版Python3をインストールし、  
```$ pip install pyautogui PySimpleGUI numpy keyboard```  
のように必要なパッケージをインストールしてからnotes_counter.pywをダブルクリックしてください。

スコア取得間隔はsettings.jsonのsleep_timeから変更可能です(デフォルト:1秒)。  
密度の高い曲でクイックリトライした場合は取得が追いつかず、少し低めに出る場合があります。  
厳密さを求める方はsleep_timeを小さめに設定してもいいかもしれません。

フルコンエフェクトが派手だと最後のノーツのスコアが反映されないかもしれません。  
CANNON BALLERZのフルコンエフェクトだと影響を受けにくいです。

当分ないと思いますが、プレー画面のレイアウトが変わると使えなくなります。  
その際はなるべく早く対応するつもりですが、ベストエフォートな対応となりますことをご了承ください。

# ライセンス
Apache License 2.0に準じるものとします。

非営利・営利問わず配信などに使っていただいて問題ありません。  
クレジット表記等も特に必要ないですが、書いてもらえたら喜びます。

# 連絡先
Twitter: @cold_planet_
