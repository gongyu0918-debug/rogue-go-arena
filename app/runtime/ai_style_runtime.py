from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn
from app.runtime.ai_style_adapters import AiStyleMoveBinding


@dataclass(frozen=True)
class AiStyleMoveRuntimeFns:
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    choose_or_generate_style_move: Callable[..., Awaitable[str]]
    analyze_position: Callable[..., Awaitable[Any]]
    choose_style_move: Callable[..., Any]
    generate_move: Callable[[str, int, float], Awaitable[str]]
    gtp_to_coord: Callable[..., Any]
    play_chosen_move: EngineCommandFn


@dataclass(frozen=True)
class AiStyleMoveDependencies:
    runtime: AiStyleMoveRuntimeFns


def build_ai_style_move_binding(
    dependencies: AiStyleMoveDependencies,
) -> AiStyleMoveBinding:
    return AiStyleMoveBinding(
        sync_board_to_katago=dependencies.runtime.sync_board_to_katago,
        choose_or_generate_style_move=dependencies.runtime.choose_or_generate_style_move,
        analyze_position=dependencies.runtime.analyze_position,
        choose_style_move=dependencies.runtime.choose_style_move,
        generate_move=dependencies.runtime.generate_move,
        gtp_to_coord=dependencies.runtime.gtp_to_coord,
        play_chosen_move=dependencies.runtime.play_chosen_move,
    )
