from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import app.config.gameplay as gameplay_config


AsyncSend = Callable[[dict[str, Any]], Awaitable[None]]
CoordParser = Callable[[str, int], tuple[int, int] | None]
NoResignMoveFn = Callable[[Any, str], Awaitable[str]]
RetryAvoidingKoFn = Callable[[Any, str], Awaitable[str]]
CheckCaptureFoulFn = Callable[..., Awaitable[None]]
PreparePlayerTurnFn = Callable[[Any], None]
EngineCommandFn = Callable[[str], Awaitable[str]]
RunCoachTurnFn = Callable[[Any, AsyncSend], Awaitable[None]]
FinishAiMoveFn = Callable[[Any, AsyncSend, str, str | None, str, str | None], Awaitable[None]]
AllowedRestrictionMoveFn = Callable[
    [Any, str, int, float, list[tuple[int, int]]],
    Awaitable[str | None],
]
AvoidRestrictionMoveFn = Callable[
    [Any, str, int, float, list[tuple[int, int]]],
    Awaitable[str | None],
]


async def finalize_forced_ai_pass(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    message: str,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    run_engine_command: EngineCommandFn,
) -> None:
    await run_engine_command(f"play {color} pass")
    game.moves.append((color, "pass"))
    game.passed[color] = True
    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)
    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})
    await send_fn({
        "type": "ai_move",
        "gtp": "pass",
        "color": color,
        "x": None,
        "y": None,
    })
    await send_fn({"type": "rogue_event", "msg": message})


async def try_finalize_forced_ai_stone(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    gtp_move: str,
    coord: tuple[int, int],
    message: str,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    run_engine_command: EngineCommandFn,
    push_history: bool = True,
) -> bool:
    resp = await run_engine_command(f"play {color} {gtp_move}")
    if "?" in resp:
        return False

    x, y = coord
    game.moves.append((color, gtp_move))
    game.place_stone(x, y, color)
    game.passed[color] = False
    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)
    if push_history:
        game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})
    await send_fn({
        "type": "ai_move",
        "gtp": gtp_move,
        "color": color,
        "x": x,
        "y": y,
    })
    await send_fn({"type": "rogue_event", "msg": message})
    return True


async def try_apply_puppet_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    target: tuple[int, int],
    coord_to_gtp: Callable[[int, int, int], str | None],
    run_engine_command: EngineCommandFn,
    finish_ai_move: FinishAiMoveFn,
) -> bool:
    tx, ty = target
    puppet_gtp = coord_to_gtp(tx, ty, game.size)
    game.rogue_puppet_target = None

    if game.board[ty][tx] != 0:
        await send_fn({
            "type": "rogue_event",
            "msg": f"🎭 傀儡术目标 {puppet_gtp} 已被占用，AI 改为正常应手",
        })
        return False

    if game.is_ko(tx, ty, color) or not game.is_legal_move(tx, ty, color):
        await send_fn({
            "type": "rogue_event",
            "msg": f"🎭 傀儡术目标 {puppet_gtp} 当前不合法，AI 改为正常应手",
        })
        return False

    resp = await run_engine_command(f"play {color} {puppet_gtp}")
    if "?" in resp:
        await send_fn({
            "type": "rogue_event",
            "msg": f"🎭 傀儡术目标 {puppet_gtp} 执行失败，AI 改为正常应手",
        })
        return False

    if game.rogue_uses.get("puppet", 0) > 0:
        game.rogue_uses["puppet"] -= 1
    await finish_ai_move(
        game,
        send_fn,
        color,
        card,
        puppet_gtp,
        f"🎭 傀儡术生效，AI 被迫落子于 {puppet_gtp}",
    )
    await send_fn({"type": "rogue_uses_update", "uses": game.rogue_uses})
    return True


async def try_finish_allowed_restriction_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    restriction: Any | None,
    visits: int,
    time_limit: float,
    choose_allowed_move: AllowedRestrictionMoveFn,
    finish_ai_move: FinishAiMoveFn,
) -> bool:
    if restriction is None:
        return False

    gtp_move = await choose_allowed_move(
        game,
        color,
        visits,
        time_limit,
        restriction.points,
    )
    if not gtp_move:
        return False

    await finish_ai_move(
        game,
        send_fn,
        color,
        card,
        gtp_move,
        restriction.message,
    )
    return True


async def try_finish_sansan_restriction_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    restriction: Any | None,
    visits: int,
    time_limit: float,
    choose_allowed_move: AllowedRestrictionMoveFn,
    choose_avoid_move: AvoidRestrictionMoveFn,
    finish_ai_move: FinishAiMoveFn,
) -> bool:
    if restriction is None:
        return False

    if restriction.kind == "allow_only":
        gtp_move = await choose_allowed_move(
            game,
            color,
            visits,
            time_limit,
            restriction.points,
        )
        if gtp_move:
            await finish_ai_move(
                game,
                send_fn,
                color,
                card,
                gtp_move,
                restriction.message,
            )
            return True

    gtp_move = await choose_avoid_move(
        game,
        color,
        visits,
        time_limit,
        restriction.points,
    )
    await finish_ai_move(
        game,
        send_fn,
        color,
        card,
        gtp_move,
        restriction.message,
    )
    return True


async def finalize_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    gtp_move: str,
    rogue_msg: str | None = None,
    gtp_to_coord: CoordParser,
    no_resign_move: NoResignMoveFn,
    retry_avoiding_ko: RetryAvoidingKoFn,
    check_capture_foul: CheckCaptureFoulFn,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    run_engine_command: EngineCommandFn,
    run_coach_turn_if_needed: RunCoachTurnFn,
) -> None:
    if game.game_over:
        return

    if gtp_move.upper() == "RESIGN":
        if card:
            gtp_move = await no_resign_move(game, color)
        else:
            game.game_over = True
            game.winner = game.player_color
            await send_fn({
                "type": "game_over",
                "winner": game.player_color,
                "score": None,
                "reason": "ai_resign",
            })
            return

    coord = gtp_to_coord(gtp_move, game.size)
    if coord and gtp_move.upper() != "PASS" and game.is_ko(coord[0], coord[1], color):
        gtp_move = await retry_avoiding_ko(game, color)
        coord = gtp_to_coord(gtp_move, game.size) if gtp_move.upper() not in ("PASS", "RESIGN") else None

    game.moves.append((color, gtp_move))
    captured = 0
    if gtp_move.upper() != "PASS":
        if coord:
            captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    await check_capture_foul(game, send_fn, color, captured, ultimate=False)

    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)

    if card == "erosion" and captured > 0:
        shift = gameplay_config.ROGUE_EROSION_SHIFT * captured
        if game.ai_color == "W":
            game.komi += shift
        else:
            game.komi -= shift
        await run_engine_command(f"komi {game.komi}")
        await send_fn({
            "type": "rogue_event",
            "msg": f"🐛 蚕食！AI 提 {captured} 子，贴目变为 {game.komi}",
        })

    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if game.passed["B"] and game.passed["W"]:
        resp_score = await run_engine_command("final_score")
        score_str = resp_score.replace("=", "").strip()
        winner = "B" if score_str.startswith("B") else "W"
        game.game_over = True
        game.winner = winner
        await send_fn({
            "type": "ai_move",
            "gtp": gtp_move,
            "color": color,
            "x": None,
            "y": None,
        })
        await send_fn({
            "type": "game_over",
            "winner": winner,
            "score": score_str,
            "reason": "double_pass",
        })
        return

    await send_fn({
        "type": "ai_move",
        "gtp": gtp_move,
        "color": color,
        "x": coord[0] if coord else None,
        "y": coord[1] if coord else None,
    })
    if rogue_msg:
        await send_fn({"type": "rogue_event", "msg": rogue_msg})
    await run_coach_turn_if_needed(game, send_fn)
