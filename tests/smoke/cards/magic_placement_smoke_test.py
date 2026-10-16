from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.domain.game_state import GoGame
from app.gameplay.effect_utils import set_points_to_color, spawn_bonus_points


def every_point(game: GoGame) -> list[tuple[int, int]]:
    return [(x, y) for y in range(game.size) for x in range(game.size)]


def smoke_filling_the_board_keeps_existing_stones() -> None:
    game = GoGame(size=5)
    existing = [(0, 0), (1, 0), (2, 2)]
    for x, y in existing:
        game.board[y][x] = 1
    placed = spawn_bonus_points(game, every_point(game), "B")
    assert all(game.board[y][x] == 1 for x, y in existing), "card stones wiped out the owner's stones"
    assert placed, "some stones are still gifted"
    empties = sum(row.count(0) for row in game.board)
    assert empties >= 1, "the last liberty is never filled"
    for x, y in placed:
        assert game.has_liberty(game.get_group(x, y))


def smoke_gifted_stone_still_captures() -> None:
    game = GoGame(size=5)
    game.board[0][0] = 2  # white in the corner, one liberty left at (0, 1)
    game.board[0][1] = 1
    placed = spawn_bonus_points(game, [(0, 1)], "B")
    assert placed == [(0, 1)] and game.board[0][0] == 0


def smoke_suicidal_point_is_skipped_without_capturing() -> None:
    game = GoGame(size=5)
    # (0, 0) is surrounded by white groups that keep their liberties.
    game.board[0][1] = 2
    game.board[1][0] = 2
    placed = set_points_to_color(game, [(0, 0)], "B")
    assert placed == [] and game.board[0][0] == 0
    assert game.board[0][1] == 2 and game.board[1][0] == 2


def main() -> None:
    smoke_filling_the_board_keeps_existing_stones()
    smoke_gifted_stone_still_captures()
    smoke_suicidal_point_is_skipped_without_capturing()
    print("magic placement smoke ok")


if __name__ == "__main__":
    main()
