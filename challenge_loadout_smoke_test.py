from __future__ import annotations

import asyncio
import copy

import server as s
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import (
    ChallengeRogueLoadoutResult,
    apply_challenge_rogue_loadout,
)


def _game() -> GoGame:
    game = GoGame(size=9, player_color="B", level="5k")
    game.challenge_beta = True
    return game


def test_challenge_loadout_empty_resets_state() -> None:
    game = _game()
    game.challenge_cards = ["missing"]
    game.rogue_card = "old"
    game.rogue_enabled = True
    game.rogue_uses = {"old": 2}
    game.rogue_seal_points = [(1, 1)]
    game.rogue_handicap_active = True
    game.rogue_handicap_bonuses = 2
    game.rogue_handicap_passes = 2

    result = apply_challenge_rogue_loadout(
        game,
        card_ids_fn=lambda _cards: [],
        get_rogue_card_fn=lambda _card_id: (_ for _ in ()).throw(AssertionError("no cards expected")),
    )

    assert result == ChallengeRogueLoadoutResult(cards=[])
    assert game.rogue_card is None
    assert game.rogue_enabled is False
    assert game.rogue_uses == {}
    assert game.rogue_seal_points == []
    assert game.rogue_handicap_active is False
    assert game.rogue_handicap_bonuses == 0
    assert game.rogue_handicap_passes == 0


def test_challenge_loadout_applies_stackable_card_state() -> None:
    game = _game()
    game.challenge_cards = [
        "komi_relief",
        "blackhole",
        "golden_corner",
        "joseki_ocd",
        "god_hand",
        "quickthink",
        "coach_mode",
        "twin",
    ]
    calls = []

    result = apply_challenge_rogue_loadout(
        game,
        card_ids_fn=lambda cards: list(cards),
        get_rogue_card_fn=s.get_rogue_card,
        active_use_bonus_fn=lambda _game, card_id: calls.append(("bonus", card_id)) or 1,
        challenge_zone_points_fn=lambda _game, points: [(x + 10, y + 10) for x, y in points],
        choose_corner=lambda: 2,
        make_rng=lambda: calls.append(("rng",)) or object(),
        get_blackhole_points_fn=lambda _size: [(0, 0)],
        get_golden_corner_points_fn=lambda _size, corner, span: [(corner, span)],
        pick_joseki_targets_fn=lambda _size, _count: [(0, 0), (1, 1)],
        random_hidden_center_fn=lambda _size, _radius, _rng: (4, 4),
        diamond_points_fn=lambda x, y, radius, size: [(x, y), (radius, size)],
        golden_corner_span=3,
        joseki_target_count=2,
        godhand_radius=4,
    )

    assert result == ChallengeRogueLoadoutResult(cards=game.challenge_cards)
    assert game.rogue_card == "twin"
    assert game.rogue_enabled is True
    assert game.komi == 0.5
    assert game.rogue_seal_points == [(10, 10), (12, 13)]
    assert game.rogue_joseki_targets == [(0, 0), (1, 1)]
    assert game.rogue_godhand_center == (4, 4)
    assert game.rogue_godhand_trigger == [(4, 4), (4, game.size)]
    assert game.rogue_quickthink_stage == 1
    assert game.rogue_uses["twin"] == s.get_rogue_card("twin")["uses"] + 1
    assert game.rogue_uses["coach_mode"] == s.get_rogue_card("coach_mode").get("uses", 1) + 1
    assert ("rng",) in calls


def test_challenge_loadout_preserves_filtering_and_conditional_initializers() -> None:
    game = _game()
    game.challenge_cards = ["missing", "twin"]

    result = apply_challenge_rogue_loadout(
        game,
        card_ids_fn=s.rogue_card_ids,
        get_rogue_card_fn=s.get_rogue_card,
    )

    assert result == ChallengeRogueLoadoutResult(cards=["twin"])
    assert game.rogue_card == "twin"
    assert game.rogue_enabled is True

    white_game = GoGame(size=9, komi=7.5, player_color="W", level="5k")
    white_game.challenge_beta = True
    white_game.challenge_cards = ["komi_relief"]
    apply_challenge_rogue_loadout(
        white_game,
        card_ids_fn=s.rogue_card_ids,
        get_rogue_card_fn=s.get_rogue_card,
    )
    assert white_game.komi == 14.5

    game = _game()
    game.current_player = game.ai_color
    game.challenge_cards = ["quickthink"]
    apply_challenge_rogue_loadout(
        game,
        card_ids_fn=s.rogue_card_ids,
        get_rogue_card_fn=s.get_rogue_card,
    )
    assert game.rogue_quickthink_stage == 0

    game = _game()
    game.challenge_cards = ["joseki_ocd", "joseki_ocd", "god_hand", "god_hand"]
    calls = []
    apply_challenge_rogue_loadout(
        game,
        card_ids_fn=lambda cards: list(cards),
        get_rogue_card_fn=s.get_rogue_card,
        pick_joseki_targets_fn=lambda _size, _count: calls.append("joseki") or [(0, 0)],
        make_rng=lambda: calls.append("rng") or object(),
        random_hidden_center_fn=lambda _size, _radius, _rng: (4, 4),
        diamond_points_fn=lambda x, y, radius, size: [(x, y), (radius, size)],
    )
    assert calls == ["joseki", "rng"]
    assert game.rogue_joseki_targets == [(0, 0)]
    assert game.rogue_godhand_trigger


async def _server_challenge_loadout_wrapper_injects_dependencies_and_syncs_komi() -> None:
    game = _game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def run_executor(func, *args):
        calls.append(("executor", func is s.engine.send_command, args))
        return func(*args)

    def send_command(command):
        calls.append(("engine", command))
        return "="

    def fake_loadout(game_arg, **kwargs):
        calls.append((
            "loadout",
            game_arg is game,
            kwargs["card_ids_fn"] is s.rogue_card_ids,
            kwargs["get_rogue_card_fn"] is s.get_rogue_card,
            kwargs["active_use_bonus_fn"] is s._challenge_active_use_bonus,
            kwargs["challenge_zone_points_fn"] is s._challenge_zone_points,
            kwargs["choose_corner"]() == 3,
            callable(kwargs["make_rng"]),
            kwargs["get_blackhole_points_fn"] is s._get_blackhole_points,
            kwargs["get_golden_corner_points_fn"] is s._get_golden_corner_points,
            kwargs["pick_joseki_targets_fn"] is s._pick_joseki_targets,
            kwargs["random_hidden_center_fn"] is s._random_hidden_center,
            kwargs["diamond_points_fn"] is s._diamond_points,
            kwargs["golden_corner_span"] == 6,
            kwargs["joseki_target_count"] == 5,
            kwargs["godhand_radius"] == 4,
        ))
        game_arg.komi = 4.5
        return ChallengeRogueLoadoutResult(cards=["komi_relief"])

    original_ready = s.engine.ready
    original_send_command = s.engine.send_command
    original_run_executor = s.run_in_executor
    original_loadout = s.apply_challenge_rogue_loadout_state
    original_random_int = s.random.randint
    original_span = s.ROGUE_GOLDEN_CORNER_SPAN
    original_joseki_count = s.ROGUE_JOSEKI_TARGET_COUNT
    original_godhand_radius = s.ROGUE_GODHAND_RADIUS
    s.engine.ready = True
    s.engine.send_command = send_command
    s.run_in_executor = run_executor
    s.apply_challenge_rogue_loadout_state = fake_loadout
    s.random.randint = lambda _low, _high: 3
    s.ROGUE_GOLDEN_CORNER_SPAN = 6
    s.ROGUE_JOSEKI_TARGET_COUNT = 5
    s.ROGUE_GODHAND_RADIUS = 4
    try:
        await s._apply_challenge_rogue_loadout(game, send)
    finally:
        s.engine.ready = original_ready
        s.engine.send_command = original_send_command
        s.run_in_executor = original_run_executor
        s.apply_challenge_rogue_loadout_state = original_loadout
        s.random.randint = original_random_int
        s.ROGUE_GOLDEN_CORNER_SPAN = original_span
        s.ROGUE_JOSEKI_TARGET_COUNT = original_joseki_count
        s.ROGUE_GODHAND_RADIUS = original_godhand_radius

    assert calls == [
        (
            "loadout",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
        ("executor", True, ("komi 4.5",)),
        ("engine", "komi 4.5"),
    ]
    assert sent == []


def test_server_challenge_loadout_wrapper_injects_dependencies_and_syncs_komi() -> None:
    asyncio.run(_server_challenge_loadout_wrapper_injects_dependencies_and_syncs_komi())


async def _server_challenge_loadout_wrapper_syncs_whenever_engine_ready() -> None:
    game = _game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def run_executor(*_args):
        calls.append("executor")

    def fake_loadout(_game, **_kwargs):
        return ChallengeRogueLoadoutResult(cards=[])

    original_ready = s.engine.ready
    original_run_executor = s.run_in_executor
    original_loadout = s.apply_challenge_rogue_loadout_state
    s.engine.ready = False
    s.run_in_executor = run_executor
    s.apply_challenge_rogue_loadout_state = fake_loadout
    try:
        await s._apply_challenge_rogue_loadout(game, send)
    finally:
        s.engine.ready = original_ready
        s.run_in_executor = original_run_executor
        s.apply_challenge_rogue_loadout_state = original_loadout

    assert calls == []
    assert sent == []

    def fake_no_sync_field(_game, **_kwargs):
        return ChallengeRogueLoadoutResult(cards=[])

    original_ready = s.engine.ready
    original_run_executor = s.run_in_executor
    original_loadout = s.apply_challenge_rogue_loadout_state
    s.engine.ready = True
    s.run_in_executor = run_executor
    s.apply_challenge_rogue_loadout_state = fake_no_sync_field
    try:
        await s._apply_challenge_rogue_loadout(game, send)
    finally:
        s.engine.ready = original_ready
        s.run_in_executor = original_run_executor
        s.apply_challenge_rogue_loadout_state = original_loadout

    assert calls == ["executor"]
    assert sent == []


def test_server_challenge_loadout_wrapper_syncs_whenever_engine_ready() -> None:
    asyncio.run(_server_challenge_loadout_wrapper_syncs_whenever_engine_ready())


if __name__ == "__main__":
    test_challenge_loadout_empty_resets_state()
    test_challenge_loadout_applies_stackable_card_state()
    test_challenge_loadout_preserves_filtering_and_conditional_initializers()
    test_server_challenge_loadout_wrapper_injects_dependencies_and_syncs_komi()
    test_server_challenge_loadout_wrapper_syncs_whenever_engine_ready()
    print("challenge_loadout_smoke_test passed")
