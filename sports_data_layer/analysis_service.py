from __future__ import annotations

from datetime import date

from .hypotheses.base import Discovery, apply_multiple_comparisons_correction
from .hypotheses.run_all_hypotheses import ALL_HYPOTHESES
from .models import Match, StandingRow
from .storage import SportsDatabase
from .temporal_analysis import run_temporal_analysis


def run_hypotheses(matches: list[Match], standings: list[StandingRow] | None = None, alpha: float = 0.05) -> list[Discovery]:
    """Executa todas as hipóteses sobre o histórico disponível.

    O retorno mantém também candidatos não significativos para auditoria:
    o campo ``adjusted_significant`` indica quais sobreviveram ao BH/FDR.
    """
    finished = [match for match in matches if match.is_finished]
    context = {"standings": standings or []}
    candidates: list[Discovery] = []
    for hypothesis in ALL_HYPOTHESES:
        candidates.extend(hypothesis.evaluate(finished, context))
    return apply_multiple_comparisons_correction(candidates, alpha=alpha)


def run_temporal_hypotheses(matches: list[Match], standings: list[StandingRow] | None = None, discovery_fraction: float = 0.65, alpha: float = 0.05):
    """Executa descoberta e validação em ordem cronológica, sem banco."""
    return run_temporal_analysis(matches, standings=standings, discovery_fraction=discovery_fraction, alpha=alpha)


def ingest_and_analyze(
    db: SportsDatabase,
    matches: list[Match],
    competition: str,
    source: str,
    requested_days: int = 0,
    standings: list[StandingRow] | None = None,
    alpha: float = 0.05,
) -> dict[str, int]:
    """Persiste uma coleta incremental e recalcula as hipóteses no histórico inteiro."""
    run_id = db.start_ingest(competition, source, requested_days)
    try:
        persisted = db.upsert_matches(matches, source=source)
        history = db.get_matches(competition=competition)
        discoveries = run_hypotheses(history, standings=standings, alpha=alpha)
        saved = db.save_discoveries(discoveries, run_id=run_id)
        db.finish_ingest(run_id, len(matches), persisted, "success")
        significant = sum(1 for discovery in discoveries if discovery.adjusted_significant)
        return {"run_id": run_id, "received": len(matches), "persisted": persisted, "history": len(history), "discoveries": saved, "significant": significant}
    except Exception as exc:
        db.finish_ingest(run_id, len(matches), 0, "error", str(exc))
        raise
