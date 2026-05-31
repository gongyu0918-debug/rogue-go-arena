from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Awaitable, Callable

from app.config.gameplay import (
    AI_STYLE_OPTIONS,
    RANK_VISITS,
    ROGUE_HANDICAP_REQUIRED_PASSES,
    ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
    ULTIMATE_JOSEKI_TARGET_COUNT,
)
from app.data.cards import (
    CHALLENGE_BETA_HANDICAPS,
    CHALLENGE_BETA_POOL,
    TWO_PLAYER_ROGUE_POOL,
    ULTIMATE_CARDS,
    get_ultimate_card,
    rogue_card_summary,
    ultimate_card_summary,
)
from app.gameplay.ultimate_effects import reset_ultimate_effect_state
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_session_actions import (
    handle_load_position,
    handle_reconnect,
    handle_request_hint,
    handle_resign,
    handle_set_level,
    handle_time_expired,
    wait_for_engine_ready,
)
from app.runtime.ws_action_utils import board_point_from_data as _board_point_from_data
from app.runtime.ws_rogue_actions import (
    handle_challenge_refresh_offer,
    handle_rogue_seal_point,
    handle_rogue_select_card,
    handle_rogue_use_coach,
    handle_rogue_use_exchange,
    handle_rogue_use_puppet,
    handle_rogue_use_twin,
)
from app.runtime.ws_turn_actions import (
    handle_pass,
    handle_score,
    handle_undo,
)


async def handle_new_game(ctx: WebSocketActionContext, data: dict) -> None:
    config_errors = ctx.reload_live_card_config()
    if config_errors:
        await ctx.send_error("卡牌配置加载失败：" + "；".join(config_errors[:6]))
        return

    if not ctx.engine.ready and not data.get("two_player", False):
        if not await wait_for_engine_ready(ctx, "game_start"):
            return

    ctx.active_games.prune()
    size = int(data.get("size", 19))
    komi = float(data.get("komi", 7.5))
    handicap = int(data.get("handicap", 0))
    player_color = data.get("player_color", "B")
    level = data.get("level", "a3d")
    two_player = bool(data.get("two_player", False))
    ai_observer = bool(data.get("ai_observer", False)) and not two_player
    if ai_observer:
        two_player = False
    rogue_enabled = bool(data.get("rogue", False))
    ai_rogue_enabled = bool(data.get("ai_rogue", False)) and rogue_enabled and not two_player
    challenge_beta = bool(data.get("challenge_beta", False))
    challenge_stage = int(data.get("challenge_stage", 0) or 0)
    challenge_cards = [
        card_id for card_id in data.get("challenge_cards", [])
        if card_id in CHALLENGE_BETA_POOL
    ]
    challenge_limits = data.get("challenge_limits", {}) or {}
    challenge_refreshes = int(data.get("challenge_refreshes", 0) or 0)
    if challenge_beta:
        two_player = False
        ai_observer = False
        rogue_enabled = True
        ai_rogue_enabled = False
        handicap = CHALLENGE_BETA_HANDICAPS.get(challenge_stage, handicap)
    ai_style = str(data.get("ai_style", "balanced"))
    if ai_style not in AI_STYLE_OPTIONS:
        ai_style = "balanced"
    ai_level_black = str(data.get("ai_level_black", level))
    if ai_level_black not in RANK_VISITS:
        ai_level_black = level
    ai_level_white = str(data.get("ai_level_white", level))
    if ai_level_white not in RANK_VISITS:
        ai_level_white = level
    ai_style_black = str(data.get("ai_style_black", ai_style))
    if ai_style_black not in AI_STYLE_OPTIONS:
        ai_style_black = ai_style
    ai_style_white = str(data.get("ai_style_white", ai_style))
    if ai_style_white not in AI_STYLE_OPTIONS:
        ai_style_white = ai_style

    game = ctx.GoGame(size, komi, handicap, player_color, level, two_player)
    game.ai_observer = ai_observer
    game.ai_style = ai_style
    game.ai_level_black = ai_level_black
    game.ai_level_white = ai_level_white
    game.ai_style_black = ai_style_black
    game.ai_style_white = ai_style_white
    game.rogue_enabled = rogue_enabled
    game.ai_rogue_enabled = ai_rogue_enabled
    game.challenge_beta = challenge_beta
    game.challenge_stage = challenge_stage
    game.challenge_cards = challenge_cards
    game.challenge_refreshes = challenge_refreshes
    game.challenge_limits = {
        "undo": int(challenge_limits.get("undo", 0) or 0),
        "hint": int(challenge_limits.get("hint", 0) or 0),
        "coach": int(challenge_limits.get("coach", 0) or 0),
    }
    game.challenge_usage = {"undo": 0, "hint": 0, "coach": 0}
    ctx.active_games.set(ctx.game_id, game)
    ctx.game = game

    if ctx.engine.ready:
        visits = ctx.get_game_visits(level, len(game.moves))
        await ctx.run_in_executor(ctx.engine.set_visits, visits)
        await ctx.run_in_executor(ctx.engine.send_command, f"boardsize {size}")
        await ctx.run_in_executor(ctx.engine.send_command, "clear_board")
        await ctx.run_in_executor(ctx.engine.send_command, f"komi {komi}")
        rules = "chinese" if komi == 7.5 else "japanese"
        await ctx.run_in_executor(ctx.engine.send_command, f"kata-set-rules {rules}")

    if handicap > 0 and ctx.engine.ready:
        resp = await ctx.run_in_executor(ctx.engine.send_command, f"fixed_handicap {handicap}")
        if resp.startswith("="):
            for gtp in resp[1:].strip().split():
                coord = ctx.gtp_to_coord(gtp, size)
                if coord:
                    game.place_stone(coord[0], coord[1], "B")
                    game.moves.append(("B", gtp))
            game.current_player = "W"
    if challenge_beta and challenge_cards:
        await ctx.apply_challenge_rogue_loadout(game, ctx.send)
    game.reset_history()

    await ctx.send({"type": "game_start", **game.to_state()})

    ultimate = bool(data.get("ultimate", False))
    if ultimate and not two_player and ctx.engine.ready:
        game.ultimate = True
        choices = ctx.pick_ultimate_choices(3)
        cards_data = [ultimate_card_summary(cid) for cid in choices]
        await ctx.send({"type": "ultimate_offer", "cards": cards_data})
    elif rogue_enabled and (two_player or ctx.engine.ready):
        should_offer_rogue = True
        if challenge_beta and len(challenge_cards) >= max(1, challenge_stage):
            should_offer_rogue = False
        if should_offer_rogue:
            if challenge_beta:
                rogue_pool = [card_id for card_id in CHALLENGE_BETA_POOL if card_id not in challenge_cards]
                choices = ctx.pick_challenge_beta_choices(challenge_cards, 3, pool=rogue_pool)
            else:
                rogue_pool = TWO_PLAYER_ROGUE_POOL if two_player else None
                choices = ctx.pick_rogue_choices(3, pool=rogue_pool)
            game.challenge_offer_cards = choices if challenge_beta else []
            cards_data = [rogue_card_summary(cid) for cid in choices]
            await ctx.send(
                {
                    "type": "rogue_offer",
                    "cards": cards_data,
                    "challenge_beta": challenge_beta,
                    "challenge_stage": challenge_stage,
                    "refresh_remaining": challenge_refreshes,
                }
            )
        else:
            if ai_observer and ctx.engine.ready:
                asyncio.create_task(ctx.run_ai_observer_loop(game, ctx.send))
            elif not two_player and ctx.engine.ready and game.ai_color == game.current_player:
                await ctx.ai_move(game, ctx.send)
    else:
        if ai_observer and ctx.engine.ready:
            asyncio.create_task(ctx.run_ai_observer_loop(game, ctx.send))
        elif not two_player and ctx.engine.ready and game.ai_color == game.current_player:
            await ctx.ai_move(game, ctx.send)

    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_play(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over:
        await ctx.send_error("暂无进行中的对局")
        return
    if not game.two_player and game.rogue_card == "coach_mode" and game.rogue_coach_moves_left > 0:
        await ctx.send_error("代练上号接管中，请等待强化 AI 完成代打")
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
        await _handle_ultimate_play(ctx, game, data, color)
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

    point = _board_point_from_data(data, game.size)
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
    elif not game.two_player and ctx.engine.ready:
        if quickthink_bonus:
            await ctx.send({"type": "rogue_event", "msg": "⚡ 快速思考：2 秒追加手已开启"})
        else:
            await ctx.ai_move(game, ctx.send)

    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


async def _handle_ultimate_play(ctx: WebSocketActionContext, game: Any, data: dict, color: str) -> None:
    point = _board_point_from_data(data, game.size)
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
    game.ultimate_player_card = card_id
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
    elif ctx.engine.ready:
        await ctx.ultimate_ai_move(game, ctx.send)
    if not game.game_over and ctx.engine.ready:
        asyncio.create_task(ctx.do_analysis_bg(game))


WS_ACTION_HANDLERS: dict[str, Callable[[WebSocketActionContext, dict], Awaitable[None]]] = {
    "new_game": handle_new_game,
    "play": handle_play,
    "pass": handle_pass,
    "undo": handle_undo,
    "reconnect": handle_reconnect,
    "resign": handle_resign,
    "request_hint": handle_request_hint,
    "set_level": handle_set_level,
    "load_position": handle_load_position,
    "time_expired": handle_time_expired,
    "rogue_select_card": handle_rogue_select_card,
    "challenge_refresh_offer": handle_challenge_refresh_offer,
    "rogue_seal_point": handle_rogue_seal_point,
    "rogue_use_puppet": handle_rogue_use_puppet,
    "rogue_use_twin": handle_rogue_use_twin,
    "rogue_use_exchange": handle_rogue_use_exchange,
    "rogue_use_coach": handle_rogue_use_coach,
    "ultimate_select_card": handle_ultimate_select_card,
    "ultimate_quickthink_end": handle_ultimate_quickthink_end,
    "score": handle_score,
}
