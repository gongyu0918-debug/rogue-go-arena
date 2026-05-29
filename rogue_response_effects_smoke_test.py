from __future__ import annotations

import asyncio
import copy

import app.config.gameplay as gameplay_config
import server as s
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.gameplay.effect_utils import adjacent8_points
from app.gameplay.rogue_effects import (
    RogueBoardEffectResult,
    apply_ai_rogue_response_board_effects,
)


def _ai_rogue_game() -> GoGame:
    game = GoGame(size=9, player_color="B")
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "sansan_trap"
    return game


def _count_adjacent_ai_stones(game: GoGame, x: int, y: int) -> int:
    ai_val = 1 if game.ai_color == "B" else 2
    return sum(
        1
        for px, py in adjacent8_points(x, y, game.size)
        if game.board[py][px] == ai_val
    )


def test_ai_rogue_response_skips_inactive_paths() -> None:
    game = _ai_rogue_game()
    game.ai_rogue_enabled = False
    result = apply_ai_rogue_response_board_effects(
        game,
        x=2,
        y=2,
        coord_to_gtp=coord_to_gtp,
    )
    assert result == RogueBoardEffectResult(False, [], [])

    game = _ai_rogue_game()
    game.two_player = True
    result = apply_ai_rogue_response_board_effects(
        game,
        x=2,
        y=2,
        coord_to_gtp=coord_to_gtp,
    )
    assert result == RogueBoardEffectResult(False, [], [])

    game = _ai_rogue_game()
    game.ai_rogue_card = "fog"
    result = apply_ai_rogue_response_board_effects(
        game,
        x=2,
        y=2,
        coord_to_gtp=coord_to_gtp,
    )
    assert result == RogueBoardEffectResult(False, [], [])

    game = _ai_rogue_game()
    result = apply_ai_rogue_response_board_effects(
        game,
        x=4,
        y=4,
        coord_to_gtp=coord_to_gtp,
    )
    assert result == RogueBoardEffectResult(False, [], [])


def test_ai_rogue_response_sansan_trap_places_ai_stones() -> None:
    game = _ai_rogue_game()
    game.place_stone(2, 2, "B")

    result = apply_ai_rogue_response_board_effects(
        game,
        x=2,
        y=2,
        coord_to_gtp=coord_to_gtp,
        shuffle_points=lambda _points: None,
    )

    assert result.modified is True
    assert result.trap_bonus_sources == []
    assert result.messages == [
        f"三三陷阱发动，在 C7 相邻点反打 {gameplay_config.ROGUE_SANSAN_TRAP_STONES} 子"
    ]
    assert _count_adjacent_ai_stones(game, 2, 2) == gameplay_config.ROGUE_SANSAN_TRAP_STONES


def test_ai_rogue_response_sansan_trap_skips_without_empty_neighbors() -> None:
    game = _ai_rogue_game()
    game.place_stone(2, 2, "B")
    for px, py in adjacent8_points(2, 2, game.size):
        game.board[py][px] = 1

    result = apply_ai_rogue_response_board_effects(
        game,
        x=2,
        y=2,
        coord_to_gtp=coord_to_gtp,
        shuffle_points=lambda _points: None,
    )

    assert result == RogueBoardEffectResult(False, [], [])


async def _server_ai_rogue_response_wrapper_syncs_and_sends_messages() -> None:
    game = _ai_rogue_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_board_effect(game_arg, **kwargs):
        calls.append((
            "board_effect",
            game_arg is game,
            kwargs["x"],
            kwargs["y"],
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["shuffle_points"] is s.random.shuffle,
        ))
        return RogueBoardEffectResult(True, ["AI response message"], [])

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_board_effect = s.apply_ai_rogue_response_board_effects
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.apply_ai_rogue_response_board_effects = fake_board_effect
    try:
        await s._apply_ai_rogue_response_effects(game, send, 2, 2, "B")
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.apply_ai_rogue_response_board_effects = original_board_effect

    assert calls == [
        ("board_effect", True, 2, 2, True, True),
        ("sync", True),
    ]
    assert sent == [{"type": "rogue_event", "msg": "AI response message"}]


def test_server_ai_rogue_response_wrapper_syncs_and_sends_messages() -> None:
    asyncio.run(_server_ai_rogue_response_wrapper_syncs_and_sends_messages())


async def _server_ai_rogue_response_wrapper_skips_sync_without_modification() -> None:
    game = _ai_rogue_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def fake_sync(_game):
        calls.append("sync")

    def fake_board_effect(_game, **_kwargs):
        return RogueBoardEffectResult(False, [], [])

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_board_effect = s.apply_ai_rogue_response_board_effects
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.apply_ai_rogue_response_board_effects = fake_board_effect
    try:
        await s._apply_ai_rogue_response_effects(game, send, 2, 2, "B")
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.apply_ai_rogue_response_board_effects = original_board_effect

    assert calls == []
    assert sent == []


def test_server_ai_rogue_response_wrapper_skips_sync_without_modification() -> None:
    asyncio.run(_server_ai_rogue_response_wrapper_skips_sync_without_modification())


async def _server_ai_rogue_response_wrapper_sends_without_engine_sync() -> None:
    game = _ai_rogue_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def fake_sync(_game):
        calls.append("sync")

    def fake_board_effect(_game, **_kwargs):
        return RogueBoardEffectResult(True, ["first", "second"], [])

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_board_effect = s.apply_ai_rogue_response_board_effects
    s.engine.ready = False
    s._sync_board_to_katago = fake_sync
    s.apply_ai_rogue_response_board_effects = fake_board_effect
    try:
        await s._apply_ai_rogue_response_effects(game, send, 2, 2, "B")
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.apply_ai_rogue_response_board_effects = original_board_effect

    assert calls == []
    assert sent == [
        {"type": "rogue_event", "msg": "first"},
        {"type": "rogue_event", "msg": "second"},
    ]


def test_server_ai_rogue_response_wrapper_sends_without_engine_sync() -> None:
    asyncio.run(_server_ai_rogue_response_wrapper_sends_without_engine_sync())


if __name__ == "__main__":
    test_ai_rogue_response_skips_inactive_paths()
    test_ai_rogue_response_sansan_trap_places_ai_stones()
    test_ai_rogue_response_sansan_trap_skips_without_empty_neighbors()
    test_server_ai_rogue_response_wrapper_syncs_and_sends_messages()
    test_server_ai_rogue_response_wrapper_skips_sync_without_modification()
    test_server_ai_rogue_response_wrapper_sends_without_engine_sync()
    print("rogue_response_effects_smoke_test passed")
