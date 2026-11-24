"""旧バージョンのプレーログを現行OneResultへ変換する。"""

import datetime
import pickle

from src.classes import detect_mode
from src.funcs import convert_difficulty, convert_lamp, convert_play_style
from src.result import OneResult, PlayOption


def load_v2_results(pkl_path):
    """v2 alllog.pklを読み、変換できたOneResultと元件数を返す。"""
    with open(pkl_path, "rb") as stream:
        data = pickle.load(stream)
    results = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) not in (14, 15):
            continue
        try:
            timestamp = datetime.datetime(
                year=int(item[-1][0:4]),
                month=int(item[-1][5:7]),
                day=int(item[-1][8:10]),
                hour=int(item[-1][11:13]),
                minute=int(item[-1][14:16]),
            ).timestamp()
            option = PlayOption(None)
            option.convert_from_v2(item[-2])
            results.append(
                OneResult(
                    title=item[1],
                    play_style=convert_play_style(item[2][:2]),
                    difficulty=convert_difficulty(item[2][-1]),
                    lamp=convert_lamp(item[7]),
                    timestamp=int(timestamp),
                    playspeed=None,
                    option=option,
                    detect_mode=detect_mode.select,
                    is_arcade=False,
                    judge=None,
                    score=item[9],
                    bp=item[11] if item[11] else 99999999,
                    notes=item[3],
                    registered_at=int(timestamp),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return results, len(data)

