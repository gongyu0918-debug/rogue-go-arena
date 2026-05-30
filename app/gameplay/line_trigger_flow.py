from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
SyncBoardFn = Callable[[Any], Awaitable[None]]
EstimateWinrateFn = Callable[[Any, str], Awaitable[float]]
ApplyRogueFiveFn = Callable[..., Any]
ApplyRogueLastFn = Callable[..., Any]
ApplyUltimateTriggerFn = Callable[..., Any]


@dataclass(frozen=True)
class RogueFiveInRowDeps:
    apply_five_in_row: ApplyRogueFiveFn
    shuffle_points: Callable[[list], None]
    should_bonus_derivative: Callable[[Any], bool]
    support_stones: int
    engine_ready: Callable[[], bool]
    sync_board: SyncBoardFn


@dataclass(frozen=True)
class RogueLastStandDeps:
    apply_last_stand: ApplyRogueLastFn
    estimate_side_winrate: EstimateWinrateFn
    make_rng: Callable[[], Any]
    get_forbidden_points: Callable[[Any, str], set[tuple[int, int]]]
    clear_count: int
    spawn_count: int
    threshold: float
    engine_ready: Callable[[], bool]
    sync_board: SyncBoardFn


@dataclass(frozen=True)
class UltimateLastStandDeps:
    apply_last_stand: ApplyUltimateTriggerFn
    estimate_side_winrate: EstimateWinrateFn
    make_rng: Callable[[], Any]
    threshold: float


@dataclass(frozen=True)
class UltimateFiveInRowDeps:
    apply_five_in_row: ApplyUltimateTriggerFn
    make_rng: Callable[[], Any]


async def _send_rogue_events(send_fn: SendFn, messages: list[str]) -> None:
    for message in messages:
        await send_fn({"type": "rogue_event", "msg": message})


async def trigger_rogue_five_in_row(
    game: Any,
    send_fn: SendFn,
    color: str,
    deps: RogueFiveInRowDeps,
) -> None:
    result = deps.apply_five_in_row(
        game,
        color,
        shuffle_points=deps.shuffle_points,
        should_bonus_derivative_fn=deps.should_bonus_derivative,
        support_stones=deps.support_stones,
    )
    if result.modified and deps.engine_ready():
        await deps.sync_board(game)
    await _send_rogue_events(send_fn, result.messages)


async def trigger_rogue_last_stand(
    game: Any,
    send_fn: SendFn,
    color: str,
    center: tuple[int, int],
    deps: RogueLastStandDeps,
) -> None:
    if game.rogue_last_stand_done.get(color):
        return
    if await deps.estimate_side_winrate(game, color) >= deps.threshold:
        return

    result = deps.apply_last_stand(
        game,
        color,
        center,
        rng=deps.make_rng(),
        forbidden_points=deps.get_forbidden_points(game, color),
        clear_count=deps.clear_count,
        spawn_count=deps.spawn_count,
    )
    if result.modified and deps.engine_ready():
        await deps.sync_board(game)
    await _send_rogue_events(send_fn, result.messages)


async def trigger_ultimate_last_stand(
    game: Any,
    send_fn: SendFn,
    color: str,
    deps: UltimateLastStandDeps,
) -> bool:
    if game.ultimate_last_stand_done.get(color):
        return False
    if await deps.estimate_side_winrate(game, color) >= deps.threshold:
        return False

    result = deps.apply_last_stand(
        game,
        color,
        rng=deps.make_rng(),
    )
    await _send_rogue_events(send_fn, result.messages)
    return result.modified


async def trigger_ultimate_five_in_row(
    game: Any,
    send_fn: SendFn,
    color: str,
    deps: UltimateFiveInRowDeps,
) -> bool:
    result = deps.apply_five_in_row(
        game,
        color,
        rng=deps.make_rng(),
    )
    await _send_rogue_events(send_fn, result.messages)
    return result.modified
