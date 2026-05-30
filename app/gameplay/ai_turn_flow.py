from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn

EngineReadyFn = Callable[[], bool]
SyncBoardFn = Callable[[Any], Awaitable[None]]
SnapshotTurnFn = Callable[[Any], Any]
PlanSearchFn = Callable[[Any, Any], Any]
RefreshFogFn = Callable[[Any, SendFn, Any, Any], Awaitable[None]]
TryFinishFn = Callable[[Any, SendFn, Any], Awaitable[bool]]
TryFinishWithPlanFn = Callable[[Any, SendFn, Any, Any], Awaitable[bool]]


@dataclass(frozen=True)
class AiTurnFlowDeps:
    engine_ready: EngineReadyFn
    sync_board_to_katago: SyncBoardFn
    snapshot_turn: SnapshotTurnFn
    try_finish_forced: TryFinishFn
    plan_search: PlanSearchFn
    refresh_fog_restriction: RefreshFogFn
    try_finish_restriction: TryFinishWithPlanFn
    try_finish_shadow: TryFinishWithPlanFn
    try_finish_suboptimal: TryFinishWithPlanFn
    try_finish_generated: TryFinishWithPlanFn


async def run_ai_turn(
    game: Any,
    send_fn: SendFn,
    deps: AiTurnFlowDeps,
) -> None:
    if game.game_over or not deps.engine_ready():
        return

    await deps.sync_board_to_katago(game)

    turn = deps.snapshot_turn(game)
    if await deps.try_finish_forced(game, send_fn, turn):
        return

    ai_plan = deps.plan_search(game, turn)
    await deps.refresh_fog_restriction(game, send_fn, turn, ai_plan)

    if await deps.try_finish_restriction(game, send_fn, turn, ai_plan):
        return

    if await deps.try_finish_shadow(game, send_fn, turn, ai_plan):
        return

    if await deps.try_finish_suboptimal(game, send_fn, turn, ai_plan):
        return

    await deps.try_finish_generated(game, send_fn, turn, ai_plan)
