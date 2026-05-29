from types import SimpleNamespace

import server as s
from app.domain.coordinates import coord_to_gtp, gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.effect_utils import player_non_pass_coords
from app.gameplay.rogue_effects import apply_player_rogue_board_effects
from app.gameplay.ultimate_effects import apply_ultimate_state_effect


def make_game():
    return SimpleNamespace(
        size=9,
        moves=[
            ("B", "C7"),
            ("W", "E5"),
            ("B", "PASS"),
            ("B", "T1"),
            ("B", "G7"),
            ("B", "E3"),
        ],
    )


def test_player_non_pass_coords_filters_and_limits() -> None:
    game = make_game()

    assert player_non_pass_coords(game, "B", gtp_to_coord) == [(2, 2), (6, 2), (4, 6)]
    assert player_non_pass_coords(game, "W", gtp_to_coord) == [(4, 4)]
    assert player_non_pass_coords(game, "B", gtp_to_coord, limit=2) == [(2, 2), (6, 2)]


def test_server_wrapper_uses_shared_move_history_helper() -> None:
    game = make_game()

    assert s._player_non_pass_coords(game, "B") == [(2, 2), (6, 2), (4, 6)]
    assert s._player_non_pass_coords(game, "B", limit=1) == [(2, 2)]


def test_rogue_sanrensei_ignores_pass_invalid_and_opponent_moves() -> None:
    game = GoGame(size=9)
    game.rogue_card = "sanrensei"
    game.moves = make_game().moves

    result = apply_player_rogue_board_effects(
        game,
        x=4,
        y=6,
        color="B",
        captured=0,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )

    assert result.modified is True
    assert game.rogue_sanrensei_done is True
    assert any("三连星" in message for message in result.messages)


def test_ultimate_sanrensei_ignores_pass_invalid_and_opponent_moves() -> None:
    game = GoGame(size=9)
    game.ultimate = True
    game.moves = make_game().moves

    result = apply_ultimate_state_effect(
        game,
        x=4,
        y=6,
        color="B",
        card="sanrensei",
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )

    assert result is not None
    assert result.modified is True
    assert game.ultimate_sanrensei_done is True
    assert any("三连星" in message for message in result.messages)


if __name__ == "__main__":
    test_player_non_pass_coords_filters_and_limits()
    test_server_wrapper_uses_shared_move_history_helper()
    test_rogue_sanrensei_ignores_pass_invalid_and_opponent_moves()
    test_ultimate_sanrensei_ignores_pass_invalid_and_opponent_moves()
    print("move_history_smoke_test passed")
