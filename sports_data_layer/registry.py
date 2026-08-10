from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from .capabilities import Capability
from .models import Match, StandingRow


class SimpleTTLCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._values.get(key)
        if item is None:
            return None
        created, value = item
        if time.time() - created >= self.ttl_seconds:
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._values[key] = (time.time(), value)


@dataclass
class ProviderConfig:
    primary_by_competition: dict[str, str]
    fallback_by_competition: dict[str, str]


class SportsDataRegistry:
    def __init__(self, providers: dict[str, Any], config: ProviderConfig, cache: SimpleTTLCache | None = None) -> None:
        self._providers = providers
        self._config = config
        self._cache = cache or SimpleTTLCache()

    def _provider_for(self, competition: str) -> Any:
        names = [self._config.primary_by_competition.get(competition), self._config.fallback_by_competition.get(competition)]
        for name in names:
            if name and name in self._providers:
                return self._providers[name]
        raise LookupError(f"Nenhum provedor ativo para a competição {competition!r}")

    def supports(self, competition: str, capability: Capability) -> bool:
        try:
            return self._provider_for(competition).supports(capability)
        except LookupError:
            return False

    def get_matches(self, competition: str, start: date, end: date) -> list[Match]:
        provider = self._provider_for(competition)
        key = f"matches:{provider.provider}:{competition}:{start}:{end}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = provider.get_matches(start, end)
        self._cache.set(key, result)
        return result

    def get_matches_by_days(self, competition: str, days: list[date]) -> list[Match]:
        provider = self._provider_for(competition)
        key = f"matches-days:{provider.provider}:{competition}:{days[0] if days else 'empty'}:{days[-1] if days else 'empty'}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = provider.get_matches_by_days(days)
        self._cache.set(key, result)
        return result

    def get_matches_by_rounds(self, competition: str, rounds: list[int], season: str) -> list[Match]:
        provider = self._provider_for(competition)
        key = f"matches-rounds:{provider.provider}:{competition}:{season}:{rounds[0] if rounds else 'empty'}:{rounds[-1] if rounds else 'empty'}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = provider.get_matches_by_rounds(rounds, season)
        self._cache.set(key, result)
        return result

    def get_standings(self, competition: str, season: str) -> list[StandingRow]:
        provider = self._provider_for(competition)
        key = f"standings:{provider.provider}:{competition}:{season}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = provider.get_standings(season)
        self._cache.set(key, result)
        return result
