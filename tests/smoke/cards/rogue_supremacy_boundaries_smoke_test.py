from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
from app.domain.game_state import GoGame


async def send_noop(_payload):
    return None


def make_game(size: int = 9) -> GoGame:
    game = GoGame(size=size, komi=7.5, player_color="B", level="5k", two_player=False)
    game.current_player = game.player_color
    return game


def add_player_move(game: GoGame, move: str) -> tuple[int, int]:
    x, y = s.gtp_to_coord(move, game.size)
    game.moves.append(("B", move))
    game.board[y][x] = 1
    return x, y


def black_count(game: GoGame) -> int:
    return sum(1 for row in game.board for cell in row if cell == 1)


async def apply_player_effect(game: GoGame, x: int, y: int) -> None:
    await s._apply_player_rogue_move_effects(game, send_noop, x, y, "B", 0)


async def smoke_defense_first_boundaries() -> None:
    game = make_game()
    game.rogue_card = "defense_first"
    for move in ("A9", "E5", "J1"):
        x, y = add_player_move(game, move)

    before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == before + 1
    assert game.rogue_defense_first_triggers["B"] == 1
    assert game.rogue_defense_first_last_index["B"] == 3

    repeat_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == repeat_before
    assert game.rogue_defense_first_triggers["B"] == 1

    for move in ("A1", "C1"):
        x, y = add_player_move(game, move)
        overlap_before = black_count(game)
        await apply_player_effect(game, x, y)
        assert black_count(game) == overlap_before
        assert game.rogue_defense_first_triggers["B"] == 1
        assert game.rogue_defense_first_last_index["B"] == 3

    x, y = add_player_move(game, "D1")
    second_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == second_before + 1
    assert game.rogue_defense_first_triggers["B"] == 2
    assert game.rogue_defense_first_last_index["B"] == 6

    for move in ("F1", "G1", "H1"):
        x, y = add_player_move(game, move)
    capped_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == capped_before
    assert game.rogue_defense_first_triggers["B"] == 2
    assert game.rogue_defense_first_last_index["B"] == 6


async def smoke_defense_first_requires_safe_window() -> None:
    game = make_game()
    game.rogue_card = "defense_first"
    for move in ("C7", "E5", "G3"):
        x, y = add_player_move(game, move)
    game.board[4][5] = 2

    before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == before
    assert game.rogue_defense_first_triggers["B"] == 0
    assert game.rogue_defense_first_last_index["B"] == 0


async def smoke_attack_first_boundaries() -> None:
    game = make_game()
    game.rogue_card = "attack_first"
    for enemy in ((3, 2), (5, 4), (7, 6)):
        game.board[enemy[1]][enemy[0]] = 2
    for move in ("C7", "E5", "G3"):
        x, y = add_player_move(game, move)

    before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == before + 1
    assert game.rogue_attack_first_triggers["B"] == 1
    assert game.rogue_attack_first_last_index["B"] == 3

    repeat_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == repeat_before
    assert game.rogue_attack_first_triggers["B"] == 1

    for enemy in ((0, 7), (1, 7), (3, 8)):
        game.board[enemy[1]][enemy[0]] = 2
    for move in ("A1", "B1"):
        x, y = add_player_move(game, move)
        overlap_before = black_count(game)
        await apply_player_effect(game, x, y)
        assert black_count(game) == overlap_before
        assert game.rogue_attack_first_triggers["B"] == 1
        assert game.rogue_attack_first_last_index["B"] == 3

    x, y = add_player_move(game, "C1")
    second_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == second_before + 1
    assert game.rogue_attack_first_triggers["B"] == 2
    assert game.rogue_attack_first_last_index["B"] == 6

    for enemy in ((4, 7), (5, 7), (6, 7)):
        game.board[enemy[1]][enemy[0]] = 2
    for move in ("E1", "F1", "G1"):
        x, y = add_player_move(game, move)
    capped_before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == capped_before
    assert game.rogue_attack_first_triggers["B"] == 2
    assert game.rogue_attack_first_last_index["B"] == 6


async def smoke_attack_first_requires_enemy_contact() -> None:
    game = make_game()
    game.rogue_card = "attack_first"
    for enemy in ((3, 2), (5, 4)):
        game.board[enemy[1]][enemy[0]] = 2
    for move in ("C7", "E5", "G3"):
        x, y = add_player_move(game, move)

    before = black_count(game)
    await apply_player_effect(game, x, y)
    assert black_count(game) == before
    assert game.rogue_attack_first_triggers["B"] == 0
    assert game.rogue_attack_first_last_index["B"] == 0


async def main() -> None:
    old_sync = s._sync_board_to_katago
    old_shuffle = s.random.shuffle
    try:
        async def fake_sync(_game):
            return None

        s._sync_board_to_katago = fake_sync
        s.random.shuffle = lambda _items: None

        await smoke_defense_first_boundaries()
        await smoke_defense_first_requires_safe_window()
        await smoke_attack_first_boundaries()
        await smoke_attack_first_requires_enemy_contact()
    finally:
        s._sync_board_to_katago = old_sync
        s.random.shuffle = old_shuffle

    print("rogue_supremacy_boundaries_smoke_test passed")


if __name__ == "__main__":
    asyncio.run(main())
