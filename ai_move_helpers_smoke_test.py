import server as s
from app.domain.game_state import GoGame
from app.gameplay.ai_moves import is_suspicious_ai_pass


def make_game(size: int = 9) -> GoGame:
    return GoGame(size=size, player_color="B")


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
    test_suspicious_ai_pass_requires_pass()
    test_suspicious_ai_pass_detects_early_open_board_pass()
    test_suspicious_ai_pass_allows_established_pass()
    test_suspicious_ai_pass_allows_late_small_board_pass()
    print("ai_move_helpers_smoke_test passed")
