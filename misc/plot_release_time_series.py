"""1件のプレーログから平均リリース時間の時系列SVGを生成する試作スクリプト。

Run:
    .codex-venv/bin/python -B misc/plot_release_time_series.py
    .codex-venv/bin/python -B misc/plot_release_time_series.py --result-id 16248
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path


DEFAULT_DB = Path("daken_counter.db")
DEFAULT_OUTPUT = Path("out/release_time_series.svg")


@dataclass
class ReleaseLog:
    result_id: int
    title: str
    chart: str
    timestamp: int
    interval_seconds: float
    histogram: list[float | None]

    @property
    def values(self) -> list[float]:
        return [value for value in self.histogram if value is not None]

    @property
    def average(self) -> float:
        return sum(self.values) / len(self.values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="1件のプレーログの平均リリース時間をSVGグラフへ出力します。"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="入力SQLite DB")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="出力SVG")
    parser.add_argument(
        "--result-id",
        type=int,
        help="対象results.id。省略時はリリース時間付きの最新リザルト",
    )
    return parser.parse_args()


def chart_name(play_style: int | None, difficulty: int | None) -> str:
    styles = {0: "SP", 1: "DP"}
    difficulties = {0: "B", 1: "N", 2: "H", 3: "A", 4: "L"}
    return f"{styles.get(play_style, '?')}{difficulties.get(difficulty, '?')}"


def load_release_log(db_path: Path, result_id: int | None) -> ReleaseLog:
    if not db_path.is_file():
        raise FileNotFoundError(f"DBが見つかりません: {db_path}")

    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        where = "AND id = ?" if result_id is not None else ""
        params = (result_id,) if result_id is not None else ()
        row = connection.execute(
            f"""
            SELECT id, title, play_style, difficulty, timestamp,
                   average_release_json
              FROM results
             WHERE average_release_json IS NOT NULL
               AND timestamp > 0
               {where}
             ORDER BY timestamp DESC, id DESC
             LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        target = f"results.id={result_id}" if result_id is not None else "最新ログ"
        raise RuntimeError(f"リリース時間付きの{target}がありません")

    payload = json.loads(row["average_release_json"])
    interval_seconds = float(payload["interval_seconds"])
    histogram = [
        None if value is None else float(value)
        for value in payload["histogram"]
    ]
    if interval_seconds <= 0 or not any(
        value is not None and math.isfinite(value) for value in histogram
    ):
        raise RuntimeError("有効なリリース時間がありません")

    return ReleaseLog(
        result_id=int(row["id"]),
        title=str(row["title"] or "(unknown)"),
        chart=chart_name(row["play_style"], row["difficulty"]),
        timestamp=int(row["timestamp"]),
        interval_seconds=interval_seconds,
        histogram=histogram,
    )


def nice_range(values: list[float]) -> tuple[float, float]:
    low = math.floor(min(values) / 5) * 5
    high = math.ceil(max(values) / 5) * 5
    if high - low < 20:
        center = (low + high) / 2
        low = math.floor((center - 10) / 5) * 5
        high = math.ceil((center + 10) / 5) * 5
    return low, high


def render_svg(log: ReleaseLog, output_path: Path) -> None:
    width = 900
    height = 420
    plot_x = 82
    plot_y = 105
    plot_width = 780
    plot_height = 235
    value_min, value_max = nice_range(log.values)
    duration = len(log.histogram) * log.interval_seconds
    played_at = datetime.fromtimestamp(log.timestamp).strftime("%Y/%m/%d %H:%M:%S")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text { font-family: "Yu Gothic UI", "Meiryo", sans-serif; fill: #26323d; } '
        '.small { font-size: 12px; fill: #63717d; } .axis { stroke: #c8d0d7; stroke-width: 1; }'
        '</style>',
        f'<text x="28" y="35" font-size="21" font-weight="700">{escape(log.title)} '
        f'[{escape(log.chart)}]</text>',
        f'<text x="28" y="61" class="small">{played_at} / results.id={log.result_id} / '
        f'全区間平均 {log.average:.1f} ms / {len(log.histogram)}区間 × '
        f'{log.interval_seconds:g}秒</text>',
        f'<text x="18" y="{plot_y + plot_height / 2}" class="small" '
        f'transform="rotate(-90 18 {plot_y + plot_height / 2})" text-anchor="middle">'
        '平均リリース時間 (ms)</text>',
        f'<text x="{plot_x + plot_width / 2}" y="395" class="small" '
        'text-anchor="middle">プレー開始からの経過時間</text>',
    ]

    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = plot_y + plot_height * fraction
        value = value_max - (value_max - value_min) * fraction
        parts.extend([
            f'<line x1="{plot_x}" y1="{y:.1f}" x2="{plot_x + plot_width}" '
            f'y2="{y:.1f}" class="axis"/>',
            f'<text x="{plot_x - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'class="small">{value:g}</text>',
        ])

    tick_seconds = 10 if duration <= 90 else 20 if duration <= 180 else 30
    elapsed = 0
    while elapsed <= duration + 0.001:
        x = plot_x + elapsed / duration * plot_width
        parts.extend([
            f'<line x1="{x:.1f}" y1="{plot_y}" x2="{x:.1f}" '
            f'y2="{plot_y + plot_height}" class="axis" opacity="0.55"/>',
            f'<text x="{x:.1f}" y="{plot_y + plot_height + 22}" '
            f'text-anchor="middle" class="small">{elapsed:g}s</text>',
        ])
        elapsed += tick_seconds

    segments: list[list[tuple[float, float]]] = []
    points: list[tuple[float, float, float]] = []
    current: list[tuple[float, float]] = []
    for index, value in enumerate(log.histogram):
        if value is None or not math.isfinite(value):
            if current:
                segments.append(current)
                current = []
            continue
        midpoint = (index + 0.5) * log.interval_seconds
        x = plot_x + midpoint / duration * plot_width
        y = plot_y + (value_max - value) / (value_max - value_min) * plot_height
        current.append((x, y))
        points.append((x, y, value))
    if current:
        segments.append(current)

    for segment in segments:
        coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in segment)
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="#1677c8" '
            'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    for x, y, value in points:
        parts.extend([
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#1677c8">'
            f'<title>{value:.1f} ms</title></circle>',
            f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
            f'class="small">{value:.1f}</text>',
        ])

    parts.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    args = parse_args()
    log = load_release_log(args.db, args.result_id)
    render_svg(log, args.output)
    print(f"results.id={log.result_id} を出力しました: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
