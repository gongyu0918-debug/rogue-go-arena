from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import AiMovePlacement as ReExportedAiMovePlacement
from app.gameplay.move_placement import (
    AiMovePlacement,
    place_auxiliary_ai_move_on_board,
)


def smoke_auxiliary_move_placement_preserves_board_and_pass_flags() -> None:
    game = GoGame(size=5, player_color="B")

    placed = place_auxiliary_ai_move_on_board(game, "W", "C3", (2, 2))
    passed = place_auxiliary_ai_move_on_board(game, "B", "pass", None)
    invalid = place_auxiliary_ai_move_on_board(game, "W", "bad", None)

    assert AiMovePlacement is ReExportedAiMovePlacement
    assert placed == AiMovePlacement(coord=(2, 2), captured=0)
    assert passed == AiMovePlacement(coord=None, captured=0)
    assert invalid == AiMovePlacement(coord=None, captured=0)
    assert game.moves == [("W", "C3"), ("B", "pass"), ("W", "bad")]
    assert game.board[2][2] == 2
    assert game.passed["B"] is True
    assert game.passed["W"] is True


def smoke_auxiliary_move_placement_returns_capture_count() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[1][1] = 1
    game.board[0][1] = 2
    game.board[2][1] = 2
    game.board[1][0] = 2

    captured = place_auxiliary_ai_move_on_board(game, "W", "C2", (2, 1))

    assert captured == AiMovePlacement(coord=(2, 1), captured=1)
    assert game.board[1][1] == 0
    assert game.captures["W"] == 1
    assert game.passed["W"] is False


def main() -> None:
    smoke_auxiliary_move_placement_preserves_board_and_pass_flags()
    smoke_auxiliary_move_placement_returns_capture_count()
    print("move placement smoke test: OK")


if __name__ == "__main__":
    main()
