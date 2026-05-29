import server as s
from app.domain.game_state import GoGame
from app.gameplay.ai_moves import (
    compute_game_visits,
    is_suspicious_ai_pass,
    plan_ultimate_ai_search,
    resolve_occupied_ai_move,
    snapshot_ai_turn,
)


def make_game(size: int = 9) -> GoGame:
    return GoGame(size=size, player_color="B")


class FirstChoiceRng:
    def choice(self, items):
        return items[0]


def test_snapshot_ai_turn_collects_move_counts_and_cards() -> None:
    game = make_game()
    game.rogue_card = "suboptimal"
    game.moves = [
        ("B", "E5"),
        ("W", "D4"),
        ("W", "pass"),
        ("B", "C3"),
    ]
    calls = []

    def rogue_cards(game_arg):
        calls.append(game_arg is game)
        return ["suboptimal", "nerf", "suboptimal"]

    snapshot = snapshot_ai_turn(game, rogue_cards)

    assert snapshot.color == "W"
    assert snapshot.card == "suboptimal"
    assert snapshot.rogue_cards == {"suboptimal", "nerf"}
    assert snapshot.move_count == 4
    assert snapshot.ai_move_count == 2
    assert calls == [True]


def test_snapshot_ai_turn_uses_black_ai_when_player_is_white() -> None:
    game = GoGame(size=9, player_color="W")
    game.moves = [
        ("B", "D4"),
        ("W", "E5"),
        ("B", "Q16"),
    ]

    snapshot = snapshot_ai_turn(game, lambda _game: [])

    assert snapshot.color == "B"
    assert snapshot.card is None
    assert snapshot.rogue_cards == set()
    assert snapshot.move_count == 3
    assert snapshot.ai_move_count == 2


def test_plan_ultimate_ai_search_uses_ultimate_visits_and_ai_card() -> None:
    game = make_game()
    game.level = "5k"
    game.ultimate_ai_card = "meteor"
    game.moves = [("B", "E5"), ("W", "D4")]
    calls = []

    plan = plan_ultimate_ai_search(
        game,
        get_territory_forbidden=lambda _game, _color_value: calls.append((_game, _color_value)),
        get_game_visits=compute_game_visits,
    )

    assert plan.color == "W"
    assert plan.ai_card == "meteor"
    assert plan.color_value == 2
    assert plan.forbidden == set()
    assert plan.visits == compute_game_visits("5k", 2, "ultimate")
    assert calls == []


def test_plan_ultimate_ai_search_applies_player_territory_forbidden() -> None:
    game = make_game()
    game.ultimate_player_card = "territory"
    calls = []

    def forbidden(game_arg, color_value):
        calls.append((game_arg, color_value))
        return {(2, 2), (3, 3)}

    plan = plan_ultimate_ai_search(
        game,
        get_territory_forbidden=forbidden,
        get_game_visits=compute_game_visits,
    )

    assert calls == [(game, 2)]
    assert plan.forbidden == {(2, 2), (3, 3)}


def test_plan_ultimate_ai_search_uses_black_color_value_for_black_ai() -> None:
    game = GoGame(size=9, player_color="W")
    game.ultimate_player_card = "territory"
    calls = []

    def forbidden(game_arg, color_value):
        calls.append((game_arg, color_value))
        return {(4, 4)}

    plan = plan_ultimate_ai_search(
        game,
        get_territory_forbidden=forbidden,
        get_game_visits=compute_game_visits,
    )

    assert plan.color == "B"
    assert plan.color_value == 1
    assert calls == [(game, 1)]
    assert plan.forbidden == {(4, 4)}


def test_resolve_occupied_ai_move_keeps_pass_and_empty_move() -> None:
    game = make_game()

    assert resolve_occupied_ai_move(
        game,
        "W",
        "pass",
        None,
        coord_to_gtp=s.coord_to_gtp,
    ) == ("pass", None)
    assert resolve_occupied_ai_move(
        game,
        "W",
        "A9",
        (0, 0),
        coord_to_gtp=s.coord_to_gtp,
    ) == ("A9", (0, 0))


def test_resolve_occupied_ai_move_chooses_legal_empty_point() -> None:
    game = make_game()
    game.board[0][0] = 1

    gtp, coord = resolve_occupied_ai_move(
        game,
        "W",
        "A9",
        (0, 0),
        coord_to_gtp=s.coord_to_gtp,
        rng=FirstChoiceRng(),
    )

    assert coord == (1, 0)
    assert gtp == "B9"


def test_resolve_occupied_ai_move_skips_illegal_empty_points() -> None:
    game = make_game()
    game.board[0][0] = 1
    game.is_legal_move = lambda x, y, _color: (x, y) != (1, 0)

    gtp, coord = resolve_occupied_ai_move(
        game,
        "W",
        "A9",
        (0, 0),
        coord_to_gtp=s.coord_to_gtp,
        rng=FirstChoiceRng(),
    )

    assert coord == (2, 0)
    assert gtp == "C9"


def test_resolve_occupied_ai_move_passes_when_no_empty_point_exists() -> None:
    game = make_game(size=2)
    for y in range(game.size):
        for x in range(game.size):
            game.board[y][x] = 1

    assert resolve_occupied_ai_move(
        game,
        "W",
        "A2",
        (0, 0),
        coord_to_gtp=s.coord_to_gtp,
        rng=FirstChoiceRng(),
    ) == ("pass", None)


def test_suspicious_ai_pass_requires_pass() -> None:
    game = make_game()

    assert is_suspicious_ai_pass(game, "D4", "W") is False
    assert s._is_suspicious_ai_pass(game, "D4", "W") is False


def test_suspicious_ai_pass_detects_early_open_board_pass() -> None:
    game = make_game()
    game.moves = [("B", "E5"), ("W", "D4"), ("B", "F5")]

    assert is_suspicious_ai_pass(game, "pass", "W") is True
    assert s._is_suspicious_ai_pass(game, "pass", "W") is True


def test_suspicious_ai_pass_allows_established_pass() -> None:
    game = make_game()
    game.moves = [
        ("W", "D4"),
        ("W", "E4"),
        ("W", "F4"),
    ]

    assert is_suspicious_ai_pass(game, "PASS", "W") is False
    assert s._is_suspicious_ai_pass(game, "PASS", "W") is False


def test_suspicious_ai_pass_allows_late_small_board_pass() -> None:
    game = make_game(size=5)
    for y in range(game.size):
        for x in range(game.size):
            if not (x == 0 and y == 0):
                game.board[y][x] = 1

    assert is_suspicious_ai_pass(game, "PASS", "W") is False
    assert s._is_suspicious_ai_pass(game, "PASS", "W") is False


if __name__ == "__main__":
    test_snapshot_ai_turn_collects_move_counts_and_cards()
    test_snapshot_ai_turn_uses_black_ai_when_player_is_white()
    test_plan_ultimate_ai_search_uses_ultimate_visits_and_ai_card()
    test_plan_ultimate_ai_search_applies_player_territory_forbidden()
    test_plan_ultimate_ai_search_uses_black_color_value_for_black_ai()
    test_resolve_occupied_ai_move_keeps_pass_and_empty_move()
    test_resolve_occupied_ai_move_chooses_legal_empty_point()
    test_resolve_occupied_ai_move_skips_illegal_empty_points()
    test_resolve_occupied_ai_move_passes_when_no_empty_point_exists()
    test_suspicious_ai_pass_requires_pass()
    test_suspicious_ai_pass_detects_early_open_board_pass()
    test_suspicious_ai_pass_allows_established_pass()
    test_suspicious_ai_pass_allows_late_small_board_pass()
    print("ai_move_helpers_smoke_test passed")
