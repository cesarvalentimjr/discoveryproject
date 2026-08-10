from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..capabilities import Capability
from ..models import Match
from ..tools.stats_utils import two_proportion_p_value
from .base import Discovery, Hypothesis


class HotColdStreak(Hypothesis):
    code = "D010"
    title = "Sequência quente/fria"
    required_capabilities = {Capability.BASIC_RESULTS}
    min_sample_size = 4

    def evaluate(self, matches: list[Match], context: dict | None = None) -> list[Discovery]:
        by_team: dict[str, list[tuple[date, int]]] = defaultdict(list)
        names: dict[str, str] = {}
        for match in matches:
            if not match.is_finished:
                continue
            if match.home_score > match.away_score:
                hp, ap = 3, 0
            elif match.home_score < match.away_score:
                hp, ap = 0, 3
            else:
                hp = ap = 1
            by_team[match.home_team.id].append((match.date, hp)); names[match.home_team.id] = match.home_team.name
            by_team[match.away_team.id].append((match.date, ap)); names[match.away_team.id] = match.away_team.name
        result: list[Discovery] = []
        for team_id, games in by_team.items():
            games.sort(key=lambda item: item[0])
            if len(games) < self.min_sample_size * 2:
                continue
            recent = [points for _, points in games[-self.min_sample_size:]]
            previous = [points for _, points in games[:-self.min_sample_size]]
            recent_pct = 100 * sum(recent) / (3 * len(recent))
            previous_pct = 100 * sum(previous) / (3 * len(previous))
            diff = recent_pct - previous_pct
            if abs(diff) < 25:
                continue
            recent_wins = sum(point == 3 for point in recent)
            previous_wins = sum(point == 3 for point in previous)
            label = "quente" if diff > 0 else "fria"
            result.append(Discovery(
                code=self.code,
                title=f"{names[team_id]} está em sequência {label}",
                detail=f"Últimos {len(recent)} jogos: {recent_pct:.0f}% de aproveitamento; período anterior: {previous_pct:.0f}%.",
                sample_size=len(games), subject=names[team_id],
                p_value=two_proportion_p_value(recent_wins, len(recent), previous_wins, len(previous)),
            ))
        return result
