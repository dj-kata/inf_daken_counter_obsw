# 説明書

- [サイトのトップページ](index.md)
- [通常の導入手順](install.md)
- [v2からの移行](migration-v2.md)
- [OBS向けHTMLビュー](obs-views.md)
- [設定画面で設定できること](settings.md)
- [ゲーム画面の取得](capture.md)
- [更新情報](releases.md)

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
時計テンプレートの仮ページは削除し、導入手順と各機能の説明をサイト内にまとめています。

## GitHub Pagesへ公開する

`.github/workflows/docs.yml` は、説明書用ブランチ・mainへの対象ファイルのpushやPRでビルドを検証します。
この時点では自動公開しません。公開時には次の操作を行います。

1. 内容を確認し、説明書の変更を既定ブランチへマージします。
2. Settings → Actions → General の **Actions permissions** で、GitHub公式のActionを許可します（後述）。
3. GitHubリポジトリの Settings → Pages → Source を **GitHub Actions** に設定します。
4. Actions → Documentation → Run workflow で既定ブランチを選び、`deploy` を有効にして実行します。

公開URLは `https://dj-kata.github.io/inf_daken_counter_obsw/` を想定しています。
手動の公開処理は既定ブランチからのみ実行できます。通常のpush・PRはビルドと成果物の作成だけです。
既存のPages公開元が設定されている場合は、切り替え前に確認してください。

### Documentationが起動直後に失敗する場合

2026-10-22のコミット `620c0bf` の実行は、ジョブが作成される前の `startup_failure` でした。
[該当する実行](https://github.com/dj-kata/inf_daken_counter_obsw/actions/runs/39728136116)のAnnotationsには、
dj-kata所有のActionだけを許可するポリシーによって、次のGitHub公式Actionが拒否されたことが表示されています。

- `actions/checkout@v4`
- `actions/setup-python@v5`
- `actions/upload-pages-artifact@v3`
- `actions/deploy-pages@v4`

このエラーはMarkdownやMkDocsのビルドエラーではなく、リポジトリの管理設定で解消します。

1. [Settings → Actions → General](https://github.com/dj-kata/inf_daken_counter_obsw/settings/actions) を開きます。
2. Actions permissionsで **Allow dj-kata, and select non-dj-kata, actions and reusable workflows** を選びます。
3. **Allow actions created by GitHub** を有効にして保存します。これにより、上記のActionと、その内部で使うGitHub公式Actionを許可できます。
4. 失敗した実行で **Re-run all jobs** を選ぶか、Documentationを手動実行して、buildジョブが成功することを確認します。
5. 公開する場合はPagesのSourceを確認し、既定ブランチから `deploy` を有効にしてDocumentationを実行します。

Actionを許可しただけではサイトは公開されません。通常のpush・PRではビルドと成果物作成までです。
また、ワークフローの `pages: write` や `contents: read` を変更しても、この起動拒否は解消しません。
許可ポリシーの説明は[GitHub公式ドキュメント](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#allowing-select-actions-and-reusable-workflows-to-run)を参照してください。

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

本文のMarkdownは原則そのまま使い、`#` 形式の見出しをバージョン見出しの下へ移します。
旧説明書のリンクは、HTMLビュー・スマホ連携など対応するサイト内ページへ置き換えます。
コードブロック内の見出しは変更しません。公開日・元ページへのリンクも付けます。
本文の訂正はGitHub Releasesで行い、再取り込みして差分を確認してください。
GitHub固有の表示（単独のIssue番号の自動リンクなど）は完全には再現しません。
相対URLやHTMLを含む本文を取り込む際は、生成ページでリンクや表示を確認してください。
取得・変換に失敗した場合は、既存の更新情報を置き換えません。

## 更新方針

利用者向け説明は、このディレクトリのMarkdownを原稿とし、生成したHTMLサイト内で読めるように管理します。
導入（通常・v2移行）とOBS向けHTMLビューを先頭にし、その下に各機能を配置します。
コードを変更するときは、関連する操作手順・初期値・制約も同じ変更で更新します。
説明を旧Wikiへ誘導せず、必要な操作と前提をサイト内のページに記載します。
v2固有の引き継ぎ手順は `migration-v2.md` に集め、機能ページでは利用目的と操作に絞ります。
GitHubの公開設定は、ローカルでのサイト作成時には変更しません。

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
基本設定の全7タブを撮影する場合は、次を実行します。

```bash
.codex-venv/bin/python misc/capture_manual.py --offscreen --section settings
```

出力先は `docs/images/settings-<タブ名>-ja.png` です。こちらも `--language en` と `--output-dir` に対応します。
初期設定の表示なので、SpoutやRANDOMレーン認識など、初期状態で無効な項目は無効のまま撮影します。
全タブの撮影には、開発環境の `infnotebook/` とOCRリソースも必要です。ダイアログの依存先を読み込む際に参照しますが、画面取得は開始しません。
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

## Wikiからの移行記録

2026-10-22時点のWiki（コミット `6bd6078`）を参照し、次の情報をHTMLサイト内へ移しています。
Wiki自体の編集・削除は行いません。

| Wikiの原稿 | サイト内の移行先 |
| --- | --- |
| [Home](https://github.com/dj-kata/inf_daken_counter_obsw/wiki) | [トップ](index.md)：機能の概要・クレジット・ライセンス・連絡先 |
| [打鍵カウンタの設定方法](https://github.com/dj-kata/inf_daken_counter_obsw/wiki/打鍵カウンタの設定方法) | [導入](install.md)・[画面取得とSpout](capture.md)・[OBS制御](obs-control.md)・[スマホ連携](mobile.md) |
| [各ビューのHTMLについて](https://github.com/dj-kata/inf_daken_counter_obsw/wiki/各ビューのHTMLについて) | [HTMLビュー](obs-views.md)：表示例・目安サイズ・CSS・別PCでの接続 |
| [設定画面で設定できること](https://github.com/dj-kata/inf_daken_counter_obsw/wiki/設定画面で設定できること) | [設定画面](settings.md)：全7タブ・初期値・各機能の操作ページへのリンク |

説明は現行の `src/config.py`・UI・テンプレートと照合しています。
Wikiの `today_results.html` は現行の `today_result.html` に、CSS例の `root:` は `:root` に修正しています。
レーン番号の設定は `body` に指定します。RANDOM配置ビューの生成ファイルと、WebSocket接続先設定の違いも補足しています。
`whole_layout.html` の `--skip-no-update` は現行の親ページで子ビューに渡されないため、設定例には含めていません。

設定画面の画像は現行コードから再撮影しています。SpoutのOBS側設定とビューの表示例はWikiの画像を
`docs/images/wiki/` にコピーし、元URLを `sources.json` に記録しています。
ビューの画像はWiki掲載時点の表示例で、現行版で撮り直したものではありません。
サイトのビルド中には、Wikiや画像をネットワーク取得しません。
