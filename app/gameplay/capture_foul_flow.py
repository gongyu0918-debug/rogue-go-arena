from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.callback_types import SendFn
from app.gameplay.capture_foul import check_capture_foul


SyncKomiFn = Callable[[Any], Awaitable[None]]
SyncBoardFn = Callable[[Any], Awaitable[None]]
PickBestPointFn = Callable[[Any, str], Awaitable[tuple[int, int] | None]]
SpawnBonusFn = Callable[[Any, list[tuple[int, int]], str], list[tuple[int, int]]]
CoordFormatter = Callable[[int, int, int], str | None]
CheckCaptureFoulFn = Callable[..., Any]


async def check_capture_foul_event(
    game: Any,
    send_fn: SendFn,
    offender: str,
    captured: int,
    *,
    ultimate: bool,
    sync_komi: SyncKomiFn,
    sync_board: SyncBoardFn | None = None,
    pick_best_point: PickBestPointFn | None = None,
    spawn_bonus_points: SpawnBonusFn | None = None,
    coord_to_gtp: CoordFormatter | None = None,
    check_capture_foul_fn: CheckCaptureFoulFn = check_capture_foul,
) -> None:
    result = check_capture_foul_fn(game, offender, captured, ultimate=ultimate)
    if not result.triggered:
        return

    if result.beneficiary is not None:
        bonus = (
            await pick_best_point(game, result.beneficiary)
            if pick_best_point is not None
            else None
        )
        changed = (
            spawn_bonus_points(game, [bonus], result.beneficiary)
            if bonus and spawn_bonus_points is not None
            else []
        )
        if changed:
            bx, by = changed[0]
            point_label = (
                coord_to_gtp(bx, by, game.size)
                if coord_to_gtp is not None
                else f"({bx}, {by})"
            )
            await send_fn(
                {
                    "type": "rogue_event",
                    "msg": f"{result.message}，在我方推荐点 {point_label} 赠送 1 颗己棋",
                }
            )
            if sync_board is not None:
                await sync_board(game)
            return

        await send_fn(
            {
                "type": "rogue_event",
                "msg": f"{result.message}，但当前没有可用推荐点",
            }
        )
        return

    await send_fn(
        {
            "type": "rogue_event",
            "msg": result.message,
        }
    )
    if result.sync_komi:
        await sync_komi(game)
