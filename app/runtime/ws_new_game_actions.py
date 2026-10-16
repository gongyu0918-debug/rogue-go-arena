from __future__ import annotations

import asyncio
from collections.abc import Mapping

import app.config.gameplay as gameplay_config
from app.config.gameplay import AI_STYLE_OPTIONS, RANK_VISITS
from app.data.cards import (
    CHALLENGE_BETA_POOL,
    TWO_PLAYER_ROGUE_POOL,
    rogue_card_summary,
    ultimate_card_summary,
)
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.game_input_validation import (
    VALID_BOARD_SIZES,
    VALID_HANDICAPS,
    normalize_komi,
    normalize_rules,
    payload_int,
)
from app.domain.event_text import event_text
from app.gameplay.card_komi import settle_card_komi
from app.gameplay.run_curve import clamp_stage, run_stage_setup
from app.gameplay.difficulty import (
    difficulty_points,
    komi_for_ai_points,
    normalize_difficulty,
    plain_game_setup,
)
from app.runtime.gtp_safety import normalize_gtp_color
from app.runtime.ws_session_actions import (
    claim_engine_session,
    release_engine_session,
    wait_for_engine_ready,
)


async def handle_new_game(ctx: WebSocketActionContext, data: dict) -> None:
    config_errors = ctx.reload_live_card_config()
    if config_errors:
        await ctx.send_error(event_text(
            "error.config.load_failed", "卡牌配置加载失败：" + "；".join(config_errors[:6]),
            detail="; ".join(config_errors[:6])))
        return

    if data.get("ultimate") and not gameplay_config.ULTIMATE_ENABLED:
        await ctx.send_error(event_text("error.setup.ultimate_archived", "大招对战已归档，暂不可用"))
        return

    size = payload_int(data.get("size", 19), 19)
    komi = normalize_komi(data.get("komi", 7.5))
    handicap = payload_int(data.get("handicap", 0), 0)
    player_color = normalize_gtp_color(data.get("player_color", "B"))
    level = str(data.get("level", gameplay_config.STANDARD_AI_LEVEL))
    if level not in RANK_VISITS:
        level = gameplay_config.STANDARD_AI_LEVEL
    two_player = bool(data.get("two_player", False))
    ai_observer = bool(data.get("ai_observer", False)) and not two_player
    if ai_observer:
        two_player = False
    rogue_enabled = bool(data.get("rogue", False))
    ai_rogue_enabled = bool(data.get("ai_rogue", False)) and rogue_enabled and not two_player
    challenge_beta = bool(data.get("challenge_beta", False))
    challenge_stage = payload_int(data.get("challenge_stage", 0) or 0, 0)
    raw_challenge_cards = data.get("challenge_cards", [])
    if not isinstance(raw_challenge_cards, (list, tuple)):
        await ctx.send_error(event_text("error.challenge.invalid_cards", "闯关卡牌设置无效"))
        return
    challenge_cards = [
        card_id for card_id in raw_challenge_cards
        if card_id in CHALLENGE_BETA_POOL
    ]
    challenge_limits = data.get("challenge_limits", {}) or {}
    if not isinstance(challenge_limits, Mapping):
        await ctx.send_error(event_text("error.challenge.invalid_limits", "闯关次数设置无效"))
        return
    challenge_refreshes = payload_int(data.get("challenge_refreshes", 0) or 0, 0)
    rules = normalize_rules(data.get("rules"))
    if challenge_beta:
        rules = "chinese"
        two_player = False
        ai_observer = False
        rogue_enabled = True
        ai_rogue_enabled = False
        challenge_stage = clamp_stage(challenge_stage)
    if size not in VALID_BOARD_SIZES:
        await ctx.send_error(event_text("error.setup.invalid_board", "棋盘尺寸无效"))
        return
    if komi is None:
        await ctx.send_error(event_text("error.setup.invalid_komi", "贴目设置无效"))
        return
    if player_color is None:
        await ctx.send_error(event_text("error.setup.invalid_color", "执棋颜色无效"))
        return
    if handicap not in VALID_HANDICAPS:
        await ctx.send_error(event_text("error.setup.invalid_handicap", "让子设置无效"))
        return
    ctx.active_games.prune()
    if not ctx.engine.ready and not two_player:
        if not await wait_for_engine_ready(ctx, "game_start"):
            return

    ai_style = str(data.get("ai_style", "balanced"))
    if ai_style not in AI_STYLE_OPTIONS:
        ai_style = "balanced"
    if rogue_enabled or challenge_beta:
        # Card games always face the standard AI; difficulty comes from komi and stones.
        level = gameplay_config.STANDARD_AI_LEVEL
    # A difficulty replaces the manual komi/handicap; without one (Advanced setup)
    # the player's own values stand.
    difficulty = normalize_difficulty(data.get("difficulty"))
    if two_player or ai_observer:
        difficulty = None
    if challenge_beta:
        # Runs: the player is White; the stage curve plus difficulty set the AI's head start.
        run = run_stage_setup(challenge_stage, difficulty_points(difficulty) if difficulty else 0.0)
        handicap, komi, player_color = run.handicap, run.komi, "W"
    elif difficulty and player_color is not None:
        if rogue_enabled:
            ai_color = "W" if player_color == "B" else "B"
            komi = komi_for_ai_points(difficulty_points(difficulty), ai_color)
            handicap = 0
        else:
            plain = plain_game_setup(difficulty, player_color)
            handicap, komi, player_color = plain.handicap, plain.komi, plain.player_color
    ai_level_black = str(data.get("ai_level_black", level))
    if ai_level_black not in RANK_VISITS and ai_level_black != gameplay_config.STANDARD_AI_LEVEL:
        ai_level_black = level
    ai_level_white = str(data.get("ai_level_white", level))
    if ai_level_white not in RANK_VISITS and ai_level_white != gameplay_config.STANDARD_AI_LEVEL:
        ai_level_white = level
    ai_style_black = str(data.get("ai_style_black", ai_style))
    if ai_style_black not in AI_STYLE_OPTIONS:
        ai_style_black = ai_style
    ai_style_white = str(data.get("ai_style_white", ai_style))
    if ai_style_white not in AI_STYLE_OPTIONS:
        ai_style_white = ai_style

    game = ctx.GoGame(size, komi, handicap, player_color, level, two_player)
    game.ai_observer = ai_observer
    game.difficulty = difficulty
    game.rules = rules
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
        "undo": payload_int(challenge_limits.get("undo", 0) or 0, 0),
        "hint": payload_int(challenge_limits.get("hint", 0) or 0, 0),
        "coach": payload_int(challenge_limits.get("coach", 0) or 0, 0),
    }
    game.challenge_usage = {"undo": 0, "hint": 0, "coach": 0}
    if challenge_beta and challenge_cards:
        # Cards carried over from earlier stages are charged before the first move.
        settle_card_komi(game)
        komi = game.komi
    if not await claim_engine_session(ctx):
        return
    try:
        ctx.active_games.set(ctx.game_id, game)
    except Exception:
        release_engine_session(ctx)
        raise
    ctx.game = game

    if ctx.engine.ready:
        visits = ctx.get_game_visits(level, len(game.moves))
        await ctx.run_in_executor(ctx.engine.set_visits, visits)
        await ctx.run_in_executor(ctx.engine.send_command, f"boardsize {size}")
        await ctx.run_in_executor(ctx.engine.send_command, "clear_board")
        await ctx.run_in_executor(ctx.engine.send_command, f"komi {komi}")
        # The player's choice, independent of komi (6.5 no longer implies Japanese).
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
        game.ultimate_offer_cards = list(choices)
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
            game.rogue_offer_cards = [] if challenge_beta else list(choices)
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
