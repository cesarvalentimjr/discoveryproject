from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from statistics import mean
from typing import Any

from .hypotheses.base import Discovery, apply_multiple_comparisons_correction
from .hypotheses.run_all_hypotheses import ALL_HYPOTHESES
from .models import Match
from .temporal_analysis import PreMatchSnapshot, build_prematch_snapshots


@dataclass
class SeasonalEvidence:
    code: str
    subject: str
    title: str
    seasons_tested: int
    seasons_with_discovery: int
    seasons_validated: int
    discovery_rounds: str
    validation_rounds: str
    mean_discovery_n: float
    mean_validation_n: float
    mean_p_value: float
    status: str
    details: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _round_groups(matches: list[Match], fraction: float) -> tuple[list[Match], list[Match], tuple[int, int]]:
    finished = [m for m in matches if m.is_finished]
    available = sorted({m.round_number for m in finished if m.round_number is not None})
    if len(available) < 2:
        ordered = sorted(finished, key=lambda m: (m.date, m.id))
        cut = min(max(int(len(ordered) * fraction), 1), max(len(ordered) - 1, 1))
        return ordered[:cut], ordered[cut:], (0, 0)
    cut_index = min(max(int(len(available) * fraction), 1), len(available) - 1)
    discovery_rounds = set(available[:cut_index])
    validation_rounds = set(available[cut_index:])
    return ([m for m in finished if m.round_number in discovery_rounds], [m for m in finished if m.round_number in validation_rounds], (min(discovery_rounds), max(discovery_rounds)))


def _evaluate(matches: list[Match], alpha: float) -> list[Discovery]:
    candidates: list[Discovery] = []
    for hypothesis in ALL_HYPOTHESES:
        candidates.extend(hypothesis.evaluate(matches, {"standings": []}))
    return apply_multiple_comparisons_correction(candidates, alpha=alpha)


def run_seasonal_temporal_analysis(matches: list[Match], fraction: float = 0.65, alpha: float = 0.05) -> tuple[list[SeasonalEvidence], list[PreMatchSnapshot]]:
    """Divide cada temporada por rodada e consolida evidências por código/entidade."""
    by_season: dict[str, list[Match]] = defaultdict(list)
    for match in matches:
        by_season[match.season or "unknown"].append(match)
    records: list[dict[str, Any]] = []
    snapshots: list[PreMatchSnapshot] = []
    for season, season_matches in sorted(by_season.items()):
        discovery, validation, rounds = _round_groups(season_matches, fraction)
        snapshots.extend(build_prematch_snapshots(season_matches))
        discovery_map = {(item.code, item.subject): item for item in _evaluate(discovery, alpha)}
        validation_map = {(item.code, item.subject): item for item in _evaluate(validation, alpha)} if validation else {}
        keys = set(discovery_map) | set(validation_map)
        for key in keys:
            d = discovery_map.get(key)
            v = validation_map.get(key)
            records.append({
                "season": season,
                "code": key[0],
                "subject": key[1],
                "title": (d or v).title,
                "discovery": d,
                "validation": v,
                "discovery_rounds": rounds,
                "validation_rounds": (rounds[1] if len(rounds) > 1 else 0, max((m.round_number or 0) for m in validation) if validation else 0),
            })
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["code"], record["subject"])].append(record)
    output: list[SeasonalEvidence] = []
    for (code, subject), items in grouped.items():
        discovered = [item for item in items if item["discovery"] is not None]
        validated = [item for item in items if item["discovery"] is not None and item["validation"] is not None and item["discovery"].adjusted_significant and item["validation"].adjusted_significant]
        status = "replicated" if len(validated) >= 2 else "validated" if validated else "candidate" if discovered else "exploratory"
        p_values = [item["discovery"].p_value for item in discovered]
        output.append(SeasonalEvidence(
            code=code,
            subject=subject,
            title=items[0]["title"],
            seasons_tested=len(by_season),
            seasons_with_discovery=len(discovered),
            seasons_validated=len(validated),
            discovery_rounds="por temporada",
            validation_rounds="por temporada",
            mean_discovery_n=mean([item["discovery"].sample_size for item in discovered]) if discovered else 0.0,
            mean_validation_n=mean([item["validation"].sample_size for item in validated]) if validated else 0.0,
            mean_p_value=mean(p_values) if p_values else 1.0,
            status=status,
            details=f"{len(validated)} temporada(s) com o mesmo sinal sobrevivendo na validação intratemporada.",
        ))
    return sorted(output, key=lambda item: (item.status, item.code, item.subject)), snapshots
