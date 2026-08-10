from __future__ import annotations

from datetime import date, datetime
import time
from typing import Any

import requests

from ..capabilities import Capability, CapabilityMatrix
from ..models import Match, StandingRow, TeamRef
from ..tools.path_utils import get_by_path


class GenericMappingAdapter:
    def __init__(self, provider: str, url: str, capability_matrix: CapabilityMatrix, headers: dict | None = None, mapping: dict | None = None) -> None:
        self.provider = provider
        self.url = url
        self.headers = headers or {}
        self._matrix = capability_matrix
        self._mapping = mapping or {"list_path": "events", "standings_path": "standings"}
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._last_round_request_at = 0.0

    def supports(self, capability: Capability) -> bool:
        return self._matrix.supports(self.provider, capability)

    def _request_json(self, url: str | None = None) -> Any:
        response = self._session.get(url or self.url, timeout=30)
        response.raise_for_status()
        return response.json()

    def _extract(self, record: dict, concept: str) -> Any:
        aliases = {
            "id": ("idEvent", "id", "event_id"),
            "home_id": ("idHomeTeam", "home_team_id"),
            "away_id": ("idAwayTeam", "away_team_id"),
            "home_name": ("strHomeTeam", "home_team", "home_name"),
            "away_name": ("strAwayTeam", "away_team", "away_name"),
            "home_score": ("intHomeScore", "home_score", "homeScore"),
            "away_score": ("intAwayScore", "away_score", "awayScore"),
            "date": ("dateEvent", "date", "match_date", "strTimestamp"),
            "season": ("strSeason", "season"),
            "team_id": ("idTeam", "team_id"),
            "team_name": ("strTeam", "team_name"),
            "position": ("intRank", "position", "rank"),
            "played": ("intPlayed", "played"),
            "points": ("intPoints", "points"),
            "wins": ("intWin", "wins"),
            "draws": ("intDraw", "draws"),
            "losses": ("intLoss", "losses"),
            "goals_for": ("intGoalsFor", "goals_for"),
            "goals_against": ("intGoalsAgainst", "goals_against"),
        }
        for key in aliases.get(concept, (concept,)):
            if key in record and record[key] not in (None, ""):
                return record[key]
        return None

    @staticmethod
    def _int(value: Any) -> int | None:
        if value in (None, "", "null", "-", " postponed"):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _date(value: Any) -> date | None:
        if not value:
            return None
        text = str(value).replace("Z", "")
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text[:19], fmt).date()
            except ValueError:
                pass
        return None

    def _record_to_match(self, record: dict, competition: str) -> Match | None:
        event_date = self._date(self._extract(record, "date"))
        home_id, away_id = self._extract(record, "home_id"), self._extract(record, "away_id")
        home_name, away_name = self._extract(record, "home_name"), self._extract(record, "away_name")
        if not event_date or not home_name or not away_name:
            return None
        return Match(
            id=str(self._extract(record, "id") or f"{event_date}:{home_name}:{away_name}"),
            date=event_date,
            home_team=TeamRef(str(home_id or home_name), str(home_name)),
            away_team=TeamRef(str(away_id or away_name), str(away_name)),
            home_score=self._int(self._extract(record, "home_score")),
            away_score=self._int(self._extract(record, "away_score")),
            competition=competition,
            season=str(self._extract(record, "season") or ""),
        )

    def get_matches(self, start: date, end: date) -> list[Match]:
        payload = self._request_json()
        records = get_by_path(payload, self._mapping.get("list_path", "events"), []) or []
        result = [self._record_to_match(item, self._mapping.get("competition", "")) for item in records if isinstance(item, dict)]
        return [m for m in result if m and start <= m.date <= end]

    def get_matches_by_days(self, days: list[date]) -> list[Match]:
        """Busca partidas dia a dia usando eventsday.php quando configurado.

        O endpoint Free retorna até três eventos por dia; a função remove
        duplicatas pelo ID do evento antes de devolver os jogos.
        """
        league_id = self._mapping.get("league_id")
        if not league_id:
            raise ValueError("O mapeamento precisa de league_id para coleta por dia")
        unique: dict[str, Match] = {}
        for day in days:
            url = f"https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d={day.isoformat()}&l={league_id}"
            payload = self._request_json(url)
            for record in (payload.get("events") or []) if isinstance(payload, dict) else []:
                if not isinstance(record, dict):
                    continue
                match = self._record_to_match(record, self._mapping.get("competition", ""))
                if match:
                    unique[match.id] = match
        return sorted(unique.values(), key=lambda match: (match.date, match.id))

    def get_matches_by_rounds(self, rounds: list[int], season: str, stop_after_empty: int = 2) -> list[Match]:
        """Busca uma temporada rodada a rodada usando ``eventsround.php``.

        A consulta é deduplicada pelo ID do evento. A coleta para depois de
        ``stop_after_empty`` rodadas vazias consecutivas, evitando dezenas de
        chamadas desnecessárias depois do fim da competição.
        """
        league_id = self._mapping.get("league_id")
        if not league_id:
            raise ValueError("O mapeamento precisa de league_id para coleta por rodada")
        unique: dict[str, Match] = {}
        empty_streak = 0
        for round_number in rounds:
            elapsed = time.monotonic() - self._last_round_request_at
            if elapsed < 2.1:
                time.sleep(2.1 - elapsed)
            url = f"https://www.thesportsdb.com/api/v1/json/123/eventsround.php?id={league_id}&r={int(round_number)}&s={season}"
            self._last_round_request_at = time.monotonic()
            try:
                payload = self._request_json(url)
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 429:
                    raise
                retry_after = int(exc.response.headers.get("Retry-After", "60"))
                time.sleep(min(max(retry_after, 30), 90))
                payload = self._request_json(url)
            records = (payload.get("events") or []) if isinstance(payload, dict) else []
            if not records:
                empty_streak += 1
                if empty_streak >= stop_after_empty:
                    break
                continue
            empty_streak = 0
            for record in records:
                if not isinstance(record, dict):
                    continue
                match = self._record_to_match(record, self._mapping.get("competition", ""))
                if match:
                    unique[match.id] = match
        return sorted(unique.values(), key=lambda match: (match.date, match.id))

    def get_standings(self, season: str) -> list[StandingRow]:
        standings_url = self._mapping.get("standings_url")
        if not standings_url:
            return []
        payload = self._request_json(standings_url)
        records = get_by_path(payload, self._mapping.get("standings_path", "standings"), []) or []
        rows = []
        for item in records:
            if not isinstance(item, dict):
                continue
            team_id = self._extract(item, "team_id")
            position = self._int(self._extract(item, "position"))
            if team_id is None or position is None:
                continue
            rows.append(StandingRow(
                team_id=str(team_id), position=position,
                played=self._int(self._extract(item, "played")) or 0,
                points=self._int(self._extract(item, "points")) or 0,
                wins=self._int(self._extract(item, "wins")) or 0,
                draws=self._int(self._extract(item, "draws")) or 0,
                losses=self._int(self._extract(item, "losses")) or 0,
                goals_for=self._int(self._extract(item, "goals_for")) or 0,
                goals_against=self._int(self._extract(item, "goals_against")) or 0,
                team_name=str(self._extract(item, "team_name") or ""),
            ))
        return sorted(rows, key=lambda row: row.position)
