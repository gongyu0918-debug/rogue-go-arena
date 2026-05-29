import server as s
import app.config.gameplay as gameplay_config
import app.gameplay.turn_modifiers as turn_modifiers
from app.domain.game_state import GoGame
from app.gameplay.ultimate_effects import get_ultimate_territory_forbidden_points
from app.gameplay.turn_modifiers import record_ultimate_player_action


def make_game() -> GoGame:
    return GoGame(size=9, player_color="B")


def test_record_ultimate_player_action_counts_normal_and_double_turns() -> None:
    game = make_game()
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1

    game.ultimate_double_pending = True
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1

    game.ultimate_double_pending = False
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 2


def test_record_ultimate_player_action_counts_quickthink_once() -> None:
    game = make_game()
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True

    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1
    assert game.ultimate_quickthink_turn_counted is True

    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1


def test_server_record_ultimate_player_action_preserves_turn_hook() -> None:
    game = make_game()
    calls: list[GoGame] = []
    old_record = s._record_ultimate_turn
    try:
        s._record_ultimate_turn = calls.append
        s._record_ultimate_player_action(game)
        assert calls == [game]
        assert game.ultimate_move_count == 0
    finally:
        s._record_ultimate_turn = old_record


def test_gameplay_record_ultimate_player_action_resolves_turn_hook_late() -> None:
    game = make_game()
    calls: list[GoGame] = []
    old_record = turn_modifiers.record_ultimate_turn
    try:
        turn_modifiers.record_ultimate_turn = calls.append
        turn_modifiers.record_ultimate_player_action(game)
        assert calls == [game]
        assert game.ultimate_move_count == 0
    finally:
        turn_modifiers.record_ultimate_turn = old_record


def test_ultimate_territory_forbidden_points_use_opponent_stones() -> None:
    game = make_game()
    game.board[4][4] = 2
    game.board[0][0] = 1

    forbidden = get_ultimate_territory_forbidden_points(game, 1)
    assert (4, 4) in forbidden
    assert (4, 2) in forbidden
    assert (2, 4) in forbidden
    assert (2, 2) in forbidden
    assert (1, 4) not in forbidden
    assert (4, 1) not in forbidden
    assert (0, 0) not in forbidden
    assert len(forbidden) == 25

    black_owner_forbidden = get_ultimate_territory_forbidden_points(game, 2)
    assert (0, 0) in black_owner_forbidden
    assert (2, 2) in black_owner_forbidden
    assert (3, 0) not in black_owner_forbidden

    assert s._ultimate_get_territory_forbidden(game, 1) == get_ultimate_territory_forbidden_points(game, 1)


def test_ultimate_territory_radius_reads_live_config() -> None:
    game = make_game()
    game.board[4][4] = 2

    old_radius = gameplay_config.ULTIMATE_TERRITORY_RADIUS
    try:
        gameplay_config.ULTIMATE_TERRITORY_RADIUS = 1
        forbidden = get_ultimate_territory_forbidden_points(game, 1)
        assert forbidden == {(4, 4), (4, 3), (4, 5), (3, 4), (5, 4)}
    finally:
        gameplay_config.ULTIMATE_TERRITORY_RADIUS = old_radius


if __name__ == "__main__":
    test_record_ultimate_player_action_counts_normal_and_double_turns()
    test_record_ultimate_player_action_counts_quickthink_once()
    test_server_record_ultimate_player_action_preserves_turn_hook()
    test_gameplay_record_ultimate_player_action_resolves_turn_hook_late()
    test_ultimate_territory_forbidden_points_use_opponent_stones()
    test_ultimate_territory_radius_reads_live_config()
    print("ultimate_helpers_smoke_test passed")
