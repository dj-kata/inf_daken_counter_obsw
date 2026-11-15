# 開発基盤・アーキテクチャ改善ロードマップ

## この文書の位置づけ

この文書は、`inf_daken_counter_obsw` の今後の開発方針を検討するための参考資料である。
記載された項目は原則として未実装であり、個別の機能開発より常に優先するという意味ではない。
既存機能との互換性を保ち、必要になった箇所から小さく導入する。

関連プロジェクトである `siren6_helper`、`sdvx_helper`、`otoge_input_viewer` との比較も踏まえているが、
本書ではこのリポジトリに適用する方針を中心に扱う。

## 結論

- 当面は Python と PySide6 を継続し、Rustへの全面移植は行わない。
- 性能問題は言語移植より先に計測し、画像コピー、DBアクセス、スレッド競合などのボトルネックを特定する。
- 新しい大規模フレームワークは導入せず、テスト、静的解析、型、モジュール境界を段階的に強化する。
- GitHub Actionsで再現可能なWindowsビルドを作るが、自動公開はせず、実機確認後に手動公開する。
- 他プロジェクトとの共通化は、各アプリ固有の認識・状態・UIではなく、OBS、WebSocket、更新、ログなどから始める。

## Pythonを継続する理由

本アプリの負荷が高い処理の多くは、OpenCV、NumPy、Pillow、Qt、DXGI、Spoutなどの
ネイティブ実装へ委譲されている。Pythonは主に状態管理、UI、各ライブラリの連携を担当しているため、
全面的にRustへ移植しても画像認識性能が大幅に向上するとは限らない。

また、Rustへ移植してもQt、OpenCV、Windows APIなどのFFI境界は残る。
既存資産の移植、GUIライブラリの再選定、配布方法の再構築に対する利益が現時点では小さい。

将来、計測によって狭い処理に明確な問題が見つかった場合は、その処理だけをネイティブ化する選択肢を残す。

## 品質基盤の改善

### 1. pytestとpytest-qt

既存の `unittest` テストは維持し、新規テストからpytestを利用する。
一括変換は行わず、既存テストも同じテスト実行から呼び出せる構成にする。

`pytest-qt` は次の用途へ限定して導入する。

- 設定ダイアログの初期値、保存、キャンセル
- Qt Signalの発火と引数
- ワーカースレッドの完了通知
- OBS接続状態など、バックグラウンド処理からUIへの反映
- アプリ終了時のワーカー停止

テストでは実OBS、ゲーム画面、ユーザー設定へ依存せず、`tmp_path`、fake、mockを利用する。

### 2. Ruff

最初はformatterを全体へ適用せず、安全性に関係するlintだけを有効にする。

初期候補:

```toml
[tool.ruff]
target-version = "py312"
exclude = [
    "infnotebook",
    "RandomLaneAnalysis_OCR",
    "build",
    "dist",
]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]
```

既存コード全体の一括修正は避け、当初は変更したファイルと新規ファイルを対象にする。
ルール追加は既存違反の件数と修正リスクを確認してから行う。

### 3. 段階的な型チェック

最初からプロジェクト全体へstrictな型チェックを適用しない。
UIや外部ライブラリ境界より、データモデルと純粋ロジックから型を追加する。

優先対象:

- リザルト、判定、配置認識などのデータモデル
- 設定値と設定移行処理
- OBS接続設定
- WebSocketで送受信するメッセージ
- DBの入出力
- 時刻、キャプチャ、保存先などの境界

組み込みの `dataclass`、`Enum`、`TypedDict`、`Protocol` を優先し、
外部入力の検証が複雑になった場合だけPydanticなどを検討する。

型チェックは対象モジュールを明示して開始し、通過範囲を徐々に広げる。

## アーキテクチャ改善

### 1. 認識、状態遷移、副作用の分離

画面処理を次の段階に分ける。

```text
キャプチャ画像
  -> 認識結果
  -> アプリ状態の遷移
  -> DB保存・WebSocket配信・OBS操作・音声案内
```

認識処理は可能な限り、画像と設定を受け取って認識結果を返す形にする。
状態遷移は `Enum` と明示的な遷移関数で表現し、副作用を直接実行しない。

これにより、実ゲームやOBSがなくても、認識結果のイベント列から次の動作をテストできるようにする。
外部のステートマシンフレームワークは、組み込み機能で表現できなくなるまで導入しない。

### 2. 外部機能をProtocolで分離

大規模なDIコンテナは導入せず、コンストラクタ引数と `typing.Protocol` で境界を作る。

候補:

```python
class CaptureSource(Protocol):
    def capture(self) -> np.ndarray | None: ...


class OBSClient(Protocol):
    def connect(self) -> None: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...


class ResultRepository(Protocol):
    def save(self, result: Result) -> None: ...
```

テスト時にはfake実装へ差し替え、OBS、実時刻、ユーザーDB、画面取得へ依存しないようにする。

### 3. スレッドと非同期処理のルール

新規実装では次の使い分けを基本とする。

| 処理 | 方式 |
| --- | --- |
| GUI操作 | Qtメインスレッドのみ |
| 1回限りのバックグラウンド処理 | `QThreadPool` / `QRunnable` |
| 長時間動くQtワーカー | worker `QObject` + 専用 `QThread` |
| WebSocketなどの非同期I/O | 専用asyncioイベントループ |
| ワーカーからUIへの通知 | Qt Signal |
| Qtを使わない単純な常駐処理 | 必要に応じて `threading.Thread` |

バックグラウンドスレッドからQWidgetを直接操作しない。
WebSocketサービスごとにイベントループを増やさず、可能な範囲で1つのネットワークサービスへまとめる。
Python 3.11以降の新規asyncio処理では、関連タスクの終了と例外回収に `TaskGroup` を検討する。

既存処理は一括変更せず、機能修正時に責任範囲が明確な箇所から移行する。

### 4. 画像認識のGolden Test

匿名化・切り抜き済みの固定画像と期待値を組にしたテストデータを整備する。

```text
testdata/
  recognition/
    select/
    play/
    result/
    false_positive/
```

期待値はJSONなどで管理し、曲、譜面、スコア、画面状態などを比較する。
誤認識を修正した場合は、再発防止用画像を追加する。

大量の実画像、個人情報、第三者が再配布できない素材はGitへ追加しない。
必要に応じて、公開可能な最小の切り抜きや人工的なfixtureを作る。

## 他プロジェクトとの共通化

共通化は、複数アプリで仕様が実際に一致している部分に限定する。
1つのアプリだけで将来利用を予想して抽象化しない。

### 共通化候補

- ロガー初期化
- ネットワークインターフェース列挙
- GitHub Releasesを利用する更新処理の基礎
- OBS接続設定モデル
- OBS WebSocketの低レベル操作
- WebSocketの接続、再接続、ブロードキャスト基盤
- 音声ファイル再生の基礎
- ブラウザソース側の接続先決定と再接続処理
- アプリ名、バージョン、メッセージ種別を持つ共通プロトコル

### 共通化しない範囲

- ゲーム固有の画像認識
- ゲーム固有の状態遷移
- リザルトモデルとDBスキーマ
- 設定ダイアログ全体
- メインウィンドウ
- OBSシーン切り替えのゲーム固有ルール

共通パッケージを作る場合は小さくバージョン管理し、各アプリが利用バージョンを固定する。
アプリのリリースと共通パッケージの最新版を常に同期させる構成にはしない。

## CI/CDとリリースビルド

### 基本方針

GitHub ActionsでWindows向け成果物を再現ビルドする。
ただし、OBS、Spout、実ゲーム画面、GPU、音声、Windows Defenderなどはrunner上で十分に検証できないため、
リリースは次の二段階にする。

```text
GitHub Actionsでビルド
  -> ドラフトReleaseへZIPとSHA256を添付
  -> 手元のWindows環境でスモークテスト
  -> 手動でPublish
```

公開リポジトリの標準GitHub-hosted runnerは、本書作成時点では無料で利用できる。
料金や制限は変更される可能性があるため、導入時に公式ドキュメントを再確認する。

現在のZIPは300MBを超えるため、Actions Artifactとして何世代も保持しない。
検証用Artifactは保持期間を短くし、正式な成果物はGitHub Releaseへ添付する。

### CI導入前に解消する項目

#### ローカル依存のビルドコマンド

現在の `Makefile` は特定のWSL/Windows上のuvパスを参照している。
ローカルとCIの両方から同じコマンドで呼べる、プラットフォーム非依存の小さいビルドスクリプトへ整理する。

候補:

```text
scripts/build_release.py
  - cx_Freezeビルド
  - template、version.txt、songinfo、resourcesの配置
  - 一時ファイルとログの除去
  - ZIP作成
  - SHA256生成
```

CIのYAMLへ配布物の構築手順を直接書き散らさず、このスクリプトをローカルビルドでも利用する。

#### infnotebookの固定

`infnotebook/` はGit管理対象外であり、現在のREADMEでは別途cloneする。
CIで毎回最新のmainを取得すると、同じアプリタグでも成果物が変わる。

次のいずれかでcommitを固定する。

- Git submodule
- ビルド設定へcommit SHAを記録し、ワークフローでそのSHAをcheckout

依存先を更新する場合は、固定SHAの更新とアプリ側の動作確認を同じ変更として扱う。

#### バージョンの一元化

`version.txt`、`pyproject.toml`、`setup.py` のバージョンが独立している。
正とする場所を1つ決め、ビルド時にはそこから他のメタデータを生成する。

タグビルドでは、タグ名とアプリバージョンが一致しなければ失敗させる。

#### 再現可能な依存解決

CIでは `uv.lock` を利用し、依存関係を暗黙に更新しない。

```text
uv sync --locked
uv run --locked ...
```

uv本体とGitHub Actionsも、確認済みバージョンまたはcommit SHAへ固定する。

#### Actions利用ポリシー

このリポジトリでは、GitHub公式Actionがリポジトリ設定で拒否された履歴がある。
ビルドワークフローを追加する前に、SettingsのActions permissionsで次を確認する。

- `actions/checkout` などのGitHub公式Action
- uvのセットアップに使用するAction
- Release作成に必要な権限

PR用CIには書き込み権限を与えず、Releaseを作成するjobだけに `contents: write` を指定する。

### 段階的な導入

#### 段階1: 手動ビルド

- `workflow_dispatch` だけで起動する。
- Windows runnerでlocked依存インストール、テスト、cx_Freeze、ZIP作成を実行する。
- 成果物の内容と起動を手元で確認する。
- この段階ではReleaseを作成しない。

#### 段階2: ドラフトRelease

- `v*` タグまたは手動実行を起点にする。
- タグとバージョンの一致を確認する。
- ZIPと `SHA256SUMS.txt` をドラフトReleaseへ添付する。
- 手元で確認後、GitHub上で手動公開する。

#### 段階3: 通常CI

- push/PRではビルドより軽い静的解析と単体テストを実行する。
- cx_Freezeの完全ビルドはタグ、手動実行、または必要な変更時に限定する。
- Qtテストはoffscreenで実行し、実機確認の代替とみなさない。

### 配布物の機械検査

ビルド後に最低限、次を検査する。

- 想定するEXEが存在する。
- `version.txt` が存在し、タグと一致する。
- `template/`、`songinfo.infdc`、`infnotebook/resources` が存在する。
- `config.json`、ログ、キャッシュ、認証情報など、利用者固有ファイルが混入していない。
- ZIPが展開できる。
- SHA256を生成できる。

将来的には、配布版EXEへ `--version` または副作用のない `--self-test` を追加し、
Qtと主要モジュールのロードを終了コードで確認できるようにする。

## 推奨する実施順序

### 優先度A: ビルドの再現性

- [ ] バージョン情報の正を決める。
- [ ] `infnotebook` のcommitを固定する。
- [ ] ローカルとCIで共用するリリースビルドスクリプトを作る。
- [ ] 配布物検査とSHA256生成を追加する。
- [ ] `workflow_dispatch` によるWindowsビルドを追加する。
- [ ] 安定後、タグからドラフトReleaseを作成する。

### 優先度B: 変更時の安全網

- [ ] pytestから既存のunittestを実行できるようにする。
- [ ] pytest-qtで新規UIテストを書けるようにする。
- [ ] Ruffを限定ルールで導入する。
- [ ] CIで静的解析と副作用のないテストを実行する。
- [ ] 代表的な画像認識のGolden Testを追加する。

### 優先度C: コード境界の改善

- [ ] 新規データモデルをdataclassとEnumで表現する。
- [ ] WebSocketメッセージと設定値へ型を付ける。
- [ ] キャプチャ、OBS、時刻、DBの境界へProtocolを導入する。
- [ ] 認識、状態遷移、副作用を機能修正に合わせて分離する。
- [ ] 対象モジュールを限定して型チェックを開始する。
- [ ] 新規ワーカーをスレッド利用ルールに合わせる。

### 優先度D: 共通化

- [ ] `sdvx_helper` などとの同一・類似コードを再調査する。
- [ ] 最小の共通対象と公開APIを決める。
- [ ] 1つの低リスク機能で共通パッケージ化を試す。
- [ ] 各アプリが共通パッケージのバージョンを固定できることを確認する。

## 当面行わないこと

- Rustへの全面移植
- FastAPI、Django、Celeryなどの大型フレームワーク導入
- DIコンテナの導入
- 全内部モデルのPydantic化
- 全コードへの一括formatter適用
- 全コードへのstrictな型チェックの一括適用
- 全スレッド・asyncio処理の一括置換
- CI成功直後のRelease自動公開
- 実OBS、Spout、ゲーム画面を確認せずに「動作確認済み」とすること

## 判断基準

新しいライブラリ、抽象化、共通パッケージを導入する場合は、少なくとも次を確認する。

1. 実在する不具合、重複、検証困難、性能問題のどれを解決するか。
2. 既存の標準ライブラリや小さい関数では不十分か。
3. cx_Freeze後のWindows配布へ影響しないか。
4. ユーザー設定、DB、WebSocket、HTMLとの互換性を保てるか。
5. 実機なしで検証できる範囲が増えるか。
6. 複数アプリで共通化する場合、本当に仕様が一致しているか。
7. Codexを含む開発者が、必要なコード範囲と失敗理由を追いやすくなるか。

## 参考資料

- [pytest fixtures](https://docs.pytest.org/en/stable/reference/fixtures.html)
- [pytest-qt](https://pytest-qt.readthedocs.io/en/stable/intro.html)
- [Ruff](https://docs.astral.sh/ruff/)
- [mypy: Using mypy with an existing codebase](https://mypy.readthedocs.io/en/stable/existing_code.html)
- [Python: asyncio.TaskGroup](https://docs.python.org/3/library/asyncio-task.html#task-groups)
- [Qt for Python: Multithreading Technologies in Qt](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-technologies.html)
- [uv: Using uv in GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
