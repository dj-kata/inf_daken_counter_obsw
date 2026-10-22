# INFINITAS打鍵カウンタ

beatmania IIDX INFINITASのプレー画面から、打鍵数やスコアを記録するツールです。
SP・DPに対応し、OBSへの情報表示やスマホでのスコア確認にも使えます。

リザルト画像の自動保存、プレーログ・月間ノーツ数の記録、配信向けHTMLビュー、
OBSの自動制御、スコアビューワでのライバル比較、自己ベストCSVの出力を利用できます。

## 打鍵カウンタの導入方法

- [通常の手順](install.md) — 初めて使う場合のダウンロード・起動・画面取得の確認
- [打鍵カウンタv2から移行する場合に必要な手順](migration-v2.md) — 設定・プレーログの引き継ぎとHTMLの入れ替え
- [ゲーム画面の取得](capture.md) — 直接取得・Spout・OBS WebSocketの使い分けと設定

## 設定項目を調べる

[設定画面で設定できること](settings.md)で、基本設定の各タブと初期値を確認できます。
画像保存、スマホ連携、ライバル登録など、目的ごとの手順にも移動できます。

## OBS向けHTMLビューの利用方法

[HTMLビューをOBSに追加する](obs-views.md)。プレーログ、ノーツ数グラフ、ライバル比較などを配信に表示できます。
使えるビューの一覧や、別PCのOBSに表示する方法もこちらで説明しています。

## その他の機能

| 機能 | できること |
| --- | --- |
| [スコアビューワ](score-viewer.md) | 自己ベストの検索、プレー履歴の確認・削除、ライバルとの比較 |
| [HTTPサーバ（スマホ連携）](mobile.md) | 同じLANのスマホからスコアの確認やリザルト画像の結合 |
| [ライバル登録](rivals.md) | Google DriveのCSVを登録し、スコアを比較 |
| [OBS自動制御](obs-control.md) | ゲーム画面に合わせたソースの表示切り替えやシーン切り替え |
| [リザルト画像の保存](image-save.md) | 自動保存、ライバル欄の加工、統計情報の追加 |
| [その他の機能](features.md) | 成果の投稿、自己ベスト登録、難易度表、RANDOM配置認識 |

## ダウンロード・更新情報

- [最新版のReleaseページ](https://github.com/dj-kata/inf_daken_counter_obsw/releases/latest)
- [バージョンごとの更新情報](releases.md)

不具合や要望は[GitHub Issues](https://github.com/dj-kata/inf_daken_counter_obsw/issues)へお寄せください。

## 利用・クレジット

非営利・営利を問わず配信などに利用できます。ライセンスは
[Apache License 2.0](https://github.com/dj-kata/inf_daken_counter_obsw/blob/main/LICENSE)です。
配信でのクレジット表記は必須ではありません。記載する場合は、次を使えます。

```text
INFINITAS打鍵カウンタ
https://github.com/dj-kata/inf_daken_counter_obsw
```

作者の連絡先は [X（@cold_planet_）](https://x.com/cold_planet_) です。バグ報告はGitHub Issuesを利用してください。
