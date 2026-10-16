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
    game.rogue_card = "attack_first"
    return game


def play(game: GoGame, x: int, y: int, color: str = "B"):
    captured = game.place_stone(x, y, color)
    assert captured >= 0, (x, y, captured)
    game.moves.append((color, coord_to_gtp(x, y, game.size)))
    if color != "B":
        return None
    return apply_player_rogue_board_effects(
        game, x=x, y=y, color=color, captured=captured,
        coord_to_gtp=coord_to_gtp, gtp_to_coord=gtp_to_coord,
    )


def new_black_stones(before: list[list[int]], game: GoGame) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
        if game.board[y][x] == 1 and before[y][x] != 1
    ]


def smoke_three_contact_moves_gift_a_stone_beside_the_fight() -> None:
    for seed in range(20):
        random.seed(seed)
        game = make_game()
        # Far-away white stones the gift used to land beside at random.
        for x, y in ((2, 2), (16, 2), (2, 16), (16, 16), (3, 15), (15, 3)):
            game.board[y][x] = 2
        for x in (7, 9, 11):
            game.board[10][x] = 2
        results = []
        for x in (7, 9, 11):
            before = [row[:] for row in game.board]
            results.append(play(game, x, 9))
        assert [r.modified for r in results] == [False, False, True], (seed, results)
        assert "进攻至上触发" in results[2].messages[0]
        gifts = [p for p in new_black_stones(before, game) if p != (11, 9)]
        assert len(gifts) == 1, (seed, gifts)
        gx, gy = gifts[0]
        reach = gameplay_config.ROGUE_ATTACK_SPAWN_RADIUS + 1
        assert abs(gx - 11) <= reach and abs(gy - 9) <= reach, (seed, gifts[0])


def smoke_a_move_away_from_the_enemy_resets_the_count() -> None:
    random.seed(1)
    game = make_game()
    for x in (5, 9, 13):
        game.board[10][x] = 2
    play(game, 5, 9)
    play(game, 9, 9)
    assert not play(game, 3, 3).modified  # tenuki
    assert not play(game, 13, 9).modified
    assert game.rogue_attack_first_triggers["B"] == 0


def smoke_triggers_at_most_twice_per_game() -> None:
    random.seed(2)
    game = make_game()
    for x in range(1, 19, 2):
        game.board[10][x] = 2
    fired = sum(1 for x in range(1, 19, 2) if play(game, x, 9).modified)
    assert fired == gameplay_config.ROGUE_SUPREMACY_MAX_TRIGGERS, fired


def main() -> None:
    smoke_three_contact_moves_gift_a_stone_beside_the_fight()
    smoke_a_move_away_from_the_enemy_resets_the_count()
    smoke_triggers_at_most_twice_per_game()
    print("attack first smoke test: OK")


if __name__ == "__main__":
    main()
