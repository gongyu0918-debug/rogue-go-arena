from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn

TryFinishShadowFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class ShadowRogueAiTurnDeps:
    try_finish_shadow_restriction_move: TryFinishShadowFn
    roll_random: Callable[[], float]
    choose_restriction: Callable[[Any, str, int], Any | None]
    choose_allowed_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]


async def try_finish_shadow_rogue_ai_turn_event(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    deps: ShadowRogueAiTurnDeps,
) -> bool:
    return await deps.try_finish_shadow_restriction_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        roll_random=deps.roll_random,
        choose_restriction=deps.choose_restriction,
        choose_allowed_move=deps.choose_allowed_move,
        finish_ai_move=deps.finish_ai_move,
    )
