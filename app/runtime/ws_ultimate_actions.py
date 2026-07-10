from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from app.config.gameplay import (
    ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
    ULTIMATE_JOSEKI_TARGET_COUNT,
)
from app.data.cards import ULTIMATE_CARDS, get_ultimate_card
from app.gameplay.ultimate_effects import reset_ultimate_effect_state
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_action_utils import board_point_from_data
from app.runtime.ws_session_actions import ensure_engine_ready_for_game


async def handle_ultimate_play(
    ctx: WebSocketActionContext,
    game: Any,
    data: dict,
    color: str,
) -> None:
    point = board_point_from_data(data, game.size)
    if point is None:
        await ctx.send_error("落点超出棋盘范围")
        return
    x, y = point

    if game.ultimate_ai_card == "territory":
        cv_player = 1 if color == "B" else 2
        if (x, y) in ctx.ultimate_get_territory_forbidden(game, cv_player):
            await ctx.send_error("这里已被绝对领地封锁，不能在 AI 的禁区内落子")
            return

    if game.board[y][x] != 0:
        await ctx.send_error("该位置已有棋子")
        return
    if game.is_ko(x, y, color):
        await ctx.send_error("打劫禁着：不能立即提回")
        return
    gtp = ctx.coord_to_gtp(x, y, game.size)
    if gtp is None:
        await ctx.send_error("落点超出棋盘范围")
        return
    captured = game.place_stone(x, y, color)
    if captured == -1:
        await ctx.send_error("打劫禁着：不能立即提回")
        return
    if captured == -2:
        await ctx.send_error("这手属于自杀禁着，不能这样下")
        return
    was_double_pending = game.ultimate_double_pending
    ctx.record_ultimate_player_action(game)
    game.moves.append((color, gtp))
    game.passed[color] = False
    await ctx.check_capture_foul(game, ctx.send, color, captured, ultimate=True)

    p_card = game.ultimate_player_card
    if p_card == "quickthink":
        if not game.ultimate_quickthink_active:
            game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True
        game.current_player = game.player_color
        await ctx.send({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count >= 20:
            ctx.finish_ultimate_quickthink_turn(game)
            await ctx.ultimate_force_score(game, ctx.send)
        return

    board_modified = False
    opp_val = 2 if color == "B" else 1
    opp_before = ctx.count_stones(game, opp_val)
    if p_card:
        board_modified = await ctx.apply_ultimate_effect(game, ctx.send, x, y, color, p_card)
    pending_modified = await ctx.resolve_pending_ultimate_shadow_links(game, ctx.send)
    if board_modified or pending_modified:
        await ctx.sync_board_to_katago(game)
        effect_removed = max(0, opp_before - ctx.count_stones(game, opp_val))
        if effect_removed > 0:
            await ctx.check_capture_foul(game, ctx.send, color, effect_removed, ultimate=True)

    chain_bonus = p_card == "chain" and random.random() < ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
    double_bonus = p_card == "double" and not was_double_pending
    game.ultimate_extra_turn = chain_bonus or double_bonus
    game.ultimate_double_pending = bool(double_bonus)
    game.current_player = game.player_color if (chain_bonus or double_bonus) else game.ai_color
    game.push_history()
    await ctx.send({"type": "game_state", **game.to_state()})

    if game.ultimate_move_count >= 20:
        await ctx.ultimate_force_score(game, ctx.send)
        return
    if chain_bonus:
        await ctx.send({"type": "rogue_event", "msg": "连珠棋触发成功，你可以继续落子"})
        return
    if double_bonus:
        await ctx.send({"type": "rogue_event", "msg": "双刀流触发成功，你可以继续落子"})
        return

    game.ultimate_extra_turn = False
    if ctx.engine.ready:
        await ctx.ultimate_ai_move(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_ultimate_select_card(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.ultimate:
        return
    card_id = data.get("card_id", "")
    if card_id not in ULTIMATE_CARDS:
        return
    if game.ultimate_player_card is not None or card_id not in game.ultimate_offer_cards:
        await ctx.send_error("卡牌选择已失效，请使用当前卡牌报价")
        return
    game.ultimate_player_card = card_id
    game.ultimate_offer_cards = []
    reset_ultimate_effect_state(game)
    if card_id == "joseki_burst":
        game.ultimate_joseki_targets = ctx.pick_joseki_targets(game.size, ULTIMATE_JOSEKI_TARGET_COUNT)
    elif card_id == "god_hand":
        rng = random.Random(time.time_ns())
        game.ultimate_godhand_center = ctx.random_hidden_center(game.size, 2, rng)
        game.ultimate_godhand_trigger = ctx.diamond_points(
            game.ultimate_godhand_center[0],
            game.ultimate_godhand_center[1],
            2,
            game.size,
        )
    elif card_id == "quickthink" and game.current_player == game.player_color:
        game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True
    pdef = get_ultimate_card(card_id)
    ai_card_id = ctx.pick_ai_ultimate_card(exclude=[card_id])
    game.ultimate_ai_card = ai_card_id
    adef = get_ultimate_card(ai_card_id)
    game.reset_history()
    await ctx.send(
        {
            "type": "ultimate_cards_selected",
            "player_card": card_id,
            "player_name": pdef["name"],
            "player_icon": pdef["icon"],
            "ai_card": ai_card_id,
            "ai_name": adef["name"],
            "ai_icon": adef["icon"],
            **game.to_state(),
        }
    )
    if not await ensure_engine_ready_for_game(ctx, game, "ultimate_select_card"):
        return
    if card_id == "joseki_burst":
        pts = ", ".join(ctx.coord_to_gtp(px, py, game.size) for px, py in game.ultimate_joseki_targets)
        await ctx.send({"type": "rogue_event", "msg": f"定式爆发已点亮目标点：{pts}。命中其中 3 个后会触发爆发"})
    if ctx.engine.ready and game.ai_color == game.current_player:
        await ctx.ultimate_ai_move(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_ultimate_quickthink_end(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.ultimate:
        return
    if game.ultimate_player_card != "quickthink" or not game.ultimate_quickthink_active:
        return
    ctx.finish_ultimate_quickthink_turn(game)
    game.current_player = game.ai_color
    await ctx.send({"type": "game_state", **game.to_state()})
    if game.ultimate_move_count >= 20:
        await ctx.ultimate_force_score(game, ctx.send)
    elif await ensure_engine_ready_for_game(ctx, game, "ultimate_quickthink_end"):
        await ctx.ultimate_ai_move(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))
