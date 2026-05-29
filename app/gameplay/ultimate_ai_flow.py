from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


AsyncSend = Callable[[dict], Awaitable[None]]
CountStonesFn = Callable[[Any, int], int]
ApplyUltimateEffectFn = Callable[[Any, AsyncSend, int, int, str, str], Awaitable[bool]]
ResolvePendingShadowLinksFn = Callable[[Any, AsyncSend], Awaitable[bool]]
SyncBoardFn = Callable[[Any], Awaitable[None]]
CheckCaptureFoulFn = Callable[..., Awaitable[None]]


def opponent_color_value(color: str) -> int:
    return 1 if color == "W" else 2


async def apply_ultimate_ai_post_move_effects(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    ai_card: str | None,
    gtp_move: str,
    coord: tuple[int, int] | None,
    count_stones: CountStonesFn,
    apply_ultimate_effect: ApplyUltimateEffectFn,
    resolve_pending_ultimate_shadow_links: ResolvePendingShadowLinksFn,
    sync_board_to_katago: SyncBoardFn,
    check_capture_foul: CheckCaptureFoulFn,
) -> bool:
    opponent_value = opponent_color_value(color)
    opponent_before = count_stones(game, opponent_value)

    board_modified = False
    if ai_card and coord is not None and gtp_move.upper() != "PASS":
        board_modified = await apply_ultimate_effect(
            game,
            send_fn,
            coord[0],
            coord[1],
            color,
            ai_card,
        )

    pending_modified = await resolve_pending_ultimate_shadow_links(game, send_fn)
    if not (board_modified or pending_modified):
        return False

    await sync_board_to_katago(game)
    effect_removed = max(0, opponent_before - count_stones(game, opponent_value))
    if effect_removed > 0:
        await check_capture_foul(game, send_fn, color, effect_removed, ultimate=True)
    return True
