from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.rogue_card_flow import (
    AiRogueCardActivationFlowDeps,
    RogueCardActivationFlowDeps,
    activate_ai_rogue_card_event,
    activate_rogue_card_event,
)


SendFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class RogueCardActivationBinding:
    get_card: Callable[[str], dict[str, Any]]
    apply_activation: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    choose_corner: Callable[[], int]
    make_rng: Callable[[], Any]
    get_blackhole_points: Callable[..., Any]
    get_golden_corner_points: Callable[..., Any]
    pick_joseki_targets: Callable[..., Any]
    random_hidden_center: Callable[..., Any]
    diamond_points: Callable[..., Any]
    sync_engine_komi: Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class AiRogueCardActivationBinding:
    get_card: Callable[[str], dict[str, Any]]
    apply_activation: Callable[..., Any]
    choose_corner: Callable[[], int]
    get_blackhole_points: Callable[..., Any]
    get_golden_corner_points: Callable[..., Any]
    refresh_ai_rogue_player_turn: Callable[[Any], Any]
    golden_corner_span: int


def build_rogue_card_activation_deps(binding: RogueCardActivationBinding) -> RogueCardActivationFlowDeps:
    return RogueCardActivationFlowDeps(
        get_card=binding.get_card,
        apply_activation=binding.apply_activation,
        coord_to_gtp=binding.coord_to_gtp,
        choose_corner=binding.choose_corner,
        make_rng=binding.make_rng,
        get_blackhole_points=binding.get_blackhole_points,
        get_golden_corner_points=binding.get_golden_corner_points,
        pick_joseki_targets=binding.pick_joseki_targets,
        random_hidden_center=binding.random_hidden_center,
        diamond_points=binding.diamond_points,
        sync_engine_komi=binding.sync_engine_komi,
    )


def build_ai_rogue_card_activation_deps(
    binding: AiRogueCardActivationBinding,
) -> AiRogueCardActivationFlowDeps:
    return AiRogueCardActivationFlowDeps(
        get_card=binding.get_card,
        apply_activation=binding.apply_activation,
        choose_corner=binding.choose_corner,
        get_blackhole_points=binding.get_blackhole_points,
        get_golden_corner_points=binding.get_golden_corner_points,
        refresh_ai_rogue_player_turn=binding.refresh_ai_rogue_player_turn,
        golden_corner_span=binding.golden_corner_span,
    )


async def activate_rogue_card(
    game: Any,
    send_fn: SendFn,
    card_id: str,
    binding: RogueCardActivationBinding,
) -> Any:
    return await activate_rogue_card_event(
        game,
        send_fn,
        card_id,
        build_rogue_card_activation_deps(binding),
    )


async def activate_ai_rogue_card(
    game: Any,
    send_fn: SendFn,
    card_id: str,
    binding: AiRogueCardActivationBinding,
) -> None:
    await activate_ai_rogue_card_event(
        game,
        send_fn,
        card_id,
        build_ai_rogue_card_activation_deps(binding),
    )
