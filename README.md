# INFINITAS打鍵カウンタ(OBS websocket版)
beatmania IIDX INFINITAS専用の打鍵カウンタです。

SP,DPのどちらにも対応しています。  
リアルタイム判定内訳表示の部分を逐次スキャンし、叩いたノーツ数を算出します。  
その日の各判定(ピカグレ、黄グレ、…)の合計値も表示します。
その日に打鍵したノーツ数をTwitterに投稿するための機能も備えています。

また、HTMLでリアルタイム表示するためのIFを備えており、OBS配信でも使いやすくなっています。

# 動作環境
下記の環境で確認しています。
```
OS: Windows10 64bit(21H2)
CPU: Intel系(i7-12700F)
GPU: NVIDIA系(RTX3050)
ウイルス対策ソフト: Windows Defender
OBS: 29.0.2
```

注意点
- OBS28.0以降でないと動きません。OBS27以前を使いたい方は、[前のバージョン](https://github.com/dj-kata/inf_daken_counter)をお使いください。
- 32bitOSでは動作しません。
- プレー設定(Start->E2)の「判定の数リアルタイム表示」を有効にしないと動きません

# 本ツールのメリット
## SP,DPの両方に対応
本ツールはDPでも使えます。  
また、1P/2P/DPを自動判別する仕様のため、1日にSP/DPを両方やる人にも対応できます。  
あと、Double Battle系オプション(DBR,DBM,...)にも対応しています(内部的にはDP扱い)。

## 曲中以外(選曲画面など)での打鍵をカウントしない
選曲画面で迷子になる人や空打ちの多い人も安心です。  

## OBSでの配信で使いやすい
OBSのブラウザソースで読み込めるhtmlを同梱しているため、配信のたびに適切な位置にウィンドウを移動する作業が不要です。  
(INFINITASで使っているモニタ内にあるウィンドウはOBSで拾えない)

また、HTMLなので表示部分の見た目をCSSによって自由にカスタマイズできます。  
(以下にCSSのサンプルも記載しています)

# ファイル一覧
|ファイル名|説明|
|---|---|
|notes_counter.exe|ツール本体|
|layout\autoload.html|OBSで読み込むノーツ数表示用HTMLファイル|
|layout\option.html|OBSで読み込むオプション表示用HTMLファイル|
|layout\gauge.html|OBSで読み込むグルーブゲージ情報表示用HTMLファイル|
|layout\graph.html|OBSで読み込むノーツ数リアルタイム表示用HTMLファイル|
|layout\judge.html|OBSで読み込む判定内訳表示用HTMLファイル|
|data.xml|自動生成されるスコア情報|
|option.xml|自動生成される設定中のオプション情報|
|settings.json|ツール本体の設定ファイル。|
|README.txt|説明書|
|LICENSE|ライセンス情報|

# インストール方法
## 打鍵カウンタのインストール
[リリースページ](https://github.com/dj-kata/inf_daken_counter_obsw/releases)から最新版のパッケージ(.zip)をダウンロードし、好きなフォルダに解凍してください。  
アップデートする場合は、古いバージョンのフォルダを最新版のファイルで上書きしてください。  
(settings.jsonを新バージョンのフォルダに移行するだけでもOK)

## OBSwebsocketのインストール
また、[OBSwebsocket](https://github.com/obsproject/obs-websocket/releases)もインストールしておいてください。  
5.0のアルファ版は不安定らしいので、4.9系を推奨します。(2023/3/16時点)

OBSのメニューバー内ツール -> obs-websocket設定 を開き、
- WebSocketサーバを有効にする にチェック
- システムトレイアラートを有効にする にチェック
- サーバーパスワードを好きな文字列に変更(打鍵カウンタにも入力するので忘れないように注意)

しておいてください。  
![image](https://user-images.githubusercontent.com/61326119/225536753-c118d425-c0dc-4555-b2a4-9a50076e5993.png)

## 打鍵カウンタの設定
in_daken_counter内のnotes_counter.exeを実行します。  
メニューバー内ファイル -> 設定 を開きます。

OBSwebsocket関連の情報を入力してください。  
- OBS hostは基本的にlocalhostで良いはずですが、環境に応じてローカルIPアドレスを設定してください。
- OBS websocket portはOBS側と同一の値に設定してください。(OBS側を変更していなければ4444)
- OBS websocket passwordはOBS側で設定したサーバーパスワードと同一のものを入力してください。
- INFINITAS用ソース名にはOBS側でINFINITASの画面を取り込んでいるゲームキャプチャソースの名前を入力してください。
![image](https://user-images.githubusercontent.com/61326119/225537930-49d98183-46b3-499d-a1d1-31f7d95e9dd3.png)

参考までに、作者がINFINITAS用に使っているゲームキャプチャソースの設定も載せておきます。  
(INFINITASという名前にしています)  
![image](https://user-images.githubusercontent.com/61326119/225539433-eb40a3e1-958e-4d64-a3c2-2dacb3c06441.png)

正しく設定できていれば、打鍵カウンタの設定画面を閉じた時に以下のような接続通知が出ます。  
![image](https://user-images.githubusercontent.com/61326119/225539830-22796190-d969-4866-932c-1e220f3e1ae4.png)

websocket設定及びINFINITAS用ソース名が正しく設定されていれば、  
testボタンを押した時にキャプチャ画像の保存が行われます。  
うまく動かない場合は確認してみてください。
![image](https://user-images.githubusercontent.com/61326119/225552625-a7ff3dc4-5500-4ed4-9353-6615c8afd113.png)

# 使い方
1. OBSを起動する。
2. notes_counter.exeを起動する。
3. startをクリックする。(```起動時に即start```にチェックすると、次回以降はスキップ可能)
4. INFINITASをプレーする。

resetをクリックするとカウンタ(プレー回数・ノーツ数・各判定値)をリセットできます。  
また、```start時にreset```にチェックしておくと、start後にカウンタを自動でリセットします。  
(resetを押しても即座に設定ファイルから消えるようにはしていません。間違えて押してしまった場合は、すぐにnotes_counter.exeを終了すればカウント値を元に戻せます。)  
![image](https://user-images.githubusercontent.com/61326119/225540137-a724ec95-3642-4031-b9de-b5b4403fbb08.png)

tweetをクリックすると、その時点でのプレー曲数・ノーツ数をTwitterに投稿できます。  
(ブラウザが開きます)
![image](https://user-images.githubusercontent.com/61326119/225540232-9ea35c48-a228-4a81-bdb4-72ab5e004248.png)

## OBSへの設定方法
### ノーツ数グラフの表示方法
1. ソースの追加 -> ブラウザを選択する。好きな名前を付けてOK。  
![image](https://user-images.githubusercontent.com/61326119/182008724-44d2711d-fb3e-4e32-b1f1-9fa95b8ed751.png)
2. 1.で作成したブラウザソースをダブルクリックする。
3. ローカルファイルのチェックを入れ、同梱のlayout\graph.htmlを選択する。
4. 画面の大きさは幅800、高さ400ぐらいに設定する。(Alt+ドラッグでトリミングできるので小さすぎなければ適当で良いです)
5. 背景に色を付ける場合は以下のようなカスタムCSSを設定する。(graph.htmlのみOBS側での設定が必要。他はHTML内の変更でもOK。)
```
body { background-color: rgba(0, 0, 0, 0.8); margin: 0px auto; overflow: hidden; }
```
![image](https://user-images.githubusercontent.com/61326119/225551460-856b8fc3-0731-465e-b202-bc33bcf8d7ca.png)

### プレーオプションの表示方法
プレーオプション(乱やFLIP等)をOBSに表示するためのlayout\option.htmlも同梱しています。  
プレーオプション設定画面を開くと自動でオプション情報を取得します。  
(オプション取得処理に0.5秒くらいかかるため、Startボタンを離すのが速すぎると取得できません)

こちらもOBSでの設定方法は同様ですが、そのまま使う場合は幅2000,高さ130ぐらいにするといいかもです。  
プレー画面でのみオプションを表示するためのタグ(<opt_dyn>)も用意しています。  
必要に応じてHTMLを修正しながら使っていただけたらと思います。

![image](https://user-images.githubusercontent.com/61326119/187085019-392eed60-71f5-4380-b2b4-43e3b9df533f.png)

### グルーブゲージ情報の表示方法
グルーブゲージ種別(EX-HARDとかEASYとか)を表示するためのlayout\gauge.htmlも同梱しています。  
取得タイミングはプレーオプションと同時(約0.5s必要)なので、切り替えが速すぎると取得漏れする場合があります。  

また、曲中だけオプションを表示するための<normal_dyn>などのタグも用意しています。  
(layout\gauge.html内でコメントアウトしています)
必要に応じてHTMLを編集して使ってください。

### 配信タイトル内のシリーズ文字列の表示方法
**第237回**のような文字列を配信タイトルから抽出して表示するlayout\series.html及び、  
**九段たぬきのDP配信**のような固定のタイトル部分を抽出するlayout\basetitle.htmlも同梱しています。  
下記画像の赤枠で囲んだ領域を自動で更新してくれる感じのやつです。
![image](https://user-images.githubusercontent.com/61326119/225545656-26384c8c-fd45-460c-9c6a-4753b596d7fc.png)

配信を行う度に、以下のようにURLを取り込む必要があります。

1. ファイル -> 配信を告知する を押して配信準備用ウィンドウを開く
2. YoutubeLiveのURLを入力する
3. タイトル文字列に応じて検索クエリを設定する。  
(例えば、九段たぬきのINFINITAS DP配信 #85 のようなタイトルの場合、#[number]と設定)
4. goボタンをクリック(または入力欄でEnterキーを押す)
5. ブラウザにて配信情報をツイートするための画面が表示されます。また、アプリ上にOBSで使うコメント欄用のURLが表示されます。

![image](https://user-images.githubusercontent.com/61326119/225545103-15dff519-9e11-400f-b6f5-13d1fe5865a5.png)
![image](https://user-images.githubusercontent.com/61326119/225545357-5c515419-0bae-4853-9f60-8048e83048bf.png)

あとは、OBSのブラウザソースでseries.html, basetitle.htmlを取り込んでおいてください。  

# その他
設定ファイル(settings.json)がない場合は起動時に生成されます。  
設定がおかしくなった場合は起動前にsettings.jsonを削除すればリセットできます。

スコア取得開始後はdata.xmlにデータが逐次書き込まれます。

スコア取得間隔はsettings.jsonのsleep_timeから変更可能です(デフォルト:1秒)。  
密度の高い曲でクイックリトライした場合は取得が追いつかず、少し低めに出る場合があります。  
厳密さを求める方はsleep_timeを小さめに設定してもいいかもしれません。

当分ないと思いますが、プレー画面のレイアウトが変わると使えなくなります。  
その際はなるべく早く対応するつもりですが、ベストエフォートな対応となりますことをご了承ください。

# ライセンス
Apache License 2.0に準じるものとします。

非営利・営利問わず配信などに使っていただいて問題ありません。  
クレジット表記等も特に必要ないですが、書いてもらえたら喜びます。

# 連絡先
Twitter: @cold_planet_
