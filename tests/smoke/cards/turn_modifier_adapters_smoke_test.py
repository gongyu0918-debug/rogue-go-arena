from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import random

import app.config.gameplay as gameplay_config
import server as s
from app.domain.game_state import GoGame
from app.runtime import turn_modifier_adapters as adapters


def make_game() -> GoGame:
    game = GoGame(size=9, player_color="B")
    game.current_player = "B"
    return game


def smoke_adapter_player_non_pass_coords_uses_supplied_parser() -> None:
    game = make_game()
    game.moves = [
        ("B", "A9"),
        ("B", "pass"),
        ("B", "B8"),
        ("W", "C7"),
    ]
    calls = []

    def parser(gtp: str, size: int):
        calls.append((gtp, size))
        return {
            "A9": (0, 0),
            "B8": (1, 1),
            "C7": (2, 2),
        }.get(gtp)

    assert adapters.player_non_pass_coords(game, "B", parser, limit=1) == [(0, 0)]
    assert calls == [("A9", 9)]


def smoke_adapter_refresh_forwards_fog_picker_hooks() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"
    mask_calls = []
    point_calls = []

    def pick_mask(size: int, rng: random.Random):
        mask_calls.append(size)
        return [(3, 3)]

    def pick_point(game_arg, rng: random.Random):
        point_calls.append(game_arg)
        return [(4, 4)]

    adapters.refresh_ai_rogue_player_turn(
        game,
        pick_fog_mask_fn=pick_mask,
        pick_fog_point_fn=pick_point,
    )
    assert game.ai_rogue_seal_points == [(3, 3)]
    assert mask_calls == [9]
    assert point_calls == []

    game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
    adapters.refresh_ai_rogue_player_turn(
        game,
        pick_fog_mask_fn=pick_mask,
        pick_fog_point_fn=pick_point,
    )
    assert game.ai_rogue_seal_points == [(4, 4)]
    assert point_calls == [game]


def smoke_server_record_player_action_uses_current_record_wrapper() -> None:
    game = make_game()
    game.ultimate = True
    calls = []
    original = s._record_ultimate_turn
    try:
        s._record_ultimate_turn = lambda game_arg: calls.append(game_arg)
        s._record_ultimate_player_action(game)
    finally:
        s._record_ultimate_turn = original

    assert calls == [game]
    assert game.ultimate_move_count == 0


def smoke_server_clear_modifiers_uses_current_quickthink_wrapper() -> None:
    game = make_game()
    game.rogue_quickthink_stage = 2
    game.ultimate_quickthink_active = True
    calls = []
    original = s._finish_ultimate_quickthink_turn
    try:
        s._finish_ultimate_quickthink_turn = lambda game_arg: calls.append(game_arg)
        s._clear_player_turn_modifiers(game)
    finally:
        s._finish_ultimate_quickthink_turn = original

    assert game.rogue_quickthink_stage == 0
    assert calls == [game]
    assert game.ultimate_quickthink_active is True


def smoke_server_refresh_uses_current_fog_picker_wrappers() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"
    original_mask = s._pick_fog_mask
    original_point = s._pick_fog_point
    try:
        s._pick_fog_mask = lambda _size, _rng: [(6, 6)]
        s._pick_fog_point = lambda _game, _rng: [(7, 7)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(6, 6)]

        game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(7, 7)]
    finally:
        s._pick_fog_mask = original_mask
        s._pick_fog_point = original_point


def main() -> None:
    smoke_adapter_player_non_pass_coords_uses_supplied_parser()
    smoke_adapter_refresh_forwards_fog_picker_hooks()
    smoke_server_record_player_action_uses_current_record_wrapper()
    smoke_server_clear_modifiers_uses_current_quickthink_wrapper()
    smoke_server_refresh_uses_current_fog_picker_wrappers()
    print("turn modifier adapters smoke test: OK")


if __name__ == "__main__":
    main()
