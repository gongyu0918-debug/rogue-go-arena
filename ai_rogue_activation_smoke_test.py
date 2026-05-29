from __future__ import annotations

import asyncio
import copy

import app.config.gameplay as gameplay_config
import server as s
from app.data.cards import get_rogue_card
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import apply_ai_rogue_card_activation


def _game() -> GoGame:
    game = GoGame(size=9, player_color="B")
    game.ai_rogue_enabled = False
    game.ai_rogue_card = "old"
    game.ai_rogue_seal_points = [(1, 1)]
    game.ai_rogue_sansan_trap_done = True
    return game


def test_ai_rogue_activation_resets_base_state() -> None:
    game = _game()

    apply_ai_rogue_card_activation(
        game,
        "dice",
        refresh_ai_rogue_player_turn_fn=lambda _game: None,
    )

    assert game.ai_rogue_enabled is True
    assert game.ai_rogue_card == "dice"
    assert game.ai_rogue_seal_points == []
    assert game.ai_rogue_sansan_trap_done is False


def test_ai_rogue_activation_blackhole_and_golden_corner() -> None:
    game = _game()

    apply_ai_rogue_card_activation(
        game,
        "blackhole",
        get_blackhole_points_fn=lambda _size: [(4, 4)],
        refresh_ai_rogue_player_turn_fn=lambda _game: None,
    )

    assert game.ai_rogue_card == "blackhole"
    assert game.ai_rogue_seal_points == [(4, 4)]
    assert game.ai_rogue_sansan_trap_done is False

    game = _game()
    apply_ai_rogue_card_activation(
        game,
        "golden_corner",
        choose_corner=lambda: 2,
        get_golden_corner_points_fn=lambda _size, corner, span: [(corner, span)],
        refresh_ai_rogue_player_turn_fn=lambda _game: None,
        golden_corner_span=3,
    )

    assert game.ai_rogue_card == "golden_corner"
    assert game.ai_rogue_seal_points == [(2, 3)]


def test_ai_rogue_activation_fog_uses_refresh_callback() -> None:
    game = _game()
    calls = []

    def refresh(game_arg):
        calls.append(game_arg is game)
        game_arg.ai_rogue_seal_points = [(3, 3)]

    apply_ai_rogue_card_activation(
        game,
        "fog",
        refresh_ai_rogue_player_turn_fn=refresh,
    )

    assert calls == [True]
    assert game.ai_rogue_card == "fog"
    assert game.ai_rogue_seal_points == [(3, 3)]


async def _server_activate_ai_rogue_card_wrapper_sends_payload_and_injects_dependencies() -> None:
    game = _game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    def fake_activation(game_arg, card_id, **kwargs):
        calls.append((
            game_arg is game,
            card_id,
            kwargs["choose_corner"]() == 1,
            kwargs["get_blackhole_points_fn"] is s._get_blackhole_points,
            kwargs["get_golden_corner_points_fn"] is s._get_golden_corner_points,
            kwargs["refresh_ai_rogue_player_turn_fn"] is s._refresh_ai_rogue_player_turn,
            kwargs["golden_corner_span"] == 6,
        ))
        game_arg.ai_rogue_enabled = True
        game_arg.ai_rogue_card = card_id
        game_arg.ai_rogue_seal_points = [(8, 8)]
        game_arg.ai_rogue_sansan_trap_done = False

    original_random_int = s.random.randint
    original_activation = s.apply_ai_rogue_card_activation
    original_span = s.ROGUE_GOLDEN_CORNER_SPAN
    s.random.randint = lambda _low, _high: 1
    s.apply_ai_rogue_card_activation = fake_activation
    s.ROGUE_GOLDEN_CORNER_SPAN = 6
    try:
        await s._activate_ai_rogue_card(game, send, "golden_corner")
    finally:
        s.random.randint = original_random_int
        s.apply_ai_rogue_card_activation = original_activation
        s.ROGUE_GOLDEN_CORNER_SPAN = original_span

    assert calls == [(True, "golden_corner", True, True, True, True, True)]
    assert sent == [{
        "type": "rogue_ai_selected",
        "card_id": "golden_corner",
        "name": get_rogue_card("golden_corner")["name"],
        "icon": get_rogue_card("golden_corner")["icon"],
        **game.to_state(),
    }]


def test_server_activate_ai_rogue_card_wrapper_sends_payload_and_injects_dependencies() -> None:
    asyncio.run(_server_activate_ai_rogue_card_wrapper_sends_payload_and_injects_dependencies())


async def _server_activate_ai_rogue_card_wrapper_calls_get_rogue_card() -> None:
    game = _game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    def fake_get_rogue_card(card_id):
        calls.append(("get_card", card_id))
        return {"name": "Fake AI", "icon": "FA"}

    def fake_activation(game_arg, card_id, **_kwargs):
        calls.append(("activation", card_id))
        game_arg.ai_rogue_enabled = True
        game_arg.ai_rogue_card = card_id
        game_arg.ai_rogue_seal_points = []
        game_arg.ai_rogue_sansan_trap_done = False

    original_get_rogue_card = s.get_rogue_card
    original_activation = s.apply_ai_rogue_card_activation
    s.get_rogue_card = fake_get_rogue_card
    s.apply_ai_rogue_card_activation = fake_activation
    try:
        await s._activate_ai_rogue_card(game, send, "fog")
    finally:
        s.get_rogue_card = original_get_rogue_card
        s.apply_ai_rogue_card_activation = original_activation

    assert calls == [("get_card", "fog"), ("activation", "fog")]
    assert sent[0]["name"] == "Fake AI"
    assert sent[0]["icon"] == "FA"


def test_server_activate_ai_rogue_card_wrapper_calls_get_rogue_card() -> None:
    asyncio.run(_server_activate_ai_rogue_card_wrapper_calls_get_rogue_card())


if __name__ == "__main__":
    test_ai_rogue_activation_resets_base_state()
    test_ai_rogue_activation_blackhole_and_golden_corner()
    test_ai_rogue_activation_fog_uses_refresh_callback()
    test_server_activate_ai_rogue_card_wrapper_sends_payload_and_injects_dependencies()
    test_server_activate_ai_rogue_card_wrapper_calls_get_rogue_card()
    print("ai_rogue_activation_smoke_test passed")
