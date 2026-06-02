from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.capture_foul import check_capture_foul
from app.gameplay.capture_foul_flow import check_capture_foul_event
from app.callback_types import SendFn


@dataclass(frozen=True)
class CaptureFoulBinding:
    sync_komi: Callable[[Any], Awaitable[None]]
    sync_board: Callable[[Any], Awaitable[None]] | None = None
    pick_best_point: Callable[[Any, str], Awaitable[tuple[int, int] | None]] | None = None
    spawn_bonus_points: Callable[[Any, list[tuple[int, int]], str], list[tuple[int, int]]] | None = None
    coord_to_gtp: Callable[[int, int, int], str | None] | None = None
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
        sync_board=binding.sync_board,
        pick_best_point=binding.pick_best_point,
        spawn_bonus_points=binding.spawn_bonus_points,
        coord_to_gtp=binding.coord_to_gtp,
        check_capture_foul_fn=binding.check_capture_foul,
    )
