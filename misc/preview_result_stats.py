"""ResultStatsWriter preview helper.

Usage:
    python misc/preview_result_stats.py input.png
    python misc/preview_result_stats.py input.png --sample dp --output preview_dp.png
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.classes import clear_lamp, difficulty, play_style
from src.result import BpiArenaAverage
from src.result_stats_writer import ResultStatsWriter


class PreviewSongInfo:
    def __init__(
        self,
        *,
        level=12,
        katate_11=None,
        katate_12=None,
        dp_unofficial=None,
        dp_ereter_easy=None,
        dp_ereter_hard=None,
        dp_ereter_exh=None,
        sp12_clear=None,
        sp12_hard=None,
        sp11_clear=None,
        sp11_hard=None,
    ):
        self.level = level
        self.katate_11 = katate_11
        self.katate_12 = katate_12
        self.dp_unofficial = dp_unofficial
        self.dp_ereter_easy = dp_ereter_easy
        self.dp_ereter_hard = dp_ereter_hard
        self.dp_ereter_exh = dp_ereter_exh
        self.sp12_clear = sp12_clear
        self.sp12_hard = sp12_hard
        self.sp11_clear = sp11_clear
        self.sp11_hard = sp11_hard


DIFFICULTIES = {
    "b": difficulty.beginner,
    "n": difficulty.normal,
    "h": difficulty.hyper,
    "a": difficulty.another,
    "l": difficulty.leggendaria,
}

LAMPS = {
    "failed": clear_lamp.failed,
    "assist": clear_lamp.assist,
    "easy": clear_lamp.easy,
    "clear": clear_lamp.clear,
    "hard": clear_lamp.hard,
    "exh": clear_lamp.exh,
    "fc": clear_lamp.fc,
}


def build_sample(name: str):
    if name == "dp":
        return {
            "title": "千年ノ理",
            "level": 12,
            "play_style": play_style.dp,
            "difficulty": difficulty.another,
            "ex_score": 2866,
            "bp": 6,
            "max_notes": 1608,
            "lamp": clear_lamp.assist,
            "bpi": None,
            "bpi_label": "BPI",
            "bpi_arena_averages": None,
            "songinfo": PreviewSongInfo(
                level=12,
                dp_unofficial="12.0",
                dp_ereter_easy="11.7",
                dp_ereter_hard="12.2",
                dp_ereter_exh="12.6",
            ),
            "enable_katate_difficulty_display": False,
        }

    return {
        "title": "TRIP THE DEEP",
        "level": 11,
        "play_style": play_style.sp,
        "difficulty": difficulty.another,
        "ex_score": 2001,
        "bp": 14,
        "max_notes": 1289,
        "lamp": clear_lamp.exh,
        "bpi": -15.0,
        "bpi_label": "BPIM2",
        "bpi_arena_averages": [
            BpiArenaAverage("A5", 2047),
            BpiArenaAverage("A4", 2148),
        ],
        "songinfo": PreviewSongInfo(level=11, katate_11=3),
        "enable_katate_difficulty_display": True,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Preview result statistics overlay.")
    parser.add_argument("input", type=Path, help="Base result image path.")
    parser.add_argument("-o", "--output", type=Path, help="Output image path.")
    parser.add_argument("--sample", choices=("sp", "dp"), default="sp")
    parser.add_argument("--title", help="Override title.")
    parser.add_argument("--style", choices=("sp", "dp"), help="Override play style.")
    parser.add_argument("--difficulty", choices=tuple(DIFFICULTIES), help="Override difficulty: b/n/h/a/l.")
    parser.add_argument("--level", type=int, help="Override level.")
    parser.add_argument("--ex-score", type=int, help="Override EX score.")
    parser.add_argument("--bp", type=int, help="Override BP.")
    parser.add_argument("--notes", type=int, help="Override notes.")
    parser.add_argument("--lamp", choices=tuple(LAMPS), help="Override lamp.")
    parser.add_argument("--bpi", type=float, help="Override BPI/BPIM2 value.")
    return parser.parse_args()


def main():
    args = parse_args()
    params = build_sample(args.sample)

    if args.title:
        params["title"] = args.title
    if args.style:
        params["play_style"] = play_style[args.style]
    if args.difficulty:
        params["difficulty"] = DIFFICULTIES[args.difficulty]
    if args.level:
        params["level"] = args.level
        params["songinfo"].level = args.level
    if args.ex_score is not None:
        params["ex_score"] = args.ex_score
    if args.bp is not None:
        params["bp"] = args.bp
    if args.notes is not None:
        params["max_notes"] = args.notes
    if args.lamp:
        params["lamp"] = LAMPS[args.lamp]
    if args.bpi is not None:
        params["bpi"] = args.bpi

    output = args.output
    if output is None:
        output = args.input.with_name(f"{args.input.stem}_stats_preview.png")

    img = Image.open(args.input)
    result = ResultStatsWriter().write_statistics(img, **params)
    result.save(output)
    print(f"saved: {output}")


if __name__ == "__main__":
    main()
