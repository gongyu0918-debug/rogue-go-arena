from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.runtime.rogue_ai_turn_adapters import (
    ForcedRogueAiTurnBinding,
    RestrictionRogueAiTurnBinding,
    ShadowRogueAiTurnBinding,
    SuboptimalRogueAiTurnBinding,
)


@dataclass(frozen=True)
class RogueAiTurnSharedFns:
    roll_random: Callable[[], float]
    gtp_to_coord: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    finish_ai_move: Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class ForcedRogueAiTurnFns:
    try_finish_forced_rogue_ai_move: Callable[..., Awaitable[bool]]
    mirror_coord: Callable[..., Any]
    finalize_forced_pass: Callable[..., Awaitable[None]]
    finalize_forced_stone: Callable[..., Awaitable[bool]]
    apply_puppet_move: Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class RestrictionRogueAiTurnFns:
    try_finish_rogue_restriction_ai_move: Callable[..., Awaitable[bool]]
    choose_tengen_target: Callable[..., Any]
    tengen_followup_points: Callable[..., Any]
    gravity_allowed_points: Callable[..., Any]
    lowline_allowed_points: Callable[..., Any]
    sansan_opening_restriction: Callable[..., Any]
    choose_allowed_move: Callable[..., Awaitable[str | None]]
    choose_avoid_move: Callable[..., Awaitable[str | None]]
    finish_allowed_restriction_move: Callable[..., Awaitable[bool]]
    finish_sansan_restriction_move: Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class ShadowRogueAiTurnFns:
    try_finish_shadow_restriction_move: Callable[..., Awaitable[bool]]
    choose_restriction: Callable[[Any, str, int], Any | None]
    choose_allowed_move: Callable[..., Awaitable[str | None]]


@dataclass(frozen=True)
class SuboptimalRogueAiTurnFns:
    try_finish_suboptimal_rogue_move: Callable[..., Awaitable[bool]]
    choose_suboptimal_move: Callable[..., Awaitable[str | None]]


@dataclass(frozen=True)
class RogueAiTurnTuning:
    dice_pass_chance: float
    mirror_chance: float


@dataclass(frozen=True)
class RogueAiTurnDependencies:
    shared: RogueAiTurnSharedFns
    forced: ForcedRogueAiTurnFns
    restriction: RestrictionRogueAiTurnFns
    shadow: ShadowRogueAiTurnFns
    suboptimal: SuboptimalRogueAiTurnFns
    tuning: RogueAiTurnTuning


def build_forced_rogue_ai_turn_binding(
    dependencies: RogueAiTurnDependencies,
) -> ForcedRogueAiTurnBinding:
    return ForcedRogueAiTurnBinding(
        try_finish_forced_rogue_ai_move=dependencies.forced.try_finish_forced_rogue_ai_move,
        roll_random=dependencies.shared.roll_random,
        dice_pass_chance=dependencies.tuning.dice_pass_chance,
        mirror_chance=dependencies.tuning.mirror_chance,
        gtp_to_coord=dependencies.shared.gtp_to_coord,
        coord_to_gtp=dependencies.shared.coord_to_gtp,
        mirror_coord=dependencies.forced.mirror_coord,
        prepare_player_turn_modifiers=dependencies.shared.prepare_player_turn_modifiers,
        finalize_forced_pass=dependencies.forced.finalize_forced_pass,
        finalize_forced_stone=dependencies.forced.finalize_forced_stone,
        apply_puppet_move=dependencies.forced.apply_puppet_move,
        finish_ai_move=dependencies.shared.finish_ai_move,
    )


def build_restriction_rogue_ai_turn_binding(
    dependencies: RogueAiTurnDependencies,
) -> RestrictionRogueAiTurnBinding:
    return RestrictionRogueAiTurnBinding(
        try_finish_rogue_restriction_ai_move=dependencies.restriction.try_finish_rogue_restriction_ai_move,
        choose_tengen_target=dependencies.restriction.choose_tengen_target,
        tengen_followup_points=dependencies.restriction.tengen_followup_points,
        gravity_allowed_points=dependencies.restriction.gravity_allowed_points,
        lowline_allowed_points=dependencies.restriction.lowline_allowed_points,
        sansan_opening_restriction=dependencies.restriction.sansan_opening_restriction,
        coord_to_gtp=dependencies.shared.coord_to_gtp,
        finalize_forced_stone=dependencies.forced.finalize_forced_stone,
        prepare_player_turn_modifiers=dependencies.shared.prepare_player_turn_modifiers,
        choose_allowed_move=dependencies.restriction.choose_allowed_move,
        choose_avoid_move=dependencies.restriction.choose_avoid_move,
        finish_ai_move=dependencies.shared.finish_ai_move,
        finish_allowed_restriction_move=dependencies.restriction.finish_allowed_restriction_move,
        finish_sansan_restriction_move=dependencies.restriction.finish_sansan_restriction_move,
    )


def build_shadow_rogue_ai_turn_binding(
    dependencies: RogueAiTurnDependencies,
) -> ShadowRogueAiTurnBinding:
    return ShadowRogueAiTurnBinding(
        try_finish_shadow_restriction_move=dependencies.shadow.try_finish_shadow_restriction_move,
        roll_random=dependencies.shared.roll_random,
        choose_restriction=dependencies.shadow.choose_restriction,
        choose_allowed_move=dependencies.shadow.choose_allowed_move,
        finish_ai_move=dependencies.shared.finish_ai_move,
    )


def build_suboptimal_rogue_ai_turn_binding(
    dependencies: RogueAiTurnDependencies,
) -> SuboptimalRogueAiTurnBinding:
    return SuboptimalRogueAiTurnBinding(
        try_finish_suboptimal_rogue_move=dependencies.suboptimal.try_finish_suboptimal_rogue_move,
        roll_random=dependencies.shared.roll_random,
        choose_suboptimal_move=dependencies.suboptimal.choose_suboptimal_move,
        finish_ai_move=dependencies.shared.finish_ai_move,
    )
