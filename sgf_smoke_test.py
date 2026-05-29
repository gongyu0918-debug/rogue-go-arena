from __future__ import annotations

from app.domain.game_state import GoGame
from app.domain.sgf import generate_sgf, gtp_to_sgf


def main() -> int:
    assert gtp_to_sgf("D4", 9) == "df"
    assert gtp_to_sgf("PASS", 9) == ""
    assert gtp_to_sgf("bad", 9) == ""

    game = GoGame(size=9, komi=7.5, player_color="B", level="5k")
    game.moves = [("B", "D4"), ("W", "PASS"), ("B", "E5")]
    game.winner = "B"
    sgf = generate_sgf(game)

    assert "GM[1]FF[4]CA[UTF-8]" in sgf
    assert "SZ[9]KM[7.5]" in sgf
    assert "PB[Player]PW[AI]" in sgf
    assert "RE[B+]" in sgf
    assert ";B[df]" in sgf
    assert ";W[]" in sgf
    assert ";B[ee]" in sgf
    assert sgf.endswith(")\n")

    print("sgf smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
