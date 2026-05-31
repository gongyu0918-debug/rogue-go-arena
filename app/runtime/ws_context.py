from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, get_type_hints

from app.runtime.ws_action_context import WebSocketActionContext


@dataclass(frozen=True)
class WebSocketRuntimeDeps:
    active_games: Any
    engine: Any
    run_in_executor: Any
    GoGame: Any
    coord_to_gtp: Any
    gtp_to_coord: Any


@dataclass(frozen=True)
class WebSocketEngineDeps:
    engine_state_snapshot: Any
    start_engine_background: Any
    get_game_visits: Any
    sync_board_to_katago: Any


@dataclass(frozen=True)
class WebSocketCardSelectionDeps:
    reload_live_card_config: Any
    pick_rogue_choices: Any
    pick_ultimate_choices: Any
    pick_challenge_beta_choices: Any
    pick_ai_rogue_card: Any
    pick_ai_ultimate_card: Any


@dataclass(frozen=True)
class WebSocketModeFlowDeps:
    apply_challenge_rogue_loadout: Any
    activate_rogue_card: Any
    activate_ai_rogue_card: Any
    ai_move: Any
    ultimate_ai_move: Any
    ultimate_force_score: Any
    run_coach_turn_if_needed: Any
    run_ai_observer_loop: Any


@dataclass(frozen=True)
class WebSocketRuleEffectDeps:
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


@dataclass(frozen=True)
class WebSocketContextDeps:
    runtime: WebSocketRuntimeDeps
    engine_control: WebSocketEngineDeps
    card_selection: WebSocketCardSelectionDeps
    mode_flow: WebSocketModeFlowDeps
    rule_effects: WebSocketRuleEffectDeps

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        for group in _websocket_context_groups(self):
            try:
                return getattr(group, name)
            except AttributeError:
                continue
        raise AttributeError(name)


WEBSOCKET_CONTEXT_GROUP_NAMES = tuple(
    field.name for field in fields(WebSocketContextDeps)
)
_WEBSOCKET_CONTEXT_TYPE_HINTS = get_type_hints(WebSocketContextDeps)
WEBSOCKET_CONTEXT_GROUP_SPECS = tuple(
    (field.name, _WEBSOCKET_CONTEXT_TYPE_HINTS[field.name])
    for field in fields(WebSocketContextDeps)
)
WEBSOCKET_CONTEXT_GROUP_TYPES = tuple(
    group_type for _group_name, group_type in WEBSOCKET_CONTEXT_GROUP_SPECS
)


def _websocket_context_field_names() -> tuple[str, ...]:
    return tuple(
        field.name
        for group_type in WEBSOCKET_CONTEXT_GROUP_TYPES
        for field in fields(group_type)
    )


WEBSOCKET_CONTEXT_FIELD_NAMES = _websocket_context_field_names()


def _websocket_context_groups(deps: WebSocketContextDeps) -> tuple[Any, ...]:
    groups = []
    for name, _group_type in WEBSOCKET_CONTEXT_GROUP_SPECS:
        try:
            groups.append(object.__getattribute__(deps, name))
        except AttributeError:
            continue
    return tuple(groups)


def flatten_websocket_context_deps(deps: WebSocketContextDeps) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for group in _websocket_context_groups(deps):
        values.update({field.name: getattr(group, field.name) for field in fields(group)})
    return values


def build_websocket_action_context(
    *,
    game_id: str,
    game: Any,
    send: Any,
    send_error: Any,
    do_analysis: Any,
    do_analysis_bg: Any,
    deps: WebSocketContextDeps,
) -> WebSocketActionContext:
    return WebSocketActionContext(
        game_id=game_id,
        game=game,
        send=send,
        send_error=send_error,
        do_analysis=do_analysis,
        do_analysis_bg=do_analysis_bg,
        **flatten_websocket_context_deps(deps),
    )
