from __future__ import annotations

import asyncio

import server as s
from app.domain.game_state import GoGame
from app.gameplay.ultimate_scoring import compute_ultimate_area_score


def test_compute_ultimate_area_score_counts_single_owner_territory() -> None:
    game = GoGame(size=3, komi=0.0, player_color="B")
    game.board = [
        [1, 1, 1],
        [1, 0, 1],
        [1, 1, 1],
    ]

    result = compute_ultimate_area_score(game)

    assert result.winner == "B"
    assert result.score == "B+9.0"
    assert result.reason == "ultimate_20moves"
    assert result.black_score == 9.0
    assert result.white_score == 0.0


def test_compute_ultimate_area_score_counts_white_owned_territory() -> None:
    game = GoGame(size=3, komi=0.0, player_color="B")
    game.board = [
        [2, 2, 2],
        [2, 0, 2],
        [2, 2, 2],
    ]

    result = compute_ultimate_area_score(game)

    assert result.winner == "W"
    assert result.score == "W+9.0"
    assert result.black_score == 0.0
    assert result.white_score == 9.0


def test_compute_ultimate_area_score_ignores_mixed_border_region() -> None:
    game = GoGame(size=3, komi=0.0, player_color="B")
    game.board[1][0] = 1
    game.board[1][2] = 2

    result = compute_ultimate_area_score(game)

    assert result.winner == "W"
    assert result.score == "W+0.0"
    assert result.black_score == 1.0
    assert result.white_score == 1.0


def test_compute_ultimate_area_score_applies_komi_and_formats_margin() -> None:
    game = GoGame(size=1, komi=1.5, player_color="B")
    game.board[0][0] = 1

    result = compute_ultimate_area_score(game)

    assert result.winner == "W"
    assert result.score == "W+0.5"
    assert result.black_score == 1.0
    assert result.white_score == 1.5


def test_compute_ultimate_area_score_tie_goes_to_white() -> None:
    game = GoGame(size=1, komi=0.0, player_color="B")

    result = compute_ultimate_area_score(game)

    assert result.winner == "W"
    assert result.score == "W+0.0"


async def _server_ultimate_force_score_sends_state_then_game_over() -> None:
    game = GoGame(size=1, komi=0.0, player_color="B")
    game.board[0][0] = 1
    sent = []

    async def send(payload):
        sent.append(payload)

    await s._ultimate_force_score(game, send)

    assert game.game_over is True
    assert game.winner == "B"
    assert game._history[-1]["game_over"] is True
    assert game._history[-1]["winner"] == "B"
    assert len(sent) == 2
    assert sent[0]["type"] == "game_state"
    assert sent[0]["game_over"] is True
    assert sent[0]["winner"] == "B"
    assert sent[1] == {
        "type": "game_over",
        "winner": "B",
        "score": "B+1.0",
        "reason": "ultimate_20moves",
    }


def test_server_ultimate_force_score_sends_state_then_game_over() -> None:
    asyncio.run(_server_ultimate_force_score_sends_state_then_game_over())


if __name__ == "__main__":
    test_compute_ultimate_area_score_counts_single_owner_territory()
    test_compute_ultimate_area_score_counts_white_owned_territory()
    test_compute_ultimate_area_score_ignores_mixed_border_region()
    test_compute_ultimate_area_score_applies_komi_and_formats_margin()
    test_compute_ultimate_area_score_tie_goes_to_white()
    test_server_ultimate_force_score_sends_state_then_game_over()
    print("ultimate_scoring_smoke_test passed")
