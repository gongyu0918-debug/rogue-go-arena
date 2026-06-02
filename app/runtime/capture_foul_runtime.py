from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.runtime.capture_foul_adapters import CaptureFoulBinding


@dataclass(frozen=True)
class CaptureFoulRuntimeFns:
    sync_komi: Callable[[Any], Awaitable[None]]
    sync_board: Callable[[Any], Awaitable[None]] | None = None
    pick_best_point: Callable[[Any, str], Awaitable[tuple[int, int] | None]] | None = None
    spawn_bonus_points: Callable[[Any, list[tuple[int, int]], str], list[tuple[int, int]]] | None = None
    coord_to_gtp: Callable[[int, int, int], str | None] | None = None


@dataclass(frozen=True)
class CaptureFoulDependencies:
    runtime: CaptureFoulRuntimeFns


def build_capture_foul_binding(
    dependencies: CaptureFoulDependencies,
) -> CaptureFoulBinding:
    return CaptureFoulBinding(
        sync_komi=dependencies.runtime.sync_komi,
        sync_board=dependencies.runtime.sync_board,
        pick_best_point=dependencies.runtime.pick_best_point,
        spawn_bonus_points=dependencies.runtime.spawn_bonus_points,
        coord_to_gtp=dependencies.runtime.coord_to_gtp,
    )
