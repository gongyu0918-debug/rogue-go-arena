from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn

TryFinishSuboptimalFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class SuboptimalRogueAiTurnDeps:
    try_finish_suboptimal_rogue_move: TryFinishSuboptimalFn
    roll_random: Callable[[], float]
    choose_suboptimal_move: Callable[..., Awaitable[str | None]]
    finish_ai_move: Callable[..., Awaitable[None]]


async def try_finish_suboptimal_rogue_ai_turn_event(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    deps: SuboptimalRogueAiTurnDeps,
) -> bool:
    return await deps.try_finish_suboptimal_rogue_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        roll_random=deps.roll_random,
        choose_suboptimal_move=deps.choose_suboptimal_move,
        finish_ai_move=deps.finish_ai_move,
    )
