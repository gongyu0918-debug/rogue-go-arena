from __future__ import annotations

from collections.abc import Callable

from app.gameplay.ai_moves import compute_game_visits


CpuModeFn = Callable[[], bool]
ComputeVisitsFn = Callable[..., int]


def runtime_game_visits(
    level: str,
    move_count: int = -1,
    mode: str = "normal",
    *,
    cpu_mode_fn: CpuModeFn,
    compute_visits_fn: ComputeVisitsFn = compute_game_visits,
) -> int:
    return compute_visits_fn(
        level,
        move_count,
        mode,
        cpu_mode=cpu_mode_fn(),
    )
