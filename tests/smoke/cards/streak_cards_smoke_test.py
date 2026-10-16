from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import random

from app.config import gameplay as gameplay_config
from app.data import cards as card_data
from app.domain.coordinates import coord_to_gtp, gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import apply_player_rogue_board_effects, reset_rogue_effect_state


def make_game(card_id: str) -> GoGame:
    game = GoGame(size=19, player_color="B")
    game.rogue_enabled = True
    game.rogue_card = card_id
    return game


def play(game: GoGame, x: int, y: int, color: str = "B"):
    captured = game.place_stone(x, y, color)
    assert captured >= 0, (x, y, captured)
    game.moves.append((color, coord_to_gtp(x, y, game.size)))
    return apply_player_rogue_board_effects(
        game, x=x, y=y, color=color, captured=captured,
        coord_to_gtp=coord_to_gtp, gtp_to_coord=gtp_to_coord,
    ), captured


def count(game: GoGame, value: int) -> int:
    return sum(row.count(value) for row in game.board)


def assert_board_legal(game: GoGame) -> None:
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x]:
                assert game.has_liberty(game.get_group(x, y)), f"dead group left at {(x, y)}"


def smoke_cards_are_registered() -> None:
    for card_id in ("momentum", "iron_wall", "capture_chain"):
        assert card_id in card_data.ROGUE_CARDS
        assert card_id in card_data.offerable_rogue_card_ids()
        assert card_data.rogue_offer_weight(card_id) > 1


def smoke_momentum_rewards_every_third_contact_move() -> None:
    random.seed(3)
    game = make_game("momentum")
    for x in (3, 5, 7, 9, 11):
        game.board[10][x] = 2  # a row of separated white stones to attack
    blacks_before = count(game, 1)
    results = [play(game, x, 9)[0] for x in (3, 5, 7)]
    assert [r.modified for r in results] == [False, False, True], results
    assert count(game, 1) == blacks_before + 3 + 1
    assert game.to_state()["rogue_streaks"] == {"momentum": 3}
    result, _ = play(game, 15, 3)  # no contact: streak resets
    assert not result.modified and game.rogue_streaks["momentum:B"] == 0
    assert "乘胜追击 3 连击" in results[2].messages[0]
    assert_board_legal(game)


def smoke_iron_wall_reinforces_weakest_group() -> None:
    random.seed(5)
    game = make_game("iron_wall")
    # A lone black stone in atari: its only liberty is (1, 1).
    game.board[0][1] = 1
    game.board[0][0] = 2
    game.board[0][2] = 2
    play(game, 9, 9)  # isolated: no streak (does not connect)
    assert game.rogue_streaks.get("iron_wall:B", 0) == 0
    r1, _ = play(game, 9, 10)
    r2, _ = play(game, 9, 11)
    r3, _ = play(game, 9, 12)
    assert not r1.modified and not r2.modified and r3.modified, (r1, r2, r3)
    assert game.board[1][1] == 1, "the weakest group's liberty is reinforced"
    assert_board_legal(game)


def smoke_capture_chain_pays_from_second_capture() -> None:
    random.seed(7)
    game = make_game("capture_chain")
    # Two white stones in atari, far apart.
    for (wx, wy), blacks in (((5, 5), [(4, 5), (6, 5), (5, 4)]), ((14, 14), [(13, 14), (15, 14), (14, 13)])):
        game.board[wy][wx] = 2
        for bx, by in blacks:
            game.board[by][bx] = 1
    first, captured = play(game, 5, 6)
    assert captured == 1 and not first.modified
    blacks = count(game, 1)
    second, captured = play(game, 14, 15)
    assert captured == 1 and second.modified, second
    assert count(game, 1) == blacks + 1 + 1
    play(game, 9, 9)  # no capture resets
    assert game.rogue_streaks["capture_chain:B"] == 0
    assert_board_legal(game)


def smoke_triggers_are_capped_and_reset_per_game() -> None:
    random.seed(11)
    game = make_game("momentum")
    for x in range(1, 18, 2):
        for y in (2, 6, 10, 14):
            game.board[y][x] = 2
    gifts = 0
    for y in (1, 5, 9, 13):
        for x in range(1, 18, 2):
            result, _ = play(game, x, y)
            gifts += sum(1 for m in result.messages if "乘胜追击" in m)
    assert gifts == gameplay_config.ROGUE_STREAK_MAX_TRIGGERS, gifts
    reset_rogue_effect_state(game)
    assert game.rogue_streaks == {} and game.rogue_streak_triggers == {}


def main() -> None:
    smoke_cards_are_registered()
    smoke_momentum_rewards_every_third_contact_move()
    smoke_iron_wall_reinforces_weakest_group()
    smoke_capture_chain_pays_from_second_capture()
    smoke_triggers_are_capped_and_reset_per_game()
    print("streak cards smoke ok")


if __name__ == "__main__":
    main()
