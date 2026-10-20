# 更新情報

GitHub Releasesから取り込んだ、一部のバージョンのリリースノートです。
本文は公開当時の内容です。現在の機能や今後の予定とは異なる場合があります。
説明書へのリンクは、このサイト内の案内へ置き換えています。
最新版は[最新のReleaseページ](https://github.com/dj-kata/inf_daken_counter_obsw/releases/latest)で確認できます。
全バージョンの情報と配布ファイルは[GitHub Releases](https://github.com/dj-kata/inf_daken_counter_obsw/releases)を参照してください。

<!-- misc/import_release_notes.py で生成。本文の修正はGitHub Releasesで行い再取り込みする。 -->

## 3.0.22 オプション未確定のままリザルトを保存しないように修正

公開日（UTC）: 2026-09-27 · タグ: `3.0.22` · [元のリリース・ダウンロード](https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/3.0.22)

### 更新内容
- オプションが確定するまでリザルトの保存を行わないように戻した
  - 主に1P側向け

設定方法については[使い方](obs-views.md)を参照してください。

### 注意
自動アップデートで上手く取り込めない場合はお手数ですが[こちらのzip](https://t.co/QxLQoAitG8)を手動でインストールしてください。

### 今後の予定
- 英語化漏れへの対応
- regul-speed、all-scr、及びDP関連のバグ修正
  - この辺を作者が全く使わないこともあり、修正までに時間はかかるかも

### その他
inf_daken_counter.zipをダウンロードしてインストールしてください。  
設定方法などは[説明書](index.md)を参照してください。

**Full Changelog**: https://github.com/dj-kata/inf_daken_counter_obsw/compare/3.0.11...3.0.12

---

## 3.0.21 同一リザルトの多重保存対策

公開日（UTC）: 2026-09-17 · タグ: `3.0.21` · [元のリリース・ダウンロード](https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/3.0.21)

### 更新内容
- 同一リザルトを複数回保存しないように修正
- 画面取得方式について、dxcam/ImageGrab(従来)を切り替えられるようにした
- HTTPサーバ機能において、一部ページの自動更新が行われないバグを修正

設定方法については[使い方](obs-views.md)を参照してください。

### 注意
自動アップデートで上手く取り込めない場合はお手数ですが[こちらのzip](https://t.co/QxLQoAitG8)を手動でインストールしてください。

### 今後の予定
- 英語化漏れへの対応
- regul-speed、all-scr、及びDP関連のバグ修正
  - この辺を作者が全く使わないこともあり、修正までに時間はかかるかも

### その他
inf_daken_counter.zipをダウンロードしてインストールしてください。  
設定方法などは[説明書](index.md)を参照してください。

**Full Changelog**: https://github.com/dj-kata/inf_daken_counter_obsw/compare/3.0.11...3.0.12

---

## 3.0.20 直接取得の修正、細かい調整

公開日（UTC）: 2026-09-16 · タグ: `3.0.20` · [元のリリース・ダウンロード](https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/3.0.20)

### 更新内容
- 直接取得モードに関する修正
  - 画面取得処理方式を変更(dxcam)
  - 例外処理方式を見直し
- オプション取得に失敗した場合のケアを追加

設定方法については[使い方](obs-views.md)を参照してください。

### 注意
自動アップデートで上手く取り込めない場合はお手数ですが[こちらのzip](https://t.co/QxLQoAitG8)を手動でインストールしてください。

### 今後の予定
- 英語化漏れへの対応
- regul-speed、all-scr、及びDP関連のバグ修正
  - この辺を作者が全く使わないこともあり、修正までに時間はかかるかも

### その他
inf_daken_counter.zipをダウンロードしてインストールしてください。  
設定方法などは[説明書](index.md)を参照してください。

**Full Changelog**: https://github.com/dj-kata/inf_daken_counter_obsw/compare/3.0.11...3.0.12

---

## 3.0.19 直接取得モードの安定化

公開日（UTC）: 2026-09-06 · タグ: `3.0.19` · [元のリリース・ダウンロード](https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/3.0.19)

### 更新内容
- 直接取得モードにおける画面取得処理を修正

設定方法については[使い方](obs-views.md)を参照してください。

### 注意
自動アップデートで上手く取り込めない場合はお手数ですが[こちらのzip](https://t.co/QxLQoAitG8)を手動でインストールしてください。

### 今後の予定
- 英語化漏れへの対応
- regul-speed、all-scr、及びDP関連のバグ修正
  - この辺を作者が全く使わないこともあり、修正までに時間はかかるかも

### その他
inf_daken_counter.zipをダウンロードしてインストールしてください。  
設定方法などは[説明書](index.md)を参照してください。

**Full Changelog**: https://github.com/dj-kata/inf_daken_counter_obsw/compare/3.0.11...3.0.12

---

## 3.0.18 HTML周りのバグ修正、自己べcsvのフォーマット変更

公開日（UTC）: 2026-09-02 · タグ: `3.0.18` · [元のリリース・ダウンロード](https://github.com/dj-kata/inf_daken_counter_obsw/releases/tag/3.0.18)

### 更新内容
- HTML周りのバグ修正
  - OBSで表示できないデグレを修正 #38
  - iframeを使うHTML(whole_layoutなど)の2PC対応漏れを修正
- 自己べcsv(inf_score.csv)にプレー回数の列を追加 #39
  - v2以前のリザルトについては、設定で`v2以前のログを集計対象とする`にチェックしている場合に加算される
- その他バグ修正

設定方法については[使い方](obs-views.md)を参照してください。

### 注意
自動アップデートで上手く取り込めない場合はお手数ですが[こちらのzip](https://t.co/QxLQoAitG8)を手動でインストールしてください。

### 今後の予定
- 英語化漏れへの対応
- regul-speed、all-scr、及びDP関連のバグ修正
  - この辺を作者が全く使わないこともあり、修正までに時間はかかるかも

### その他
inf_daken_counter.zipをダウンロードしてインストールしてください。  
設定方法などは[説明書](index.md)を参照してください。

**Full Changelog**: https://github.com/dj-kata/inf_daken_counter_obsw/compare/3.0.11...3.0.12

---
