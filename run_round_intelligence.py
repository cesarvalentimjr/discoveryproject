from __future__ import annotations

import argparse
import json
from dataclasses import replace

from sports_data_layer.adapters.generic_mapping_adapter import GenericMappingAdapter
from sports_data_layer.analysis_service import run_temporal_hypotheses
from sports_data_layer.capabilities import Capability, CapabilityMatrix
from sports_data_layer.registry import ProviderConfig, SportsDataRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta uma temporada por rodada e executa análise temporal sem banco")
    parser.add_argument("--league-id", type=int, default=4351)
    parser.add_argument("--seasons", default="2025", help="Temporadas separadas por vírgula; exemplo: 2023,2024,2025")
    parser.add_argument("--start-round", type=int, default=1)
    parser.add_argument("--end-round", type=int, default=38)
    parser.add_argument("--discovery-fraction", type=float, default=0.65, help="Fração cronológica usada na descoberta; o restante é validação")
    parser.add_argument("--output", default="temporal_evidence.json", help="Arquivo JSON para evidências e snapshots")
    args = parser.parse_args()
    if args.end_round < args.start_round:
        parser.error("--end-round deve ser maior ou igual à --start-round")
    if not 0.5 <= args.discovery_fraction < 1:
        parser.error("--discovery-fraction deve estar entre 0.5 e 0.99")

    matrix = CapabilityMatrix()
    matrix.set("thesportsdb", {Capability.BASIC_RESULTS})
    adapter = GenericMappingAdapter("thesportsdb", "https://www.thesportsdb.com/api/v1/json/123/eventsround.php", matrix, mapping={"list_path": "events", "competition": "competition", "league_id": str(args.league_id)})
    registry = SportsDataRegistry({"thesportsdb": adapter}, ProviderConfig({"competition": "thesportsdb"}, {}))
    seasons = list(dict.fromkeys(item.strip() for item in args.seasons.split(",") if item.strip()))
    if not seasons:
        parser.error("--seasons precisa conter pelo menos uma temporada")
    unique = {}
    for season in seasons:
        for round_number in range(args.start_round, args.end_round + 1):
            matches = registry.get_matches_by_rounds("competition", [round_number], season)
            unique.update({match.id: replace(match, season=season, competition="competition") for match in matches})
            print(f"Temporada {season} · rodada {round_number}: {len(matches)} partidas; total único: {len(unique)}")
    history = sorted(unique.values(), key=lambda match: (match.date, match.id))
    evidence, snapshots = run_temporal_hypotheses(history, [], discovery_fraction=args.discovery_fraction)
    payload = {
        "metadata": {"league_id": args.league_id, "seasons": seasons, "start_round": args.start_round, "end_round": args.end_round, "discovery_fraction": args.discovery_fraction, "matches": len(history)},
        "evidence": [item.to_dict() for item in evidence],
        "prematch_snapshots": [snapshot.__dict__ for snapshot in snapshots],
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"Temporada consolidada: {len(history)} partidas")
    print(f"Candidatos: {sum(item.final_status in {'candidate', 'exploratory'} for item in evidence)}")
    print(f"Validados: {sum(item.final_status == 'validated' for item in evidence)}")
    print(f"Catálogo salvo em: {args.output}")


if __name__ == "__main__":
    main()
