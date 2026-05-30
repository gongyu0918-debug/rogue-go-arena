from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn, SendFn

TryFinishRestrictionFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class RestrictionRogueAiTurnDeps:
    try_finish_rogue_restriction_ai_move: TryFinishRestrictionFn
    choose_tengen_target: Callable[..., Any]
    tengen_followup_points: Callable[..., Any]
    gravity_allowed_points: Callable[..., Any]
    lowline_allowed_points: Callable[..., Any]
    sansan_opening_restriction: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    finalize_forced_stone: Callable[..., Awaitable[bool]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    choose_allowed_move: Callable[..., Awaitable[str | None]]
    choose_avoid_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]
    finish_allowed_restriction_move: Callable[..., Awaitable[bool]]
    finish_sansan_restriction_move: Callable[..., Awaitable[bool]]


async def try_finish_restriction_rogue_ai_turn_event(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    run_engine_command: EngineCommandFn,
    deps: RestrictionRogueAiTurnDeps,
) -> bool:
    return await deps.try_finish_rogue_restriction_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        choose_tengen_target=deps.choose_tengen_target,
        tengen_followup_points=deps.tengen_followup_points,
        gravity_allowed_points=deps.gravity_allowed_points,
        lowline_allowed_points=deps.lowline_allowed_points,
        sansan_opening_restriction=deps.sansan_opening_restriction,
        coord_to_gtp=deps.coord_to_gtp,
        finalize_forced_stone=deps.finalize_forced_stone,
        prepare_player_turn_modifiers=deps.prepare_player_turn_modifiers,
        run_engine_command=run_engine_command,
        choose_allowed_move=deps.choose_allowed_move,
        choose_avoid_move=deps.choose_avoid_move,
        finish_ai_move=deps.finish_ai_move,
        finish_allowed_restriction_move=deps.finish_allowed_restriction_move,
        finish_sansan_restriction_move=deps.finish_sansan_restriction_move,
    )
