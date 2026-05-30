from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


EngineCommandFn = Callable[[str], Awaitable[str]]
GenerateMoveFn = Callable[[str, int, float], Awaitable[str]]


@dataclass(frozen=True)
class AiStyleMoveDeps:
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    choose_or_generate_style_move: Callable[..., Awaitable[str]]
    analyze_position: Callable[..., Awaitable[Any]]
    choose_style_move: Callable[..., Any]
    generate_move: GenerateMoveFn
    gtp_to_coord: Callable[..., Any]
    play_chosen_move: EngineCommandFn


def resolve_ai_style_for_color(game: Any, color: str) -> str:
    if not game.ai_observer:
        return game.ai_style
    return game.ai_style_black if color == "B" else game.ai_style_white


async def generate_ai_style_move_event(
    game: Any,
    *,
    color: str,
    visits: int,
    time_limit: float,
    deps: AiStyleMoveDeps,
) -> str:
    await deps.sync_board_to_katago(game)
    return await deps.choose_or_generate_style_move(
        game,
        color=color,
        visits=visits,
        time_limit=time_limit,
        style=resolve_ai_style_for_color(game, color),
        analyze_position=deps.analyze_position,
        choose_style_move=deps.choose_style_move,
        generate_move=deps.generate_move,
        gtp_to_coord=deps.gtp_to_coord,
        play_chosen_move=deps.play_chosen_move,
    )
