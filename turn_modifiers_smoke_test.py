import random

import app.config.gameplay as gameplay_config
import server as s
from app.domain.game_state import GoGame
from app.gameplay import turn_modifiers


def make_game() -> GoGame:
    game = GoGame(size=9, player_color="B")
    game.current_player = "B"
    return game


def test_ai_rogue_forbidden_points() -> None:
    game = make_game()
    game.ai_rogue_seal_points = [(1, 1), (2, 2)]

    for card in ["blackhole", "golden_corner", "fog"]:
        game.ai_rogue_card = card
        assert turn_modifiers.get_ai_rogue_forbidden_points(game) == [(1, 1), (2, 2)]

    game.ai_rogue_card = "mirror"
    assert turn_modifiers.get_ai_rogue_forbidden_points(game) == []


def test_player_bonus_forbidden_points() -> None:
    game = make_game()
    game.ai_rogue_card = "fog"
    game.ai_rogue_seal_points = [(4, 4)]

    assert turn_modifiers.get_player_bonus_forbidden_points(game, "B") == {(4, 4)}
    assert turn_modifiers.get_player_bonus_forbidden_points(game, "W") == set()

    game.two_player = True
    assert turn_modifiers.get_player_bonus_forbidden_points(game, "B") == set()


def test_refresh_ai_rogue_fog_mask_and_point_modes() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"

    turn_modifiers.refresh_ai_rogue_player_turn(
        game,
        rng_factory=lambda: random.Random(1),
        pick_fog_mask_fn=lambda _size, _rng: [(3, 3), (3, 4)],
    )
    assert game.ai_rogue_seal_points == [(3, 3), (3, 4)]

    game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
    point_calls = [[(5, 5)], [(5, 5)]]

    def pick_duplicate_point(_game, _rng):
        return point_calls.pop(0) if point_calls else [(6, 6)]

    turn_modifiers.refresh_ai_rogue_player_turn(
        game,
        rng_factory=lambda: random.Random(2),
        pick_fog_point_fn=pick_duplicate_point,
    )
    assert game.ai_rogue_seal_points == [(5, 5)]

    game.current_player = "W"
    game.ai_rogue_seal_points = [(7, 7)]
    turn_modifiers.refresh_ai_rogue_player_turn(game)
    assert game.ai_rogue_seal_points == []


def test_prepare_and_clear_quickthink_turns() -> None:
    game = make_game()
    game.rogue_card = "quickthink"
    game.ultimate = True
    game.ultimate_player_card = "quickthink"

    refresh_calls: list[GoGame] = []
    turn_modifiers.prepare_player_turn_modifiers(
        game,
        refresh_ai_rogue_player_turn_fn=refresh_calls.append,
    )
    assert refresh_calls == [game]
    assert game.rogue_quickthink_stage == 1
    assert game.ultimate_quickthink_active is True
    assert game.ultimate_quickthink_token == 1

    turn_modifiers.prepare_player_turn_modifiers(
        game,
        refresh_ai_rogue_player_turn_fn=refresh_calls.append,
    )
    assert game.ultimate_quickthink_token == 1

    game.rogue_quickthink_stage = 2
    game.ultimate_quickthink_turn_counted = True
    turn_modifiers.clear_player_turn_modifiers(game)
    assert game.rogue_quickthink_stage == 0
    assert game.ultimate_quickthink_active is False
    assert game.ultimate_quickthink_turn_counted is False


def test_apply_ultimate_ai_move_result_records_stone_move() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "A9",
        (0, 0),
        count_turn=True,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == [game]
    assert game.moves == [("W", "A9")]
    assert game.board[0][0] == 2
    assert game.passed["W"] is False


def test_apply_ultimate_ai_move_result_records_pass_without_counting_double_bonus() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "pass",
        None,
        count_turn=False,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == []
    assert game.moves == [("W", "pass")]
    assert game.passed["W"] is True


def test_apply_ultimate_ai_move_result_treats_missing_coord_as_pass_state() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "D4",
        None,
        count_turn=True,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == [game]
    assert game.moves == [("W", "D4")]
    assert game.passed["W"] is True
    assert all(cell == 0 for row in game.board for cell in row)


def test_finish_ultimate_ai_normal_turn_prepares_player_and_pushes_history() -> None:
    game = make_game()
    game.ultimate = True
    game.current_player = "W"
    game.ultimate_extra_turn = True
    history_len = len(game._history)
    prepare_calls: list[GoGame] = []

    def prepare(game_arg):
        prepare_calls.append(game_arg)
        game_arg.rogue_quickthink_stage = 1

    turn_modifiers.finish_ultimate_ai_normal_turn(
        game,
        prepare_player_turn_modifiers_fn=prepare,
    )

    assert game.ultimate_extra_turn is False
    assert game.current_player == game.player_color
    assert prepare_calls == [game]
    assert len(game._history) == history_len + 1
    assert game._history[-1]["current_player"] == game.player_color
    assert game._history[-1]["rogue_quickthink_stage"] == 1


def test_server_wrapper_preserves_fog_monkeypatch() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"

    old_pick_fog_mask = s._pick_fog_mask
    try:
        s._pick_fog_mask = lambda _size, _rng: [(4, 4)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(4, 4)]
    finally:
        s._pick_fog_mask = old_pick_fog_mask

    game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
    old_pick_fog_point = s._pick_fog_point
    try:
        s._pick_fog_point = lambda _game, _rng: [(5, 5)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(5, 5)]
    finally:
        s._pick_fog_point = old_pick_fog_point


if __name__ == "__main__":
    test_ai_rogue_forbidden_points()
    test_player_bonus_forbidden_points()
    test_refresh_ai_rogue_fog_mask_and_point_modes()
    test_prepare_and_clear_quickthink_turns()
    test_apply_ultimate_ai_move_result_records_stone_move()
    test_apply_ultimate_ai_move_result_records_pass_without_counting_double_bonus()
    test_apply_ultimate_ai_move_result_treats_missing_coord_as_pass_state()
    test_finish_ultimate_ai_normal_turn_prepares_player_and_pushes_history()
    test_server_wrapper_preserves_fog_monkeypatch()
    print("turn_modifiers_smoke_test passed")
