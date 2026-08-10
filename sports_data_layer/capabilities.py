from __future__ import annotations

from enum import Enum


class Capability(str, Enum):
    BASIC_RESULTS = "basic_results"
    STANDINGS = "standings"
    MATCH_EVENTS = "match_events"
    SUBSTITUTIONS = "substitutions"


class CapabilityMatrix:
    def __init__(self) -> None:
        self._by_provider: dict[str, set[Capability]] = {}

    def set(self, provider: str, capabilities: set[Capability]) -> None:
        self._by_provider[provider] = set(capabilities)

    def get(self, provider: str) -> set[Capability]:
        return set(self._by_provider.get(provider, set()))

    def supports(self, provider: str, capability: Capability) -> bool:
        return capability in self._by_provider.get(provider, set())

    def __contains__(self, provider: str) -> bool:
        return provider in self._by_provider
