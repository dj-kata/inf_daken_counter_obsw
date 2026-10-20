# 説明書

- [サイトのトップページ](index.md)
- [リザルト画像の保存を設定する](image-save.md)
- [更新情報](releases.md)
- その他の機能は当面[既存Wiki](https://github.com/dj-kata/inf_daken_counter_obsw/wiki)を参照してください。

## サイトをプレビューする

原稿はMarkdown、公開サイトはMkDocs Materialで生成します。このREADMEは作業者向けで、サイトには含めません。
依存パッケージはアプリと分けて `requirements-docs.txt` に定義しています。
ユーザー管理の `.venv` を変更せず、Codex用の環境を明示して準備します。

```bash
python3 -m venv .codex-venv  # Codex用環境がまだない場合のみ
uv pip install --python .codex-venv/bin/python -r requirements-docs.txt
.codex-venv/bin/python -m mkdocs serve
```

WindowsではPythonのパスを `.codex-venv\Scripts\python.exe` に読み替えてください。
ブラウザで `http://127.0.0.1:8000/` を開くと、原稿の編集が反映されます。

```bash
.codex-venv/bin/python -m mkdocs build --strict
```

生成物はGit管理対象外の `site/` に出力されます。画像生成やリリース情報の取得はビルド時には行いません。
従来の `docs/index.html` は `docs/clock-legacy.html` に移し、元のレイアウトで保存しています。

## GitHub Pagesへ公開する

`.github/workflows/docs.yml` は、説明書用ブランチ・masterへの対象ファイルのpushやPRでビルドを検証します。
この時点では自動公開しません。公開時には次の操作を行います。

1. 内容を確認し、説明書の変更を既定ブランチへマージします。
2. GitHubリポジトリの Settings → Pages → Source を **GitHub Actions** に設定します。
3. Actions → Documentation → Run workflow で既定ブランチを選び、`deploy` を有効にして実行します。

公開URLは `https://dj-kata.github.io/inf_daken_counter_obsw/` を想定しています。
手動の公開処理は既定ブランチからのみ実行できます。通常のpush・PRはビルドと成果物の作成だけです。
既存のPages公開元が設定されている場合は、切り替え前に確認してください。

## リリース情報を取り込む

GitHub Releasesを原本とし、Python標準ライブラリだけでMarkdownへ変換します。
初回は正式版の直近5件を取り込んでいます。全バージョンの移行は不要です。

```bash
.codex-venv/bin/python misc/import_release_notes.py
.codex-venv/bin/python misc/import_release_notes.py --limit 10
.codex-venv/bin/python misc/import_release_notes.py --tag 3.0.22 --tag 3.0.20
```

出力先は `docs/releases.md` で、再取り込み時には全体を上書きします。
指定タグは件数指定より優先し、指定したプレリリースも含めます。下書きは取り込みません。
タグ未指定時は公開日時の新しい順に正式版を選び、`--include-prereleases` でプレリリースも対象にできます。
公開情報の取得は認証なしで行うため、GitHub APIのレート制限に達した場合は時間を置いて再実行してください。

APIの応答をJSONで保存してある場合は、通信なしでも変換できます。

```bash
.codex-venv/bin/python misc/import_release_notes.py --input-json releases.json
```

本文のMarkdownは原則そのまま使い、`#` 形式の見出しだけをバージョン見出しの下へ移します。
コードブロック内の見出しは変更しません。公開日・元ページへのリンクも付けます。
本文の訂正はGitHub Releasesで行い、再取り込みして差分を確認してください。
GitHub固有の表示（単独のIssue番号の自動リンクなど）は完全には再現しません。
相対URLやHTMLを含む本文を取り込む際は、生成ページでリンクや表示を確認してください。
取得・変換に失敗した場合は、既存の更新情報を置き換えません。

## 更新方針

画像保存機能の説明は、このディレクトリのMarkdownを原稿として管理します。
コードを変更するときは、関連する操作手順・初期値・制約も同じ変更で更新します。
Wikiに同じ説明を独立して書き直さず、この原稿へのリンクを使います。
Wikiの既存ページやGitHubの公開設定は、ローカルでのサイト作成時には変更しません。

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
.codex-venv/bin/python -B -m unittest misc.test_import_release_notes
.codex-venv/bin/python -m mkdocs build --strict
```

初期表示、適用前に設定が変わらないこと、設定の保存と復元、日本語・英語の画像生成、
撮影時に既存の `config.json` を変更しないことを確認します。
Windows上でのアプリ全体の操作や、実際のリザルト画像保存は別途確認してください。
