from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import server as s
from app.runtime.ws_context import (
    WEBSOCKET_CONTEXT_FIELD_NAMES,
    WEBSOCKET_CONTEXT_GROUP_SPECS,
    WebSocketContextDeps,
    build_websocket_action_context,
    flatten_websocket_context_deps,
)
from app.runtime.ws_context_adapters import (
    WebSocketContextBinding,
    build_websocket_context_binding,
    build_websocket_context_deps,
)


class FakeActiveGames:
    def __init__(self, saved_game):
        self.saved_game = saved_game
        self.calls = []

    def get(self, game_id: str, *, touch: bool = False):
        self.calls.append((game_id, touch))
        return self.saved_game


async def async_marker(*_args, **_kwargs):
    return None


def make_deps(active_games) -> WebSocketContextDeps:
    values = {
        name: SimpleNamespace(name=name)
        for name in WEBSOCKET_CONTEXT_FIELD_NAMES
    }
    values["active_games"] = active_games
    return build_websocket_context_deps(WebSocketContextBinding(**values))


def smoke_context_factory_maps_runtime_deps() -> None:
    active_games = FakeActiveGames(saved_game=object())
    deps = make_deps(active_games)

    ctx = build_websocket_action_context(
        game_id="smoke-session",
        game=None,
        send=async_marker,
        send_error=async_marker,
        do_analysis=async_marker,
        do_analysis_bg=async_marker,
        deps=deps,
    )

    assert ctx.game_id == "smoke-session"
    assert ctx.game is None
    assert ctx.send is async_marker
    assert ctx.send_error is async_marker
    assert ctx.do_analysis is async_marker
    assert ctx.do_analysis_bg is async_marker

    flattened = flatten_websocket_context_deps(deps)
    for name in WEBSOCKET_CONTEXT_FIELD_NAMES:
        assert getattr(ctx, name) is flattened[name], name
    assert deps.active_games is active_games
    assert deps.ai_move is flattened["ai_move"]


def smoke_grouped_deps_round_trip_to_flat_binding() -> None:
    expected = {}
    group_values = {}
    for group_name, group_type in WEBSOCKET_CONTEXT_GROUP_SPECS:
        values = {}
        for field in fields(group_type):
            marker = SimpleNamespace(name=f"{group_name}.{field.name}")
            expected[field.name] = marker
            values[field.name] = marker
        group_values[group_name] = group_type(**values)

    deps = WebSocketContextDeps(**group_values)
    binding = build_websocket_context_binding(deps)
    rebuilt_deps = build_websocket_context_deps(binding)
    flattened = flatten_websocket_context_deps(rebuilt_deps)

    for name, marker in expected.items():
        assert getattr(binding, name) is marker, name
        assert flattened[name] is marker, name


def smoke_context_restore_uses_active_game_store() -> None:
    saved_game = object()
    active_games = FakeActiveGames(saved_game=saved_game)
    deps = make_deps(active_games)
    ctx = build_websocket_action_context(
        game_id="restore-session",
        game=None,
        send=async_marker,
        send_error=async_marker,
        do_analysis=async_marker,
        do_analysis_bg=async_marker,
        deps=deps,
    )

    assert ctx.restore_game() is saved_game
    assert ctx.game is saved_game
    assert active_games.calls == [("restore-session", True)]


def assert_bound_method(actual, expected) -> None:
    assert getattr(actual, "__self__", None) is getattr(expected, "__self__", None)
    assert getattr(actual, "__func__", None) is getattr(expected, "__func__", None)


def smoke_server_ws_context_deps_maps_current_runtime_objects() -> None:
    deps = build_websocket_context_deps(s._ws_context_binding())

    expected = {
        "active_games": s.active_games,
        "engine": s.engine,
        "run_in_executor": s.run_in_executor,
        "GoGame": s.GoGame,
        "coord_to_gtp": s.coord_to_gtp,
        "gtp_to_coord": s.gtp_to_coord,
        "engine_state_snapshot": s._engine_state_snapshot,
        "reload_live_card_config": s.reload_live_card_config,
        "get_game_visits": s.get_game_visits,
        "pick_rogue_choices": s.pick_rogue_choices,
        "pick_ultimate_choices": s.pick_ultimate_choices,
        "pick_challenge_beta_choices": s.pick_challenge_beta_choices,
        "pick_ai_rogue_card": s.pick_ai_rogue_card,
        "pick_ai_ultimate_card": s.pick_ai_ultimate_card,
        "apply_challenge_rogue_loadout": s._apply_challenge_rogue_loadout,
        "activate_rogue_card": s._activate_rogue_card,
        "activate_ai_rogue_card": s._activate_ai_rogue_card,
        "ai_move": s._ai_move,
        "ultimate_ai_move": s._ultimate_ai_move,
        "ultimate_force_score": s._ultimate_force_score,
        "run_coach_turn_if_needed": s._run_coach_turn_if_needed,
        "run_ai_observer_loop": s._run_ai_observer_loop,
        "sync_board_to_katago": s._sync_board_to_katago,
        "challenge_remaining": s._challenge_remaining,
        "challenge_zone_points": s._challenge_zone_points,
        "rogue_has": s._rogue_has,
        "get_ai_rogue_forbidden_points": s._get_ai_rogue_forbidden_points,
        "ultimate_get_territory_forbidden": s._ultimate_get_territory_forbidden,
        "record_ultimate_player_action": s._record_ultimate_player_action,
        "check_capture_foul": s._check_capture_foul,
        "count_stones": s._count_stones,
        "apply_ultimate_effect": s._apply_ultimate_effect,
        "resolve_pending_ultimate_shadow_links": s._resolve_pending_ultimate_shadow_links,
        "apply_player_rogue_move_effects": s._apply_player_rogue_move_effects,
        "apply_ai_rogue_response_effects": s._apply_ai_rogue_response_effects,
        "prepare_player_turn_modifiers": s._prepare_player_turn_modifiers,
        "finish_ultimate_quickthink_turn": s._finish_ultimate_quickthink_turn,
        "pick_joseki_targets": s._pick_joseki_targets,
        "random_hidden_center": s._random_hidden_center,
        "diamond_points": s._diamond_points,
    }

    flattened = flatten_websocket_context_deps(deps)
    for name, expected_value in expected.items():
        assert flattened[name] is expected_value, name
    assert_bound_method(deps.start_engine_background, s.engine_runtime.start_background)


def main() -> None:
    smoke_context_factory_maps_runtime_deps()
    smoke_grouped_deps_round_trip_to_flat_binding()
    smoke_context_restore_uses_active_game_store()
    smoke_server_ws_context_deps_maps_current_runtime_objects()
    print("ws context smoke test: OK")


if __name__ == "__main__":
    main()
