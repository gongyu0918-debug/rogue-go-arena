from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ai_style_move_flow import (
    AiStyleMoveDeps,
    generate_ai_style_move_event,
)
from app.callback_types import EngineCommandFn


@dataclass(frozen=True)
class AiStyleMoveBinding:
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    choose_or_generate_style_move: Callable[..., Awaitable[str]]
    analyze_position: Callable[..., Awaitable[Any]]
    choose_style_move: Callable[..., Any]
    generate_move: Callable[[str, int, float], Awaitable[str]]
    gtp_to_coord: Callable[..., Any]
    play_chosen_move: EngineCommandFn


def build_ai_style_move_deps(binding: AiStyleMoveBinding) -> AiStyleMoveDeps:
    return AiStyleMoveDeps(
        sync_board_to_katago=binding.sync_board_to_katago,
        choose_or_generate_style_move=binding.choose_or_generate_style_move,
        analyze_position=binding.analyze_position,
        choose_style_move=binding.choose_style_move,
        generate_move=binding.generate_move,
        gtp_to_coord=binding.gtp_to_coord,
        play_chosen_move=binding.play_chosen_move,
    )


async def generate_ai_style_move(
    game: Any,
    *,
    color: str,
    visits: int,
    time_limit: float,
    binding: AiStyleMoveBinding,
) -> str:
    return await generate_ai_style_move_event(
        game,
        color=color,
        visits=visits,
        time_limit=time_limit,
        deps=build_ai_style_move_deps(binding),
    )
