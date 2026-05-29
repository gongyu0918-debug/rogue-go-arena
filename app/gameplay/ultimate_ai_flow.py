from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


AsyncSend = Callable[[dict], Awaitable[None]]
CountStonesFn = Callable[[Any, int], int]
ApplyUltimateEffectFn = Callable[[Any, AsyncSend, int, int, str, str], Awaitable[bool]]
ResolvePendingShadowLinksFn = Callable[[Any, AsyncSend], Awaitable[bool]]
SyncBoardFn = Callable[[Any], Awaitable[None]]
CheckCaptureFoulFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class UltimateAiMoveChoice:
    gtp_move: str
    coord: tuple[int, int] | None


def opponent_color_value(color: str) -> int:
    return 1 if color == "W" else 2


async def choose_ultimate_ai_move(
    game: Any,
    *,
    color: str,
    visits: int,
    forbidden: set[tuple[int, int]],
    generate_move: Callable[[], Awaitable[str]],
    no_resign_move: Callable[[Any, str], Awaitable[str]],
    undo_engine_move: Callable[[], None],
    pick_ranked_legal_move: Callable[..., Awaitable[str | None]],
    pick_nonpass_fallback_move: Callable[..., Awaitable[str | None]],
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]],
    is_suspicious_ai_pass: Callable[[Any, str, str], bool],
    resolve_occupied_ai_move: Callable[..., tuple[str, tuple[int, int] | None]],
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None],
    coord_to_gtp: Callable[[int, int, int], str],
    log_fn: Callable[[str], None],
) -> UltimateAiMoveChoice:
    gtp_move = await generate_move()
    if gtp_move.upper() == "RESIGN":
        gtp_move = await no_resign_move(game, color)

    if forbidden and gtp_move.upper() not in ("PASS", "RESIGN"):
        coord = gtp_to_coord(gtp_move, game.size)
        if coord and coord in forbidden:
            undo_engine_move()
            ranked = await pick_ranked_legal_move(game, color, visits, forbidden, time_limit=1.2)
            gtp_move = ranked or "pass"

    if is_suspicious_ai_pass(game, gtp_move, color):
        fallback_move = await pick_nonpass_fallback_move(game, color, visits, forbidden)
        if fallback_move:
            log_fn(f"Suspicious early PASS in ultimate mode, replaced with {fallback_move}")
            gtp_move = fallback_move

    coord = gtp_to_coord(gtp_move, game.size)
    gtp_move, coord = resolve_occupied_ai_move(
        game,
        color,
        gtp_move,
        coord,
        coord_to_gtp=coord_to_gtp,
    )

    if gtp_move.upper() != "PASS" and coord and game.is_ko(coord[0], coord[1], color):
        gtp_move = await retry_avoiding_ko(game, color)
        coord = gtp_to_coord(gtp_move, game.size) if gtp_move.upper() not in ("PASS", "RESIGN") else None

    return UltimateAiMoveChoice(gtp_move=gtp_move, coord=coord)


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
