from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Any

from .hypotheses.base import Discovery, apply_multiple_comparisons_correction
from .hypotheses.run_all_hypotheses import ALL_HYPOTHESES
from .models import Match


@dataclass(frozen=True)
class PreMatchSnapshot:
    """Estado conhecido antes de uma partida; nunca usa o próprio placar."""

    match_id: str
    match_date: str
    team_id: str
    opponent_id: str
    venue: str
    prior_matches: int
    points_last_5: int
    points_last_10: int
    goals_for_last_5: int
    goals_against_last_5: int
    days_since_previous_match: int | None


@dataclass
class TemporalEvidence:
    code: str
    subject: str
    title: str
    discovery_status: str
    validation_status: str
    final_status: str
    n_discovery: int
    n_validation: int
    p_value: float
    q_value: float | None
    discovery_detail: str
    validation_detail: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_chronologically(matches: list[Match], discovery_fraction: float = 0.65) -> tuple[list[Match], list[Match]]:
    """Divide por tempo, nunca aleatoriamente."""
    ordered = sorted((m for m in matches if m.is_finished), key=lambda item: (item.date, item.id))
    if len(ordered) < 2:
        return ordered, []
    cut = min(max(int(len(ordered) * discovery_fraction), 1), len(ordered) - 1)
    return ordered[:cut], ordered[cut:]


def _points(match: Match, team_id: str) -> int:
    if team_id == match.home_team.id:
        return 3 if match.home_score > match.away_score else 1 if match.home_score == match.away_score else 0
    return 3 if match.away_score > match.home_score else 1 if match.home_score == match.away_score else 0


def _goals(match: Match, team_id: str) -> tuple[int, int]:
    if team_id == match.home_team.id:
        return match.home_score, match.away_score
    return match.away_score, match.home_score


def build_prematch_snapshots(matches: list[Match], windows: tuple[int, ...] = (5, 10)) -> list[PreMatchSnapshot]:
    """Gera variáveis defasadas usando somente partidas anteriores à observação."""
    ordered = sorted((m for m in matches if m.is_finished), key=lambda item: (item.date, item.id))
    history: dict[str, list[Match]] = {}
    snapshots: list[PreMatchSnapshot] = []
    for match in ordered:
        for team_id, opponent_id, venue in ((match.home_team.id, match.away_team.id, "home"), (match.away_team.id, match.home_team.id, "away")):
            previous = history.get(team_id, [])
            last_5 = previous[-5:]
            last_10 = previous[-10:]
            previous_date = previous[-1].date if previous else None
            rest = (match.date - previous_date).days if previous_date else None
            snapshots.append(PreMatchSnapshot(
                match_id=match.id,
                match_date=match.date.isoformat(),
                team_id=team_id,
                opponent_id=opponent_id,
                venue=venue,
                prior_matches=len(previous),
                points_last_5=sum(_points(item, team_id) for item in last_5),
                points_last_10=sum(_points(item, team_id) for item in last_10),
                goals_for_last_5=sum(_goals(item, team_id)[0] for item in last_5),
                goals_against_last_5=sum(_goals(item, team_id)[1] for item in last_5),
                days_since_previous_match=rest,
            ))
        history.setdefault(match.home_team.id, []).append(match)
        history.setdefault(match.away_team.id, []).append(match)
    return snapshots


def _evaluate(matches: list[Match], standings: list[Any] | None = None, alpha: float = 0.05) -> list[Discovery]:
    candidates: list[Discovery] = []
    context = {"standings": standings or []}
    for hypothesis in ALL_HYPOTHESES:
        candidates.extend(hypothesis.evaluate(matches, context))
    return apply_multiple_comparisons_correction(candidates, alpha=alpha)


def run_temporal_analysis(matches: list[Match], standings: list[Any] | None = None, discovery_fraction: float = 0.65, alpha: float = 0.05) -> tuple[list[TemporalEvidence], list[PreMatchSnapshot]]:
    discovery_matches, validation_matches = split_chronologically(matches, discovery_fraction)
    discovery = _evaluate(discovery_matches, standings, alpha)
    validation = _evaluate(validation_matches, standings, alpha) if validation_matches else []
    validation_map = {(item.code, item.subject): item for item in validation}
    evidence: list[TemporalEvidence] = []
    for item in discovery:
        future = validation_map.get((item.code, item.subject))
        if future is None:
            status = "candidate" if item.adjusted_significant else "exploratory"
            reason = "não houve candidato equivalente na janela futura"
            validation_status = "not_reproduced"
            validation_detail = "sem evidência equivalente na validação"
            n_validation = 0
        else:
            status = "validated" if item.adjusted_significant and future.adjusted_significant else "candidate"
            reason = "mesmo código e entidade reapareceram na janela futura" if status == "validated" else "padrão reapareceu, mas não sobreviveu ao ajuste futuro"
            validation_status = "replicated_candidate" if future.adjusted_significant else "reproduced_unadjusted"
            validation_detail = future.detail
            n_validation = future.sample_size
        evidence.append(TemporalEvidence(
            code=item.code,
            subject=item.subject,
            title=item.title,
            discovery_status="significant" if item.adjusted_significant else "candidate",
            validation_status=validation_status,
            final_status=status,
            n_discovery=item.sample_size,
            n_validation=n_validation,
            p_value=item.p_value,
            q_value=getattr(item, "q_value", None),
            discovery_detail=item.detail,
            validation_detail=validation_detail,
            reason=reason,
        ))
    return evidence, build_prematch_snapshots(matches)
