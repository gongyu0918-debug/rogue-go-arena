"""AI rally: keeps big Rogue leads contested.

When the player's lead (from the latest analysis) passes a threshold, the AI
plays one extra stone on its best point right after its own move, two when the
lead is twice the threshold. The threshold drops and the per-game cap rises in
later challenge stages, a cooldown spaces rallies out, and close games are
never touched. Unlike a komi change, the extra stone is on the board, so the
player sees it and can answer it.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config
from app.domain.event_text import event_text


@dataclass(frozen=True)
class RallyPlan:
    lead: float
    needed: float
    stones: int
    remaining_after: int


def rally_stage(game: Any) -> int:
    return max(1, int(getattr(game, "challenge_stage", 0) or 0))


def rally_lead_needed(stage: int) -> float:
    lead = gameplay_config.AI_RALLY_LEAD - gameplay_config.AI_RALLY_STAGE_STEP * (stage - 1)
    return max(gameplay_config.AI_RALLY_MIN_LEAD, lead)


def rally_cap(stage: int) -> int:
    if gameplay_config.AI_RALLY_MAX_PER_GAME <= 0:
        return 0
    return gameplay_config.AI_RALLY_MAX_PER_GAME + gameplay_config.AI_RALLY_STAGE_BONUS * (stage - 1)


def player_lead(game: Any) -> float | None:
    """The player's score lead from the latest analysis, or None if there is none."""
    analysis = getattr(game, "last_analysis", None) or {}
    score = analysis.get("score")
    if not analysis.get("analysis_ready") or not isinstance(score, (int, float)):
        return None
    return float(score) if game.player_color == "B" else -float(score)


def plan_ai_rally(game: Any) -> RallyPlan | None:
    if not getattr(game, "rogue_enabled", False):
        return None
    if any(getattr(game, flag, False) for flag in ("two_player", "game_over", "ai_observer", "ultimate")):
        return None
    stage = rally_stage(game)
    cap = rally_cap(stage)
    count = getattr(game, "ai_rally_count", 0)
    moves = len(getattr(game, "moves", []))
    if count >= cap or moves < gameplay_config.AI_RALLY_MIN_MOVES:
        return None
    last = getattr(game, "ai_rally_last_move", None)
    if last is not None and moves - last < gameplay_config.AI_RALLY_COOLDOWN_MOVES:
        return None
    lead = player_lead(game)
    needed = rally_lead_needed(stage)
    if lead is None or lead < needed:
        return None
    stones = 2 if lead >= 2 * needed else 1
    return RallyPlan(lead=lead, needed=needed, stones=stones, remaining_after=cap - count - 1)


async def try_apply_ai_rally(
    game: Any,
    send_fn: Callable[[dict], Awaitable[None]],
    *,
    pick_best_point: Callable[[Any, str], Awaitable[tuple[int, int] | None]],
    spawn_bonus_points: Callable[[Any, list[tuple[int, int]], str], list[tuple[int, int]]],
    sync_board_to_engine: Callable[[Any], Awaitable[None]],
    coord_to_gtp: Callable[..., Any],
) -> bool:
    plan = plan_ai_rally(game)
    if plan is None:
        return False
    placed: list[tuple[int, int]] = []
    for index in range(plan.stones):
        if index:
            await sync_board_to_engine(game)
        point = await pick_best_point(game, game.ai_color)
        if not point:
            break
        changed = spawn_bonus_points(game, [point], game.ai_color)
        if not changed:
            break
        placed.extend(changed)
    if not placed:
        return False
    game.ai_rally_count = getattr(game, "ai_rally_count", 0) + 1
    game.ai_rally_last_move = len(game.moves)
    points = [coord_to_gtp(x, y, game.size) for x, y in placed]
    lead = round(plan.lead)
    await send_fn({
        "type": "rogue_event",
        "msg": event_text(
            "ai.rally",
            f"⚡ AI 反扑！你领先 {lead} 目，AI 在 {'、'.join(points)} 追加 {len(placed)} 子，本局剩余 {plan.remaining_after} 次",
            lead=lead,
            points=points,
            count=len(placed),
            remaining=plan.remaining_after,
        ),
    })
    return True
