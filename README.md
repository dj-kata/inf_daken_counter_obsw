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
GPU: NVIDIA系(RTX5060)
ウイルス対策ソフト: Windows Defender
OBS: 32.0.0
```

注意点
- 32bitOSでは動作しません。
- 一部の機能はプレー設定(Start->E2)の「判定の数リアルタイム表示」を有効にしないと動きません
- Spout経由の画面取得やOBS自動制御起動を用いる場合は、OBS28.0以降でないと動きません。
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
[説明書](docs/index.md)を参照してください。
[通常の導入手順](docs/install.md)、[v2からの移行](docs/migration-v2.md)、[OBS向けHTMLビュー](docs/obs-views.md)を掲載しています。
画像保存の設定は[こちら](docs/image-save.md)、プレビューや更新方法は[作業者向け手順](docs/README.md)を参照してください。
[設定画面の各タブ](docs/settings.md)と[画面取得・Spoutの設定手順](docs/capture.md)も説明書内に掲載しています。

「追加設定」タブの「データ表示設定」にある「本日の成果に含めるオフセット」で、起動時刻の何時間前以降のリザルトを本日の成果に含めるか指定できます。例：4時間に設定して20:00に起動すると、16:00以降が対象です。データ表示用ポートも同じセクションで変更できます。画像保存先は「画像保存」タブで設定できます。

## ゲーム画面取得とOBS自動制御
新規設定の画面取得は「直接取得(GDI)」がデフォルトです（従来の「直接取得(旧方式)」）。
既存設定で選択した取得方式は維持されます。
OBS自動制御は「ゲーム画面取得」で選んだ方式の画像を判定に使います。
直接取得・Spoutの場合、OBS制御設定の「監視画像」に取得元を表示し、OBSの監視対象ソース指定は不要です。
OBSのシーン切り替えやソース操作には、別途OBS WebSocket接続が必要です。
OBS制御設定の先頭にある「OBS WebSocket連携を有効にする」をOFFにすると、パスワードや制御設定を残したまま連携を停止できます。OBS WebSocket経由での画面取得も停止します。
スマホ用サーバ・HTTPポート・表示NICは、追加設定の「スマホ連携(HTTPサーバ)設定」で変更できます。
表示・非表示・自動保存するソースは、引き続きOBSのソースから選択します。

## RANDOM配置認識（SP・Spout）
「基本設定」の「ゲーム画面取得」でSpoutを選び、「RANDOMレーン認識」タブで認識を有効にしてください。
1920×1080のゲーム映像を使い、「配置認識テンプレートフォルダ」に元のRandomLaneAnalysis_OCRで作成した`templates`フォルダを指定してください。
`SCRATCH.png`、`GET_READY.png`、`OP_CURRENT_SCORE.png`、`Op.MIRROR.png`、`Op.RANDOM.png`、`Op.R-.png`、`Op.S-.png`を使用します。画像はコピーせず、指定フォルダから読み込みます。
配置オプションはプレー画面のテンプレートから認識し、GET READYの表示と消失を各3フレーム確認してから記録・解析を開始します。本アプリのオプション画面認識には依存しません。テンプレート不足・未認識の場合は記録しません。設定を保存するとテンプレートを再読込します。
REGULARまたはMIRRORで譜面データを登録すると、同じ譜面のRANDOM・R-RANDOM配置を解析できます。
登録は全レーンが出現して配置を一意に識別できた時点で完了し、解析は5040候補をイベントごとに絞り込み、1候補になった時点で確定します。最低イベント数や一致率による判定は行いません。
GET READY消失後からのイベント列へ切り替えたため、従来の登録データは保持しますが、REGULARまたはMIRRORで再登録が必要です。

検出帯は「RANDOMレーン認識」タブで「デフォルト設定を変更する」にチェックすると、1P／2P別に上端（ROI内Y）と高さを編集できます。初期値は上端55・高さ20pxです。保存済みの値は維持されますが、誤操作防止のため設定画面を開くたびに編集がロックされます。
高さは1～300pxで、広げすぎると近接ノーツを区別できなくなる場合があります。
検出帯の変更は次のプレーから適用され、変更後の帯でREGULARまたはMIRRORの登録が必要です。
初期値に戻すと、従来の譜面データを再び使えます。

### 履歴・本日結果のレーン番号表示

`history_cursong.html`と`today_result.html`は、初期状態では従来のオプション名を表示します。
OBSのブラウザソースのカスタムCSSで、次の設定を加えるとレーン番号表示になります。

```css
body {
    --show-lane-numbers: 1;
}
```

`whole_layout.html`を使う場合は、そのブラウザソースに同じ設定を指定してください。
埋め込まれた履歴・本日結果の両方に反映されます。`0`でオプション名表示に戻ります。
REGULAR／MIRRORは固定配置、RANDOM／R-RANDOMは保存された配置を表示し、配置不明時はオプション名を表示します。
`template/v2/history_cursong.html`も同じ設定に対応しています。
配置の一部だけ分かった場合も、確定した数字と白鍵・青鍵の色を表示します。数字不明の鍵盤は文字なし、色も不明の鍵盤は灰色です。何も分からない場合はオプション名を表示します。部分配置もリザルトへ保存されます。
番号表示専用の`random_lane.html`は、この設定にかかわらず配置・部分配置を表示します。

## HTTPサーバからのリザルト画像投稿

HTTPサーバの「RESULT IMAGES」やプレー履歴から、ファイル保存していないリザルトも投稿用画像に選べます。
起動中に取得したリザルト画像は専用の一時フォルダに保持し、通常の画像保存先には、従来通り手動保存したものと自動保存条件を満たしたものだけを保存します。
一時画像にも画像保存設定のモザイク・カット・統計情報を適用します。

「追加設定」タブの「スマホ連携(HTTPサーバ)設定」で、一時保存機能の有効／無効と保持件数を設定できます。件数は「全件」「100件」「件数を指定」の3択です。初期値は有効・全件保持で、従来の設定も引き継ぎます。無効にして保存すると一時画像はすべて破棄され、以後の一時保存を停止します。通常保存した画像ファイルには影響しません。
例えば100にすると直近100枚を保持し、古い一時画像を削除します。上限の変更は即時反映され、一度削除した画像は復元されません。
一時画像は正常終了時に削除され、再起動後は利用できません。ファイルとして保存済みの画像は引き続き利用できます。
一時画像はPNG形式でディスクに保持するため、300枚程度でも非圧縮画像を全件メモリに保持する必要はありません（一時ディスク容量は画像内容に依存します）。

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

# 謝辞
下記OSSの機能を一部使わせてもらっています。  
- https://github.com/kaktuswald/inf-notebook/branches (曲名認識、リザルト情報取得)
- https://github.com/yuki-RAI01/RandomLaneAnalysis_OCR (レーン配置情報取得)

# 連絡先
Twitter: @cold_planet_
