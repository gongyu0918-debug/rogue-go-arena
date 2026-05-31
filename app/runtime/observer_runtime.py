from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn, SendFn
from app.runtime.observer_adapters import (
    AiObserverLoopBinding,
    ObserverDoublePassBinding,
    ObserverMovePlacementBinding,
)


@dataclass(frozen=True)
class ObserverRuntimeFns:
    engine_ready: Callable[[], bool]
    sync_board: Callable[[Any], Awaitable[None]]
    run_engine_command: EngineCommandFn
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    sleep: Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class ObserverMoveFns:
    get_game_visits: Callable[[str, int], int]
    generate_ai_style_move: Callable[[Any, str, int, float], Awaitable[str]]
    is_suspicious_ai_pass: Callable[[Any, str, str], bool]
    pick_nonpass_fallback_move: Callable[[Any, str, int], Awaitable[str | None]]
    place_auxiliary_move: Callable[[Any, str, str, tuple[int, int] | None], Any]
    place_ai_move_on_board: Callable[[Any, str, str], Any]
    finish_double_pass: Callable[[Any, SendFn], Awaitable[bool]]


@dataclass(frozen=True)
class ObserverTuning:
    opening_move_threshold: int


@dataclass(frozen=True)
class ObserverDependencies:
    runtime: ObserverRuntimeFns
    moves: ObserverMoveFns
    tuning: ObserverTuning


def build_observer_double_pass_binding(
    dependencies: ObserverDependencies,
) -> ObserverDoublePassBinding:
    return ObserverDoublePassBinding(
        run_engine_command=dependencies.runtime.run_engine_command,
    )


def build_observer_move_placement_binding(
    dependencies: ObserverDependencies,
) -> ObserverMovePlacementBinding:
    return ObserverMovePlacementBinding(
        gtp_to_coord=dependencies.runtime.gtp_to_coord,
        place_auxiliary_move=dependencies.moves.place_auxiliary_move,
    )


def build_ai_observer_loop_binding(
    dependencies: ObserverDependencies,
) -> AiObserverLoopBinding:
    return AiObserverLoopBinding(
        engine_ready=dependencies.runtime.engine_ready,
        sync_board=dependencies.runtime.sync_board,
        get_game_visits=dependencies.moves.get_game_visits,
        generate_ai_style_move=dependencies.moves.generate_ai_style_move,
        is_suspicious_ai_pass=dependencies.moves.is_suspicious_ai_pass,
        pick_nonpass_fallback_move=dependencies.moves.pick_nonpass_fallback_move,
        place_ai_move_on_board=dependencies.moves.place_ai_move_on_board,
        finish_double_pass=dependencies.moves.finish_double_pass,
        sleep=dependencies.runtime.sleep,
        opening_move_threshold=dependencies.tuning.opening_move_threshold,
    )
