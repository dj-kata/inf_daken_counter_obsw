"""GitHub Releasesの本文を説明書の更新情報へ取り込む（Python標準ライブラリのみ）。"""

import argparse
import json
from pathlib import Path
import re
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "dj-kata/inf_daken_counter_obsw"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"


def fetch_releases():
    releases = []
    page = 1
    while True:
        request = Request(
            f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "infdc-docs"},
        )
        with urlopen(request, timeout=30) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError("GitHub APIの応答がリリース一覧ではありません")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def select_releases(releases, limit=5, tags=None, include_prereleases=False):
    if not isinstance(releases, list):
        raise ValueError("入力JSONはリリース一覧の配列にしてください")
    requested = set(tags or [])
    selected = [release for release in releases
                if not release.get("draft") and release.get("published_at")
                and (release.get("tag_name") in requested if requested
                     else include_prereleases or not release.get("prerelease"))]
    if requested:
        missing = requested - {release["tag_name"] for release in selected}
        if missing:
            raise ValueError("公開済みリリースが見つかりません: " + ", ".join(sorted(missing)))
    selected.sort(key=lambda release: release["published_at"], reverse=True)
    selected = selected if requested else selected[:limit]
    if not selected:
        raise ValueError("取り込める公開済みリリースがありません")
    return selected


def nest_headings(body):
    """リリース本文の見出しを各バージョンの下へ配置する。コード内は変えない。"""
    lines = []
    fence_char = None
    fence_length = 0
    for line in body.replace("\r\n", "\n").splitlines():
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker, suffix = fence.groups()
            if fence_char is None:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length and not suffix.strip():
                fence_char = None
            lines.append(line)
            continue
        if fence_char is None:
            line = re.sub(r"^( {0,3})(#{1,6})(?=\s|$)",
                          lambda m: m[1] + "#" * min(6, len(m[2]) + 2), line)
        lines.append(line)
    return "\n".join(lines).strip()


def render_releases(releases):
    lines = [
        "# 更新情報", "",
        "GitHub Releasesから取り込んだ、一部のバージョンのリリースノートです。",
        "本文は公開当時の内容です。現在の機能や今後の予定とは異なる場合があります。",
        f"最新版は[最新のReleaseページ]({RELEASES_URL}/latest)で確認できます。",
        f"全バージョンの情報と配布ファイルは[GitHub Releases]({RELEASES_URL})を参照してください。",
        "", "<!-- misc/import_release_notes.py で生成。本文の修正はGitHub Releasesで行い再取り込みする。 -->", "",
    ]
    for release in releases:
        title = (release.get("name") or release["tag_name"]).replace("\n", " ").replace("\r", " ")
        label = "（プレリリース）" if release.get("prerelease") else ""
        lines.extend([
            f"## {title}{label}", "",
            f"公開日（UTC）: {release['published_at'][:10]} · "
            f"タグ: `{release['tag_name']}` · [元のリリース・ダウンロード]({release['html_url']})",
            "", nest_headings(release.get("body") or "本文はありません。"), "", "---", "",
        ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="取得する最近のリリース件数（初期値5）")
    parser.add_argument("--tag", action="append", help="対象タグを指定。複数回指定可。件数指定より優先")
    parser.add_argument("--include-prereleases", action="store_true")
    parser.add_argument("--input-json", type=Path, help="API応答を保存したJSONから取り込む（通信なし）")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "releases.md")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit は1以上にしてください")
    try:
        releases = (json.loads(args.input_json.read_text(encoding="utf-8"))
                    if args.input_json else fetch_releases())
        selected = select_releases(releases, args.limit, args.tag, args.include_prereleases)
        content = render_releases(selected)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    except (OSError, URLError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"リリース情報の取り込みに失敗しました: {error}\n")
    print(f"{len(selected)}件を保存しました: {args.output}")


if __name__ == "__main__":
    main()
