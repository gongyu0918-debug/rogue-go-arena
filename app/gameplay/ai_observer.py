from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.engine_errors import engine_error_message, is_engine_error_response

from app.callback_types import EngineCommandFn as RunEngineCommandFn, SendFn

SyncBoardFn = Callable[[Any], Awaitable[None]]
GameVisitsFn = Callable[[str, int], int]
GenerateMoveFn = Callable[[Any, str, int, float], Awaitable[str]]
SuspiciousPassFn = Callable[[Any, str, str], bool]
FallbackMoveFn = Callable[[Any, str, int], Awaitable[str | None]]
PlaceMoveFn = Callable[[Any, str, str], Any]
FinishDoublePassFn = Callable[[Any, SendFn], Awaitable[bool]]
SleepFn = Callable[[float], Awaitable[None]]
CoordParser = Callable[[str, int], tuple[int, int] | None]
PlaceAuxiliaryMoveFn = Callable[[Any, str, str, tuple[int, int] | None], Any]


@dataclass(frozen=True)
class AiObserverLoopDeps:
    engine_ready: Callable[[], bool]
    sync_board: SyncBoardFn
    get_game_visits: GameVisitsFn
    generate_ai_style_move: GenerateMoveFn
    is_suspicious_ai_pass: SuspiciousPassFn
    pick_nonpass_fallback_move: FallbackMoveFn
    run_engine_command: RunEngineCommandFn
    place_ai_move_on_board: PlaceMoveFn
    finish_double_pass: FinishDoublePassFn
    sleep: SleepFn
    opening_move_threshold: int


async def finish_observer_double_pass(
    game: Any,
    send_fn: SendFn,
    *,
    run_engine_command: RunEngineCommandFn,
) -> bool:
    if not (game.passed["B"] and game.passed["W"]):
        return False

    resp_score = await run_engine_command("final_score")
    score_str = resp_score.replace("=", "").strip()
    winner = "B" if score_str.startswith("B") else "W"
    game.game_over = True
    game.winner = winner
    await send_fn(
        {
            "type": "game_over",
            "winner": winner,
            "score": score_str,
            "reason": "double_pass",
        }
    )
    return True


def apply_observer_ai_move_to_board(
    game: Any,
    color: str,
    gtp_move: str,
    *,
    gtp_to_coord: CoordParser,
    place_auxiliary_move: PlaceAuxiliaryMoveFn,
) -> Any:
    coord = gtp_to_coord(gtp_move, game.size)
    return place_auxiliary_move(game, color, gtp_move, coord)


async def run_ai_observer_loop(
    game: Any,
    send_fn: SendFn,
    deps: AiObserverLoopDeps,
) -> None:
    while not game.game_over and game.ai_observer and deps.engine_ready():
        await deps.sync_board(game)
        color = game.current_player
        level = game.ai_level_black if color == "B" else game.ai_level_white
        visits = deps.get_game_visits(level, len(game.moves))
        time_limit = 4.0 if len(game.moves) < deps.opening_move_threshold else 8.0
        gtp_move = await deps.generate_ai_style_move(game, color, visits, time_limit)
        if is_engine_error_response(gtp_move):
            await send_fn({"type": "error", "message": engine_error_message(gtp_move)})
            break
        if deps.is_suspicious_ai_pass(game, gtp_move, color):
            undid_engine_pass = False
            if gtp_move.upper() == "PASS":
                undo_resp = await deps.run_engine_command("undo")
                undid_engine_pass = not undo_resp.startswith("?")
            fallback_move = await deps.pick_nonpass_fallback_move(game, color, visits)
            if fallback_move:
                if undid_engine_pass:
                    await deps.run_engine_command(f"play {color} {fallback_move}")
                gtp_move = fallback_move
            elif undid_engine_pass:
                await deps.run_engine_command(f"play {color} pass")

        placement = deps.place_ai_move_on_board(game, color, gtp_move)
        coord = placement.coord
        await send_fn(
            {
                "type": "ai_move",
                "gtp": gtp_move,
                "color": color,
                "x": coord[0] if coord else None,
                "y": coord[1] if coord else None,
            }
        )
        game.current_player = "W" if color == "B" else "B"
        game.push_history()
        await send_fn({"type": "game_state", **game.to_state()})
        if await deps.finish_double_pass(game, send_fn):
            break
        await deps.sleep(0.35)
