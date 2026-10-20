# OBS向けHTMLビューの利用方法

打鍵カウンタに同梱されたHTMLをOBSの「ブラウザ」ソースに指定すると、
本日のプレーログ、単曲の履歴、ノーツ数などを配信画面に表示できます。
打鍵カウンタを起動したまま使ってください。

## OBSにビューを追加する

1. OBSの「ソース」の「＋」から「ブラウザ」を追加します。名前は分かりやすいもので構いません。
2. 「ローカルファイル」を有効にして、アプリの `template` フォルダにあるHTMLを選びます。
3. 下の一覧を参考に「幅」「高さ」を設定します。
4. ゲームをプレーし、ビューの内容が更新されることを確認します。

例えば、本日のプレーログを表示するなら `template/today_result.html` を選び、幅1920・高さ1080から調整します。
切れてしまう場合はブラウザソース自体の幅・高さを広げてから、OBS上で拡大縮小やトリミングをしてください。

HTMLビューは、打鍵カウンタの「データ表示用port」（初期値 **8767**）からデータを受け取ります。
**OBS WebSocketの接続設定は、ビューを表示するだけなら不要です。**
表示・非表示をゲーム画面に合わせて切り替える場合は、[OBS自動制御](obs-control.md)も設定します。

## 使えるビュー

サイズは初めに試す目安です。文字数や配信レイアウトに合わせて調整してください。

| ファイル（`template/` 内） | 内容 | 幅×高さの目安 |
| --- | --- | --- |
| `today_result.html` | 本日のプレーログ | 1920×1080 |
| `history_cursong.html` | 現在の曲のプレー履歴 | レイアウトに合わせて調整 |
| `rival.html` | 現在の曲のライバル比較 | レイアウトに合わせて調整 |
| `graph.html` | ノーツ数のグラフ | 500×250 |
| `option.html` | 現在のオプション | レイアウトに合わせて調整 |
| `today_stats.html` | 打鍵数・レベル別の統計とプレーログ | 2600×2200 |
| `today_receipt.html` | 本日の成果をレシート形式で表示 | 1500×1500 |
| `whole_layout.html` | 複数の情報を組み合わせた配信画面風レイアウト | 1920×1080 |
| `all_info.html` | 履歴・ライバル・グラフ・レシートをまとめて表示 | レイアウトに合わせて調整 |
| `column_log_cur_graph.html` | プレーログ・単曲履歴・グラフを横並びに表示 | レイアウトに合わせて調整 |
| `random_lane.html` | SPのRANDOMレーン配置 | レイアウトに合わせて調整 |

ライバル比較には[ライバル登録](rivals.md)、RANDOM配置には[配置認識の設定](features.md)が必要です。
`mobile_score_viewer.html` は[スマホ連携](mobile.md)用の画面なので、ブラウザソースへの直接指定には使いません。

## カスタムCSSで表示を調整する

OBSのブラウザソースの「カスタムCSS」に指定します。
HTMLファイルを直接編集せず、配信レイアウトごとに設定できます。

### 本日のプレーログ

`today_result.html` でBPを表示し、更新した曲だけ表示する例です。

```css
:root {
    --show-bp: 1;
    --show-best-delta: 1;
    --filter-mode: updates_only;
}
```

`--filter-mode` は `all`（全件）、`updates_only`（更新した曲）、
`bpi_only`（指定BPI以上）、`updates_or_bpi`（更新または指定BPI以上）から選べます。
BPIのしきい値は `--bpi-min` で指定します。

表示する過去ログの範囲は、アプリ側の[自動読み込みオフセット](features.md)でも調整できます。

### 統計情報とレシート

`today_stats.html` で、統計を表示するレベルや、右側の表示内容を変える例です。

```css
:root {
    --notes-graph-days: 7;
    --stats-levels: sp11,sp12;
    --lv-stats-position: left;
    --playlog-page: receipt;
    --receipt-top-bpi-count: 10;
    --receipt-sections: bpi,rank,score,lamp,bp;
}
```

`--playlog-page` は `result` でプレーログ、`receipt` でレシートを表示します。
レシートを使う場合は幅2000・高さ2200も目安になります。
`--stats-levels` は `sp11,dp10` のようにカンマ区切りで指定できます。
`--lv-stats-position` は `left` または `bottom` です。

単独の `today_receipt.html` では、次の名前で設定します。

```css
:root {
    --top-bpi-count: 10;
    --sections: bpi,rank,score,lamp,bp;
    --hide-zero-pre-score: 1;
}
```

`--sections` の並びで表示順を変えられます。
`--hide-zero-pre-score: 1` は、それまでのスコアが0だった曲をスコア更新欄から除きます。

### ライバル欄

`rival.html` で、曲名などのヘッダーを表示する場合です。

```css
:root {
    --enable-header: 1;
}
```

## 別PCのOBSに表示する

打鍵カウンタはゲーム用PCで動かし、配信側PCのOBSにHTMLを置く構成も使えます。
配信側にも `template` フォルダを一式コピーし、OBSにHTMLを指定します。

カスタムCSSで、**打鍵カウンタが動いているPC**のLAN内IPアドレスとデータ表示用ポートを指定します。

```css
:root {
    --websocket-host: "192.168.0.10";
    --websocket-port: 8767;
}
```

アプリ側で「データ表示用port」を変えた場合は、HTML側も同じ値にします。
変更後は打鍵カウンタを再起動し、OBSのブラウザソースも再読み込みしてください。
同じLANからそのポートへ接続できるよう、Windowsのファイアウォールでも通信を許可してください。
複数のビューを組み合わせたHTMLでは、子のHTMLも参照するためフォルダ構成を保ってください。

## 表示されない・更新されない場合

- 打鍵カウンタが起動中で、ゲーム画面を取得できているか確認します。
- 指定したファイルがアプリ同梱の `template` 内のHTMLか確認します。
- 「データ表示用port」とHTMLの接続先を確認します。OBS制御用ポートやスマホ用HTTPポートとは別です。
- OBSのブラウザソースを再読み込みし、幅・高さが小さすぎないか確認します。
- HTMLを改造する場合はフォルダごとコピーしてから編集してください。アップデートで同梱ファイルが更新されることがあります。
