from __future__ import annotations

import asyncio
from dataclasses import dataclass
import random
import time
from typing import Any, Awaitable, Callable, Optional

from app.config.gameplay import (
    ROGUE_COACH_BASE_TURNS,
    ROGUE_SEAL_POINT_COUNT,
    ULTIMATE_JOSEKI_TARGET_COUNT,
)
from app.data.cards import (
    CHALLENGE_BETA_POOL,
    ROGUE_CARDS,
    ULTIMATE_CARDS,
)


@dataclass
class WebSocketActionContext:
    game_id: str
    game: Optional[Any]
    active_games: Any
    engine: Any
    send: Callable[[dict], Awaitable[None]]
    send_error: Callable[[str], Awaitable[None]]
    do_analysis: Callable[[Any], Awaitable[dict]]
    do_analysis_bg: Callable[[Any], Awaitable[None]]
    run_in_executor: Callable[..., Awaitable[Any]]
    GoGame: type
    coord_to_gtp: Callable[[int, int, int], str]
    get_game_visits: Callable[[str, int, str], int]
    pick_challenge_beta_choices: Callable[..., list[str]]
    pick_ai_rogue_card: Callable[..., str]
    pick_ai_ultimate_card: Callable[..., str]
    apply_challenge_rogue_loadout: Callable[..., Awaitable[None]]
    activate_rogue_card: Callable[..., Awaitable[None]]
    activate_ai_rogue_card: Callable[..., Awaitable[None]]
    ai_move: Callable[..., Awaitable[None]]
    ultimate_ai_move: Callable[..., Awaitable[None]]
    ultimate_force_score: Callable[..., Awaitable[None]]
    run_coach_turn_if_needed: Callable[..., Awaitable[None]]
    sync_board_to_katago: Callable[..., Awaitable[None]]
    challenge_remaining: Callable[[Any, str], int]
    challenge_zone_points: Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
    rogue_has: Callable[[Any, str], bool]
    finish_ultimate_quickthink_turn: Callable[[Any], None]
    pick_joseki_targets: Callable[[int, int], list[tuple[int, int]]]
    random_hidden_center: Callable[[int, int, random.Random], tuple[int, int]]
    diamond_points: Callable[..., list[tuple[int, int]]]

    def restore_game(self) -> Any:
        if not self.game:
            self.game = self.active_games.get(self.game_id, touch=True)
        return self.game


async def handle_reconnect(ctx: WebSocketActionContext, data: dict) -> None:
    saved = ctx.active_games.get(ctx.game_id, touch=True)
    if saved:
        ctx.game = saved
        await ctx.send({"type": "reconnected", **ctx.game.to_state()})
        if not ctx.game.game_over and ctx.engine.ready:
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
    if not game or game.game_over or not ctx.engine.ready:
        return
    if ctx.rogue_has(game, "quickthink"):
        await ctx.send_error("快速思考已禁用推荐点位，请自行判断局面")
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
    size = int(data.get("size", 19))
    komi = float(data.get("komi", 7.5))
    moves_list = data.get("moves", [])

    if ctx.engine.ready:
        await ctx.run_in_executor(ctx.engine.send_command, f"boardsize {size}")
        await ctx.run_in_executor(ctx.engine.send_command, "clear_board")
        await ctx.run_in_executor(ctx.engine.send_command, f"komi {komi}")
        for move in moves_list:
            c, g = move[0], move[1]
            await ctx.run_in_executor(ctx.engine.send_command, f"play {c} {g}")

        next_color = "B" if len(moves_list) % 2 == 0 else "W"
        temp = ctx.GoGame(size, komi, 0, "B", "a3d")
        temp.current_player = next_color
        for move in moves_list:
            temp.moves.append((move[0], move[1]))
        temp.rebuild_board()

        result = await ctx.do_analysis(temp)
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
        await ctx.apply_challenge_rogue_loadout(game, ctx.send)
        await ctx.send(
            {
                "type": "rogue_card_selected",
                "card_id": card_id,
                "name": ROGUE_CARDS[card_id]["name"],
                "icon": ROGUE_CARDS[card_id]["icon"],
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
        c = ROGUE_CARDS[cid]
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
    x, y = int(data["x"]), int(data["y"])
    if (x, y) not in game.rogue_seal_points:
        game.rogue_seal_points.append((x, y))
    await ctx.send(
        {
            "type": "rogue_seal_update",
            "points": [[px, py] for px, py in game.rogue_seal_points],
            "remaining": ROGUE_SEAL_POINT_COUNT - len(game.rogue_seal_points),
        }
    )
    if len(game.rogue_seal_points) >= ROGUE_SEAL_POINT_COUNT:
        if game.challenge_beta:
            game.rogue_seal_points = ctx.challenge_zone_points(game, game.rogue_seal_points)
        game.rogue_waiting_seal = False
        game.reset_history()
        await ctx.send({"type": "rogue_seal_done"})
        if ctx.engine.ready and game.ai_color == game.current_player:
            await ctx.ai_move(game, ctx.send)
        if not game.game_over and ctx.engine.ready:
            asyncio.create_task(ctx.do_analysis_bg(game))


async def handle_rogue_use_puppet(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over or not ctx.engine.ready:
        return
    if game.rogue_card != "puppet" or game.rogue_uses.get("puppet", 0) <= 0:
        await ctx.send_error("傀儡术已用完")
        return
    if game.current_player != game.player_color:
        await ctx.send_error("还没轮到你")
        return
    x, y = int(data["x"]), int(data["y"])
    gtp = ctx.coord_to_gtp(x, y, game.size)
    if not (0 <= x < game.size and 0 <= y < game.size):
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
    if game.rogue_card != "exchange" or game.rogue_uses.get("exchange", 0) <= 0:
        await ctx.send_error("乾坤挪移已用完")
        return
    game.rogue_uses["exchange"] -= 1
    game.rogue_skip_ai = True
    await ctx.send({"type": "rogue_event", "msg": "🔄 乾坤挪移激活！AI 下次将被迫虚手"})
    await ctx.send({"type": "rogue_uses_update", "uses": game.rogue_uses})


async def handle_rogue_use_coach(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or game.game_over or not ctx.engine.ready:
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


async def handle_ultimate_select_card(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game or not game.ultimate:
        return
    card_id = data.get("card_id", "")
    if card_id not in ULTIMATE_CARDS:
        return
    game.ultimate_player_card = card_id
    game.ultimate_joseki_targets = []
    game.ultimate_joseki_hits = 0
    game.ultimate_joseki_done = False
    game.ultimate_godhand_center = None
    game.ultimate_godhand_trigger = []
    game.ultimate_godhand_done = False
    game.ultimate_corner_helper_done = set()
    game.ultimate_sanrensei_done = False
    game.ultimate_five_in_row_seen = set()
    game.ultimate_last_stand_done = {"B": False, "W": False}
    ctx.finish_ultimate_quickthink_turn(game)
    game.ultimate_fool_shapes = set()
    game.ultimate_shadow_clone_links = []
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
    pdef = ULTIMATE_CARDS[card_id]
    ai_card_id = ctx.pick_ai_ultimate_card(exclude=[card_id])
    game.ultimate_ai_card = ai_card_id
    adef = ULTIMATE_CARDS[ai_card_id]
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


async def handle_score(ctx: WebSocketActionContext, data: dict) -> None:
    game = ctx.restore_game()
    if not game:
        return
    if ctx.engine.ready:
        await ctx.sync_board_to_katago(game)
        resp = await ctx.run_in_executor(ctx.engine.send_command, "final_score")
        score_str = resp.replace("=", "").strip()
    else:
        score_str = "?"
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


WS_ACTION_HANDLERS: dict[str, Callable[[WebSocketActionContext, dict], Awaitable[None]]] = {
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
