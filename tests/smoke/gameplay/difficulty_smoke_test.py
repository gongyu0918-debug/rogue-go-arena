from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.gameplay.difficulty import (
    BASE_KOMI,
    DIFFICULTIES,
    difficulty_points,
    komi_for_ai_points,
    normalize_difficulty,
    plain_game_setup,
)
from app.runtime.game_input_validation import VALID_HANDICAPS


def main() -> None:
    assert normalize_difficulty("Hard") == "hard"
    assert normalize_difficulty(None) is None
    assert normalize_difficulty("impossible") is None

    points = [difficulty_points(d) for d in DIFFICULTIES]
    assert points == sorted(points), "difficulties must get harder in order"
    assert difficulty_points("normal") == 0

    # Points for the AI move komi toward the AI, whichever colour it plays.
    for d in DIFFICULTIES:
        p = difficulty_points(d)
        assert komi_for_ai_points(p, "W") - BASE_KOMI == p
        assert BASE_KOMI - komi_for_ai_points(p, "B") == p

    # Plain games: more stones on easier settings; with stones the player is Black.
    stones = [plain_game_setup(d, "W").handicap for d in DIFFICULTIES]
    assert stones == sorted(stones, reverse=True), stones
    for d in DIFFICULTIES:
        setup = plain_game_setup(d, "W")
        assert setup.handicap in VALID_HANDICAPS
        if setup.handicap:
            assert setup.player_color == "B" and setup.komi == 0.5
        else:
            assert setup.player_color == "W" and setup.komi == BASE_KOMI
    print("difficulty smoke test: OK")


if __name__ == "__main__":
    main()
