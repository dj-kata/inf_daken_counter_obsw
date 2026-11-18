"""公式サイトのプレーデータCSVを自己ベストとして取り込む。"""

from __future__ import annotations

import csv
import datetime
import io
import unicodedata
from dataclasses import dataclass, field

from .classes import clear_lamp, detect_mode, difficulty, play_style
from .funcs import calc_chart_lookup_key
from .result import OneResult, PlayOption


DIFFICULTIES = {
    "BEGINNER": difficulty.beginner,
    "NORMAL": difficulty.normal,
    "HYPER": difficulty.hyper,
    "ANOTHER": difficulty.another,
    "LEGGENDARIA": difficulty.leggendaria,
}

OFFICIAL_LAMPS = {
    "NO PLAY": clear_lamp.noplay,
    "FAILED": clear_lamp.failed,
    "ASSIST CLEAR": clear_lamp.assist,
    "EASY CLEAR": clear_lamp.easy,
    "CLEAR": clear_lamp.clear,
    "HARD CLEAR": clear_lamp.hard,
    "EX HARD CLEAR": clear_lamp.exh,
    "FULLCOMBO CLEAR": clear_lamp.fc,
}

# songinfoはゲーム画面OCRで扱える表記、公式CSVは装飾文字を含む正式表記を使う。
# 記号除去だけでは同一にならない文字を含む曲のみ明示的に対応させる。
OFFICIAL_TITLE_ALIASES = {
    "ÆTHER": "ATHER",
    "焱影": "火影",
    "BLO§OM": "BLOSSOM",
    "Ignis†Iræ": "Ignis†Irae",
    "POLꞰAMAИIA": "POLKAMANIA",
    "RINИE": "RINNE",
    "uən": "uen",
}


@dataclass(frozen=True)
class OfficialCsvBest:
    title: str
    difficulty: difficulty
    score: int
    bp: int | None
    lamp: clear_lamp
    registered_at: int | None = None


@dataclass
class OfficialCsvParseResult:
    bests: list[OfficialCsvBest] = field(default_factory=list)
    row_count: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class OfficialCsvImportPlan:
    results: list[OneResult] = field(default_factory=list)
    delete_indexes: set[int] = field(default_factory=set)
    corrected_charts: set[tuple] = field(default_factory=set)
    corrections: list["OfficialCsvCorrection"] = field(default_factory=list)
    unknown_charts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OfficialCsvCorrection:
    title: str
    style: play_style
    difficulty: difficulty
    saved_score: int
    saved_bp: int | None
    saved_lamp: clear_lamp
    official_score: int
    official_bp: int | None
    official_lamp: clear_lamp
    delete_count: int


@dataclass
class OfficialCsvImportResult:
    imported: int = 0
    skipped: int = 0
    deleted: int = 0
    corrected_charts: int = 0
    unknown_charts: int = 0


def _parse_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value or value == "---":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_timestamp(value: str) -> int | None:
    value = (value or "").strip()
    if not value or value == "---":
        return None
    try:
        return int(datetime.datetime.fromisoformat(value.replace("/", "-")).timestamp())
    except ValueError:
        return None


def parse_official_csv(text: str) -> OfficialCsvParseResult:
    """貼り付けられた公式CSVを譜面単位の自己ベストへ変換する。"""
    parsed = OfficialCsvParseResult()
    reader = csv.DictReader(io.StringIO((text or "").lstrip("\ufeff")))
    headers = [header.strip() for header in (reader.fieldnames or []) if header]
    if "タイトル" not in headers or not any(
        f"{name} スコア" in headers for name in DIFFICULTIES
    ):
        parsed.errors.append("公式CSVのヘッダーを確認できませんでした。")
        return parsed

    for row_number, row in enumerate(reader, start=2):
        title = (row.get("タイトル") or "").strip()
        if not title:
            continue
        parsed.row_count += 1
        for name, diff in DIFFICULTIES.items():
            score_text = (row.get(f"{name} スコア") or "").strip()
            score = _parse_int(score_text)
            lamp_text = (row.get(f"{name} クリアタイプ") or "").strip()
            if score == 0 or (score is None and score_text in ("", "---")):
                continue
            lamp = OFFICIAL_LAMPS.get(lamp_text)
            if score is None or score <= 0 or lamp is None:
                parsed.errors.append(f"{row_number}行目 {title} {name}: 値を解釈できません。")
                continue
            parsed.bests.append(
                OfficialCsvBest(
                    title=title,
                    difficulty=diff,
                    score=score,
                    bp=_parse_int(row.get(f"{name} ミスカウント")),
                    lamp=lamp,
                    registered_at=_parse_timestamp(row.get(f"{name} 最終プレー日時")),
                )
            )
    return parsed


def result_exceeds_official(result: OneResult, official: OfficialCsvBest) -> bool:
    """保存済みログのいずれかのベスト値が公式値を超えるか返す。"""
    if result.score is not None and result.score > official.score:
        return True
    bp_counts_as_best = not result.judge or not result.dead
    if (
        bp_counts_as_best
        and official.bp is not None
        and result.bp is not None
        and result.bp < official.bp
    ):
        return True
    return bool(result.lamp and result.lamp.value > official.lamp.value)


class OfficialCsvImporter:
    """CSVの曲名解決、補正対象抽出、ResultDatabaseへの反映を担当する。"""

    def __init__(self, result_database):
        self.result_database = result_database
        self._official_title_lookup = None

    @staticmethod
    def _normalize_official_title(title: str) -> str:
        normalized = unicodedata.normalize("NFKD", title or "").casefold()
        return "".join(
            char
            for char in normalized
            if char.isalnum() and not unicodedata.combining(char)
        )

    def _build_official_title_lookup(self):
        lookup = {}
        songs = getattr(self.result_database.song_database, "songs", {})
        for song in songs.values():
            key = (
                self._normalize_official_title(song.title),
                song.play_style,
                song.difficulty,
            )
            if key in lookup:
                # 記号を除くと同名になる曲は誤登録を避けるため解決不能にする。
                lookup[key] = None
            else:
                lookup[key] = song
        self._official_title_lookup = lookup

    def _search_song(self, title: str, style: play_style, diff: difficulty):
        aliased_title = OFFICIAL_TITLE_ALIASES.get(title, title)
        song = self.result_database.song_database.search(
            title=aliased_title, play_style=style, difficulty=diff
        )
        if song is not None:
            return song
        if self._official_title_lookup is None:
            self._build_official_title_lookup()
        return self._official_title_lookup.get(
            (self._normalize_official_title(aliased_title), style, diff)
        )

    @staticmethod
    def _is_regular_best_result(result: OneResult) -> bool:
        option = result.option or PlayOption()
        return (
            result.detect_mode != detect_mode.play
            and result.playspeed in (None, 1.0)
            and not option.battle
            and not option.allscratch
            and not option.regularspeed
            and not option.special
        )

    def build_plan(
        self, bests: list[OfficialCsvBest], style: play_style
    ) -> OfficialCsvImportPlan:
        plan = OfficialCsvImportPlan()
        saved_by_chart = {}
        for index, saved in enumerate(self.result_database.results):
            if not self._is_regular_best_result(saved):
                continue
            key = calc_chart_lookup_key(
                saved.title, saved.play_style, saved.difficulty, battle=False
            )
            saved_by_chart.setdefault(key, []).append((index, saved))

        for best in bests:
            song = self._search_song(best.title, style, best.difficulty)
            if song is None:
                plan.unknown_charts.append(
                    f"{best.title} ({style.name.upper()}{best.difficulty.name[0].upper()})"
                )
                continue

            result = OneResult(
                title=song.title,
                play_style=style,
                difficulty=best.difficulty,
                lamp=best.lamp,
                timestamp=0,
                playspeed=None,
                option=PlayOption(),
                detect_mode=detect_mode.select,
                score=best.score,
                bp=best.bp,
                pre_score=None,
                # 公式CSVは現在の自己ベストそのものなので、既存値との更新判定で
                # 欠損BPに阻まれないよう、初回データと同じ扱いで登録する。
                pre_lamp=clear_lamp.noplay,
                pre_bp=None,
                notes=song.notes,
                registered_at=best.registered_at,
            )
            plan.results.append(result)

            chart_key = (song.title, style, best.difficulty)
            lookup_key = calc_chart_lookup_key(
                song.title, style, best.difficulty, battle=False
            )
            chart_results = saved_by_chart.get(lookup_key, [])
            delete_count = 0
            for index, saved in chart_results:
                if result_exceeds_official(saved, best):
                    plan.delete_indexes.add(index)
                    plan.corrected_charts.add(chart_key)
                    delete_count += 1
            if delete_count:
                saved_results = [saved for _, saved in chart_results]
                scores = [saved.score for saved in saved_results if saved.score is not None]
                bps = [
                    saved.bp
                    for saved in saved_results
                    if saved.bp is not None and (not saved.judge or not saved.dead)
                ]
                lamps = [saved.lamp for saved in saved_results if saved.lamp is not None]
                plan.corrections.append(
                    OfficialCsvCorrection(
                        title=song.title,
                        style=style,
                        difficulty=best.difficulty,
                        saved_score=max(scores) if scores else 0,
                        saved_bp=min(bps) if bps else None,
                        saved_lamp=max(lamps, key=lambda lamp: lamp.value)
                        if lamps
                        else clear_lamp.noplay,
                        official_score=best.score,
                        official_bp=best.bp,
                        official_lamp=best.lamp,
                        delete_count=delete_count,
                    )
                )
        return plan

    def apply(self, plan: OfficialCsvImportPlan, progress_callback=None) -> OfficialCsvImportResult:
        original_results = list(self.result_database.results)
        imported = 0
        skipped = 0
        total = len(plan.results)
        try:
            for index in sorted(plan.delete_indexes, reverse=True):
                del self.result_database.results[index]

            current_bests = {}
            for saved in self.result_database.results:
                if not self._is_regular_best_result(saved):
                    continue
                key = calc_chart_lookup_key(
                    saved.title, saved.play_style, saved.difficulty, battle=False
                )
                score, bp, lamp = current_bests.get(key, (None, None, None))
                if isinstance(saved.score, int):
                    score = saved.score if score is None else max(score, saved.score)
                if saved.bp is not None and (not saved.judge or not saved.dead):
                    bp = saved.bp if bp is None else min(bp, saved.bp)
                if saved.lamp is not None and (
                    lamp is None or saved.lamp.value > lamp.value
                ):
                    lamp = saved.lamp
                current_bests[key] = (score, bp, lamp)

            for current, result in enumerate(plan.results, start=1):
                key = calc_chart_lookup_key(
                    result.title,
                    result.play_style,
                    result.difficulty,
                    battle=False,
                )
                current_score, current_bp, current_lamp = current_bests.get(
                    key, (None, None, None)
                )
                is_update = current_score is None
                if current_score is not None and result.score > current_score:
                    is_update = True
                if current_lamp is None or result.lamp.value > current_lamp.value:
                    is_update = True
                if result.bp is not None and (current_bp is None or result.bp < current_bp):
                    is_update = True
                if not is_update:
                    skipped += 1
                elif self.result_database.add(result):
                    imported += 1
                    new_score = (
                        result.score
                        if current_score is None
                        else max(current_score, result.score)
                    )
                    new_bp = current_bp
                    if result.bp is not None:
                        new_bp = (
                            result.bp
                            if current_bp is None
                            else min(current_bp, result.bp)
                        )
                    new_lamp = current_lamp
                    if current_lamp is None or result.lamp.value > current_lamp.value:
                        new_lamp = result.lamp
                    current_bests[key] = (new_score, new_bp, new_lamp)
                else:
                    skipped += 1
                if progress_callback:
                    progress_callback(current, total)
            self.result_database.save()
        except Exception:
            self.result_database.results = original_results
            raise
        return OfficialCsvImportResult(
            imported=imported,
            skipped=skipped,
            deleted=len(plan.delete_indexes),
            corrected_charts=len(plan.corrected_charts),
            unknown_charts=len(plan.unknown_charts),
        )
