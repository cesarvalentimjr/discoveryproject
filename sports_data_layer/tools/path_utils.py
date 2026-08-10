from __future__ import annotations

from typing import Any


def get_by_path(value: Any, path: str, default: Any = None) -> Any:
    if path in ("", "$root", None):
        return value
    current = value
    for token in path.strip(".").split("."):
        if isinstance(current, dict):
            current = current.get(token, default)
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            current = current[index] if index < len(current) else default
        else:
            return default
        if current is default:
            return default
    return current
