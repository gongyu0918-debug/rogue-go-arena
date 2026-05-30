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
ApplyUltimateAiMoveResultFn = Callable[..., int]
ChooseUltimateAiBonusTurnFn = Callable[..., Any]
RunUltimateAiBonusTurnFn = Callable[[Any, AsyncSend, str, Any], Awaitable[bool]]
FinishUltimateAiNormalTurnFn = Callable[..., None]
ForceScoreFn = Callable[[Any, AsyncSend], Awaitable[None]]
StartUltimateAiBonusTurnFn = Callable[[Any, str], None]
RunNextUltimateAiMoveFn = Callable[[Any, AsyncSend, bool], Awaitable[None]]


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


async def run_ultimate_ai_bonus_turn(
    game: Any,
    send_fn: AsyncSend,
    color: str,
    bonus_turn: Any,
    *,
    start_bonus_turn: StartUltimateAiBonusTurnFn,
    run_next_ai_move: RunNextUltimateAiMoveFn,
) -> bool:
    start_bonus_turn(game, color)
    await send_fn({"type": "rogue_event", "msg": bonus_turn.message})
    await send_fn({"type": "game_state", **game.to_state()})
    if game.ultimate_move_count < 20:
        await run_next_ai_move(game, send_fn, bonus_turn.next_allow_double_bonus)
        return True
    return False


async def finish_ultimate_ai_turn(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    ai_card: str | None,
    gtp_move: str,
    coord: tuple[int, int] | None,
    allow_double_bonus: bool,
    chain_chance: float,
    chain_random: Callable[[], float],
    apply_ai_move_result: ApplyUltimateAiMoveResultFn,
    record_ultimate_turn: Callable[[Any], None],
    check_capture_foul: CheckCaptureFoulFn,
    post_move_effects: Callable[..., Awaitable[bool]],
    count_stones: CountStonesFn,
    apply_ultimate_effect: ApplyUltimateEffectFn,
    resolve_pending_ultimate_shadow_links: ResolvePendingShadowLinksFn,
    sync_board_to_katago: SyncBoardFn,
    choose_bonus_turn: ChooseUltimateAiBonusTurnFn,
    run_bonus_turn: RunUltimateAiBonusTurnFn,
    finish_normal_turn: FinishUltimateAiNormalTurnFn,
    prepare_player_turn_modifiers: Callable[[Any], None],
    force_score: ForceScoreFn,
) -> bool:
    captured = apply_ai_move_result(
        game,
        color,
        gtp_move,
        coord,
        count_turn=allow_double_bonus,
        record_ultimate_turn_fn=record_ultimate_turn,
    )
    await check_capture_foul(game, send_fn, color, captured, ultimate=True)

    await send_fn({
        "type": "ai_move",
        "gtp": gtp_move,
        "color": color,
        "x": coord[0] if coord else None,
        "y": coord[1] if coord else None,
    })

    await post_move_effects(
        game,
        send_fn,
        color=color,
        ai_card=ai_card,
        gtp_move=gtp_move,
        coord=coord,
        count_stones=count_stones,
        apply_ultimate_effect=apply_ultimate_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending_ultimate_shadow_links,
        sync_board_to_katago=sync_board_to_katago,
        check_capture_foul=check_capture_foul,
    )

    bonus_turn = choose_bonus_turn(
        game,
        ai_card=ai_card,
        gtp_move=gtp_move,
        allow_double_bonus=allow_double_bonus,
        chain_random=chain_random,
        chain_chance=chain_chance,
    )

    if bonus_turn is not None and await run_bonus_turn(game, send_fn, color, bonus_turn):
        return True

    finish_normal_turn(
        game,
        prepare_player_turn_modifiers_fn=prepare_player_turn_modifiers,
    )
    await send_fn({"type": "game_state", **game.to_state()})

    if game.ultimate_move_count >= 20:
        await force_score(game, send_fn)

    return False
