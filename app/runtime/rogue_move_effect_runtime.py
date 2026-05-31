from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn
from app.runtime.rogue_move_effect_adapters import (
    AiRogueResponseEffectBinding,
    PlayerRogueMoveEffectBinding,
)


@dataclass(frozen=True)
class RogueMoveEffectFns:
    has_rogue: Callable[[Any, str], bool]
    apply_player_board_effects: Callable[..., Any]
    apply_ai_response_board_effects: Callable[..., Any]


@dataclass(frozen=True)
class RogueMoveEffectRuntimeFns:
    sync_engine_komi: Callable[[Any], Awaitable[None]]
    coord_to_gtp: Callable[..., Any]
    gtp_to_coord: Callable[..., Any]
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    challenge_apply_trap_bonus: Callable[[Any, SendFn, str], Awaitable[None]]
    trigger_five_in_row: Callable[[Any, SendFn, str], Awaitable[Any]]
    trigger_last_stand: Callable[[Any, SendFn, str, tuple[int, int]], Awaitable[Any]]
    challenge_maybe_reduce_ai_level: Callable[[Any, SendFn], Awaitable[None]]
    shuffle_points: Callable[..., Any]


@dataclass(frozen=True)
class RogueMoveEffectTuning:
    erosion_shift: float


@dataclass(frozen=True)
class RogueMoveEffectDependencies:
    effects: RogueMoveEffectFns
    runtime: RogueMoveEffectRuntimeFns
    tuning: RogueMoveEffectTuning


def build_player_rogue_move_effect_binding(
    dependencies: RogueMoveEffectDependencies,
) -> PlayerRogueMoveEffectBinding:
    return PlayerRogueMoveEffectBinding(
        has_rogue=dependencies.effects.has_rogue,
        erosion_shift=dependencies.tuning.erosion_shift,
        sync_engine_komi=dependencies.runtime.sync_engine_komi,
        apply_board_effects=dependencies.effects.apply_player_board_effects,
        coord_to_gtp=dependencies.runtime.coord_to_gtp,
        gtp_to_coord=dependencies.runtime.gtp_to_coord,
        engine_ready=dependencies.runtime.engine_ready,
        sync_board_to_katago=dependencies.runtime.sync_board_to_katago,
        challenge_apply_trap_bonus=dependencies.runtime.challenge_apply_trap_bonus,
        trigger_five_in_row=dependencies.runtime.trigger_five_in_row,
        trigger_last_stand=dependencies.runtime.trigger_last_stand,
        challenge_maybe_reduce_ai_level=dependencies.runtime.challenge_maybe_reduce_ai_level,
    )


def build_ai_rogue_response_effect_binding(
    dependencies: RogueMoveEffectDependencies,
) -> AiRogueResponseEffectBinding:
    return AiRogueResponseEffectBinding(
        apply_board_effects=dependencies.effects.apply_ai_response_board_effects,
        coord_to_gtp=dependencies.runtime.coord_to_gtp,
        shuffle_points=dependencies.runtime.shuffle_points,
        engine_ready=dependencies.runtime.engine_ready,
        sync_board_to_katago=dependencies.runtime.sync_board_to_katago,
    )
