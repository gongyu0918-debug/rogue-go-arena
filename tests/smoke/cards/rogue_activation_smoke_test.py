from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import copy

import app.config.gameplay as gameplay_config
import server as s
from app.data.cards import get_rogue_card
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.gameplay.rogue_effects import (
    RogueCardActivationResult,
    apply_rogue_card_activation,
)


def _game() -> GoGame:
    return GoGame(size=9, komi=7.5, player_color="B", level="5k")


def test_rogue_activation_komi_relief_and_reset() -> None:
    game = _game()
    game.rogue_waiting_seal = True
    game.rogue_seal_points = [(1, 1)]

    result = apply_rogue_card_activation(
        game,
        "komi_relief",
        get_rogue_card("komi_relief"),
        coord_to_gtp=coord_to_gtp,
    )

    assert result == RogueCardActivationResult(messages=[], sync_komi=True)
    assert game.rogue_card == "komi_relief"
    assert game.komi == 0.5
    assert game.rogue_waiting_seal is False
    assert game.rogue_seal_points == []

    white_game = GoGame(size=9, komi=7.5, player_color="W", level="5k")
    result = apply_rogue_card_activation(
        white_game,
        "komi_relief",
        get_rogue_card("komi_relief"),
        coord_to_gtp=coord_to_gtp,
    )
    assert result.sync_komi is True
    assert white_game.komi == 14.5


def test_rogue_activation_waiting_and_zone_messages() -> None:
    game = _game()
    result = apply_rogue_card_activation(
        game,
        "seal",
        get_rogue_card("seal"),
        coord_to_gtp=coord_to_gtp,
    )
    assert result == RogueCardActivationResult(messages=[], sync_komi=False)
    assert game.rogue_waiting_seal is True

    game = _game()
    result = apply_rogue_card_activation(
        game,
        "blackhole",
        get_rogue_card("blackhole"),
        coord_to_gtp=coord_to_gtp,
        get_blackhole_points_fn=lambda _size: [(4, 4)],
    )
    assert game.rogue_seal_points == [(4, 4)]
    assert result.messages == ["黑洞已锁定中央区域，整局都会限制 AI 进入"]

    game = _game()
    result = apply_rogue_card_activation(
        game,
        "golden_corner",
        get_rogue_card("golden_corner"),
        coord_to_gtp=coord_to_gtp,
        choose_corner=lambda: 1,
        get_golden_corner_points_fn=lambda _size, corner, span: [(corner, span)],
    )
    assert game.rogue_seal_points == [(1, gameplay_config.ROGUE_GOLDEN_CORNER_SPAN)]
    assert result.messages == [
        f"黄金角已封锁 右上角 的 {gameplay_config.ROGUE_GOLDEN_CORNER_SPAN}x"
        f"{gameplay_config.ROGUE_GOLDEN_CORNER_SPAN} 区域，整局都会限制 AI 进入"
    ]


def test_rogue_activation_joseki_godhand_quickthink_and_coach() -> None:
    game = _game()
    targets = [(0, 0), (1, 1)]
    result = apply_rogue_card_activation(
        game,
        "joseki_ocd",
        get_rogue_card("joseki_ocd"),
        coord_to_gtp=coord_to_gtp,
        pick_joseki_targets_fn=lambda _size, _count: targets,
    )
    assert game.rogue_joseki_targets == targets
    assert result.messages == [
        f"定式强迫症已点亮 {gameplay_config.ROGUE_JOSEKI_TARGET_COUNT} 个目标点：A9, B8。"
        f"命中其中 {gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS} 个后会自动补上剩余 "
        f"{gameplay_config.ROGUE_JOSEKI_TARGET_COUNT - gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS} 个点位"
    ]

    game = _game()
    rng_calls = []
    result = apply_rogue_card_activation(
        game,
        "god_hand",
        get_rogue_card("god_hand"),
        coord_to_gtp=coord_to_gtp,
        make_rng=lambda: rng_calls.append("rng") or object(),
        random_hidden_center_fn=lambda _size, _radius, _rng: (4, 4),
        diamond_points_fn=lambda x, y, radius, size: [(x, y), (radius, size)],
    )
    assert result == RogueCardActivationResult(messages=[], sync_komi=False)
    assert rng_calls == ["rng"]
    assert game.rogue_godhand_center == (4, 4)
    assert game.rogue_godhand_trigger == [(4, 4), (gameplay_config.ROGUE_GODHAND_RADIUS, game.size)]

    game = _game()
    result = apply_rogue_card_activation(
        game,
        "quickthink",
        get_rogue_card("quickthink"),
        coord_to_gtp=coord_to_gtp,
    )
    assert result.messages == []
    assert game.rogue_quickthink_stage == 1

    game = _game()
    game.current_player = game.ai_color
    result = apply_rogue_card_activation(
        game,
        "quickthink",
        get_rogue_card("quickthink"),
        coord_to_gtp=coord_to_gtp,
    )
    assert result.messages == []
    assert game.rogue_quickthink_stage == 0

    game = _game()
    result = apply_rogue_card_activation(
        game,
        "coach_mode",
        get_rogue_card("coach_mode"),
        coord_to_gtp=coord_to_gtp,
    )
    assert result.messages == []
    assert game.rogue_uses["coach_mode"] == 1


async def _server_activate_rogue_card_wrapper_sends_events_and_syncs_komi() -> None:
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

    def fake_activation(game_arg, card_id, card_def, **kwargs):
        calls.append((
            "activation",
            game_arg is game,
            card_id,
            card_def is get_rogue_card("blackhole"),
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            callable(kwargs["choose_corner"]),
            callable(kwargs["make_rng"]),
            kwargs["get_blackhole_points_fn"] is s._get_blackhole_points,
            kwargs["get_golden_corner_points_fn"] is s._get_golden_corner_points,
            kwargs["pick_joseki_targets_fn"] is s._pick_joseki_targets,
            kwargs["random_hidden_center_fn"] is s._random_hidden_center,
            kwargs["diamond_points_fn"] is s._diamond_points,
        ))
        game_arg.rogue_card = card_id
        game_arg.komi = 3.5
        return RogueCardActivationResult(messages=["activation event"], sync_komi=True)

    original_ready = s.engine.ready
    original_send_command = s.engine.send_command
    original_run_executor = s.run_in_executor
    original_activation = s.apply_rogue_card_activation
    s.engine.ready = True
    s.engine.send_command = send_command
    s.run_in_executor = run_executor
    s.apply_rogue_card_activation = fake_activation
    try:
        await s._activate_rogue_card(game, send, "blackhole")
    finally:
        s.engine.ready = original_ready
        s.engine.send_command = original_send_command
        s.run_in_executor = original_run_executor
        s.apply_rogue_card_activation = original_activation

    assert calls == [
        (
            "activation",
            True,
            "blackhole",
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
        ("executor", True, ("komi 3.5",)),
        ("engine", "komi 3.5"),
    ]
    assert sent[0] == {"type": "rogue_event", "msg": "activation event"}
    assert sent[1]["type"] == "rogue_card_selected"
    assert sent[1]["card_id"] == "blackhole"
    assert sent[1]["waiting_seal"] is False
    assert sent[1]["name"] == get_rogue_card("blackhole")["name"]
    assert sent[1]["icon"] == get_rogue_card("blackhole")["icon"]
    assert sent[1]["rogue_card"] == "blackhole"
    assert sent[1]["komi"] == 3.5


def test_server_activate_rogue_card_wrapper_sends_events_and_syncs_komi() -> None:
    asyncio.run(_server_activate_rogue_card_wrapper_sends_events_and_syncs_komi())


async def _server_activate_rogue_card_wrapper_skips_komi_sync_when_not_needed_or_not_ready() -> None:
    game = _game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def run_executor(func, *args):
        calls.append(("executor", func, args))
        return func(*args)

    def fake_activation(game_arg, card_id, _card_def, **_kwargs):
        game_arg.rogue_card = card_id
        return RogueCardActivationResult(messages=[], sync_komi=False)

    original_ready = s.engine.ready
    original_run_executor = s.run_in_executor
    original_activation = s.apply_rogue_card_activation
    s.engine.ready = True
    s.run_in_executor = run_executor
    s.apply_rogue_card_activation = fake_activation
    try:
        await s._activate_rogue_card(game, send, "seal")
    finally:
        s.engine.ready = original_ready
        s.run_in_executor = original_run_executor
        s.apply_rogue_card_activation = original_activation

    assert calls == []
    assert sent[0]["type"] == "rogue_card_selected"
    assert sent[0]["card_id"] == "seal"

    game = _game()
    sent = []
    calls = []

    def fake_komi_activation(game_arg, card_id, _card_def, **_kwargs):
        game_arg.rogue_card = card_id
        game_arg.komi = 0.5
        return RogueCardActivationResult(messages=[], sync_komi=True)

    original_ready = s.engine.ready
    original_run_executor = s.run_in_executor
    original_activation = s.apply_rogue_card_activation
    s.engine.ready = False
    s.run_in_executor = run_executor
    s.apply_rogue_card_activation = fake_komi_activation
    try:
        await s._activate_rogue_card(game, send, "komi_relief")
    finally:
        s.engine.ready = original_ready
        s.run_in_executor = original_run_executor
        s.apply_rogue_card_activation = original_activation

    assert calls == []
    assert sent[0]["type"] == "rogue_card_selected"
    assert sent[0]["card_id"] == "komi_relief"
    assert sent[0]["komi"] == 0.5


def test_server_activate_rogue_card_wrapper_skips_komi_sync_when_not_needed_or_not_ready() -> None:
    asyncio.run(_server_activate_rogue_card_wrapper_skips_komi_sync_when_not_needed_or_not_ready())


if __name__ == "__main__":
    test_rogue_activation_komi_relief_and_reset()
    test_rogue_activation_waiting_and_zone_messages()
    test_rogue_activation_joseki_godhand_quickthink_and_coach()
    test_server_activate_rogue_card_wrapper_sends_events_and_syncs_komi()
    test_server_activate_rogue_card_wrapper_skips_komi_sync_when_not_needed_or_not_ready()
    print("rogue_activation_smoke_test passed")
