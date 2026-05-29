from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
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
RandomFloatFn = Callable[[], float]
SuboptimalMoveFn = Callable[..., Awaitable[str | None]]
RestrictionFn = Callable[[Any, str, int], Any | None]
RngFactory = Callable[[], Any]
ChallengeZonePointsFn = Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
PickFogMaskFn = Callable[[int, Any], list[tuple[int, int]]]
PickFogPointFn = Callable[[Any, Any], list[tuple[int, int]]]
CoordFormatter = Callable[[int, int, int], str | None]
AdjacentPointsFn = Callable[[int, int, int], list[tuple[int, int]]]
ChoosePointFn = Callable[[list[tuple[int, int]]], tuple[int, int]]
ShufflePointsFn = Callable[[list[tuple[int, int]]], None]
PointListFn = Callable[[int], list[tuple[int, int]]]
SpawnBonusPointsFn = Callable[[Any, list[tuple[int, int]], str], list[tuple[int, int]]]
TrapBonusFn = Callable[[Any, AsyncSend, str], Awaitable[None]]
PickBestPointFn = Callable[[Any, str], Awaitable[tuple[int, int] | None]]
RogueHasFn = Callable[[Any, str], bool]
ErosionMessageFn = Callable[[int, float], str]
AllowedRestrictionMoveFn = Callable[
    [Any, str, int, float, list[tuple[int, int]]],
    Awaitable[str | None],
]
AvoidRestrictionMoveFn = Callable[
    [Any, str, int, float, list[tuple[int, int]]],
    Awaitable[str | None],
]
SuspiciousPassFn = Callable[[Any, str, str], bool]
FallbackMoveFn = Callable[[Any, str, int], Awaitable[str | None]]
LogFn = Callable[[str], None]
AnalyzePositionFn = Callable[[Any, str], Awaitable[dict[str, Any]]]
ChooseStyleMoveFn = Callable[..., str | None]
GenerateMoveFn = Callable[[str, int, float], Awaitable[str]]


@dataclass(frozen=True)
class AiMoveAdjustment:
    gtp_move: str
    needs_sync: bool = False
    message: str | None = None


@dataclass(frozen=True)
class AiMoveResolution:
    gtp_move: str
    completed: bool = False


@dataclass(frozen=True)
class AiMovePlacement:
    coord: tuple[int, int] | None
    captured: int = 0


def _unique_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    return [point for point in points if not (point in seen or seen.add(point))]


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


async def try_finish_shadow_restriction_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    rogue_cards: Collection[str],
    ai_move_count: int,
    visits: int,
    time_limit: float,
    roll_random: RandomFloatFn,
    choose_restriction: RestrictionFn,
    choose_allowed_move: AllowedRestrictionMoveFn,
    finish_ai_move: FinishAiMoveFn,
) -> bool:
    if "shadow" not in rogue_cards:
        return False
    if roll_random() >= gameplay_config.ROGUE_SHADOW_CHANCE:
        return False

    restriction = choose_restriction(game, color, ai_move_count)
    return await try_finish_allowed_restriction_move(
        game,
        send_fn,
        color=color,
        card=card,
        restriction=restriction,
        visits=visits,
        time_limit=time_limit,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )


async def refresh_fog_restriction_points(
    game: Any,
    send_fn: AsyncSend,
    *,
    rogue_cards: Collection[str],
    ai_move_count: int,
    make_rng: RngFactory,
    challenge_zone_points: ChallengeZonePointsFn,
    pick_fog_mask: PickFogMaskFn,
    pick_fog_point: PickFogPointFn,
) -> bool:
    if "fog" not in rogue_cards:
        return False

    rng = make_rng()
    if ai_move_count < gameplay_config.ROGUE_FOG_AI_MOVES:
        game.rogue_seal_points = challenge_zone_points(
            game,
            pick_fog_mask(game.size, rng),
        )
        fog_msg = "🌫 战争迷雾刷新：3×3 禁区本回合对 AI 禁止落子"
    else:
        fog_pts: list[tuple[int, int]] = []
        for _ in range(gameplay_config.ROGUE_FOG_POST_MASK_POINTS):
            fog_pts.extend(challenge_zone_points(game, pick_fog_point(game, rng)))
        game.rogue_seal_points = _unique_points(fog_pts)
        fog_msg = f"🌫 战争迷雾残留：本回合随机封锁 {gameplay_config.ROGUE_FOG_POST_MASK_POINTS} 个 AI 禁着点"

    await send_fn({"type": "game_state", **game.to_state()})
    if game.rogue_seal_points:
        await send_fn({"type": "rogue_event", "msg": fog_msg})
    return True


async def apply_suspicious_pass_fallback(
    game: Any,
    *,
    color: str,
    gtp_move: str,
    visits: int,
    is_suspicious_pass: SuspiciousPassFn,
    pick_fallback_move: FallbackMoveFn,
    log_event: LogFn,
    log_prefix: str,
) -> str:
    if not is_suspicious_pass(game, gtp_move, color):
        return gtp_move

    fallback_move = await pick_fallback_move(game, color, visits)
    if fallback_move:
        log_event(f"{log_prefix}, replaced with {fallback_move}")
        return fallback_move
    return gtp_move


def apply_ai_move_to_board(
    game: Any,
    *,
    color: str,
    gtp_move: str,
    gtp_to_coord: CoordParser,
) -> AiMovePlacement:
    game.moves.append((color, gtp_move))

    if gtp_move.upper() == "PASS":
        game.passed[color] = True
        return AiMovePlacement(coord=None)

    coord = gtp_to_coord(gtp_move, game.size)
    captured = 0
    if coord:
        captured = game.place_stone(coord[0], coord[1], color)
    game.passed[color] = False
    return AiMovePlacement(coord=coord, captured=captured)


async def try_apply_sansan_trap_counter(
    game: Any,
    send_fn: AsyncSend,
    *,
    card: str | None,
    coord: tuple[int, int] | None,
    stones: int,
    get_sansan_points: PointListFn,
    adjacent_points: AdjacentPointsFn,
    shuffle_points: ShufflePointsFn,
    spawn_bonus_points: SpawnBonusPointsFn,
    coord_to_gtp: CoordFormatter,
    apply_trap_bonus: TrapBonusFn,
) -> bool:
    if card != "sansan_trap" or coord is None:
        return False
    if coord not in get_sansan_points(game.size):
        return False

    nearby = [
        (nx, ny)
        for nx, ny in adjacent_points(coord[0], coord[1], game.size)
        if game.board[ny][nx] == 0
    ]
    shuffle_points(nearby)
    changed = spawn_bonus_points(game, nearby[:stones], game.player_color)
    if not changed:
        return False

    await send_fn({
        "type": "rogue_event",
        "msg": f"△ 三三陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} 相邻点反打 {len(changed)} 子",
    })
    await apply_trap_bonus(game, send_fn, "三三陷阱")
    return True


async def try_apply_no_regret_bonus(
    game: Any,
    send_fn: AsyncSend,
    *,
    chance: float,
    roll_random: RandomFloatFn,
    has_rogue_card: RogueHasFn,
    pick_best_point: PickBestPointFn,
    spawn_bonus_points: SpawnBonusPointsFn,
    coord_to_gtp: CoordFormatter,
) -> bool:
    if not has_rogue_card(game, "no_regret"):
        return False
    if roll_random() >= chance:
        return False
    if game.game_over:
        return False

    bonus = await pick_best_point(game, game.player_color)
    if not bonus:
        return False

    changed = spawn_bonus_points(game, [bonus], game.player_color)
    if not changed:
        return False

    await send_fn({
        "type": "rogue_event",
        "msg": f"🚫 永不悔棋发动，AI 落子后在 {coord_to_gtp(bonus[0], bonus[1], game.size)} 赠送一子",
    })
    return True


async def apply_erosion_komi_counter(
    game: Any,
    send_fn: AsyncSend,
    *,
    card: str | None,
    captured: int,
    shift_per_capture: float,
    run_engine_command: EngineCommandFn,
    message: ErosionMessageFn,
) -> bool:
    if card != "erosion" or captured <= 0:
        return False

    shift = shift_per_capture * captured
    if game.ai_color == "W":
        game.komi += shift
    else:
        game.komi -= shift
    await run_engine_command(f"komi {game.komi}")
    await send_fn({
        "type": "rogue_event",
        "msg": message(captured, game.komi),
    })
    return True


async def try_finalize_double_pass(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    gtp_move: str,
    run_engine_command: EngineCommandFn,
    rogue_msg: str | None = None,
) -> bool:
    if not (game.passed["B"] and game.passed["W"]):
        return False

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
    if rogue_msg:
        await send_fn({"type": "rogue_event", "msg": rogue_msg})
    await send_fn({
        "type": "game_over",
        "winner": winner,
        "score": score_str,
        "reason": "double_pass",
    })
    return True


async def send_ai_move_and_run_coach(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    gtp_move: str,
    coord: tuple[int, int] | None,
    rogue_msg: str | None = None,
    run_coach_turn_if_needed: RunCoachTurnFn,
) -> None:
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


async def choose_or_generate_ai_style_move(
    game: Any,
    *,
    color: str,
    visits: int,
    time_limit: float,
    style: str,
    analyze_position: AnalyzePositionFn,
    choose_style_move: ChooseStyleMoveFn,
    generate_move: GenerateMoveFn,
    gtp_to_coord: CoordParser,
    play_chosen_move: EngineCommandFn,
) -> str:
    chosen = await try_choose_ai_style_move(
        game,
        color=color,
        style=style,
        analyze_position=analyze_position,
        choose_style_move=choose_style_move,
        gtp_to_coord=gtp_to_coord,
    )

    if chosen:
        await play_chosen_move(f"play {color} {chosen}")
        return chosen

    resp = await generate_move(color, visits, time_limit)
    return resp.replace("=", "").strip()


async def try_choose_ai_style_move(
    game: Any,
    *,
    color: str,
    style: str,
    analyze_position: AnalyzePositionFn,
    choose_style_move: ChooseStyleMoveFn,
    gtp_to_coord: CoordParser,
) -> str | None:
    if style == "balanced":
        return None

    try:
        analysis = await analyze_position(game, color)
        return choose_style_move(
            game,
            color,
            analysis.get("top_moves", []),
            style,
            gtp_to_coord=gtp_to_coord,
        )
    except Exception:
        return None


def apply_slip_ai_move(
    game: Any,
    *,
    color: str,
    rogue_cards: Collection[str],
    gtp_move: str,
    roll_random: RandomFloatFn,
    choose_point: ChoosePointFn,
    gtp_to_coord: CoordParser,
    coord_to_gtp: CoordFormatter,
    adjacent_points: AdjacentPointsFn,
) -> AiMoveAdjustment:
    if "slip" not in rogue_cards or gtp_move.upper() in {"PASS", "RESIGN"}:
        return AiMoveAdjustment(gtp_move)
    if roll_random() >= gameplay_config.ROGUE_SLIP_CHANCE:
        return AiMoveAdjustment(gtp_move)

    original_gtp = gtp_move
    original_coord = gtp_to_coord(gtp_move, game.size)
    if not original_coord:
        return AiMoveAdjustment(gtp_move)

    nearby = [
        (nx, ny)
        for nx, ny in adjacent_points(original_coord[0], original_coord[1], game.size)
        if game.board[ny][nx] == 0 and game.is_legal_move(nx, ny, color)
    ]
    if not nearby:
        return AiMoveAdjustment(gtp_move)

    sx, sy = choose_point(nearby)
    slipped_gtp = coord_to_gtp(sx, sy, game.size)
    if slipped_gtp is None:
        return AiMoveAdjustment(gtp_move)
    return AiMoveAdjustment(
        slipped_gtp,
        needs_sync=True,
        message=f"手滑了触发，AI 原本想下 {original_gtp}，结果滑到 {slipped_gtp}",
    )


async def retry_ai_move_avoiding_ko(
    game: Any,
    *,
    color: str,
    gtp_move: str,
    rogue_msg: str | None,
    gtp_to_coord: CoordParser,
    retry_avoiding_ko: RetryAvoidingKoFn,
) -> AiMoveAdjustment:
    if gtp_move.upper() in {"PASS", "RESIGN"}:
        return AiMoveAdjustment(gtp_move, message=rogue_msg)

    coord = gtp_to_coord(gtp_move, game.size)
    if coord and game.is_ko(coord[0], coord[1], color):
        return AiMoveAdjustment(
            await retry_avoiding_ko(game, color),
            message=None,
        )

    return AiMoveAdjustment(gtp_move, message=rogue_msg)


async def resolve_ai_resign_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    gtp_move: str,
    rogue_cards: Collection[str],
    no_resign_move: NoResignMoveFn,
) -> AiMoveResolution:
    if gtp_move.upper() != "RESIGN":
        return AiMoveResolution(gtp_move)

    if rogue_cards:
        return AiMoveResolution(await no_resign_move(game, color))

    game.game_over = True
    game.winner = game.player_color
    await send_fn({
        "type": "game_over",
        "winner": game.player_color,
        "score": None,
        "reason": "ai_resign",
    })
    return AiMoveResolution(gtp_move, completed=True)


async def try_finish_suboptimal_rogue_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    rogue_cards: Collection[str],
    ai_move_count: int,
    visits: int,
    time_limit: float,
    roll_random: RandomFloatFn,
    choose_suboptimal_move: SuboptimalMoveFn,
    finish_ai_move: FinishAiMoveFn,
) -> bool:
    attempts = (
        (
            "nerf",
            gameplay_config.ROGUE_NERF_BACKUP_AI_MOVES,
            gameplay_config.ROGUE_NERF_BACKUP_CHANCE,
            1,
            5,
            "弱化触发，AI 在多个备选点里误选了一手",
        ),
        (
            "time_press",
            gameplay_config.ROGUE_TIME_PRESS_BACKUP_AI_MOVES,
            gameplay_config.ROGUE_TIME_PRESS_BACKUP_CHANCE,
            1,
            4,
            "限时压制触发，AI 仓促落在了备选点上",
        ),
        (
            "suboptimal",
            gameplay_config.ROGUE_SUBOPTIMAL_AI_MOVES,
            None,
            None,
            None,
            "次优之选触发，AI 采用了较弱备选点",
        ),
    )

    for card_id, max_ai_moves, chance, start_idx, end_idx, message in attempts:
        if card_id not in rogue_cards or ai_move_count >= max_ai_moves:
            continue
        if chance is not None and roll_random() >= chance:
            continue

        if start_idx is None or end_idx is None:
            gtp_move = await choose_suboptimal_move(game, color, visits, time_limit)
        else:
            gtp_move = await choose_suboptimal_move(
                game,
                color,
                visits,
                time_limit,
                start_idx=start_idx,
                end_idx=end_idx,
            )
        if gtp_move:
            await finish_ai_move(
                game,
                send_fn,
                color,
                card,
                gtp_move,
                message,
            )
            return True

    return False


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

    placement = apply_ai_move_to_board(
        game,
        color=color,
        gtp_move=gtp_move,
        gtp_to_coord=gtp_to_coord,
    )
    coord = placement.coord
    captured = placement.captured
    await check_capture_foul(game, send_fn, color, captured, ultimate=False)

    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)

    await apply_erosion_komi_counter(
        game,
        send_fn,
        card=card,
        captured=captured,
        shift_per_capture=gameplay_config.ROGUE_EROSION_SHIFT,
        run_engine_command=run_engine_command,
        message=lambda capture_count, komi: f"🐛 蚕食！AI 提 {capture_count} 子，贴目变为 {komi}",
    )

    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if await try_finalize_double_pass(
        game,
        send_fn,
        color=color,
        gtp_move=gtp_move,
        run_engine_command=run_engine_command,
    ):
        return

    await send_ai_move_and_run_coach(
        game,
        send_fn,
        color=color,
        gtp_move=gtp_move,
        coord=coord,
        rogue_msg=rogue_msg,
        run_coach_turn_if_needed=run_coach_turn_if_needed,
    )
