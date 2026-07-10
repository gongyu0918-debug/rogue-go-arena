from __future__ import annotations

import math


VALID_BOARD_SIZES = frozenset({5, 9, 13, 19})
VALID_HANDICAPS = frozenset({0, 2, 3, 4, 5, 6, 7, 8, 9})
MIN_KOMI = -100.0
MAX_KOMI = 100.0


def payload_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_komi(value: object) -> float | None:
    try:
        komi = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(komi) or not MIN_KOMI <= komi <= MAX_KOMI:
        return None
    return komi
