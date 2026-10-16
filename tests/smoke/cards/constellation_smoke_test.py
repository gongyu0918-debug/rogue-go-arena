from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import random

from app.config import gameplay as gameplay_config
from app.domain.coordinates import coord_to_gtp, gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import apply_player_rogue_board_effects


def make_game() -> GoGame:
    game = GoGame(size=19, player_color="B")
    game.rogue_enabled = True
    game.rogue_card = "sanrensei"
    return game


def play(game: GoGame, x: int, y: int, color: str = "B"):
    captured = game.place_stone(x, y, color)
    assert captured >= 0
    game.moves.append((color, coord_to_gtp(x, y, game.size)))
    return apply_player_rogue_board_effects(
        game, x=x, y=y, color=color, captured=captured,
        coord_to_gtp=coord_to_gtp, gtp_to_coord=gtp_to_coord,
    )


def constellation_messages(result) -> list[str]:
    return [m for m in result.messages if "星座连线" in m]


def smoke_one_space_jumps_light_up_mid_game() -> None:
    random.seed(1)
    game = make_game()
    for x, y in [(0, 18), (18, 0), (18, 18), (1, 17), (17, 1), (16, 16), (2, 16)]:
        play(game, x, y)  # opening that is not three star points: no opening payoff
    assert not game.rogue_sanrensei_done
    assert not constellation_messages(play(game, 9, 5))
    assert not constellation_messages(play(game, 9, 7))  # one-space jump, only two stones
    result = play(game, 9, 9)  # third stone, evenly spaced: lights up
    lit = constellation_messages(result)
    assert lit and "K14-K12-K10" in lit[0], result.messages
    assert result.modified
    assert game.board[6][9] == 1 or game.board[8][9] == 1, "bonus stone lands in a gap"


def smoke_cooldown_and_cap() -> None:
    random.seed(2)
    game = make_game()
    triggers = 0
    moves = 0
    for column in range(0, 19, 3):
        for row in (2, 4, 6):
            if game.board[row][column] == 0:
                triggers += len(constellation_messages(play(game, column, row)))
                moves += 1
    assert triggers <= gameplay_config.ROGUE_CONSTELLATION_MAX_TRIGGERS
    assert triggers <= 1 + moves // gameplay_config.ROGUE_CONSTELLATION_COOLDOWN_MOVES
    assert triggers >= 2, triggers


def smoke_opening_payoff_unchanged_and_starts_cooldown() -> None:
    random.seed(3)
    game = make_game()
    results = [play(game, x, y) for x, y in [(3, 3), (3, 9), (3, 15)]]
    assert game.rogue_sanrensei_done
    assert any("三连星发动" in m for m in results[-1].messages)
    assert not constellation_messages(results[-1]), "no double payout on the opening move"


def main() -> None:
    smoke_one_space_jumps_light_up_mid_game()
    smoke_cooldown_and_cap()
    smoke_opening_payoff_unchanged_and_starts_cooldown()
    print("constellation smoke ok")


if __name__ == "__main__":
    main()
