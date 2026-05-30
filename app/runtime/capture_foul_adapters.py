from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.capture_foul import check_capture_foul
from app.gameplay.capture_foul_flow import check_capture_foul_event


SendFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class CaptureFoulBinding:
    sync_komi: Callable[[Any], Awaitable[None]]
    check_capture_foul: Callable[..., Any] = check_capture_foul


async def check_capture_foul_violation(
    game: Any,
    send_fn: SendFn,
    offender: str,
    captured: int,
    *,
    ultimate: bool,
    binding: CaptureFoulBinding,
) -> None:
    await check_capture_foul_event(
        game,
        send_fn,
        offender,
        captured,
        ultimate=ultimate,
        sync_komi=binding.sync_komi,
        check_capture_foul_fn=binding.check_capture_foul,
    )
