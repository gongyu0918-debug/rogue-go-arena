from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.gameplay.challenge_effects import (
    apply_challenge_level_decay,
    apply_challenge_trap_bonus,
    challenge_set_bonus_status_message,
)


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
RunInExecutorFn = Callable[..., Awaitable[Any]]
RandomFloatFn = Callable[[], float]
WeakenRankFn = Callable[[str], str]
VisitsFn = Callable[..., int]
SetVisitsFn = Callable[[int], Any]


@dataclass(frozen=True)
class ChallengeFlowDeps:
    roll_random: RandomFloatFn
    trap_extra_turn_chance: float
    restriction_decay_chance: float
    weaken_rank_one_step: WeakenRankFn
    rank_labels: Mapping[str, str]
    challenge_set_min_count: int
    engine_ready: Callable[[], bool]
    get_game_visits: VisitsFn
    run_in_executor: RunInExecutorFn
    set_engine_visits: SetVisitsFn


async def apply_challenge_trap_bonus_event(
    game: Any,
    send_fn: SendFn,
    source_name: str,
    deps: ChallengeFlowDeps,
) -> None:
    message = apply_challenge_trap_bonus(
        game,
        source_name,
        roll_random=deps.roll_random,
        chance=deps.trap_extra_turn_chance,
    )
    if message:
        await send_fn({"type": "rogue_event", "msg": message})


async def maybe_reduce_challenge_ai_level(
    game: Any,
    send_fn: SendFn,
    deps: ChallengeFlowDeps,
) -> None:
    result = apply_challenge_level_decay(
        game,
        roll_random=deps.roll_random,
        weaken_rank_one_step=deps.weaken_rank_one_step,
        rank_labels=deps.rank_labels,
        chance=deps.restriction_decay_chance,
    )
    if result is None:
        return

    if deps.engine_ready():
        visits = deps.get_game_visits(game.level, len(game.moves), mode="rogue")
        await deps.run_in_executor(deps.set_engine_visits, visits)

    await send_fn({"type": "rogue_event", "msg": result.message})


async def emit_challenge_set_bonus_status(
    game: Any,
    send_fn: SendFn,
    deps: ChallengeFlowDeps,
) -> None:
    message = challenge_set_bonus_status_message(
        game,
        min_count=deps.challenge_set_min_count,
    )
    if message:
        await send_fn({"type": "rogue_event", "msg": message})
