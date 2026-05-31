from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import copy

import server as s
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import (
    RogueBoardEffectResult,
    apply_rogue_five_in_row,
    apply_rogue_last_stand,
)


class IdentityRng:
    def shuffle(self, _items) -> None:
        return None


def make_game(size: int = 9) -> GoGame:
    return GoGame(size=size, player_color="B")


def test_apply_rogue_five_in_row_places_endpoints_and_marks_seen() -> None:
    game = make_game()
    for x in range(2, 7):
        game.board[4][x] = 1
    expected_line = tuple((x, 4) for x in range(2, 7))

    result = apply_rogue_five_in_row(
        game,
        "B",
        shuffle_points=lambda _points: None,
        should_bonus_derivative_fn=lambda _game: False,
        support_stones=0,
    )

    assert result.modified is True
    assert result.trap_bonus_sources == []
    assert result.messages == [
        "🎯 五子连珠发动，正好连成 5 子，首尾额外补下 2 颗棋子"
    ]
    assert game.board[4][1] == 1
    assert game.board[4][7] == 1
    assert expected_line in game.rogue_five_in_row_seen

    second = apply_rogue_five_in_row(
        game,
        "B",
        shuffle_points=lambda _points: None,
        should_bonus_derivative_fn=lambda _game: False,
        support_stones=0,
    )
    assert second == RogueBoardEffectResult(False, [], [])


def test_apply_rogue_five_in_row_records_seen_even_without_spawn() -> None:
    game = make_game(size=5)
    for y in range(game.size):
        for x in range(game.size):
            game.board[y][x] = 1
    expected_line = tuple((x, 2) for x in range(5))

    result = apply_rogue_five_in_row(
        game,
        "B",
        shuffle_points=lambda _points: None,
        should_bonus_derivative_fn=lambda _game: False,
        support_stones=0,
    )

    assert result == RogueBoardEffectResult(False, [], [])
    assert expected_line in game.rogue_five_in_row_seen


def test_apply_rogue_last_stand_clears_spawns_and_respects_forbidden() -> None:
    game = make_game()
    game.board[4][4] = 1
    game.board[3][4] = 2
    game.board[4][3] = 2

    result = apply_rogue_last_stand(
        game,
        "B",
        (4, 4),
        rng=IdentityRng(),
        forbidden_points={(5, 4)},
        clear_count=1,
        spawn_count=2,
    )

    assert result.modified is True
    assert result.messages == [
        "🫀 起死回生发动，在上一手周围扭转局面：清掉 1 颗敌子，补下 2 颗己棋"
    ]
    assert game.rogue_last_stand_done["B"] is True
    assert game.board[3][4] == 1
    assert game.board[3][3] == 1
    assert game.board[4][5] == 0
    assert game.board[4][3] == 2

    second = apply_rogue_last_stand(
        game,
        "B",
        (4, 4),
        rng=IdentityRng(),
        clear_count=1,
        spawn_count=2,
    )
    assert second == RogueBoardEffectResult(False, [], [])


async def _server_rogue_five_in_row_wrapper_syncs_and_sends_messages() -> None:
    game = make_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_apply(game_arg, color, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            color,
            kwargs["shuffle_points"] is s.random.shuffle,
            kwargs["should_bonus_derivative_fn"] is s._challenge_should_bonus_derivative,
            kwargs["support_stones"] == s.ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
        ))
        return RogueBoardEffectResult(True, ["line event"], [])

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_apply = s.apply_rogue_five_in_row
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.apply_rogue_five_in_row = fake_apply
    try:
        await s._trigger_rogue_five_in_row(game, send, "B")
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.apply_rogue_five_in_row = original_apply

    assert calls == [
        ("apply", True, "B", True, True, True),
        ("sync", True),
    ]
    assert sent == [{"type": "rogue_event", "msg": "line event"}]


def test_server_rogue_five_in_row_wrapper_syncs_and_sends_messages() -> None:
    asyncio.run(_server_rogue_five_in_row_wrapper_syncs_and_sends_messages())


async def _server_rogue_last_stand_wrapper_keeps_guard_and_runtime_edges() -> None:
    game = make_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def fake_estimate(game_arg, color):
        calls.append(("estimate", game_arg is game, color))
        return 0.2

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_forbidden(game_arg, color):
        calls.append(("forbidden", game_arg is game, color))
        return {(5, 4)}

    def fake_apply(game_arg, color, center, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            color,
            center,
            kwargs["forbidden_points"] == {(5, 4)},
            kwargs["clear_count"] == s.ROGUE_LAST_STAND_CLEAR_COUNT,
            kwargs["spawn_count"] == s.ROGUE_LAST_STAND_SPAWN_COUNT,
        ))
        return RogueBoardEffectResult(True, ["last stand event"], [])

    original_ready = s.engine.ready
    original_estimate = s._estimate_side_winrate
    original_sync = s._sync_board_to_katago
    original_forbidden = s._get_player_bonus_forbidden_points
    original_apply = s.apply_rogue_last_stand
    s.engine.ready = True
    s._estimate_side_winrate = fake_estimate
    s._sync_board_to_katago = fake_sync
    s._get_player_bonus_forbidden_points = fake_forbidden
    s.apply_rogue_last_stand = fake_apply
    try:
        await s._trigger_rogue_last_stand(game, send, "B", (4, 4))
    finally:
        s.engine.ready = original_ready
        s._estimate_side_winrate = original_estimate
        s._sync_board_to_katago = original_sync
        s._get_player_bonus_forbidden_points = original_forbidden
        s.apply_rogue_last_stand = original_apply

    assert calls == [
        ("estimate", True, "B"),
        ("forbidden", True, "B"),
        ("apply", True, "B", (4, 4), True, True, True),
        ("sync", True),
    ]
    assert sent == [{"type": "rogue_event", "msg": "last stand event"}]


def test_server_rogue_last_stand_wrapper_keeps_guard_and_runtime_edges() -> None:
    asyncio.run(_server_rogue_last_stand_wrapper_keeps_guard_and_runtime_edges())


if __name__ == "__main__":
    test_apply_rogue_five_in_row_places_endpoints_and_marks_seen()
    test_apply_rogue_five_in_row_records_seen_even_without_spawn()
    test_apply_rogue_last_stand_clears_spawns_and_respects_forbidden()
    test_server_rogue_five_in_row_wrapper_syncs_and_sends_messages()
    test_server_rogue_last_stand_wrapper_keeps_guard_and_runtime_edges()
    print("rogue_trigger_effects_smoke_test passed")
