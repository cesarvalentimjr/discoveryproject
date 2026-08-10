from __future__ import annotations

from collections import defaultdict

from ..capabilities import Capability
from ..models import Match
from ..tools.stats_utils import two_proportion_p_value
from .base import Discovery, Hypothesis


class HomeAwayPerformance(Hypothesis):
    code = "D006"
    title = "Desempenho em casa vs. fora"
    required_capabilities = {Capability.BASIC_RESULTS}
    min_sample_size = 5

    def evaluate(self, matches: list[Match], context: dict | None = None) -> list[Discovery]:
        by_team: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"home": [], "away": []})
        names: dict[str, str] = {}
        for match in matches:
            if not match.is_finished:
                continue
            names[match.home_team.id] = match.home_team.name
            names[match.away_team.id] = match.away_team.name
            if match.home_score > match.away_score:
                home_points, away_points = 3, 0
            elif match.home_score < match.away_score:
                home_points, away_points = 0, 3
            else:
                home_points = away_points = 1
            by_team[match.home_team.id]["home"].append(home_points)
            by_team[match.away_team.id]["away"].append(away_points)
        result: list[Discovery] = []
        for team_id, groups in by_team.items():
            home, away = groups["home"], groups["away"]
            if len(home) < self.min_sample_size or len(away) < self.min_sample_size:
                continue
            home_pct = 100 * sum(home) / (3 * len(home))
            away_pct = 100 * sum(away) / (3 * len(away))
            diff = home_pct - away_pct
            if abs(diff) < 20:
                continue
            home_wins = sum(point == 3 for point in home)
            away_wins = sum(point == 3 for point in away)
            result.append(Discovery(
                code=self.code,
                title=f"{names[team_id]} rende {('melhor em casa' if diff > 0 else 'melhor fora')}",
                detail=f"Aproveitamento em casa: {home_pct:.0f}% ({len(home)} jogos); fora: {away_pct:.0f}% ({len(away)} jogos).",
                sample_size=len(home) + len(away), subject=names[team_id],
                p_value=two_proportion_p_value(home_wins, len(home), away_wins, len(away)),
            ))
        return result
