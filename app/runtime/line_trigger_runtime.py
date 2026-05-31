from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.runtime.line_trigger_adapters import (
    RogueFiveInRowBinding,
    RogueLastStandBinding,
    UltimateFiveInRowBinding,
    UltimateLastStandBinding,
)


@dataclass(frozen=True)
class LineTriggerEffectFns:
    apply_rogue_five_in_row: Callable[..., Any]
    apply_rogue_last_stand: Callable[..., Any]
    apply_ultimate_last_stand: Callable[..., Any]
    apply_ultimate_five_in_row: Callable[..., Any]


@dataclass(frozen=True)
class LineTriggerRuntimeFns:
    shuffle_points: Callable[[list], None]
    should_bonus_derivative: Callable[[Any], bool]
    engine_ready: Callable[[], bool]
    sync_board: Callable[[Any], Awaitable[None]]
    estimate_side_winrate: Callable[[Any, str], Awaitable[float]]
    make_rng: Callable[[], Any]
    get_forbidden_points: Callable[[Any, str], set[tuple[int, int]]]


@dataclass(frozen=True)
class LineTriggerTuning:
    rogue_five_in_row_support_stones: int
    rogue_last_stand_clear_count: int
    rogue_last_stand_spawn_count: int
    rogue_last_stand_threshold: float
    ultimate_last_stand_threshold: float


@dataclass(frozen=True)
class LineTriggerDependencies:
    effects: LineTriggerEffectFns
    runtime: LineTriggerRuntimeFns
    tuning: LineTriggerTuning


def build_rogue_five_in_row_binding(
    dependencies: LineTriggerDependencies,
) -> RogueFiveInRowBinding:
    return RogueFiveInRowBinding(
        apply_five_in_row=dependencies.effects.apply_rogue_five_in_row,
        shuffle_points=dependencies.runtime.shuffle_points,
        should_bonus_derivative=dependencies.runtime.should_bonus_derivative,
        support_stones=dependencies.tuning.rogue_five_in_row_support_stones,
        engine_ready=dependencies.runtime.engine_ready,
        sync_board=dependencies.runtime.sync_board,
    )


def build_rogue_last_stand_binding(
    dependencies: LineTriggerDependencies,
) -> RogueLastStandBinding:
    return RogueLastStandBinding(
        apply_last_stand=dependencies.effects.apply_rogue_last_stand,
        estimate_side_winrate=dependencies.runtime.estimate_side_winrate,
        make_rng=dependencies.runtime.make_rng,
        get_forbidden_points=dependencies.runtime.get_forbidden_points,
        clear_count=dependencies.tuning.rogue_last_stand_clear_count,
        spawn_count=dependencies.tuning.rogue_last_stand_spawn_count,
        threshold=dependencies.tuning.rogue_last_stand_threshold,
        engine_ready=dependencies.runtime.engine_ready,
        sync_board=dependencies.runtime.sync_board,
    )


def build_ultimate_last_stand_binding(
    dependencies: LineTriggerDependencies,
) -> UltimateLastStandBinding:
    return UltimateLastStandBinding(
        apply_last_stand=dependencies.effects.apply_ultimate_last_stand,
        estimate_side_winrate=dependencies.runtime.estimate_side_winrate,
        make_rng=dependencies.runtime.make_rng,
        threshold=dependencies.tuning.ultimate_last_stand_threshold,
    )


def build_ultimate_five_in_row_binding(
    dependencies: LineTriggerDependencies,
) -> UltimateFiveInRowBinding:
    return UltimateFiveInRowBinding(
        apply_five_in_row=dependencies.effects.apply_ultimate_five_in_row,
        make_rng=dependencies.runtime.make_rng,
    )
