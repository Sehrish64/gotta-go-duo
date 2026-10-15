"""SQLite storage for the leaderboard. Uses only Python's built-in sqlite3 (free, no setup)."""
from __future__ import annotations

import asyncio
import os
import sqlite3
from contextlib import closing
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "gotta_go.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS duos (
    guild_id INTEGER NOT NULL, user_a INTEGER NOT NULL, user_b INTEGER NOT NULL,
    games INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
    total_score INTEGER NOT NULL DEFAULT 0, best_score INTEGER NOT NULL DEFAULT 0,
    fastest_win INTEGER,
    PRIMARY KEY (guild_id, user_a, user_b)
);
CREATE TABLE IF NOT EXISTS players (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    games INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
    helps INTEGER NOT NULL DEFAULT 0, betrays INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
"""

PLAYER_BOARDS = {"wins", "helps", "betrays"}  # whitelist: these go into ORDER BY


class Store:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.getenv("DB_PATH") or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c, c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------ writes
    def _record(self, guild_id, players, won, turns, score) -> None:
        (id1, h1, b1), (id2, h2, b2) = players
        a, b = sorted((id1, id2))
        w = 1 if won else 0
        with closing(self._conn()) as c, c:
            c.execute(
                """INSERT INTO duos (guild_id, user_a, user_b, games, wins, total_score, best_score, fastest_win)
                   VALUES (:g, :a, :b, 1, :w, :s, :s, :ft)
                   ON CONFLICT (guild_id, user_a, user_b) DO UPDATE SET
                     games = games + 1, wins = wins + :w, total_score = total_score + :s,
                     best_score = MAX(best_score, :s),
                     fastest_win = CASE WHEN :ft IS NOT NULL AND (fastest_win IS NULL OR :ft < fastest_win)
                                        THEN :ft ELSE fastest_win END""",
                {"g": guild_id, "a": a, "b": b, "w": w, "s": score, "ft": turns if won else None},
            )
            for uid, helps, betrays in players:
                c.execute(
                    """INSERT INTO players (guild_id, user_id, games, wins, helps, betrays)
                       VALUES (?, ?, 1, ?, ?, ?)
                       ON CONFLICT (guild_id, user_id) DO UPDATE SET
                         games = games + 1, wins = wins + excluded.wins,
                         helps = helps + excluded.helps, betrays = betrays + excluded.betrays""",
                    (guild_id, uid, w, helps, betrays),
                )

    async def record_game(self, guild_id, players, won, turns, score) -> None:
        await asyncio.to_thread(self._record, guild_id, players, won, turns, score)

    # ------------------------------------------------------------- reads
    def _top_duos(self, guild_id: int, limit: int) -> list[dict]:
        with closing(self._conn()) as c:
            rows = c.execute(
                """SELECT *, total_score * 1.0 / games AS avg_score FROM duos
                   WHERE guild_id = ? ORDER BY wins DESC, avg_score DESC LIMIT ?""",
                (guild_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def _top_players(self, guild_id: int, column: str, limit: int) -> list[dict]:
        if column not in PLAYER_BOARDS:
            raise ValueError("bad board")
        with closing(self._conn()) as c:
            rows = c.execute(
                f"SELECT * FROM players WHERE guild_id = ? AND {column} > 0 ORDER BY {column} DESC, games ASC LIMIT ?",
                (guild_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def _player(self, guild_id: int, user_id: int) -> dict | None:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM players WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)).fetchone()
            if row is None:
                return None
            partner = c.execute(
                """SELECT *, total_score * 1.0 / games AS avg_score FROM duos
                   WHERE guild_id = ? AND (user_a = ? OR user_b = ?) ORDER BY games DESC, wins DESC LIMIT 1""",
                (guild_id, user_id, user_id),
            ).fetchone()
        out = dict(row)
        out["partner"] = dict(partner) if partner else None
        return out

    async def top_duos(self, guild_id: int, limit: int = 10) -> list[dict]:
        return await asyncio.to_thread(self._top_duos, guild_id, limit)

    async def top_players(self, guild_id: int, column: str, limit: int = 10) -> list[dict]:
        return await asyncio.to_thread(self._top_players, guild_id, column, limit)

    async def player(self, guild_id: int, user_id: int) -> dict | None:
        return await asyncio.to_thread(self._player, guild_id, user_id)
