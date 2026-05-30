from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import server as s
from app.runtime.ws_context import WebSocketContextDeps
from app.runtime.ws_context_adapters import (
    WebSocketContextBinding,
    build_websocket_context_deps,
)


def make_binding() -> WebSocketContextBinding:
    values = {
        field.name: SimpleNamespace(name=field.name)
        for field in fields(WebSocketContextBinding)
    }
    return WebSocketContextBinding(**values)


def assert_bound_method(actual, expected) -> None:
    assert getattr(actual, "__self__", None) is getattr(expected, "__self__", None)
    assert getattr(actual, "__func__", None) is getattr(expected, "__func__", None)


def smoke_binding_maps_every_field() -> None:
    binding = make_binding()
    deps = build_websocket_context_deps(binding)

    assert [field.name for field in fields(WebSocketContextBinding)] == [
        field.name for field in fields(WebSocketContextDeps)
    ]
    for field in fields(WebSocketContextDeps):
        assert getattr(deps, field.name) is getattr(binding, field.name), field.name


def smoke_server_binding_maps_current_runtime_objects() -> None:
    binding = s._ws_context_binding()
    deps = s._ws_context_deps()

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

    for name, expected_value in expected.items():
        assert getattr(binding, name) is expected_value, name
        assert getattr(deps, name) is expected_value, name
    assert_bound_method(binding.start_engine_background, s.engine_runtime.start_background)
    assert_bound_method(deps.start_engine_background, s.engine_runtime.start_background)


def smoke_server_binding_resolves_patched_runtime_objects() -> None:
    patched_active_games = object()

    async def patched_ai_move(*_args, **_kwargs):
        return None

    async def patched_check_capture_foul(*_args, **_kwargs):
        return None

    def patched_coord_to_gtp(*_args, **_kwargs):
        return "A1"

    originals = {
        "active_games": s.active_games,
        "coord_to_gtp": s.coord_to_gtp,
        "_ai_move": s._ai_move,
        "_check_capture_foul": s._check_capture_foul,
    }
    try:
        s.active_games = patched_active_games
        s.coord_to_gtp = patched_coord_to_gtp
        s._ai_move = patched_ai_move
        s._check_capture_foul = patched_check_capture_foul

        binding = s._ws_context_binding()
        deps = s._ws_context_deps()
    finally:
        s.active_games = originals["active_games"]
        s.coord_to_gtp = originals["coord_to_gtp"]
        s._ai_move = originals["_ai_move"]
        s._check_capture_foul = originals["_check_capture_foul"]

    assert binding.active_games is patched_active_games
    assert deps.active_games is patched_active_games
    assert binding.coord_to_gtp is patched_coord_to_gtp
    assert deps.coord_to_gtp is patched_coord_to_gtp
    assert binding.ai_move is patched_ai_move
    assert deps.ai_move is patched_ai_move
    assert binding.check_capture_foul is patched_check_capture_foul
    assert deps.check_capture_foul is patched_check_capture_foul


def main() -> None:
    smoke_binding_maps_every_field()
    smoke_server_binding_maps_current_runtime_objects()
    smoke_server_binding_resolves_patched_runtime_objects()
    print("ws context adapters smoke test: OK")


if __name__ == "__main__":
    main()
