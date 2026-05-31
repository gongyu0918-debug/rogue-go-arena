from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from app.runtime.ws_actions import WebSocketActionContext
from app.runtime.ws_context import (
    WebSocketContextDeps,
    WEBSOCKET_CONTEXT_GROUP_SPECS,
    build_websocket_action_context,
    flatten_websocket_context_deps,
)


@dataclass(frozen=True)
class WebSocketContextBinding:
    active_games: Any
    engine: Any
    run_in_executor: Any
    GoGame: Any
    coord_to_gtp: Any
    gtp_to_coord: Any
    engine_state_snapshot: Any
    start_engine_background: Any
    get_game_visits: Any
    sync_board_to_katago: Any
    reload_live_card_config: Any
    pick_rogue_choices: Any
    pick_ultimate_choices: Any
    pick_challenge_beta_choices: Any
    pick_ai_rogue_card: Any
    pick_ai_ultimate_card: Any
    apply_challenge_rogue_loadout: Any
    activate_rogue_card: Any
    activate_ai_rogue_card: Any
    ai_move: Any
    ultimate_ai_move: Any
    ultimate_force_score: Any
    run_coach_turn_if_needed: Any
    run_ai_observer_loop: Any
    challenge_remaining: Any
    challenge_zone_points: Any
    rogue_has: Any
    get_ai_rogue_forbidden_points: Any
    ultimate_get_territory_forbidden: Any
    record_ultimate_player_action: Any
    check_capture_foul: Any
    count_stones: Any
    apply_ultimate_effect: Any
    resolve_pending_ultimate_shadow_links: Any
    apply_player_rogue_move_effects: Any
    apply_ai_rogue_response_effects: Any
    prepare_player_turn_modifiers: Any
    finish_ultimate_quickthink_turn: Any
    pick_joseki_targets: Any
    random_hidden_center: Any
    diamond_points: Any


def _build_group(binding: WebSocketContextBinding, group_type: type) -> Any:
    return group_type(**{field.name: getattr(binding, field.name) for field in fields(group_type)})


def build_websocket_context_deps(binding: WebSocketContextBinding) -> WebSocketContextDeps:
    return WebSocketContextDeps(**{
        group_name: _build_group(binding, group_type)
        for group_name, group_type in WEBSOCKET_CONTEXT_GROUP_SPECS
    })


def build_websocket_context_binding(deps: WebSocketContextDeps) -> WebSocketContextBinding:
    return WebSocketContextBinding(**flatten_websocket_context_deps(deps))


def build_websocket_action_context_from_binding(
    *,
    game_id: str,
    game: Any,
    send: Any,
    send_error: Any,
    do_analysis: Any,
    do_analysis_bg: Any,
    binding: WebSocketContextBinding,
) -> WebSocketActionContext:
    return build_websocket_action_context(
        game_id=game_id,
        game=game,
        send=send,
        send_error=send_error,
        do_analysis=do_analysis,
        do_analysis_bg=do_analysis_bg,
        deps=build_websocket_context_deps(binding),
    )
