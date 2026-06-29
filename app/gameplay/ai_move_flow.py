from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config

from app.callback_types import EngineCommandFn, SendFn as AsyncSend
from app.gameplay.engine_errors import engine_error_message, is_engine_error_response
from app.gameplay.move_placement import AiMovePlacement


CoordParser = Callable[[str, int], tuple[int, int] | None]
NoResignMoveFn = Callable[[Any, str], Awaitable[str]]
RetryAvoidingKoFn = Callable[[Any, str], Awaitable[str]]
CheckCaptureFoulFn = Callable[..., Awaitable[None]]
PreparePlayerTurnFn = Callable[[Any], None]
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
ApplyMoveToBoardFn = Callable[..., "AiMovePlacement"]
SyncBoardFn = Callable[[Any], Awaitable[None]]
EngineReadyFn = Callable[[], bool]
SansanTrapCounterFn = Callable[..., Awaitable[bool]]
NoRegretBonusFn = Callable[..., Awaitable[bool]]
ErosionCounterFn = Callable[..., Awaitable[bool]]
DoublePassFn = Callable[..., Awaitable[bool]]
AiMoveResponseFn = Callable[..., Awaitable[None]]
PlacementEffectsFn = Callable[..., Awaitable["AiMovePlacement"]]
FinishAiTurnResponseFn = Callable[..., Awaitable[bool]]
AiMoveCandidateFn = Callable[..., Awaitable["AiMoveCandidate"]]
PrepareGeneratedAiMoveFn = Callable[..., Awaitable["AiMovePreparation"]]
FinishPreparedAiMoveFn = Callable[..., Awaitable[bool]]
MirrorCoordFn = Callable[[int, int, int], tuple[int, int]]
FinalizeForcedPassFn = Callable[..., Awaitable[None]]
FinalizeForcedStoneFn = Callable[..., Awaitable[bool]]
PuppetMoveFn = Callable[..., Awaitable[bool]]
AiCountPlanFn = Callable[[Any, int], Any | None]
AllowedRestrictionFinishFn = Callable[..., Awaitable[bool]]
SansanRestrictionFinishFn = Callable[..., Awaitable[bool]]
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
class AiMoveCandidate:
    gtp_move: str | None
    completed: bool = False
    error_message: str | None = None


@dataclass(frozen=True)
class AiMovePreparation:
    gtp_move: str | None
    needs_sync: bool = False
    message: str | None = None
    completed: bool = False


@dataclass(frozen=True)
class GeneratedMoveCandidateDeps:
    choose_candidate: AiMoveCandidateFn
    choose_avoid_move: AvoidRestrictionMoveFn
    analyze_position: AnalyzePositionFn
    choose_style_move: ChooseStyleMoveFn
    generate_move: GenerateMoveFn
    gtp_to_coord: CoordParser
    log_error: LogFn


@dataclass(frozen=True)
class GeneratedMovePreparationDeps:
    prepare_move: PrepareGeneratedAiMoveFn
    apply_suspicious_pass_fallback_fn: Callable[..., Awaitable[str]]
    is_suspicious_pass: SuspiciousPassFn
    pick_nonpass_fallback_move: FallbackMoveFn
    undo_engine_move: Callable[[], None] | None
    run_engine_command: EngineCommandFn | None
    log_event: LogFn
    resolve_resign_move: Callable[..., Awaitable[AiMoveResolution]]
    no_resign_move: NoResignMoveFn
    apply_slip_move: Callable[..., AiMoveAdjustment]
    roll_random: RandomFloatFn
    choose_point: ChoosePointFn
    gtp_to_coord: CoordParser
    coord_to_gtp: CoordFormatter
    adjacent_points: AdjacentPointsFn
    retry_ko_move: Callable[..., Awaitable[AiMoveAdjustment]]
    retry_avoiding_ko: RetryAvoidingKoFn


@dataclass(frozen=True)
class GeneratedMoveFinishDeps:
    finish_move: FinishPreparedAiMoveFn
    apply_placement_effects: PlacementEffectsFn
    finish_turn_response: FinishAiTurnResponseFn
    gtp_to_coord: CoordParser
    sync_board_to_engine: SyncBoardFn
    engine_is_ready: EngineReadyFn
    apply_move_to_board: ApplyMoveToBoardFn
    apply_sansan_trap_counter: SansanTrapCounterFn
    try_no_regret_bonus: NoRegretBonusFn
    trap_stones: int
    get_sansan_points: PointListFn
    adjacent_points: AdjacentPointsFn
    shuffle_points: ShufflePointsFn
    spawn_bonus_points: SpawnBonusPointsFn
    coord_to_gtp: CoordFormatter
    apply_trap_bonus: TrapBonusFn
    no_regret_chance: float
    roll_random: RandomFloatFn
    has_rogue_card: RogueHasFn
    pick_best_point: PickBestPointFn
    check_capture_foul: CheckCaptureFoulFn
    prepare_player_turn_modifiers: PreparePlayerTurnFn
    apply_erosion_counter: ErosionCounterFn
    erosion_shift: float
    run_erosion_command: EngineCommandFn
    erosion_message: ErosionMessageFn
    finalize_double_pass: DoublePassFn
    run_double_pass_command: EngineCommandFn
    send_ai_move_response: AiMoveResponseFn
    run_coach_turn_if_needed: RunCoachTurnFn


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
    check_capture_foul: CheckCaptureFoulFn | None = None,
    push_history: bool = True,
) -> bool:
    resp = await run_engine_command(f"play {color} {gtp_move}")
    if "?" in resp:
        return False

    x, y = coord
    game.moves.append((color, gtp_move))
    captured = game.place_stone(x, y, color)
    game.passed[color] = False
    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)
    if check_capture_foul is not None:
        await check_capture_foul(game, send_fn, color, captured, ultimate=False)
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


async def try_finish_forced_rogue_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    rogue_cards: Collection[str],
    roll_random: RandomFloatFn,
    dice_pass_chance: float,
    mirror_chance: float,
    gtp_to_coord: CoordParser,
    coord_to_gtp: CoordFormatter,
    mirror_coord: MirrorCoordFn,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    run_engine_command: EngineCommandFn,
    finalize_forced_pass: FinalizeForcedPassFn,
    finalize_forced_stone: FinalizeForcedStoneFn,
    apply_puppet_move: PuppetMoveFn,
    finish_ai_move: FinishAiMoveFn,
    check_capture_foul: CheckCaptureFoulFn | None = None,
) -> bool:
    if "dice" in rogue_cards and roll_random() < dice_pass_chance:
        await finalize_forced_pass(
            game,
            send_fn,
            color=color,
            message="掷骰触发，AI 这手选择虚手",
            prepare_player_turn_modifiers=prepare_player_turn_modifiers,
            run_engine_command=run_engine_command,
        )
        return True

    if "mirror" in rogue_cards and roll_random() < mirror_chance and game.moves:
        last_color, last_gtp = game.moves[-1]
        if last_color == game.player_color and last_gtp.upper() != "PASS":
            coord = gtp_to_coord(last_gtp, game.size)
            if coord:
                mx, my = mirror_coord(coord[0], coord[1], game.size)
                if game.board[my][mx] == 0 and not game.is_ko(mx, my, color):
                    mirror_gtp = coord_to_gtp(mx, my, game.size)
                    if await finalize_forced_stone(
                        game,
                        send_fn,
                        color=color,
                        gtp_move=mirror_gtp,
                        coord=(mx, my),
                        message=f"镜像触发，AI 在对称点 {mirror_gtp} 落子",
                        prepare_player_turn_modifiers=prepare_player_turn_modifiers,
                        run_engine_command=run_engine_command,
                        check_capture_foul=check_capture_foul,
                    ):
                        return True

    if "exchange" in rogue_cards and game.rogue_skip_ai:
        game.rogue_skip_ai = False
        await finalize_forced_pass(
            game,
            send_fn,
            color=color,
            message="乾坤挪移生效，AI 本回合虚手并把回合交还给你",
            prepare_player_turn_modifiers=prepare_player_turn_modifiers,
            run_engine_command=run_engine_command,
        )
        return True

    if "puppet" in rogue_cards and game.rogue_puppet_target is not None:
        return await apply_puppet_move(
            game,
            send_fn,
            color=color,
            card=card,
            target=game.rogue_puppet_target,
            coord_to_gtp=coord_to_gtp,
            run_engine_command=run_engine_command,
            finish_ai_move=finish_ai_move,
        )

    return False


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


async def try_finish_rogue_restriction_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    rogue_cards: Collection[str],
    ai_move_count: int,
    visits: int,
    time_limit: float,
    choose_tengen_target: AiCountPlanFn,
    tengen_followup_points: AiCountPlanFn,
    gravity_allowed_points: AiCountPlanFn,
    lowline_allowed_points: AiCountPlanFn,
    sansan_opening_restriction: AiCountPlanFn,
    coord_to_gtp: CoordFormatter,
    finalize_forced_stone: FinalizeForcedStoneFn,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    run_engine_command: EngineCommandFn,
    choose_allowed_move: AllowedRestrictionMoveFn,
    choose_avoid_move: AvoidRestrictionMoveFn,
    finish_ai_move: FinishAiMoveFn,
    finish_allowed_restriction_move: AllowedRestrictionFinishFn,
    finish_sansan_restriction_move: SansanRestrictionFinishFn,
    check_capture_foul: CheckCaptureFoulFn | None = None,
) -> bool:
    if "tengen" in rogue_cards:
        target_plan = choose_tengen_target(game, ai_move_count)
        if target_plan:
            tx, ty = target_plan.coord
            if game.board[ty][tx] == 0 and not game.is_ko(tx, ty, color):
                tengen_gtp = coord_to_gtp(tx, ty, game.size)
                if await finalize_forced_stone(
                    game,
                    send_fn,
                    color=color,
                    gtp_move=tengen_gtp,
                    coord=(tx, ty),
                    message=target_plan.message,
                    prepare_player_turn_modifiers=prepare_player_turn_modifiers,
                    run_engine_command=run_engine_command,
                    check_capture_foul=check_capture_foul,
                ):
                    return True
        restriction = tengen_followup_points(game, ai_move_count)
        if await finish_allowed_restriction_move(
            game,
            send_fn,
            color=color,
            card=card,
            restriction=restriction,
            visits=visits,
            time_limit=time_limit,
            choose_allowed_move=choose_allowed_move,
            finish_ai_move=finish_ai_move,
        ):
            return True

    if "gravity" in rogue_cards:
        restriction = gravity_allowed_points(game, ai_move_count)
        if await finish_allowed_restriction_move(
            game,
            send_fn,
            color=color,
            card=card,
            restriction=restriction,
            visits=visits,
            time_limit=time_limit,
            choose_allowed_move=choose_allowed_move,
            finish_ai_move=finish_ai_move,
        ):
            return True

    if "lowline" in rogue_cards:
        restriction = lowline_allowed_points(game, ai_move_count)
        if await finish_allowed_restriction_move(
            game,
            send_fn,
            color=color,
            card=card,
            restriction=restriction,
            visits=visits,
            time_limit=time_limit,
            choose_allowed_move=choose_allowed_move,
            finish_ai_move=finish_ai_move,
        ):
            return True

    if "sansan" in rogue_cards:
        restriction = sansan_opening_restriction(game, ai_move_count)
        if await finish_sansan_restriction_move(
            game,
            send_fn,
            color=color,
            card=card,
            restriction=restriction,
            visits=visits,
            time_limit=time_limit,
            choose_allowed_move=choose_allowed_move,
            choose_avoid_move=choose_avoid_move,
            finish_ai_move=finish_ai_move,
        ):
            return True

    return False


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
    color: str | None = None,
    make_rng: RngFactory,
    challenge_zone_points: ChallengeZonePointsFn,
    pick_fog_mask: PickFogMaskFn,
    pick_fog_point: PickFogPointFn,
    pick_best_point: PickBestPointFn | None = None,
    best_point_chance: float = gameplay_config.ROGUE_FOG_POST_BEST_POINT_CHANCE,
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
        if (
            gameplay_config.ROGUE_FOG_POST_MASK_POINTS > 0
            and color
            and pick_best_point is not None
            and rng.random() < best_point_chance
        ):
            best = await pick_best_point(game, color)
            if best and game.board[best[1]][best[0]] == 0:
                fog_pts.append(best)
        for _ in range(max(0, gameplay_config.ROGUE_FOG_POST_MASK_POINTS - len(fog_pts))):
            fog_pts.extend(pick_fog_point(game, rng))
        game.rogue_seal_points = _unique_points(fog_pts)[:gameplay_config.ROGUE_FOG_POST_MASK_POINTS]
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
    undo_engine_move: Callable[[], None] | None = None,
    run_engine_command: EngineCommandFn | None = None,
) -> str:
    if not is_suspicious_pass(game, gtp_move, color):
        return gtp_move

    undid_engine_pass = False
    if gtp_move.upper() == "PASS" and undo_engine_move is not None:
        try:
            undo_engine_move()
            undid_engine_pass = True
        except Exception as exc:
            log_event(f"{log_prefix}, engine undo before fallback failed: {exc}")
            return gtp_move

    fallback_move = await pick_fallback_move(game, color, visits)
    if fallback_move:
        if undid_engine_pass and run_engine_command is not None:
            await run_engine_command(f"play {color} {fallback_move}")
        log_event(f"{log_prefix}, replaced with {fallback_move}")
        return fallback_move
    if undid_engine_pass and run_engine_command is not None:
        restore_resp = await run_engine_command(f"play {color} pass")
        if restore_resp.startswith("?"):
            log_event(f"{log_prefix}, failed to restore PASS after fallback miss: {restore_resp}")
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
    if is_engine_error_response(resp_score) or not score_str or score_str[0] not in {"B", "W", "0"}:
        await send_fn({"type": "error", "message": f"AI 引擎数目失败：{resp_score}"})
        return False
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
        resp = await play_chosen_move(f"play {color} {chosen}")
        if is_engine_error_response(resp):
            return resp.strip()
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


async def choose_ai_move_candidate(
    game: Any,
    *,
    color: str,
    visits: int,
    time_limit: float,
    rogue_cards: Collection[str],
    forbidden: list[tuple[int, int]],
    choose_avoid_move: AvoidRestrictionMoveFn,
    analyze_position: AnalyzePositionFn,
    choose_style_move: ChooseStyleMoveFn,
    generate_move: GenerateMoveFn,
    gtp_to_coord: CoordParser,
    log_error: LogFn,
) -> AiMoveCandidate:
    if forbidden:
        gtp_move = await choose_avoid_move(game, color, visits, time_limit, forbidden)
        if not gtp_move:
            return AiMoveCandidate("pass")
        return AiMoveCandidate(gtp_move)

    gtp_move = None
    if not rogue_cards and game.ai_style != "balanced":
        gtp_move = await try_choose_ai_style_move(
            game,
            color=color,
            style=game.ai_style,
            analyze_position=analyze_position,
            choose_style_move=choose_style_move,
            gtp_to_coord=gtp_to_coord,
        )
    if gtp_move:
        return AiMoveCandidate(gtp_move)

    resp = await generate_move(color, visits, time_limit)
    if game.game_over:
        return AiMoveCandidate(None, completed=True)
    if is_engine_error_response(resp):
        log_error(f"[AI] genmove returned error: {resp}")
        return AiMoveCandidate(None, completed=True, error_message=engine_error_message(resp))
    return AiMoveCandidate(resp.replace("=", "").strip())


async def prepare_generated_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    gtp_move: str,
    visits: int,
    rogue_cards: Collection[str],
    apply_suspicious_pass_fallback_fn: Callable[..., Awaitable[str]],
    is_suspicious_pass: SuspiciousPassFn,
    pick_nonpass_fallback_move: FallbackMoveFn,
    log_event: LogFn,
    resolve_resign_move: Callable[..., Awaitable[AiMoveResolution]],
    no_resign_move: NoResignMoveFn,
    apply_slip_move: Callable[..., AiMoveAdjustment],
    roll_random: RandomFloatFn,
    choose_point: ChoosePointFn,
    gtp_to_coord: CoordParser,
    coord_to_gtp: CoordFormatter,
    adjacent_points: AdjacentPointsFn,
    retry_ko_move: Callable[..., Awaitable[AiMoveAdjustment]],
    retry_avoiding_ko: RetryAvoidingKoFn,
    undo_engine_move: Callable[[], None] | None = None,
    run_engine_command: EngineCommandFn | None = None,
    log_prefix: str = "Suspicious early PASS in rogue/normal mode",
) -> AiMovePreparation:
    gtp_move = await apply_suspicious_pass_fallback_fn(
        game,
        color=color,
        gtp_move=gtp_move,
        visits=visits,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_nonpass_fallback_move,
        undo_engine_move=undo_engine_move,
        run_engine_command=run_engine_command,
        log_event=log_event,
        log_prefix=log_prefix,
    )

    resign_result = await resolve_resign_move(
        game,
        send_fn,
        color=color,
        gtp_move=gtp_move,
        rogue_cards=rogue_cards,
        no_resign_move=no_resign_move,
    )
    if resign_result.completed:
        return AiMovePreparation(resign_result.gtp_move, completed=True)

    slip_result = apply_slip_move(
        game,
        color=color,
        rogue_cards=rogue_cards,
        gtp_move=resign_result.gtp_move,
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        adjacent_points=adjacent_points,
    )

    ko_result = await retry_ko_move(
        game,
        color=color,
        gtp_move=slip_result.gtp_move,
        rogue_msg=slip_result.message,
        gtp_to_coord=gtp_to_coord,
        retry_avoiding_ko=retry_avoiding_ko,
    )

    return AiMovePreparation(
        ko_result.gtp_move,
        needs_sync=slip_result.needs_sync,
        message=ko_result.message,
    )


async def apply_ai_move_placement_effects(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    gtp_move: str,
    needs_sync: bool,
    gtp_to_coord: CoordParser,
    sync_board_to_engine: SyncBoardFn,
    engine_is_ready: EngineReadyFn,
    apply_move_to_board: ApplyMoveToBoardFn,
    apply_sansan_trap_counter: SansanTrapCounterFn,
    try_no_regret_bonus: NoRegretBonusFn,
    trap_stones: int,
    get_sansan_points: PointListFn,
    adjacent_points: AdjacentPointsFn,
    shuffle_points: ShufflePointsFn,
    spawn_bonus_points: SpawnBonusPointsFn,
    coord_to_gtp: CoordFormatter,
    apply_trap_bonus: TrapBonusFn,
    no_regret_chance: float,
    roll_random: RandomFloatFn,
    has_rogue_card: RogueHasFn,
    pick_best_point: PickBestPointFn,
) -> AiMovePlacement:
    placement = apply_move_to_board(
        game,
        color=color,
        gtp_move=gtp_move,
        gtp_to_coord=gtp_to_coord,
    )
    extra_board_change = await apply_sansan_trap_counter(
        game,
        send_fn,
        card=card,
        coord=placement.coord,
        stones=trap_stones,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )

    if (needs_sync or extra_board_change) and engine_is_ready():
        await sync_board_to_engine(game)
        needs_sync = False
        extra_board_change = False

    if await try_no_regret_bonus(
        game,
        send_fn,
        chance=no_regret_chance,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=coord_to_gtp,
    ):
        extra_board_change = True

    if needs_sync or extra_board_change:
        await sync_board_to_engine(game)

    return placement


async def finish_prepared_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    prepared_move: AiMovePreparation,
    apply_placement_effects: PlacementEffectsFn,
    finish_turn_response: FinishAiTurnResponseFn,
    gtp_to_coord: CoordParser,
    sync_board_to_engine: SyncBoardFn,
    engine_is_ready: EngineReadyFn,
    apply_move_to_board: ApplyMoveToBoardFn,
    apply_sansan_trap_counter: SansanTrapCounterFn,
    try_no_regret_bonus: NoRegretBonusFn,
    trap_stones: int,
    get_sansan_points: PointListFn,
    adjacent_points: AdjacentPointsFn,
    shuffle_points: ShufflePointsFn,
    spawn_bonus_points: SpawnBonusPointsFn,
    coord_to_gtp: CoordFormatter,
    apply_trap_bonus: TrapBonusFn,
    no_regret_chance: float,
    roll_random: RandomFloatFn,
    has_rogue_card: RogueHasFn,
    pick_best_point: PickBestPointFn,
    check_capture_foul: CheckCaptureFoulFn,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    apply_erosion_counter: ErosionCounterFn,
    erosion_shift: float,
    run_erosion_command: EngineCommandFn,
    erosion_message: ErosionMessageFn,
    finalize_double_pass: DoublePassFn,
    run_double_pass_command: EngineCommandFn,
    send_ai_move_response: AiMoveResponseFn,
    run_coach_turn_if_needed: RunCoachTurnFn,
) -> bool:
    if prepared_move.completed or prepared_move.gtp_move is None:
        return True

    placement = await apply_placement_effects(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=prepared_move.gtp_move,
        needs_sync=prepared_move.needs_sync,
        gtp_to_coord=gtp_to_coord,
        sync_board_to_engine=sync_board_to_engine,
        engine_is_ready=engine_is_ready,
        apply_move_to_board=apply_move_to_board,
        apply_sansan_trap_counter=apply_sansan_trap_counter,
        try_no_regret_bonus=try_no_regret_bonus,
        trap_stones=trap_stones,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
        no_regret_chance=no_regret_chance,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
    )

    return await finish_turn_response(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=prepared_move.gtp_move,
        coord=placement.coord,
        captured=placement.captured,
        rogue_msg=prepared_move.message,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn_modifiers,
        apply_erosion_counter=apply_erosion_counter,
        erosion_shift=erosion_shift,
        run_erosion_command=run_erosion_command,
        erosion_message=erosion_message,
        finalize_double_pass=finalize_double_pass,
        run_double_pass_command=run_double_pass_command,
        send_ai_move_response=send_ai_move_response,
        run_coach_turn_if_needed=run_coach_turn_if_needed,
    )


async def try_finish_generated_ai_move(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    rogue_cards: Collection[str],
    forbidden: list[tuple[int, int]],
    visits: int,
    time_limit: float,
    candidate_deps: GeneratedMoveCandidateDeps,
    preparation_deps: GeneratedMovePreparationDeps,
    finish_deps: GeneratedMoveFinishDeps,
) -> bool:
    candidate = await candidate_deps.choose_candidate(
        game,
        color=color,
        visits=visits,
        time_limit=time_limit,
        rogue_cards=rogue_cards,
        forbidden=forbidden,
        choose_avoid_move=candidate_deps.choose_avoid_move,
        analyze_position=candidate_deps.analyze_position,
        choose_style_move=candidate_deps.choose_style_move,
        generate_move=candidate_deps.generate_move,
        gtp_to_coord=candidate_deps.gtp_to_coord,
        log_error=candidate_deps.log_error,
    )
    if candidate.completed:
        if candidate.error_message:
            await send_fn({"type": "error", "message": candidate.error_message})
        return True

    prepared_move = await preparation_deps.prepare_move(
        game,
        send_fn,
        color=color,
        gtp_move=candidate.gtp_move,
        visits=visits,
        rogue_cards=rogue_cards,
        apply_suspicious_pass_fallback_fn=preparation_deps.apply_suspicious_pass_fallback_fn,
        is_suspicious_pass=preparation_deps.is_suspicious_pass,
        pick_nonpass_fallback_move=preparation_deps.pick_nonpass_fallback_move,
        log_event=preparation_deps.log_event,
        resolve_resign_move=preparation_deps.resolve_resign_move,
        no_resign_move=preparation_deps.no_resign_move,
        apply_slip_move=preparation_deps.apply_slip_move,
        roll_random=preparation_deps.roll_random,
        choose_point=preparation_deps.choose_point,
        gtp_to_coord=preparation_deps.gtp_to_coord,
        coord_to_gtp=preparation_deps.coord_to_gtp,
        adjacent_points=preparation_deps.adjacent_points,
        retry_ko_move=preparation_deps.retry_ko_move,
        retry_avoiding_ko=preparation_deps.retry_avoiding_ko,
        undo_engine_move=preparation_deps.undo_engine_move,
        run_engine_command=preparation_deps.run_engine_command,
    )

    return await finish_deps.finish_move(
        game,
        send_fn,
        color=color,
        card=card,
        prepared_move=prepared_move,
        apply_placement_effects=finish_deps.apply_placement_effects,
        finish_turn_response=finish_deps.finish_turn_response,
        gtp_to_coord=finish_deps.gtp_to_coord,
        sync_board_to_engine=finish_deps.sync_board_to_engine,
        engine_is_ready=finish_deps.engine_is_ready,
        apply_move_to_board=finish_deps.apply_move_to_board,
        apply_sansan_trap_counter=finish_deps.apply_sansan_trap_counter,
        try_no_regret_bonus=finish_deps.try_no_regret_bonus,
        trap_stones=finish_deps.trap_stones,
        get_sansan_points=finish_deps.get_sansan_points,
        adjacent_points=finish_deps.adjacent_points,
        shuffle_points=finish_deps.shuffle_points,
        spawn_bonus_points=finish_deps.spawn_bonus_points,
        coord_to_gtp=finish_deps.coord_to_gtp,
        apply_trap_bonus=finish_deps.apply_trap_bonus,
        no_regret_chance=finish_deps.no_regret_chance,
        roll_random=finish_deps.roll_random,
        has_rogue_card=finish_deps.has_rogue_card,
        pick_best_point=finish_deps.pick_best_point,
        check_capture_foul=finish_deps.check_capture_foul,
        prepare_player_turn_modifiers=finish_deps.prepare_player_turn_modifiers,
        apply_erosion_counter=finish_deps.apply_erosion_counter,
        erosion_shift=finish_deps.erosion_shift,
        run_erosion_command=finish_deps.run_erosion_command,
        erosion_message=finish_deps.erosion_message,
        finalize_double_pass=finish_deps.finalize_double_pass,
        run_double_pass_command=finish_deps.run_double_pass_command,
        send_ai_move_response=finish_deps.send_ai_move_response,
        run_coach_turn_if_needed=finish_deps.run_coach_turn_if_needed,
    )


async def finish_ai_turn_response(
    game: Any,
    send_fn: AsyncSend,
    *,
    color: str,
    card: str | None,
    gtp_move: str,
    coord: tuple[int, int] | None,
    captured: int,
    rogue_msg: str | None,
    check_capture_foul: CheckCaptureFoulFn,
    prepare_player_turn_modifiers: PreparePlayerTurnFn,
    apply_erosion_counter: ErosionCounterFn,
    erosion_shift: float,
    run_erosion_command: EngineCommandFn,
    erosion_message: ErosionMessageFn,
    finalize_double_pass: DoublePassFn,
    run_double_pass_command: EngineCommandFn,
    send_ai_move_response: AiMoveResponseFn,
    run_coach_turn_if_needed: RunCoachTurnFn,
) -> bool:
    game.current_player = game.player_color
    prepare_player_turn_modifiers(game)
    await check_capture_foul(game, send_fn, color, captured, ultimate=False)

    await apply_erosion_counter(
        game,
        send_fn,
        card=card,
        captured=captured,
        shift_per_capture=erosion_shift,
        run_engine_command=run_erosion_command,
        message=erosion_message,
    )

    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if await finalize_double_pass(
        game,
        send_fn,
        color=color,
        gtp_move=gtp_move,
        run_engine_command=run_double_pass_command,
        rogue_msg=rogue_msg,
    ):
        return True

    await send_ai_move_response(
        game,
        send_fn,
        color=color,
        gtp_move=gtp_move,
        coord=coord,
        rogue_msg=rogue_msg,
        run_coach_turn_if_needed=run_coach_turn_if_needed,
    )
    return False


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
            if is_engine_error_response(gtp_move):
                await send_fn({"type": "error", "message": engine_error_message(gtp_move)})
                return
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

    if is_engine_error_response(gtp_move):
        await send_fn({"type": "error", "message": engine_error_message(gtp_move)})
        return

    coord = gtp_to_coord(gtp_move, game.size)
    if coord and gtp_move.upper() != "PASS" and game.is_ko(coord[0], coord[1], color):
        gtp_move = await retry_avoiding_ko(game, color)
        if is_engine_error_response(gtp_move):
            await send_fn({"type": "error", "message": engine_error_message(gtp_move)})
            return
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
