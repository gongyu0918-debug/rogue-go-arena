from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn, SendFn

FinalizeAiMoveFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class AiFinishMoveDeps:
    finalize_ai_move: FinalizeAiMoveFn
    gtp_to_coord: Callable[..., Any]
    no_resign_move: Callable[[Any, str], Awaitable[str]]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    check_capture_foul: Callable[..., Awaitable[None]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    run_engine_command: EngineCommandFn
    run_coach_turn_if_needed: Callable[[Any, SendFn], Awaitable[None]]


async def finish_ai_move_event(
    game: Any,
    send_fn: SendFn,
    *,
    color: str,
    card: str | None,
    gtp_move: str,
    rogue_msg: str | None = None,
    deps: AiFinishMoveDeps,
) -> None:
    await deps.finalize_ai_move(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=gtp_move,
        rogue_msg=rogue_msg,
        gtp_to_coord=deps.gtp_to_coord,
        no_resign_move=deps.no_resign_move,
        retry_avoiding_ko=deps.retry_avoiding_ko,
        check_capture_foul=deps.check_capture_foul,
        prepare_player_turn_modifiers=deps.prepare_player_turn_modifiers,
        run_engine_command=deps.run_engine_command,
        run_coach_turn_if_needed=deps.run_coach_turn_if_needed,
    )
