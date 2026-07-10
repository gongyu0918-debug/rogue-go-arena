from __future__ import annotations

import asyncio
import time
from typing import Any

from app.runtime.game_input_validation import (
    VALID_BOARD_SIZES,
    normalize_komi,
    payload_int,
)
from app.runtime.ws_action_context import WebSocketActionContext


async def claim_engine_session(ctx: WebSocketActionContext) -> bool:
    if not getattr(ctx, "game_id", None):
        return True
    connection_token = getattr(ctx, "connection_token", None) or id(ctx)
    connection_tokens = getattr(ctx.engine, "active_connection_tokens", None)
    if not isinstance(connection_tokens, set):
        connection_tokens = set()
        ctx.engine.active_connection_tokens = connection_tokens
    connection_tokens.add(connection_token)

    def assign_owner() -> None:
        ctx.engine.active_game_id = ctx.game_id
        ctx.engine.active_game_connection_token = connection_token
        ctx.engine.active_game_claimed_at = time.time()

    def owner_state() -> tuple[str | None, object | None, Any, bool]:
        owner_id = getattr(ctx.engine, "active_game_id", None)
        owner_token = getattr(ctx.engine, "active_game_connection_token", None)
        owner_game = ctx.active_games.get(owner_id) if owner_id else None
        return owner_id, owner_token, owner_game, owner_token in connection_tokens

    owner_id, owner_token, owner_game, owner_connected = owner_state()
    if owner_id is None:
        assign_owner()
        return True
    if owner_id == ctx.game_id and owner_token == connection_token:
        ctx.engine.active_game_claimed_at = time.time()
        return True
    if getattr(owner_game, "game_over", False):
        assign_owner()
        return True
    if owner_connected:
        deadline = time.monotonic() + 0.75
        while owner_connected and time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            owner_connected = owner_token in connection_tokens

    owner_id, owner_token, owner_game, owner_connected = owner_state()
    if owner_id is None:
        assign_owner()
        return True
    if owner_id == ctx.game_id and owner_token == connection_token:
        ctx.engine.active_game_claimed_at = time.time()
        return True
    claim_age = time.time() - float(getattr(ctx.engine, "active_game_claimed_at", 0.0) or 0.0)
    if (
        getattr(owner_game, "game_over", False)
        or (owner_game is not None and not owner_connected)
        or (owner_game is None and claim_age > 120.0)
    ):
        assign_owner()
        return True
    await ctx.send_error("另一个窗口正在使用 AI 引擎，请先结束该对局")
    return False


def release_engine_session(ctx: WebSocketActionContext) -> None:
    connection_token = getattr(ctx, "connection_token", None) or id(ctx)
    if (
        getattr(ctx.engine, "active_game_id", None) == ctx.game_id
        and getattr(ctx.engine, "active_game_connection_token", None) == connection_token
    ):
        ctx.engine.active_game_id = None
        ctx.engine.active_game_connection_token = None
        ctx.engine.active_game_claimed_at = 0.0
        connection_tokens = getattr(ctx.engine, "active_connection_tokens", None)
        if isinstance(connection_tokens, set):
            connection_tokens.discard(connection_token)


def _normalize_load_position_move(ctx: WebSocketActionContext, move: Any, size: int) -> tuple[str, str] | None:
    if not isinstance(move, (list, tuple)) or len(move) < 2:
        return None
    color = str(move[0]).upper()
    gtp = str(move[1]).upper()
    if color not in {"B", "W"}:
        return None
    if any(ch.isspace() for ch in color) or any(ch.isspace() for ch in gtp):
        return None
    if gtp == "PASS":
        return color, "pass"
    if ctx.gtp_to_coord(gtp, size) is None:
        return None
    return color, gtp


async def handle_reconnect(ctx: WebSocketActionContext, data: dict) -> None:
    saved = ctx.active_games.get(ctx.game_id, touch=True)
    if saved:
        ctx.game = saved
        await ctx.send({"type": "reconnected", **ctx.game.to_state()})
        if not ctx.game.game_over and ctx.engine.ready and await claim_engine_session(ctx):
            analysis = await ctx.do_analysis(ctx.game)
            await ctx.send({"type": "analysis", **analysis})
    else:
        await ctx.send({"type": "reconnect_failed"})


async def handle_resign(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game:
        return
    game.game_over = True
    game.winner = game.ai_color if not game.two_player else ("W" if game.current_player == "B" else "B")
    await ctx.send(
        {
            "type": "game_over",
            "winner": game.winner,
            "score": None,
            "reason": "resign",
        }
    )


async def handle_request_hint(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    if ctx.rogue_has(game, "quickthink"):
        await ctx.send_error("快速思考已禁用推荐点位，请自行判断局面")
        return
    if not await ensure_engine_ready_for_game(ctx, game, "request_hint"):
        return
    if game.challenge_beta:
        if ctx.challenge_remaining(game, "hint") <= 0:
            await ctx.send_error("测试版闯关：推荐点次数已用完")
            return
        game.challenge_usage["hint"] += 1
        await ctx.send({"type": "game_state", **game.to_state()})
    analysis = await ctx.do_analysis(game)
    await ctx.send({"type": "analysis", **analysis})


async def handle_set_level(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game:
        return
    level = data.get("level", "a3d")
    game.level = level
    if ctx.engine.ready:
        mode = "ultimate" if game.ultimate else ("rogue" if game.rogue_card else "normal")
        visits = ctx.get_game_visits(level, len(game.moves), mode=mode)
        await ctx.run_in_executor(ctx.engine.set_visits, visits)
    await ctx.send({"type": "level_set", "level": level})


async def handle_load_position(ctx: WebSocketActionContext, data: dict) -> None:
    size = payload_int(data.get("size", 19), 19)
    komi = normalize_komi(data.get("komi", 7.5))
    if size not in VALID_BOARD_SIZES:
        await ctx.send_error("复盘棋盘尺寸无效")
        return
    if komi is None:
        await ctx.send_error("复盘贴目设置无效")
        return
    moves_list = data.get("moves", [])
    if not isinstance(moves_list, (list, tuple)):
        await ctx.send_error("复盘棋谱格式无效")
        return
    validated_moves = []
    for move in moves_list:
        normalized = _normalize_load_position_move(ctx, move, size)
        if normalized is None:
            await ctx.send_error("复盘棋谱包含无效着手")
            return
        validated_moves.append(normalized)

    next_color = "B" if len(validated_moves) % 2 == 0 else "W"
    temp = ctx.GoGame(size, komi, 0, "B", "a3d")
    temp.current_player = next_color
    temp.moves = list(validated_moves)
    try:
        temp.rebuild_board(strict=True)
    except ValueError:
        await ctx.send_error("复盘棋谱包含非法着手")
        return

    original_game = ctx.restore_game()
    if not await claim_engine_session(ctx):
        return

    if not ctx.engine.ready:
        if not await wait_for_engine_ready(ctx, "load_position"):
            if original_game is None:
                release_engine_session(ctx)
            return

    if ctx.engine.ready:
        try:
            result = await ctx.do_analysis(temp)
        finally:
            if original_game is not None:
                try:
                    await ctx.sync_board_to_katago(original_game)
                except Exception:
                    try:
                        await ctx.run_in_executor(ctx.engine.stop)
                    finally:
                        ctx.engine.ready = False
                        try:
                            ctx.start_engine_background("load_position_restore")
                        except Exception:
                            pass
                    raise
        await ctx.send({"type": "analysis", **result})


async def handle_time_expired(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    loser = data.get("color", "B")
    winner = "W" if loser == "B" else "B"
    game.game_over = True
    game.winner = winner
    await ctx.send(
        {
            "type": "game_over",
            "winner": winner,
            "score": f"{winner}+T",
            "reason": "timeout",
        }
    )


async def send_engine_not_ready(
    ctx: WebSocketActionContext,
    snapshot: dict[str, Any],
    fallback: str,
) -> None:
    await ctx.send(
        {
            "type": "engine_not_ready",
            "phase": snapshot.get("phase"),
            "message": snapshot.get("message") or fallback,
            "last_error": snapshot.get("last_error"),
            "log_tail": snapshot.get("log_tail"),
        }
    )


async def wait_for_engine_ready(ctx: WebSocketActionContext, reason: str) -> bool:
    def fully_ready() -> bool:
        snapshot = ctx.engine_state_snapshot()
        return bool(ctx.engine.ready and snapshot.get("phase") == "ready")

    snapshot = ctx.engine_state_snapshot()
    if snapshot.get("phase") not in {"initializing", "ready"}:
        ctx.start_engine_background(reason)
        snapshot = ctx.engine_state_snapshot()
    await send_engine_not_ready(ctx, snapshot, "KataGo 正在随游戏启动")
    deadline = time.time() + 120
    while not fully_ready() and time.time() < deadline:
        await asyncio.sleep(0.5)
        snapshot = ctx.engine_state_snapshot()
        if snapshot.get("phase") not in {"initializing", "ready"}:
            break
    if fully_ready():
        return True
    snapshot = ctx.engine_state_snapshot()
    await send_engine_not_ready(ctx, snapshot, "")
    await ctx.send_error(
        snapshot.get("message")
        or "KataGo未就绪，请稍候重试，或先使用两人对局模式"
    )
    return False


async def ensure_engine_ready_for_game(
    ctx: WebSocketActionContext,
    game: Any,
    reason: str,
    *,
    sync_board: bool = True,
) -> bool:
    if not await claim_engine_session(ctx):
        return False
    if game.two_player:
        return True
    snapshot_fn = getattr(
        ctx,
        "engine_state_snapshot",
        lambda: {"phase": "ready" if ctx.engine.ready else "stopped"},
    )
    snapshot = snapshot_fn()
    if not ctx.engine.ready or snapshot.get("phase") != "ready":
        if not await wait_for_engine_ready(ctx, reason):
            return False
        if sync_board:
            await ctx.sync_board_to_katago(game)
    return True
