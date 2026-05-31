from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn
from app.runtime.challenge_adapters import ChallengeFlowBinding, ChallengeLoadoutBinding


@dataclass(frozen=True)
class ChallengeFlowRuntimeFns:
    roll_random: Callable[[], float]
    weaken_rank_one_step: Callable[[str], str]
    engine_ready: Callable[[], bool]
    get_game_visits: Callable[..., int]
    run_in_executor: Callable[..., Awaitable[Any]]
    set_engine_visits: Callable[[int], Any]


@dataclass(frozen=True)
class ChallengeFlowTuning:
    trap_extra_turn_chance: float
    restriction_decay_chance: float
    rank_labels: Mapping[str, str]
    challenge_set_min_count: int


@dataclass(frozen=True)
class ChallengeLoadoutRuntimeFns:
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
    sync_engine_komi: Callable[[Any], Awaitable[None]]
    emit_set_bonus_status: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class ChallengeLoadoutTuning:
    golden_corner_span: int
    joseki_target_count: int
    godhand_radius: int


@dataclass(frozen=True)
class ChallengeRuntimeDependencies:
    flow_runtime: ChallengeFlowRuntimeFns
    flow_tuning: ChallengeFlowTuning
    loadout_runtime: ChallengeLoadoutRuntimeFns
    loadout_tuning: ChallengeLoadoutTuning


def build_challenge_flow_binding(
    dependencies: ChallengeRuntimeDependencies,
) -> ChallengeFlowBinding:
    return ChallengeFlowBinding(
        roll_random=dependencies.flow_runtime.roll_random,
        trap_extra_turn_chance=dependencies.flow_tuning.trap_extra_turn_chance,
        restriction_decay_chance=dependencies.flow_tuning.restriction_decay_chance,
        weaken_rank_one_step=dependencies.flow_runtime.weaken_rank_one_step,
        rank_labels=dependencies.flow_tuning.rank_labels,
        challenge_set_min_count=dependencies.flow_tuning.challenge_set_min_count,
        engine_ready=dependencies.flow_runtime.engine_ready,
        get_game_visits=dependencies.flow_runtime.get_game_visits,
        run_in_executor=dependencies.flow_runtime.run_in_executor,
        set_engine_visits=dependencies.flow_runtime.set_engine_visits,
    )


def build_challenge_loadout_binding(
    dependencies: ChallengeRuntimeDependencies,
) -> ChallengeLoadoutBinding:
    return ChallengeLoadoutBinding(
        apply_loadout=dependencies.loadout_runtime.apply_loadout,
        card_ids_fn=dependencies.loadout_runtime.card_ids_fn,
        get_rogue_card_fn=dependencies.loadout_runtime.get_rogue_card_fn,
        active_use_bonus_fn=dependencies.loadout_runtime.active_use_bonus_fn,
        challenge_zone_points_fn=dependencies.loadout_runtime.challenge_zone_points_fn,
        choose_corner=dependencies.loadout_runtime.choose_corner,
        make_rng=dependencies.loadout_runtime.make_rng,
        get_blackhole_points_fn=dependencies.loadout_runtime.get_blackhole_points_fn,
        get_golden_corner_points_fn=dependencies.loadout_runtime.get_golden_corner_points_fn,
        pick_joseki_targets_fn=dependencies.loadout_runtime.pick_joseki_targets_fn,
        random_hidden_center_fn=dependencies.loadout_runtime.random_hidden_center_fn,
        diamond_points_fn=dependencies.loadout_runtime.diamond_points_fn,
        golden_corner_span=dependencies.loadout_tuning.golden_corner_span,
        joseki_target_count=dependencies.loadout_tuning.joseki_target_count,
        godhand_radius=dependencies.loadout_tuning.godhand_radius,
        sync_engine_komi=dependencies.loadout_runtime.sync_engine_komi,
        emit_set_bonus_status=dependencies.loadout_runtime.emit_set_bonus_status,
    )
