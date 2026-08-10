from __future__ import annotations

from .base import Discovery


def format_batch(discoveries: list[Discovery]) -> str:
    if not discoveries:
        return "Nenhuma descoberta estatisticamente significativa após a correção Benjamini-Hochberg."
    lines = [f"{len(discoveries)} descoberta(s) significativa(s):"]
    for item in discoveries:
        lines.append(f"[{item.code}] {item.title} — {item.detail} (amostra: {item.sample_size}; p={item.p_value:.4f})")
    return "\n".join(lines)
