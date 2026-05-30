from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ai_observer import (
    AiObserverLoopDeps,
    apply_observer_ai_move_to_board as apply_observer_ai_move_to_board_event,
    finish_observer_double_pass as finish_observer_double_pass_event,
    run_ai_observer_loop as run_ai_observer_loop_event,
)
from app.callback_types import EngineCommandFn, SendFn


@dataclass(frozen=True)
class ObserverDoublePassBinding:
    run_engine_command: EngineCommandFn


@dataclass(frozen=True)
class ObserverMovePlacementBinding:
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    place_auxiliary_move: Callable[[Any, str, str, tuple[int, int] | None], Any]


@dataclass(frozen=True)
class AiObserverLoopBinding:
    engine_ready: Callable[[], bool]
    sync_board: Callable[[Any], Awaitable[None]]
    get_game_visits: Callable[[str, int], int]
    generate_ai_style_move: Callable[[Any, str, int, float], Awaitable[str]]
    is_suspicious_ai_pass: Callable[[Any, str, str], bool]
    pick_nonpass_fallback_move: Callable[[Any, str, int], Awaitable[str | None]]
    place_ai_move_on_board: Callable[[Any, str, str], Any]
    finish_double_pass: Callable[[Any, SendFn], Awaitable[bool]]
    sleep: Callable[[float], Awaitable[None]]
    opening_move_threshold: int


def build_ai_observer_loop_deps(binding: AiObserverLoopBinding) -> AiObserverLoopDeps:
    return AiObserverLoopDeps(
        engine_ready=binding.engine_ready,
        sync_board=binding.sync_board,
        get_game_visits=binding.get_game_visits,
        generate_ai_style_move=binding.generate_ai_style_move,
        is_suspicious_ai_pass=binding.is_suspicious_ai_pass,
        pick_nonpass_fallback_move=binding.pick_nonpass_fallback_move,
        place_ai_move_on_board=binding.place_ai_move_on_board,
        finish_double_pass=binding.finish_double_pass,
        sleep=binding.sleep,
        opening_move_threshold=binding.opening_move_threshold,
    )


async def finish_observer_double_pass(
    game: Any,
    send_fn: SendFn,
    binding: ObserverDoublePassBinding,
) -> bool:
    return await finish_observer_double_pass_event(
        game,
        send_fn,
        run_engine_command=binding.run_engine_command,
    )


def apply_observer_ai_move_to_board(
    game: Any,
    color: str,
    gtp_move: str,
    binding: ObserverMovePlacementBinding,
) -> Any:
    return apply_observer_ai_move_to_board_event(
        game,
        color,
        gtp_move,
        gtp_to_coord=binding.gtp_to_coord,
        place_auxiliary_move=binding.place_auxiliary_move,
    )


async def run_ai_observer_loop(
    game: Any,
    send_fn: SendFn,
    binding: AiObserverLoopBinding,
) -> None:
    await run_ai_observer_loop_event(
        game,
        send_fn,
        build_ai_observer_loop_deps(binding),
    )
