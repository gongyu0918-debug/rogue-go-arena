from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn
from app.gameplay.engine_errors import engine_error_message, is_engine_error_response

GameVisitsFn = Callable[..., int]
GenerateMoveFn = Callable[[Any, str, int, float], Awaitable[str]]
CoordParser = Callable[[str, int], tuple[int, int] | None]
RetryAvoidingKoFn = Callable[[Any, str], Awaitable[str]]
ChooseCoachMoveFn = Callable[[Any, str], Awaitable[tuple[str, tuple[int, int] | None]]]
PlaceAuxiliaryMoveFn = Callable[[Any, str, str, tuple[int, int] | None], Any]
CheckCaptureFoulFn = Callable[..., Awaitable[None]]
ApplyPlayerEffectsFn = Callable[[Any, SendFn, int, int, str, int], Awaitable[None]]
ApplyAiResponseEffectsFn = Callable[[Any, SendFn, int, int, str], Awaitable[None]]
EstimateWinrateFn = Callable[[Any, str], Awaitable[float]]
AiMoveFn = Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class CoachMoveChoiceDeps:
    get_game_visits: GameVisitsFn
    generate_ai_style_move: GenerateMoveFn
    gtp_to_coord: CoordParser
    retry_avoiding_ko: RetryAvoidingKoFn
    coach_visits: int
    max_move_time: float


@dataclass(frozen=True)
class CoachTurnDeps:
    engine_ready: Callable[[], bool]
    choose_coach_ai_move: ChooseCoachMoveFn
    place_auxiliary_move: PlaceAuxiliaryMoveFn
    check_capture_foul: CheckCaptureFoulFn
    apply_player_rogue_move_effects: ApplyPlayerEffectsFn
    apply_ai_rogue_response_effects: ApplyAiResponseEffectsFn
    estimate_side_winrate: EstimateWinrateFn
    ai_move: AiMoveFn
    bonus_threshold: float
    bonus_turns: int


async def choose_coach_ai_move(
    game: Any,
    color: str,
    deps: CoachMoveChoiceDeps,
) -> tuple[str, tuple[int, int] | None]:
    visits = max(
        deps.coach_visits,
        deps.get_game_visits(game.level, len(game.moves), mode="rogue"),
    )
    time_limit = min(deps.max_move_time, 8.0)
    gtp_move = await deps.generate_ai_style_move(game, color, visits, time_limit)
    if gtp_move.upper() == "RESIGN":
        gtp_move = "pass"

    coord = deps.gtp_to_coord(gtp_move, game.size)
    if coord and gtp_move.upper() != "PASS" and game.is_ko(coord[0], coord[1], color):
        gtp_move = await deps.retry_avoiding_ko(game, color)
        coord = (
            deps.gtp_to_coord(gtp_move, game.size)
            if gtp_move.upper() not in ("PASS", "RESIGN")
            else None
        )

    return gtp_move, coord


async def run_coach_turn_if_needed(
    game: Any,
    send_fn: SendFn,
    deps: CoachTurnDeps,
) -> None:
    if (
        game.game_over
        or game.two_player
        or game.current_player != game.player_color
        or game.rogue_card != "coach_mode"
        or game.rogue_coach_moves_left <= 0
        or not deps.engine_ready()
    ):
        return

    color = game.player_color
    gtp_move, coord = await deps.choose_coach_ai_move(game, color)
    if is_engine_error_response(gtp_move):
        await send_fn({"type": "error", "message": engine_error_message(gtp_move)})
        return
    placement = deps.place_auxiliary_move(game, color, gtp_move, coord)
    coord = placement.coord
    captured = placement.captured
    game.current_player = game.ai_color
    game.rogue_coach_moves_left = max(0, game.rogue_coach_moves_left - 1)

    await deps.check_capture_foul(game, send_fn, color, captured, ultimate=False)
    if coord:
        await deps.apply_player_rogue_move_effects(game, send_fn, coord[0], coord[1], color, captured)
        await deps.apply_ai_rogue_response_effects(game, send_fn, coord[0], coord[1], color)

    game.push_history()
    await send_fn(
        {
            "type": "ai_move",
            "gtp": gtp_move,
            "color": color,
            "x": coord[0] if coord else None,
            "y": coord[1] if coord else None,
        }
    )
    await send_fn(
        {
            "type": "rogue_event",
            "msg": f"🎓 代练上号：强化 AI 接管了一手，剩余 {game.rogue_coach_moves_left} 手",
        }
    )
    await send_fn({"type": "game_state", **game.to_state()})

    if game.rogue_coach_moves_left == 0 and not game.rogue_coach_bonus_checked:
        game.rogue_coach_bonus_checked = True
        if await deps.estimate_side_winrate(game, color) < deps.bonus_threshold:
            game.rogue_coach_moves_left += deps.bonus_turns
            await send_fn(
                {
                    "type": "rogue_event",
                    "msg": f"🎓 代练上号追加触发：胜率仍低于 50%，额外再代打 {deps.bonus_turns} 手",
                }
            )

    if not game.game_over and deps.engine_ready() and game.current_player == game.ai_color:
        await deps.ai_move(game, send_fn)
