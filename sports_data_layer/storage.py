from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .models import Match, TeamRef
from .hypotheses.base import Discovery


class SportsDatabase:
    """Persistência local para histórico de partidas e descobertas.

    SQLite é usado por padrão para facilitar o desenvolvimento e o deploy.
    Em ambientes efêmeros, o caminho deve apontar para um volume persistente
    ou a aplicação deve ser conectada a um banco externo em uma etapa posterior.
    """

    def __init__(self, path: str | Path = "sports_intelligence.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS matches (
                    event_id TEXT PRIMARY KEY,
                    event_date TEXT NOT NULL,
                    competition TEXT NOT NULL,
                    season TEXT NOT NULL DEFAULT '',
                    home_team_id TEXT NOT NULL,
                    home_team_name TEXT NOT NULL,
                    away_team_id TEXT NOT NULL,
                    away_team_name TEXT NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    source TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_matches_competition_date
                    ON matches(competition, event_date);
                CREATE TABLE IF NOT EXISTS ingest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition TEXT NOT NULL,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    requested_days INTEGER NOT NULL DEFAULT 0,
                    received_matches INTEGER NOT NULL DEFAULT 0,
                    inserted_or_updated INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS discoveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    sample_size INTEGER NOT NULL,
                    p_value REAL NOT NULL,
                    adjusted_significant INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, code, subject),
                    FOREIGN KEY(run_id) REFERENCES ingest_runs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_discoveries_created
                    ON discoveries(created_at DESC);
                """
            )

    def start_ingest(self, competition: str, source: str, requested_days: int) -> int:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO ingest_runs (competition, source, started_at, finished_at, requested_days, status) VALUES (?, ?, ?, ?, ?, ?)",
                (competition, source, now, now, requested_days, "running"),
            )
            return int(cur.lastrowid)

    def finish_ingest(self, run_id: int, received: int, persisted: int, status: str = "success", error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE ingest_runs SET finished_at=?, received_matches=?, inserted_or_updated=?, status=?, error=? WHERE id=?",
                (datetime.utcnow().isoformat(timespec="seconds"), received, persisted, status, error, run_id),
            )

    def upsert_matches(self, matches: Iterable[Match], source: str = "") -> int:
        rows = list(matches)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            for match in rows:
                conn.execute(
                    """
                    INSERT INTO matches (event_id, event_date, competition, season, home_team_id, home_team_name, away_team_id, away_team_name, home_score, away_score, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO UPDATE SET
                        event_date=excluded.event_date,
                        competition=excluded.competition,
                        season=excluded.season,
                        home_team_id=excluded.home_team_id,
                        home_team_name=excluded.home_team_name,
                        away_team_id=excluded.away_team_id,
                        away_team_name=excluded.away_team_name,
                        home_score=excluded.home_score,
                        away_score=excluded.away_score,
                        source=excluded.source,
                        updated_at=excluded.updated_at
                    """,
                    (match.id, match.date.isoformat(), match.competition, match.season, match.home_team.id, match.home_team.name, match.away_team.id, match.away_team.name, match.home_score, match.away_score, source, now),
                )
        return len(rows)

    def get_matches(self, competition: str | None = None, start: date | None = None, end: date | None = None) -> list[Match]:
        clauses, params = [], []
        if competition:
            clauses.append("competition = ?"); params.append(competition)
        if start:
            clauses.append("event_date >= ?"); params.append(start.isoformat())
        if end:
            clauses.append("event_date <= ?"); params.append(end.isoformat())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM matches{where} ORDER BY event_date, event_id", params).fetchall()
        return [
            Match(id=row["event_id"], date=date.fromisoformat(row["event_date"]), competition=row["competition"], season=row["season"], home_team=TeamRef(row["home_team_id"], row["home_team_name"]), away_team=TeamRef(row["away_team_id"], row["away_team_name"]), home_score=row["home_score"], away_score=row["away_score"])
            for row in rows
        ]

    def save_discoveries(self, discoveries: Iterable[Discovery], run_id: int | None = None) -> int:
        rows = list(discoveries)
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._connect() as conn:
            for discovery in rows:
                conn.execute(
                    """
                    INSERT INTO discoveries (run_id, code, title, detail, subject, sample_size, p_value, adjusted_significant, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, code, subject) DO UPDATE SET
                        title=excluded.title, detail=excluded.detail, sample_size=excluded.sample_size,
                        p_value=excluded.p_value, adjusted_significant=excluded.adjusted_significant, created_at=excluded.created_at
                    """,
                    (run_id, discovery.code, discovery.title, discovery.detail, discovery.subject, discovery.sample_size, discovery.p_value, int(discovery.adjusted_significant), now),
                )
        return len(rows)

    def get_discoveries(self, significant_only: bool = False, limit: int = 100) -> list[dict]:
        clause = "WHERE adjusted_significant = 1" if significant_only else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM discoveries {clause} ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def summary(self, competition: str | None = None) -> dict[str, int]:
        with self._connect() as conn:
            match_clause = "WHERE competition = ?" if competition else ""
            params = (competition,) if competition else ()
            row = conn.execute(f"SELECT COUNT(*) AS total, SUM(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL THEN 1 ELSE 0 END) AS finished FROM matches {match_clause}", params).fetchone()
            discoveries = conn.execute("SELECT COUNT(*) AS total, SUM(adjusted_significant) AS significant FROM discoveries").fetchone()
        return {"matches": int(row["total"] or 0), "finished": int(row["finished"] or 0), "discoveries": int(discoveries["total"] or 0), "significant": int(discoveries["significant"] or 0)}
