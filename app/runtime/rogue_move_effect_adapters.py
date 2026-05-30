from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.rogue_move_effect_flow import (
    AiRogueResponseEffectDeps,
    PlayerRogueMoveEffectDeps,
    apply_ai_rogue_response_effects_event,
    apply_player_rogue_move_effects_event,
)


SendFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class PlayerRogueMoveEffectBinding:
    has_rogue: Callable[[Any, str], bool]
    erosion_shift: float
    sync_engine_komi: Callable[[Any], Awaitable[None]]
    apply_board_effects: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    gtp_to_coord: Callable[..., Any]
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    challenge_apply_trap_bonus: Callable[[Any, SendFn, str], Awaitable[None]]
    trigger_five_in_row: Callable[[Any, SendFn, str], Awaitable[Any]]
    trigger_last_stand: Callable[[Any, SendFn, str, tuple[int, int]], Awaitable[Any]]
    challenge_maybe_reduce_ai_level: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class AiRogueResponseEffectBinding:
    apply_board_effects: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    shuffle_points: Callable[..., Any]
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]


def build_player_rogue_move_effect_deps(
    binding: PlayerRogueMoveEffectBinding,
) -> PlayerRogueMoveEffectDeps:
    return PlayerRogueMoveEffectDeps(
        has_rogue=binding.has_rogue,
        erosion_shift=binding.erosion_shift,
        sync_engine_komi=binding.sync_engine_komi,
        apply_board_effects=binding.apply_board_effects,
        coord_to_gtp=binding.coord_to_gtp,
        gtp_to_coord=binding.gtp_to_coord,
        engine_ready=binding.engine_ready,
        sync_board_to_katago=binding.sync_board_to_katago,
        challenge_apply_trap_bonus=binding.challenge_apply_trap_bonus,
        trigger_five_in_row=binding.trigger_five_in_row,
        trigger_last_stand=binding.trigger_last_stand,
        challenge_maybe_reduce_ai_level=binding.challenge_maybe_reduce_ai_level,
    )


def build_ai_rogue_response_effect_deps(
    binding: AiRogueResponseEffectBinding,
) -> AiRogueResponseEffectDeps:
    return AiRogueResponseEffectDeps(
        apply_board_effects=binding.apply_board_effects,
        coord_to_gtp=binding.coord_to_gtp,
        shuffle_points=binding.shuffle_points,
        engine_ready=binding.engine_ready,
        sync_board_to_katago=binding.sync_board_to_katago,
    )


async def apply_player_rogue_move_effects(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    captured: int,
    binding: PlayerRogueMoveEffectBinding,
) -> None:
    await apply_player_rogue_move_effects_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        captured=captured,
        deps=build_player_rogue_move_effect_deps(binding),
    )


async def apply_ai_rogue_response_effects(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    binding: AiRogueResponseEffectBinding,
) -> None:
    await apply_ai_rogue_response_effects_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        deps=build_ai_rogue_response_effect_deps(binding),
    )
