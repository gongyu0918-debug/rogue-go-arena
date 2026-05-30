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
LoadoutFn = Callable[..., Any]
SyncEngineKomiFn = Callable[[Any], Awaitable[None]]
EmitSetBonusStatusFn = Callable[[Any, SendFn], Awaitable[None]]


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


@dataclass(frozen=True)
class ChallengeLoadoutFlowDeps:
    apply_loadout: LoadoutFn
    card_ids_fn: Callable[..., Any]
    get_rogue_card_fn: Callable[..., Any]
    active_use_bonus_fn: Callable[..., Any]
    challenge_zone_points_fn: Callable[..., Any]
    choose_corner: Callable[[], int]
    make_rng: Callable[[], Any]
    get_blackhole_points_fn: Callable[..., Any]
    get_golden_corner_points_fn: Callable[..., Any]
    pick_joseki_targets_fn: Callable[..., Any]
    random_hidden_center_fn: Callable[..., Any]
    diamond_points_fn: Callable[..., Any]
    golden_corner_span: int
    joseki_target_count: int
    godhand_radius: int
    sync_engine_komi: SyncEngineKomiFn
    emit_set_bonus_status: EmitSetBonusStatusFn


async def apply_challenge_rogue_loadout_event(
    game: Any,
    send_fn: SendFn,
    deps: ChallengeLoadoutFlowDeps,
) -> Any:
    result = deps.apply_loadout(
        game,
        card_ids_fn=deps.card_ids_fn,
        get_rogue_card_fn=deps.get_rogue_card_fn,
        active_use_bonus_fn=deps.active_use_bonus_fn,
        challenge_zone_points_fn=deps.challenge_zone_points_fn,
        choose_corner=deps.choose_corner,
        make_rng=deps.make_rng,
        get_blackhole_points_fn=deps.get_blackhole_points_fn,
        get_golden_corner_points_fn=deps.get_golden_corner_points_fn,
        pick_joseki_targets_fn=deps.pick_joseki_targets_fn,
        random_hidden_center_fn=deps.random_hidden_center_fn,
        diamond_points_fn=deps.diamond_points_fn,
        golden_corner_span=deps.golden_corner_span,
        joseki_target_count=deps.joseki_target_count,
        godhand_radius=deps.godhand_radius,
    )
    await deps.sync_engine_komi(game)
    await deps.emit_set_bonus_status(game, send_fn)
    return result


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
