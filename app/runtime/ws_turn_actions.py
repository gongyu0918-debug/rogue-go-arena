from __future__ import annotations

import asyncio

from app.config.gameplay import (
    ROGUE_HANDICAP_BONUS_INTERVAL,
    ROGUE_HANDICAP_REQUIRED_PASSES,
)
from app.gameplay.engine_errors import is_engine_error_response
from app.gameplay.turn_modifiers import has_methodical_card
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_session_actions import ensure_engine_ready_for_game


async def handle_pass(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    if game.ai_observer:
        await ctx.send_error("AI 学习模式不接受人工操作")
        return
    if not game.two_player and game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
        return

    if game.two_player:
        color = game.current_player
    else:
        if game.current_player != game.player_color:
            return
        if not await ensure_engine_ready_for_game(ctx, game, "player_pass"):
            return
        color = game.player_color

    if game.ultimate and not game.two_player:
        if game.ultimate_player_card == "quickthink" and game.ultimate_quickthink_active:
            ctx.finish_ultimate_quickthink_turn(game)
            game.current_player = game.ai_color
            game.push_history()
            await ctx.send({"type": "game_state", **game.to_state()})
            if game.ultimate_move_count >= 20:
                await ctx.ultimate_force_score(game, ctx.send)
            elif ctx.engine.ready:
                await ctx.ultimate_ai_move(game, ctx.send)
            if not game.game_over and ctx.engine.ready:
                asyncio.create_task(ctx.do_analysis_bg(game))
            return
        ctx.record_ultimate_player_action(game)
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = "W" if color == "B" else "B"
        game.ultimate_double_pending = False
        ctx.finish_ultimate_quickthink_turn(game)
        game.push_history()
        await ctx.send({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count >= 20:
            await ctx.ultimate_force_score(game, ctx.send)
        elif ctx.engine.ready:
            await ctx.ultimate_ai_move(game, ctx.send)
        if not game.game_over and ctx.engine.ready:
            asyncio.create_task(ctx.do_analysis_bg(game))
        return

    if ctx.engine.ready:
        await ctx.run_in_executor(ctx.engine.send_command, f"play {color} pass")
    game.moves.append((color, "pass"))
    game.passed[color] = True
    game.current_player = "W" if color == "B" else "B"
    if game.rogue_card == "quickthink":
        game.rogue_quickthink_stage = 0
    if has_methodical_card(game):
        game.rogue_methodical_remaining = 0

    if (
        game.rogue_card == "handicap_quest"
        and not game.two_player
        and color == game.player_color
        and not game.rogue_handicap_active
    ):
        game.rogue_handicap_passes += 1
        if game.rogue_handicap_passes >= ROGUE_HANDICAP_REQUIRED_PASSES:
            game.rogue_handicap_active = True
            await ctx.send(
                {
                    "type": "rogue_event",
                    "msg": "🏋️ 让子棋任务完成！"
                    f"现在每 {ROGUE_HANDICAP_BONUS_INTERVAL} 手可多下一手",
                }
            )
        else:
            await ctx.send(
                {
                    "type": "rogue_event",
                    "msg": f"🏋️ 虚手 {game.rogue_handicap_passes}/{ROGUE_HANDICAP_REQUIRED_PASSES}",
                }
            )

    game.push_history()
    await ctx.send({"type": "game_state", **game.to_state()})

    if not game.two_player and ctx.engine.ready:
        await ctx.ai_move(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_undo(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.moves:
        return
    if game.ai_observer:
        await ctx.send_error("AI 学习模式不接受人工操作")
        return
    if ctx.rogue_has(game, "no_regret") or ctx.rogue_has(game, "quickthink"):
        await ctx.send_error("这张卡会禁用悔棋")
        return

    if game.challenge_beta:
        if ctx.challenge_remaining(game, "undo") <= 0:
            await ctx.send_error("测试版闯关：悔棋次数已用完")
            return
        game.challenge_usage["undo"] += 1

    if not game.two_player:
        if not await ensure_engine_ready_for_game(ctx, game, "undo", sync_board=False):
            return

    undo_count = 1 if game.two_player else (2 if len(game.moves) >= 2 else 1)
    if not game.undo_history(undo_count):
        return
    game.game_over = False
    game.winner = None
    if ctx.engine.ready:
        await ctx.sync_board_to_katago(game)
    ctx.prepare_player_turn_modifiers(game)
    await ctx.send({"type": "game_state", **game.to_state()})

    if ctx.engine.ready:
        analysis = await ctx.do_analysis(game)
        await ctx.send({"type": "analysis", **analysis})


async def handle_score(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game:
        return
    if game.ai_observer:
        await ctx.send_error("AI 学习模式不接受人工操作")
        return
    if not game.two_player:
        if not await ensure_engine_ready_for_game(ctx, game, "score"):
            return
    if ctx.engine.ready:
        await ctx.sync_board_to_katago(game)
        resp = await ctx.run_in_executor(ctx.engine.send_command, "final_score")
        score_str = resp.replace("=", "").strip()
    else:
        score_str = "?"
    if is_engine_error_response(score_str) or score_str[:1] not in {"B", "W", "0"}:
        await ctx.send_error(f"AI 引擎数目失败：{score_str}")
        return
    winner = "B" if score_str.startswith("B") else "W" if score_str.startswith("W") else "draw"
    game.game_over = True
    game.winner = winner
    await ctx.send(
        {
            "type": "game_over",
            "winner": winner,
            "score": score_str,
            "reason": "score",
        }
    )
