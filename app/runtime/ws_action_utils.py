from __future__ import annotations

from typing import Optional


def board_point_from_data(data: dict, size: int) -> Optional[tuple[int, int]]:
    try:
        x = int(data["x"])
        y = int(data["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= x < size and 0 <= y < size):
        return None
    return x, y
