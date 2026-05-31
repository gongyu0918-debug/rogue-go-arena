from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.runtime.rogue_activation_adapters import (
    AiRogueCardActivationBinding,
    RogueCardActivationBinding,
)


@dataclass(frozen=True)
class RogueActivationEffectFns:
    get_card: Callable[[str], dict[str, Any]]
    apply_player_activation: Callable[..., Any]
    apply_ai_activation: Callable[..., Any]


@dataclass(frozen=True)
class RogueActivationRuntimeFns:
    coord_to_gtp: Callable[..., Any]
    choose_corner: Callable[[], int]
    make_rng: Callable[[], Any]
    get_blackhole_points: Callable[..., Any]
    get_golden_corner_points: Callable[..., Any]
    pick_joseki_targets: Callable[..., Any]
    random_hidden_center: Callable[..., Any]
    diamond_points: Callable[..., Any]
    sync_engine_komi: Callable[[Any], Awaitable[None]]
    refresh_ai_rogue_player_turn: Callable[[Any], Any]


@dataclass(frozen=True)
class RogueActivationTuning:
    golden_corner_span: int


@dataclass(frozen=True)
class RogueActivationDependencies:
    effects: RogueActivationEffectFns
    runtime: RogueActivationRuntimeFns
    tuning: RogueActivationTuning


def build_rogue_card_activation_binding(
    dependencies: RogueActivationDependencies,
) -> RogueCardActivationBinding:
    return RogueCardActivationBinding(
        get_card=dependencies.effects.get_card,
        apply_activation=dependencies.effects.apply_player_activation,
        coord_to_gtp=dependencies.runtime.coord_to_gtp,
        choose_corner=dependencies.runtime.choose_corner,
        make_rng=dependencies.runtime.make_rng,
        get_blackhole_points=dependencies.runtime.get_blackhole_points,
        get_golden_corner_points=dependencies.runtime.get_golden_corner_points,
        pick_joseki_targets=dependencies.runtime.pick_joseki_targets,
        random_hidden_center=dependencies.runtime.random_hidden_center,
        diamond_points=dependencies.runtime.diamond_points,
        sync_engine_komi=dependencies.runtime.sync_engine_komi,
    )


def build_ai_rogue_card_activation_binding(
    dependencies: RogueActivationDependencies,
) -> AiRogueCardActivationBinding:
    return AiRogueCardActivationBinding(
        get_card=dependencies.effects.get_card,
        apply_activation=dependencies.effects.apply_ai_activation,
        choose_corner=dependencies.runtime.choose_corner,
        get_blackhole_points=dependencies.runtime.get_blackhole_points,
        get_golden_corner_points=dependencies.runtime.get_golden_corner_points,
        refresh_ai_rogue_player_turn=dependencies.runtime.refresh_ai_rogue_player_turn,
        golden_corner_span=dependencies.tuning.golden_corner_span,
    )
