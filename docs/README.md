# 説明書

- [リザルト画像の保存を設定する](image-save.md)
- その他の機能は当面[既存Wiki](https://github.com/dj-kata/inf_daken_counter_obsw/wiki)を参照してください。

## 更新方針

画像保存機能の説明は、このディレクトリのMarkdownを原稿として管理します。
コードを変更するときは、関連する操作手順・初期値・制約も同じ変更で更新します。
Wikiに同じ説明を独立して書き直さず、この原稿へのリンクを使います。
Wikiの既存ページや公開設定は、この試行では変更していません。

画像は画面の場所を示すために使い、手順は「タブ名」「項目名」で説明します。
画像内に番号や説明文を直接書き込まず、撮り直し後も文章を使える形にします。

## 画像を撮り直す

PySide6を含む開発環境のPythonから、リポジトリのルートで実行します。
Windowsで撮影する場合の例（Codex用環境は別途用意してください）:

```powershell
.codex-venv\Scripts\python.exe misc\capture_manual.py
```

Linuxで画面を表示せず確認する場合:

```bash
.codex-venv/bin/python misc/capture_manual.py --offscreen
```

出力先は `docs/images/image-save-ja.png` です。同名ファイルは上書きします。
`--language en` で英語版、`--output-dir <フォルダ>` で別の出力先を指定できます。
画像はアプリと共用するGUI部品から生成し、初期値は新規の一時設定ファイルから読み込みます。
アプリ本体、OBS接続、ゲーム画面取得、HTTPサーバは起動しません。
利用者の設定やプレー履歴は読み書きしません。通常のモジュールログは `log/` に出力されます。

撮影時はFusionスタイルを使い、利用可能ならNoto Sans CJK JP、Yu Gothic、Meiryoの順でフォントを選びます。
OSやQtのバージョンによる差は残るため、Windowsでの見た目を確認したい場合はWindowsで再撮影してください。
掲載画像の生成環境はLinux・画面なしです。

## Codexに更新を依頼するとき

例えば、次の依頼を機能修正と一緒に指定します。

> 画像保存機能の変更に合わせて docs/image-save.md を更新してください。
> GUI・設定値・実際の保存処理を照合し、操作手順・初期値・制約を確認してください。
> GUIの表示が変わった場合は misc/capture_manual.py で画像も再生成してください。
> 実機確認していない動作は確認済みと書かず、残った確認事項を報告してください。

生成した画像の文字切れ、選択状態、説明との一致を確認してから公開します。

## 変更後の確認

```bash
.codex-venv/bin/python -B -m unittest misc.test_image_save_settings
```

初期表示、適用前に設定が変わらないこと、設定の保存と復元、日本語・英語の画像生成、
撮影時に既存の `config.json` を変更しないことを確認します。
Windows上でのアプリ全体の操作や、実際のリザルト画像保存は別途確認してください。
