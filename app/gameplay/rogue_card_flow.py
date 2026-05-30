from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
GetCardFn = Callable[[str], dict[str, Any]]
PlayerActivationFn = Callable[..., Any]
AiActivationFn = Callable[..., Any]
SyncEngineKomiFn = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class RogueCardActivationFlowDeps:
    get_card: GetCardFn
    apply_activation: PlayerActivationFn
    coord_to_gtp: Callable[..., Any]
    choose_corner: Callable[[], int]
    make_rng: Callable[[], Any]
    get_blackhole_points: Callable[..., Any]
    get_golden_corner_points: Callable[..., Any]
    pick_joseki_targets: Callable[..., Any]
    random_hidden_center: Callable[..., Any]
    diamond_points: Callable[..., Any]
    sync_engine_komi: SyncEngineKomiFn


@dataclass(frozen=True)
class AiRogueCardActivationFlowDeps:
    get_card: GetCardFn
    apply_activation: AiActivationFn
    choose_corner: Callable[[], int]
    get_blackhole_points: Callable[..., Any]
    get_golden_corner_points: Callable[..., Any]
    refresh_ai_rogue_player_turn: Callable[[Any], Any]
    golden_corner_span: int


async def activate_rogue_card_event(
    game: Any,
    send_fn: SendFn,
    card_id: str,
    deps: RogueCardActivationFlowDeps,
) -> Any:
    card_def = deps.get_card(card_id)
    result = deps.apply_activation(
        game,
        card_id,
        card_def,
        coord_to_gtp=deps.coord_to_gtp,
        choose_corner=deps.choose_corner,
        make_rng=deps.make_rng,
        get_blackhole_points_fn=deps.get_blackhole_points,
        get_golden_corner_points_fn=deps.get_golden_corner_points,
        pick_joseki_targets_fn=deps.pick_joseki_targets,
        random_hidden_center_fn=deps.random_hidden_center,
        diamond_points_fn=deps.diamond_points,
    )
    for message in result.messages:
        await send_fn({"type": "rogue_event", "msg": message})
    if result.sync_komi:
        await deps.sync_engine_komi(game)

    await send_fn({
        "type": "rogue_card_selected",
        "card_id": card_id,
        "name": card_def["name"],
        "icon": card_def["icon"],
        "waiting_seal": card_id == "seal",
        **game.to_state(),
    })
    return result


async def activate_ai_rogue_card_event(
    game: Any,
    send_fn: SendFn,
    card_id: str,
    deps: AiRogueCardActivationFlowDeps,
) -> None:
    card_def = deps.get_card(card_id)
    deps.apply_activation(
        game,
        card_id,
        choose_corner=deps.choose_corner,
        get_blackhole_points_fn=deps.get_blackhole_points,
        get_golden_corner_points_fn=deps.get_golden_corner_points,
        refresh_ai_rogue_player_turn_fn=deps.refresh_ai_rogue_player_turn,
        golden_corner_span=deps.golden_corner_span,
    )

    await send_fn({
        "type": "rogue_ai_selected",
        "card_id": card_id,
        "name": card_def["name"],
        "icon": card_def["icon"],
        **game.to_state(),
    })
