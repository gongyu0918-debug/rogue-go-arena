from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.forced_rogue_ai_turn_flow import (
    ForcedRogueAiTurnDeps,
    try_finish_forced_rogue_ai_turn_event,
)
from app.gameplay.restriction_rogue_ai_turn_flow import (
    RestrictionRogueAiTurnDeps,
    try_finish_restriction_rogue_ai_turn_event,
)
from app.gameplay.shadow_rogue_ai_turn_flow import (
    ShadowRogueAiTurnDeps,
    try_finish_shadow_rogue_ai_turn_event,
)
from app.gameplay.suboptimal_rogue_ai_turn_flow import (
    SuboptimalRogueAiTurnDeps,
    try_finish_suboptimal_rogue_ai_turn_event,
)
from app.callback_types import EngineCommandFn, SendFn


@dataclass(frozen=True)
class ForcedRogueAiTurnBinding:
    try_finish_forced_rogue_ai_move: Callable[..., Awaitable[bool]]
    roll_random: Callable[[], float]
    dice_pass_chance: float
    mirror_chance: float
    gtp_to_coord: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    mirror_coord: Callable[..., Any]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    finalize_forced_pass: Callable[..., Awaitable[None]]
    finalize_forced_stone: Callable[..., Awaitable[bool]]
    apply_puppet_move: Callable[..., Awaitable[bool]]
    finish_ai_move: Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class RestrictionRogueAiTurnBinding:
    try_finish_rogue_restriction_ai_move: Callable[..., Awaitable[bool]]
    choose_tengen_target: Callable[..., Any]
    tengen_followup_points: Callable[..., Any]
    gravity_allowed_points: Callable[..., Any]
    lowline_allowed_points: Callable[..., Any]
    sansan_opening_restriction: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    finalize_forced_stone: Callable[..., Awaitable[bool]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    choose_allowed_move: Callable[..., Awaitable[str | None]]
    choose_avoid_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]
    finish_allowed_restriction_move: Callable[..., Awaitable[bool]]
    finish_sansan_restriction_move: Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class ShadowRogueAiTurnBinding:
    try_finish_shadow_restriction_move: Callable[..., Awaitable[bool]]
    roll_random: Callable[[], float]
    choose_restriction: Callable[[Any, str, int], Any | None]
    choose_allowed_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class SuboptimalRogueAiTurnBinding:
    try_finish_suboptimal_rogue_move: Callable[..., Awaitable[bool]]
    roll_random: Callable[[], float]
    choose_suboptimal_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]


def build_forced_rogue_ai_turn_deps(binding: ForcedRogueAiTurnBinding) -> ForcedRogueAiTurnDeps:
    return ForcedRogueAiTurnDeps(
        try_finish_forced_rogue_ai_move=binding.try_finish_forced_rogue_ai_move,
        roll_random=binding.roll_random,
        dice_pass_chance=binding.dice_pass_chance,
        mirror_chance=binding.mirror_chance,
        gtp_to_coord=binding.gtp_to_coord,
        coord_to_gtp=binding.coord_to_gtp,
        mirror_coord=binding.mirror_coord,
        prepare_player_turn_modifiers=binding.prepare_player_turn_modifiers,
        finalize_forced_pass=binding.finalize_forced_pass,
        finalize_forced_stone=binding.finalize_forced_stone,
        apply_puppet_move=binding.apply_puppet_move,
        finish_ai_move=binding.finish_ai_move,
    )


def build_restriction_rogue_ai_turn_deps(
    binding: RestrictionRogueAiTurnBinding,
) -> RestrictionRogueAiTurnDeps:
    return RestrictionRogueAiTurnDeps(
        try_finish_rogue_restriction_ai_move=binding.try_finish_rogue_restriction_ai_move,
        choose_tengen_target=binding.choose_tengen_target,
        tengen_followup_points=binding.tengen_followup_points,
        gravity_allowed_points=binding.gravity_allowed_points,
        lowline_allowed_points=binding.lowline_allowed_points,
        sansan_opening_restriction=binding.sansan_opening_restriction,
        coord_to_gtp=binding.coord_to_gtp,
        finalize_forced_stone=binding.finalize_forced_stone,
        prepare_player_turn_modifiers=binding.prepare_player_turn_modifiers,
        choose_allowed_move=binding.choose_allowed_move,
        choose_avoid_move=binding.choose_avoid_move,
        finish_ai_move=binding.finish_ai_move,
        finish_allowed_restriction_move=binding.finish_allowed_restriction_move,
        finish_sansan_restriction_move=binding.finish_sansan_restriction_move,
    )


def build_shadow_rogue_ai_turn_deps(binding: ShadowRogueAiTurnBinding) -> ShadowRogueAiTurnDeps:
    return ShadowRogueAiTurnDeps(
        try_finish_shadow_restriction_move=binding.try_finish_shadow_restriction_move,
        roll_random=binding.roll_random,
        choose_restriction=binding.choose_restriction,
        choose_allowed_move=binding.choose_allowed_move,
        finish_ai_move=binding.finish_ai_move,
    )


def build_suboptimal_rogue_ai_turn_deps(binding: SuboptimalRogueAiTurnBinding) -> SuboptimalRogueAiTurnDeps:
    return SuboptimalRogueAiTurnDeps(
        try_finish_suboptimal_rogue_move=binding.try_finish_suboptimal_rogue_move,
        roll_random=binding.roll_random,
        choose_suboptimal_move=binding.choose_suboptimal_move,
        finish_ai_move=binding.finish_ai_move,
    )


async def try_finish_forced_rogue_ai_turn(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    run_engine_command: EngineCommandFn,
    binding: ForcedRogueAiTurnBinding,
) -> bool:
    return await try_finish_forced_rogue_ai_turn_event(
        game,
        send_fn,
        run_engine_command=run_engine_command,
        turn=turn,
        deps=build_forced_rogue_ai_turn_deps(binding),
    )


async def try_finish_restriction_rogue_ai_turn(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    run_engine_command: EngineCommandFn,
    binding: RestrictionRogueAiTurnBinding,
) -> bool:
    return await try_finish_restriction_rogue_ai_turn_event(
        game,
        send_fn,
        run_engine_command=run_engine_command,
        turn=turn,
        ai_plan=ai_plan,
        deps=build_restriction_rogue_ai_turn_deps(binding),
    )


async def try_finish_shadow_rogue_ai_turn(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    binding: ShadowRogueAiTurnBinding,
) -> bool:
    return await try_finish_shadow_rogue_ai_turn_event(
        game,
        send_fn,
        turn,
        ai_plan,
        build_shadow_rogue_ai_turn_deps(binding),
    )


async def try_finish_suboptimal_rogue_ai_turn(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    binding: SuboptimalRogueAiTurnBinding,
) -> bool:
    return await try_finish_suboptimal_rogue_ai_turn_event(
        game,
        send_fn,
        turn,
        ai_plan,
        build_suboptimal_rogue_ai_turn_deps(binding),
    )
