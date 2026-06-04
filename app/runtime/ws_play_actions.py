from __future__ import annotations

import asyncio

from app.config.gameplay import (
    ROGUE_HANDICAP_REQUIRED_PASSES,
    ROGUE_METHODICAL_BASE_PLAYS,
    ROGUE_METHODICAL_BONUS_INTERVAL,
    ROGUE_METHODICAL_BONUS_PLAYS,
    ROGUE_QUICKTHINK_SECOND_SECONDS,
)
from app.gameplay.turn_modifiers import has_methodical_card
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_action_utils import board_point_from_data
from app.runtime.ws_ultimate_actions import handle_ultimate_play


async def handle_play(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        await ctx.send_error("暂无进行中的对局")
        return
    if not game.two_player and game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
        return
    if game.ai_observer:
        await ctx.send_error("AI 学习模式不接受人工落子")
        return

    if game.two_player:
        color = game.current_player
    else:
        if not ctx.engine.ready:
            snapshot = ctx.engine_state_snapshot()
            await ctx.send_error(snapshot.get("message") or "KataGo尚未就绪，当前不能进行 AI 对局")
            return
        if game.current_player != game.player_color:
            await ctx.send_error("还没轮到你")
            return
        color = game.player_color

    if game.ultimate and not game.two_player:
        await handle_ultimate_play(ctx, game, data, color)
        return

    if (
        game.rogue_card == "handicap_quest"
        and not game.two_player
        and game.rogue_handicap_passes < ROGUE_HANDICAP_REQUIRED_PASSES
    ):
        await ctx.send_error(
            f"🏋️ 让子棋任务：还需虚手 "
            f"{ROGUE_HANDICAP_REQUIRED_PASSES - game.rogue_handicap_passes} 次才能落子"
        )
        return

    point = board_point_from_data(data, game.size)
    if point is None:
        await ctx.send_error("落点超出棋盘范围")
        return
    x, y = point
    gtp = ctx.coord_to_gtp(x, y, game.size)
    if gtp is None:
        await ctx.send_error("落点超出棋盘范围")
        return
    if game.board[y][x] != 0:
        await ctx.send_error("该位置已有棋子")
        return
    if game.is_ko(x, y, color):
        await ctx.send_error("打劫禁着：不能立即提回")
        return
    player_forbidden = ctx.get_ai_rogue_forbidden_points(game)
    if not game.two_player and (x, y) in player_forbidden:
        await ctx.send_error("这里已被 AI 的 Rogue 卡限制，当前不能落子")
        return
    if not game.two_player and game.rogue_card == "puppet" and game.rogue_puppet_target == (x, y):
        await ctx.send_error("该点已被傀儡术预留给 AI")
        return

    if ctx.engine.ready:
        resp = await ctx.run_in_executor(ctx.engine.send_command, f"play {color} {gtp}")
        if "?" in resp:
            await ctx.send_error(f"无效落子: {gtp}")
            return

    captured = game.place_stone(x, y, color)
    if captured == -1:
        if ctx.engine.ready:
            await ctx.run_in_executor(ctx.engine.send_command, "undo")
        await ctx.send_error("打劫禁着：不能立即提回")
        return
    if captured == -2:
        if ctx.engine.ready:
            await ctx.run_in_executor(ctx.engine.send_command, "undo")
        await ctx.send_error("这手属于自杀禁着，不能这样下")
        return
    game.moves.append((color, gtp))
    game.passed[color] = False

    methodical_bonus = False
    methodical_remaining = 0
    if has_methodical_card(game) and not game.two_player:
        if game.rogue_methodical_remaining <= 0:
            game.rogue_methodical_turns[color] += 1
            turn_count = game.rogue_methodical_turns[color]
            game.rogue_methodical_remaining = (
                ROGUE_METHODICAL_BONUS_PLAYS
                if turn_count % ROGUE_METHODICAL_BONUS_INTERVAL == 0
                else ROGUE_METHODICAL_BASE_PLAYS
            )
        game.rogue_methodical_remaining = max(0, game.rogue_methodical_remaining - 1)
        methodical_remaining = game.rogue_methodical_remaining
        methodical_bonus = methodical_remaining > 0
        game.current_player = game.player_color if methodical_bonus else game.ai_color
    else:
        game.current_player = "W" if color == "B" else "B"

    await ctx.check_capture_foul(game, ctx.send, color, captured, ultimate=False)
    await ctx.apply_player_rogue_move_effects(game, ctx.send, x, y, color, captured)
    await ctx.apply_ai_rogue_response_effects(game, ctx.send, x, y, color)

    quickthink_bonus = False
    if game.rogue_card == "quickthink" and not game.two_player:
        if game.rogue_quickthink_stage == 1:
            game.rogue_quickthink_stage = 2
            game.current_player = game.player_color
            quickthink_bonus = True
        else:
            game.rogue_quickthink_stage = 0

    game.push_history()
    await ctx.send({"type": "game_state", **game.to_state()})

    if game.rogue_skip_ai:
        game.rogue_skip_ai = False
        game.current_player = game.player_color
        await ctx.send({"type": "game_state", **game.to_state()})
        skip_msgs = {
            "twin": "⚡ 双子星辰！你可以继续落子",
            "exchange": "🔄 乾坤挪移！你可以继续落子",
            "handicap_quest": "🏋️ 奖励回合！你可以继续落子",
        }
        await ctx.send({"type": "rogue_event", "msg": skip_msgs.get(game.rogue_card, "你可以继续落子")})
    elif methodical_bonus:
        await ctx.send({
            "type": "rogue_event",
            "msg": f"📏 一板一眼：本回合还可继续落 {methodical_remaining} 子",
        })
    elif not game.two_player and ctx.engine.ready:
        if quickthink_bonus:
            await ctx.send({
                "type": "rogue_event",
                "msg": f"⚡ 快速思考：{ROGUE_QUICKTHINK_SECOND_SECONDS:g} 秒追加手已开启",
            })
        else:
            await ctx.ai_move(game, ctx.send)

    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))
