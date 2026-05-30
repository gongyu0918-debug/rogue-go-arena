from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.line_trigger_flow import (
    RogueFiveInRowDeps,
    RogueLastStandDeps,
    UltimateFiveInRowDeps,
    UltimateLastStandDeps,
    trigger_rogue_five_in_row as trigger_rogue_five_in_row_event,
    trigger_rogue_last_stand as trigger_rogue_last_stand_event,
    trigger_ultimate_five_in_row as trigger_ultimate_five_in_row_event,
    trigger_ultimate_last_stand as trigger_ultimate_last_stand_event,
)


SendFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class RogueFiveInRowBinding:
    apply_five_in_row: Callable[..., Any]
    shuffle_points: Callable[[list], None]
    should_bonus_derivative: Callable[[Any], bool]
    support_stones: int
    engine_ready: Callable[[], bool]
    sync_board: Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class RogueLastStandBinding:
    apply_last_stand: Callable[..., Any]
    estimate_side_winrate: Callable[[Any, str], Awaitable[float]]
    make_rng: Callable[[], Any]
    get_forbidden_points: Callable[[Any, str], set[tuple[int, int]]]
    clear_count: int
    spawn_count: int
    threshold: float
    engine_ready: Callable[[], bool]
    sync_board: Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class UltimateLastStandBinding:
    apply_last_stand: Callable[..., Any]
    estimate_side_winrate: Callable[[Any, str], Awaitable[float]]
    make_rng: Callable[[], Any]
    threshold: float


@dataclass(frozen=True)
class UltimateFiveInRowBinding:
    apply_five_in_row: Callable[..., Any]
    make_rng: Callable[[], Any]


def build_rogue_five_in_row_deps(binding: RogueFiveInRowBinding) -> RogueFiveInRowDeps:
    return RogueFiveInRowDeps(
        apply_five_in_row=binding.apply_five_in_row,
        shuffle_points=binding.shuffle_points,
        should_bonus_derivative=binding.should_bonus_derivative,
        support_stones=binding.support_stones,
        engine_ready=binding.engine_ready,
        sync_board=binding.sync_board,
    )


def build_rogue_last_stand_deps(binding: RogueLastStandBinding) -> RogueLastStandDeps:
    return RogueLastStandDeps(
        apply_last_stand=binding.apply_last_stand,
        estimate_side_winrate=binding.estimate_side_winrate,
        make_rng=binding.make_rng,
        get_forbidden_points=binding.get_forbidden_points,
        clear_count=binding.clear_count,
        spawn_count=binding.spawn_count,
        threshold=binding.threshold,
        engine_ready=binding.engine_ready,
        sync_board=binding.sync_board,
    )


def build_ultimate_last_stand_deps(binding: UltimateLastStandBinding) -> UltimateLastStandDeps:
    return UltimateLastStandDeps(
        apply_last_stand=binding.apply_last_stand,
        estimate_side_winrate=binding.estimate_side_winrate,
        make_rng=binding.make_rng,
        threshold=binding.threshold,
    )


def build_ultimate_five_in_row_deps(binding: UltimateFiveInRowBinding) -> UltimateFiveInRowDeps:
    return UltimateFiveInRowDeps(
        apply_five_in_row=binding.apply_five_in_row,
        make_rng=binding.make_rng,
    )


async def trigger_rogue_five_in_row(
    game: Any,
    send_fn: SendFn,
    color: str,
    binding: RogueFiveInRowBinding,
) -> None:
    await trigger_rogue_five_in_row_event(
        game,
        send_fn,
        color,
        build_rogue_five_in_row_deps(binding),
    )


async def trigger_rogue_last_stand(
    game: Any,
    send_fn: SendFn,
    color: str,
    center: tuple[int, int],
    binding: RogueLastStandBinding,
) -> None:
    await trigger_rogue_last_stand_event(
        game,
        send_fn,
        color,
        center,
        build_rogue_last_stand_deps(binding),
    )


async def trigger_ultimate_last_stand(
    game: Any,
    send_fn: SendFn,
    color: str,
    binding: UltimateLastStandBinding,
) -> bool:
    return await trigger_ultimate_last_stand_event(
        game,
        send_fn,
        color,
        build_ultimate_last_stand_deps(binding),
    )


async def trigger_ultimate_five_in_row(
    game: Any,
    send_fn: SendFn,
    color: str,
    binding: UltimateFiveInRowBinding,
) -> bool:
    return await trigger_ultimate_five_in_row_event(
        game,
        send_fn,
        color,
        build_ultimate_five_in_row_deps(binding),
    )
