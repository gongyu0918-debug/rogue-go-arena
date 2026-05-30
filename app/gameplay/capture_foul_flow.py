from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.gameplay.capture_foul import check_capture_foul


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
SyncKomiFn = Callable[[Any], Awaitable[None]]
CheckCaptureFoulFn = Callable[..., Any]


async def check_capture_foul_event(
    game: Any,
    send_fn: SendFn,
    offender: str,
    captured: int,
    *,
    ultimate: bool,
    sync_komi: SyncKomiFn,
    check_capture_foul_fn: CheckCaptureFoulFn = check_capture_foul,
) -> None:
    result = check_capture_foul_fn(game, offender, captured, ultimate=ultimate)
    if not result.triggered:
        return

    await send_fn(
        {
            "type": "rogue_event",
            "msg": result.message,
        }
    )
    await sync_komi(game)
