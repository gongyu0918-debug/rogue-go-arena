from __future__ import annotations


SAFE_GTP_COLORS = frozenset({"B", "W"})


def normalize_gtp_color(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    color = value.strip().upper()
    return color if color in SAFE_GTP_COLORS else None
