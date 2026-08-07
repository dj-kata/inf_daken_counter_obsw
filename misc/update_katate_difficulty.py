#!/usr/bin/env python3
"""片手難易度表から☆11/☆12の難易度帯を取得してsonginfo.infdcへ埋め込む。"""

import argparse
import bz2
import csv
import io
import pickle
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.classes import difficulty, play_style


SPREADSHEET_ID = "1EiJIMKyknIdsB-SUp9U5I9bynbjf6FQCt4CpvLTDUKo"
SHEET_GID = "1439819974"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export"
    f"?format=csv&gid={SHEET_GID}"
)
ALT_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export"
    f"?format=csv&id={SPREADSHEET_ID}&gid={SHEET_GID}&single=true"
)

CIRCLED_DIGITS = {
    "①": 1,
    "②": 2,
    "③": 3,
    "④": 4,
    "⑤": 5,
    "⑥": 6,
    "⑦": 7,
    "⑧": 8,
    "⑨": 9,
    "⑩": 10,
}

GROUPS = (
    # CSV上は左11列が☆12、1列空けて右11列が☆11。
    (12, range(0, 11), "katate_12"),
    (11, range(12, 23), "katate_11"),
)

SUFFIX_DIFFICULTY = {
    "H": difficulty.hyper,
    "A": difficulty.another,
    "L": difficulty.leggendaria,
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="片手難易度表を取得してsonginfo.infdcのkatate_11/katate_12を更新する"
    )
    parser.add_argument("--url", default=CSV_URL, help="取得元CSV URL")
    parser.add_argument("--input-csv", type=Path, help="取得済みCSVを使う")
    parser.add_argument("--dry-run", action="store_true", help="DBを書き換えず結果だけ表示")
    parser.add_argument(
        "--clear-missing",
        action="store_true",
        help="表に存在しない既存katate_11/katate_12をNoneに戻す",
    )
    parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="songinfo.infdcに見つからなかった譜面を表示する",
    )
    return parser.parse_args(argv)


def read_csv_rows(args):
    if args.input_csv:
        with args.input_csv.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.reader(f))

    urls = [args.url]
    if args.url == CSV_URL:
        urls.append(ALT_CSV_URL)

    errors = []
    for url in urls:
        try:
            return csv_rows_from_text(download_text_with_urllib(url))
        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {e}")

    curl_path = shutil.which("curl")
    if curl_path:
        for url in urls:
            try:
                return csv_rows_from_text(download_text_with_curl(curl_path, url))
            except Exception as e:
                errors.append(f"curl {url}: {type(e).__name__}: {e}")

    raise RuntimeError("CSV download failed:\n  " + "\n  ".join(errors))


def csv_rows_from_text(text):
    if text.lstrip().startswith("<"):
        raise ValueError("downloaded content looks like HTML, not CSV")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or not any("片手難易度表" in cell for row in rows[:5] for cell in row):
        raise ValueError("downloaded CSV does not look like the katate difficulty sheet")
    return rows


def download_text_with_urllib(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def download_text_with_curl(curl_path, url):
    result = subprocess.run(
        [curl_path, "-L", "--fail", "--silent", "--show-error", url],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8-sig")


def parse_chart_title(text):
    """曲名末尾の(H)/(A)/(L)だけを譜面種別として解釈する。"""
    title = text.strip().replace("\u3000", " ")
    suffix = re.search(r"\((H|A|L)\)$", title)
    if suffix:
        return title[: suffix.start()].strip(), SUFFIX_DIFFICULTY[suffix.group(1)]
    return title, difficulty.another


def is_header_or_empty(text):
    stripped = text.strip()
    return (
        not stripped
        or stripped == "　"
        or "片手難易度表" in stripped
        or stripped in CIRCLED_DIGITS
    )


def parse_katate_rows(rows):
    """CSVから{(title, play_style.sp, difficulty): {11/12: band}}を作る。"""
    current_band = {11: None, 12: None}
    ret = {}
    conflicts = []

    for row in rows:
        for music_level, columns, _attr in GROUPS:
            for col in columns:
                if col >= len(row):
                    continue

                cell = row[col].strip()
                if not cell:
                    continue

                if "片手難易度表" in cell:
                    continue

                if cell in CIRCLED_DIGITS:
                    current_band[music_level] = CIRCLED_DIGITS[cell]
                    continue

                band = current_band[music_level]
                if band is None or is_header_or_empty(cell):
                    continue

                title, diff = parse_chart_title(cell)
                if not title:
                    continue

                key = (title, play_style.sp, diff)
                values = ret.setdefault(key, {})
                old = values.get(music_level)
                if old is not None and old != band:
                    conflicts.append((key, music_level, old, band))
                    band = max(old, band)
                values[music_level] = band

    return ret, conflicts


def normalize_for_fuzzy_match(title):
    title = unicodedata.normalize("NFKC", title or "")
    replacements = {
        "〜": "～",
        "―": "-",
        "‐": "-",
        "‑": "-",
        "–": "-",
        "—": "-",
        "？": "?",
        "！": "!",
        "”": '"',
        "“": '"',
        "’": "'",
        "†": "",
        "♡": "",
        "♥": "",
        "❤": "",
        "♨": "",
        "♪": "",
        "☆": "",
        "★": "",
        "?": "",
        "!": "",
        " ": "",
        "　": "",
    }
    for src, dst in replacements.items():
        title = title.replace(src, dst)
    title = re.sub(r"\([^)]*remix[^)]*\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠々〆ーØøΑ-Ωα-ω]+", "", title)
    return title.lower()


def build_fuzzy_index(sdb):
    index = defaultdict(list)
    for chart_id, song in sdb.songs.items():
        if song.play_style != play_style.sp:
            continue
        key = (normalize_for_fuzzy_match(song.title), song.difficulty)
        index[key].append(chart_id)
    return index


def find_chart_id(sdb, fuzzy_index, title, diff):
    song = sdb.search(title=title, play_style=play_style.sp, difficulty=diff)
    if song:
        return song.chart_id

    candidates = fuzzy_index.get((normalize_for_fuzzy_match(title), diff), [])
    if len(candidates) == 1:
        return candidates[0]
    return None


def update_song_database(sdb, katate, clear_missing=False):
    fuzzy_index = build_fuzzy_index(sdb)
    unmatched = []
    updated = []
    matched_chart_ids = set()

    for (title, _style, diff), values in sorted(
        katate.items(),
        key=lambda item: (item[0][0], item[0][2].value),
    ):
        chart_id = find_chart_id(sdb, fuzzy_index, title, diff)
        if chart_id is None:
            unmatched.append((title, diff, values))
            continue

        song = sdb.songs[chart_id]
        matched_chart_ids.add(chart_id)
        for music_level, _columns, attr in GROUPS:
            if music_level not in values:
                continue
            new_value = values[music_level]
            old_value = getattr(song, attr)
            if old_value != new_value:
                setattr(song, attr, new_value)
                updated.append((song, attr, old_value, new_value))

    cleared = []
    if clear_missing:
        for chart_id, song in sdb.songs.items():
            if chart_id in matched_chart_ids:
                continue
            for _music_level, _columns, attr in GROUPS:
                if getattr(song, attr) is not None:
                    old_value = getattr(song, attr)
                    setattr(song, attr, None)
                    cleared.append((song, attr, old_value, None))

    return updated, cleared, unmatched


def load_song_database_without_autosave():
    from src.songinfo import SongDatabase, dbfile

    sdb = object.__new__(SongDatabase)
    with bz2.BZ2File(dbfile, "rb", compresslevel=9) as f:
        sdb.songs = pickle.load(f)
    sdb._rebuild_lookup_keys()
    return sdb


def print_changes(label, changes, limit=40):
    print(f"{label}: {len(changes)}")
    for song, attr, old_value, new_value in changes[:limit]:
        print(
            f"  {song.title} ({song.play_style.name.upper()}{song.difficulty.name[0].upper()}) "
            f"{attr}: {old_value} -> {new_value}"
        )
    if len(changes) > limit:
        print(f"  ... and {len(changes) - limit} more")


def main(argv=None):
    args = parse_args(argv)
    rows = read_csv_rows(args)
    katate, conflicts = parse_katate_rows(rows)

    sdb = load_song_database_without_autosave()
    updated, cleared, unmatched = update_song_database(
        sdb,
        katate,
        clear_missing=args.clear_missing,
    )

    print(f"parsed charts: {len(katate)}")
    print(f"conflicts: {len(conflicts)}")
    for key, music_level, old, new in conflicts[:20]:
        print(f"  {key[0]} ({key[2].name}) ☆{music_level}: {old} vs {new}; kept {max(old, new)}")
    if len(conflicts) > 20:
        print(f"  ... and {len(conflicts) - 20} more")

    print_changes("updated", updated)
    print_changes("cleared", cleared)

    print(f"unmatched: {len(unmatched)}")
    if args.show_unmatched:
        for title, diff, values in unmatched:
            bands = ", ".join(f"☆{lv}:{band}" for lv, band in sorted(values.items()))
            print(f"  {title} ({diff.name}) {bands}")

    if args.dry_run:
        print("dry-run: songinfo.infdc was not saved")
        return 0

    sdb.save()
    print("saved songinfo.infdc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
