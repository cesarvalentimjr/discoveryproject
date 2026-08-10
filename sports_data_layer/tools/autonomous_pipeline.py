from __future__ import annotations

import logging
from urllib.parse import parse_qs, urlparse

from ..adapters.generic_mapping_adapter import GenericMappingAdapter
from ..capabilities import Capability, CapabilityMatrix

logger = logging.getLogger(__name__)


def run_autonomous_ingestion(provider: str, url: str, competition: str, capability_matrix: CapabilityMatrix, headers: dict | None = None) -> GenericMappingAdapter:
    """Inicializa um adaptador validando que a fonte responde como JSON.

    A API gratuita V1 do TheSportsDB entrega eventos em ``events``. O
    adaptador mantém o mapeamento conservador: só declara BASIC_RESULTS,
    porque a fonte não fornece uma tabela de classificação confiável neste
    endpoint de temporada.
    """
    query = parse_qs(urlparse(url).query)
    mapping = {"list_path": "events", "competition": competition, "league_id": (query.get("id") or [None])[0]}
    adapter = GenericMappingAdapter(provider, url, capability_matrix, headers, mapping)
    payload = adapter._request_json()
    if not isinstance(payload, dict):
        raise ValueError(f"Resposta inesperada do provedor {provider}: objeto JSON esperado")
    records = payload.get("events")
    if records is None:
        # Alguns provedores usam data/results; aceitamos apenas listas para
        # não transformar uma resposta de erro em dados silenciosamente.
        for candidate in ("data", "results", "matches"):
            if isinstance(payload.get(candidate), list):
                mapping["list_path"] = candidate
                records = payload[candidate]
                break
    if not isinstance(records, list):
        raise ValueError(f"Provedor {provider} não retornou uma lista de partidas")
    capabilities = {Capability.BASIC_RESULTS}
    if records and isinstance(records[0], dict) and any(key in records[0] for key in ("standings", "table")):
        capabilities.add(Capability.STANDINGS)
    capability_matrix.set(provider, capabilities)
    logger.info("%s: %d registros detectados; capacidades=%s", provider, len(records), sorted(c.value for c in capabilities))
    return adapter
