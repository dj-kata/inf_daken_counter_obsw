"""打鍵カウンタ用SQLiteデータベース。"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class SQLiteDatabase:
    """プレーログとライバルキャッシュを1つのSQLiteへ保存する。"""

    SCHEMA_VERSION = 1

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = FULL")
        self._create_schema()

    def _create_schema(self):
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence INTEGER NOT NULL,
                    title TEXT,
                    play_style INTEGER,
                    difficulty INTEGER,
                    lamp INTEGER,
                    timestamp INTEGER NOT NULL,
                    playspeed REAL,
                    option_present INTEGER NOT NULL DEFAULT 0,
                    option_valid INTEGER NOT NULL DEFAULT 0,
                    option_arrange TEXT,
                    option_flip TEXT,
                    option_assist TEXT,
                    option_battle INTEGER NOT NULL DEFAULT 0,
                    option_allscratch INTEGER NOT NULL DEFAULT 0,
                    option_regularspeed INTEGER NOT NULL DEFAULT 0,
                    detect_mode INTEGER,
                    is_arcade INTEGER NOT NULL DEFAULT 0,
                    judge_pg INTEGER,
                    judge_gr INTEGER,
                    judge_gd INTEGER,
                    judge_bd INTEGER,
                    judge_pr INTEGER,
                    judge_cb INTEGER,
                    score INTEGER,
                    bp INTEGER,
                    pre_score INTEGER,
                    pre_lamp INTEGER,
                    pre_bp INTEGER,
                    notes INTEGER,
                    dead INTEGER,
                    average_release_json TEXT,
                    bpim2 REAL,
                    bpim2_arena_averages_json TEXT,
                    image_path TEXT,
                    lane_layout TEXT,
                    registered_at INTEGER,
                    official_play_count INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_results_chart
                    ON results (title, play_style, difficulty);
                CREATE INDEX IF NOT EXISTS idx_results_timestamp
                    ON results (timestamp);
                CREATE TABLE IF NOT EXISTS rival_scores (
                    rival_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    lamp INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    bp INTEGER NOT NULL,
                    last_played TEXT,
                    option TEXT,
                    PRIMARY KEY (rival_name, title, mode)
                );
                """
            )
            columns = {
                row["name"] for row in self._conn.execute("PRAGMA table_info(results)")
            }
            if "sequence" not in columns:
                self._conn.execute(
                    "ALTER TABLE results ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0"
                )
                self._conn.execute("UPDATE results SET sequence = id WHERE sequence = 0")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_results_sequence ON results (sequence)"
            )
            self.set_metadata("schema_version", str(self.SCHEMA_VERSION))
            self._conn.commit()

    def execute(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql, params):
        with self._lock:
            return self._conn.executemany(sql, params)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def rollback(self):
        with self._lock:
            self._conn.rollback()

    @contextmanager
    def transaction(self):
        """複数SQLを他スレッドの処理と混在させずに確定する。"""
        with self._lock:
            try:
                yield
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.commit()
                self._conn.close()
                self._conn = None

    def get_metadata(self, key, default=None):
        row = self.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_metadata(self, key, value):
        self.execute(
            """INSERT INTO metadata (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, str(value)),
        )

    def get_all_results(self):
        return self.execute("SELECT * FROM results ORDER BY sequence ASC, id ASC").fetchall()

    def insert_result(self, values):
        columns = tuple(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        cursor = self.execute(
            f"INSERT INTO results ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )
        return cursor.lastrowid

    def update_result(self, row_id, values):
        columns = tuple(values.keys())
        assignments = ", ".join(f"{column} = ?" for column in columns)
        self.execute(
            f"UPDATE results SET {assignments} WHERE id = ?",
            tuple(values[column] for column in columns) + (row_id,),
        )

    def delete_results(self, row_ids):
        self.executemany("DELETE FROM results WHERE id = ?", ((row_id,) for row_id in row_ids))

    def replace_rival_scores(self, rivals):
        self.execute("DELETE FROM rival_scores")
        rows = []
        for rival in rivals:
            if rival.error:
                continue
            for (title, mode), entry in rival.scores.items():
                rows.append((
                    rival.name,
                    title,
                    mode,
                    entry.lamp.value,
                    entry.score,
                    entry.bp,
                    entry.last_played,
                    entry.option,
                ))
        self.executemany(
            """INSERT INTO rival_scores
               (rival_name, title, mode, lamp, score, bp, last_played, option)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    def get_all_rival_scores(self):
        return self.execute(
            "SELECT * FROM rival_scores ORDER BY rival_name, title, mode"
        ).fetchall()

