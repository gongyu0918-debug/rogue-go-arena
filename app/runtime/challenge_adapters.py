from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.gameplay.challenge_flow import (
    ChallengeFlowDeps,
    ChallengeLoadoutFlowDeps,
    apply_challenge_rogue_loadout_event,
    apply_challenge_trap_bonus_event,
    emit_challenge_set_bonus_status,
    maybe_reduce_challenge_ai_level,
)


@dataclass(frozen=True)
class ChallengeFlowBinding:
    roll_random: Callable[[], float]
    trap_extra_turn_chance: float
    restriction_decay_chance: float
    weaken_rank_one_step: Callable[[str], str]
    rank_labels: Mapping[str, str]
    challenge_set_min_count: int
    engine_ready: Callable[[], bool]
    get_game_visits: Callable[..., int]
    run_in_executor: Callable[..., Awaitable[Any]]
    set_engine_visits: Callable[[int], Any]


@dataclass(frozen=True)
class ChallengeLoadoutBinding:
    apply_loadout: Callable[..., Any]
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
    sync_engine_komi: Callable[[Any], Awaitable[None]]
    emit_set_bonus_status: Callable[[Any, Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]


def build_challenge_flow_deps(binding: ChallengeFlowBinding) -> ChallengeFlowDeps:
    return ChallengeFlowDeps(
        roll_random=binding.roll_random,
        trap_extra_turn_chance=binding.trap_extra_turn_chance,
        restriction_decay_chance=binding.restriction_decay_chance,
        weaken_rank_one_step=binding.weaken_rank_one_step,
        rank_labels=binding.rank_labels,
        challenge_set_min_count=binding.challenge_set_min_count,
        engine_ready=binding.engine_ready,
        get_game_visits=binding.get_game_visits,
        run_in_executor=binding.run_in_executor,
        set_engine_visits=binding.set_engine_visits,
    )


def build_challenge_loadout_flow_deps(binding: ChallengeLoadoutBinding) -> ChallengeLoadoutFlowDeps:
    return ChallengeLoadoutFlowDeps(
        apply_loadout=binding.apply_loadout,
        card_ids_fn=binding.card_ids_fn,
        get_rogue_card_fn=binding.get_rogue_card_fn,
        active_use_bonus_fn=binding.active_use_bonus_fn,
        challenge_zone_points_fn=binding.challenge_zone_points_fn,
        choose_corner=binding.choose_corner,
        make_rng=binding.make_rng,
        get_blackhole_points_fn=binding.get_blackhole_points_fn,
        get_golden_corner_points_fn=binding.get_golden_corner_points_fn,
        pick_joseki_targets_fn=binding.pick_joseki_targets_fn,
        random_hidden_center_fn=binding.random_hidden_center_fn,
        diamond_points_fn=binding.diamond_points_fn,
        golden_corner_span=binding.golden_corner_span,
        joseki_target_count=binding.joseki_target_count,
        godhand_radius=binding.godhand_radius,
        sync_engine_komi=binding.sync_engine_komi,
        emit_set_bonus_status=binding.emit_set_bonus_status,
    )


async def apply_challenge_trap_bonus(
    game: Any,
    send_fn: Callable[[dict[str, Any]], Awaitable[None]],
    source_name: str,
    binding: ChallengeFlowBinding,
) -> None:
    await apply_challenge_trap_bonus_event(
        game,
        send_fn,
        source_name,
        build_challenge_flow_deps(binding),
    )


async def maybe_reduce_challenge_level(
    game: Any,
    send_fn: Callable[[dict[str, Any]], Awaitable[None]],
    binding: ChallengeFlowBinding,
) -> None:
    await maybe_reduce_challenge_ai_level(
        game,
        send_fn,
        build_challenge_flow_deps(binding),
    )


async def emit_challenge_set_status(
    game: Any,
    send_fn: Callable[[dict[str, Any]], Awaitable[None]],
    binding: ChallengeFlowBinding,
) -> None:
    await emit_challenge_set_bonus_status(
        game,
        send_fn,
        build_challenge_flow_deps(binding),
    )


async def apply_challenge_loadout(
    game: Any,
    send_fn: Callable[[dict[str, Any]], Awaitable[None]],
    binding: ChallengeLoadoutBinding,
) -> Any:
    return await apply_challenge_rogue_loadout_event(
        game,
        send_fn,
        build_challenge_loadout_flow_deps(binding),
    )
