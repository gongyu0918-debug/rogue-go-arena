from __future__ import annotations

import asyncio

from app.config.gameplay import ROGUE_COACH_BASE_TURNS, ROGUE_SEAL_POINT_COUNT
from app.data.cards import CHALLENGE_BETA_POOL, ROGUE_CARDS, get_rogue_card
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_action_utils import board_point_from_data
from app.runtime.ws_session_actions import ensure_engine_ready_for_game


async def handle_rogue_select_card(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game:
        return
    card_id = data.get("card_id", "")
    if card_id not in ROGUE_CARDS:
        return
    if game.challenge_beta:
        if card_id in game.challenge_cards or card_id not in game.challenge_offer_cards:
            return
        game.challenge_cards.append(card_id)
        game.challenge_offer_cards = []
        card_def = get_rogue_card(card_id)
        await ctx.apply_challenge_rogue_loadout(game, ctx.send)
        await ctx.send(
            {
                "type": "rogue_card_selected",
                "card_id": card_id,
                "name": card_def["name"],
                "icon": card_def["icon"],
                "waiting_seal": False,
                **game.to_state(),
            }
        )
    else:
        await ctx.activate_rogue_card(game, ctx.send, card_id)
    if game.ai_rogue_enabled and not game.two_player and not game.challenge_beta:
        ai_card_id = ctx.pick_ai_rogue_card(exclude=[card_id])
        await ctx.activate_ai_rogue_card(game, ctx.send, ai_card_id)
    game.reset_history()
    if card_id != "seal":
        if not game.two_player:
            if not await ensure_engine_ready_for_game(ctx, game, "rogue_select_card"):
                return
        if not game.two_player and ctx.engine.ready and game.ai_color == game.current_player:
            await ctx.ai_move(game, ctx.send)
        if not game.game_over and ctx.engine.ready:
            asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_challenge_refresh_offer(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.challenge_beta:
        return
    if game.challenge_refreshes <= 0:
        await ctx.send_error("当前测试版闯关没有剩余刷新次数")
        return
    pool = [card_id for card_id in CHALLENGE_BETA_POOL if card_id not in game.challenge_cards]
    if len(pool) < 3:
        await ctx.send_error("当前可刷新卡牌不足 3 张")
        return
    game.challenge_refreshes -= 1
    choices = ctx.pick_challenge_beta_choices(game.challenge_cards, 3, pool=pool)
    game.challenge_offer_cards = choices
    cards_data = []
    for cid in choices:
        c = get_rogue_card(cid)
        cards_data.append(
            {
                "id": cid,
                "name": c["name"],
                "desc": c["desc"],
                "icon": c["icon"],
            }
        )
    await ctx.send(
        {
            "type": "rogue_offer",
            "cards": cards_data,
            "challenge_beta": True,
            "challenge_stage": game.challenge_stage,
            "refresh_remaining": game.challenge_refreshes,
        }
    )


async def handle_rogue_seal_point(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.rogue_waiting_seal:
        return
    point = board_point_from_data(data, game.size)
    if point is None:
        await ctx.send_error("目标点超出棋盘范围")
        return
    x, y = point
    if (x, y) not in game.rogue_seal_points:
        game.rogue_seal_points.append((x, y))
    await ctx.send(
        {
            "type": "rogue_seal_update",
            "points": [[px, py] for px, py in game.rogue_seal_points],
            "remaining": ROGUE_SEAL_POINT_COUNT - len(game.rogue_seal_points),
            "required": ROGUE_SEAL_POINT_COUNT,
            "selected": len(game.rogue_seal_points),
        }
    )
    if len(game.rogue_seal_points) >= ROGUE_SEAL_POINT_COUNT:
        if game.challenge_beta:
            game.rogue_seal_points = ctx.challenge_zone_points(game, game.rogue_seal_points)
        game.rogue_waiting_seal = False
        game.reset_history()
        await ctx.send({"type": "rogue_seal_done"})
        if not game.two_player:
            if not await ensure_engine_ready_for_game(ctx, game, "rogue_seal_done"):
                return
        if ctx.engine.ready and game.ai_color == game.current_player:
            await ctx.ai_move(game, ctx.send)
        if not game.game_over and ctx.engine.ready:
            asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_rogue_use_puppet(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over or not ctx.engine.ready:
        return
    if game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
        return
    if game.rogue_card != "puppet" or game.rogue_uses.get("puppet", 0) <= 0:
        await ctx.send_error("傀儡术已用完")
        return
    if game.current_player != game.player_color:
        await ctx.send_error("还没轮到你")
        return
    point = board_point_from_data(data, game.size)
    if point is None:
        await ctx.send_error("目标点超出棋盘范围")
        return
    x, y = point
    gtp = ctx.coord_to_gtp(x, y, game.size)
    if gtp is None:
        await ctx.send_error("目标点超出棋盘范围")
        return
    if game.board[y][x] != 0:
        await ctx.send_error(f"该位置已有棋子: {gtp}")
        return
    game.rogue_puppet_target = (x, y)
    await ctx.send({"type": "game_state", **game.to_state()})
    await ctx.send({"type": "rogue_event", "msg": f"🎭 傀儡术待命：你先正常落子，随后 AI 会被迫下在 {gtp}"})
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_rogue_use_twin(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    if game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
        return
    if game.rogue_card != "twin" or game.rogue_uses.get("twin", 0) <= 0:
        await ctx.send_error("双子星辰已用完")
        return
    game.rogue_uses["twin"] -= 1
    game.rogue_skip_ai = True
    await ctx.send(
        {
            "type": "rogue_event",
            "msg": f"⚡ 双子星辰激活！下一手后可连续落子（剩余 {game.rogue_uses.get('twin', 0)} 次）",
        }
    )
    await ctx.send({"type": "rogue_uses_update", "uses": game.rogue_uses})


async def handle_rogue_use_exchange(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    if game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
        return
    if game.rogue_card != "exchange" or game.rogue_uses.get("exchange", 0) <= 0:
        await ctx.send_error("乾坤挪移已用完")
        return
    if game.current_player != game.player_color:
        await ctx.send_error("还没轮到你")
        return

    from_point = board_point_from_data(
        {"x": data.get("from_x"), "y": data.get("from_y")},
        game.size,
    )
    to_point = board_point_from_data(
        {"x": data.get("to_x"), "y": data.get("to_y")},
        game.size,
    )
    if from_point is None or to_point is None:
        await ctx.send_error("请选择对方棋子和目标空点")
        return
    fx, fy = from_point
    tx, ty = to_point
    opp_val = 2 if game.player_color == "B" else 1
    if game.board[fy][fx] != opp_val:
        await ctx.send_error("乾坤挪移只能移动对方棋子")
        return
    if game.board[ty][tx] != 0:
        await ctx.send_error("目标位置必须是空点")
        return

    game.board[fy][fx] = 0
    game.board[ty][tx] = opp_val
    game.ko_point = None
    if ctx.engine.ready:
        await ctx.sync_board_to_katago(game)
    game.rogue_uses["exchange"] -= 1
    game.push_history()
    from_gtp = ctx.coord_to_gtp(fx, fy, game.size)
    to_gtp = ctx.coord_to_gtp(tx, ty, game.size)
    await ctx.send({"type": "game_state", **game.to_state()})
    await ctx.send({"type": "rogue_event", "msg": f"🔄 乾坤挪移：已将对方 {from_gtp} 的棋子摆动到 {to_gtp}"})
    await ctx.send({"type": "rogue_uses_update", "uses": game.rogue_uses})
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_rogue_use_coach(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        return
    if not await ensure_engine_ready_for_game(ctx, game, "coach_mode"):
        return
    if game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号已经在接管中")
        return
    if game.challenge_beta:
        if ctx.challenge_remaining(game, "coach") <= 0:
            await ctx.send_error("测试版闯关：代下次数已用完")
            return
        game.challenge_usage["coach"] += 1
    if game.rogue_card != "coach_mode" or game.rogue_uses.get("coach_mode", 0) <= 0:
        await ctx.send_error("代练上号已经用完了")
        return
    if game.current_player != game.player_color:
        await ctx.send_error("还没轮到你")
        return
    game.rogue_uses["coach_mode"] -= 1
    game.rogue_coach_moves_left = ROGUE_COACH_BASE_TURNS
    game.rogue_coach_bonus_checked = False
    await ctx.send(
        {
            "type": "rogue_event",
            "msg": f"🎓 代练上号启动：接下来 {ROGUE_COACH_BASE_TURNS} 手将由更强 AI 代打",
        }
    )
    await ctx.send({"type": "rogue_uses_update", "uses": game.rogue_uses})
    await ctx.send({"type": "game_state", **game.to_state()})
    await ctx.run_coach_turn_if_needed(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))
