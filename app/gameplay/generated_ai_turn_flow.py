from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import DepsFactory, EngineCommandFn, FinishDepsFactory, SendFn

RogueForbiddenPointsFn = Callable[..., list[tuple[int, int]]]
ChallengeZonePointsFn = Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
TryFinishGeneratedFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class GeneratedAiTurnDeps:
    rogue_forbidden_points: RogueForbiddenPointsFn
    challenge_zone_points: ChallengeZonePointsFn
    try_finish_generated_ai_move: TryFinishGeneratedFn
    candidate_deps: DepsFactory
    preparation_deps: DepsFactory
    finish_deps: FinishDepsFactory


async def try_finish_generated_ai_turn_event(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    run_engine_command: EngineCommandFn,
    deps: GeneratedAiTurnDeps,
) -> bool:
    forbidden = deps.rogue_forbidden_points(
        game,
        turn.rogue_cards,
        turn.ai_move_count,
        challenge_zone_points=deps.challenge_zone_points,
    )

    return await deps.try_finish_generated_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        forbidden=forbidden,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        candidate_deps=deps.candidate_deps(),
        preparation_deps=deps.preparation_deps(),
        finish_deps=deps.finish_deps(run_engine_command),
    )
