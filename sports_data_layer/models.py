from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TeamRef:
    id: str
    name: str


@dataclass(frozen=True)
class Match:
    id: str
    date: date
    home_team: TeamRef
    away_team: TeamRef
    home_score: int | None
    away_score: int | None
    competition: str = ""
    season: str = ""
    round_number: int | None = None

    @property
    def is_finished(self) -> bool:
        return self.home_score is not None and self.away_score is not None


@dataclass(frozen=True)
class StandingRow:
    team_id: str
    position: int
    played: int
    points: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    team_name: str = ""


@dataclass(frozen=True)
class Team:
    id: str
    name: str
