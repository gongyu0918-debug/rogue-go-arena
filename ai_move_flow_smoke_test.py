from __future__ import annotations

import asyncio

import app.config.gameplay as gameplay_config
import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import (
    finalize_ai_move,
    finalize_forced_ai_pass,
    try_apply_puppet_ai_move,
    try_finalize_forced_ai_stone,
)


async def _unused_no_resign(_game, _color):
    raise AssertionError("no_resign_move should not be called")


async def _unused_retry_ko(_game, _color):
    raise AssertionError("retry_avoiding_ko should not be called")


async def _finalize_ai_move_places_stone_and_sends_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("x"), payload.get("y")))

    async def check_capture_foul(_game, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate, send_fn is send))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, send_fn):
        calls.append(("coach", send_fn is send))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        rogue_msg="forced move",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.board[2][2] == 2
    assert game.moves[-1] == ("W", "C3")
    assert game.passed["W"] is False
    assert game.current_player == "B"
    assert calls == [
        ("capture_foul", "W", 0, False, True),
        ("prepare", "B"),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "C3", 2, 2),
        ("send", "rogue_event", None, None, None),
        ("coach", True),
    ]


def test_finalize_ai_move_places_stone_and_sends_message() -> None:
    asyncio.run(_finalize_ai_move_places_stone_and_sends_message())


async def _finalize_ai_move_resign_without_card_ends_game() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign_move(*_args):
        calls.append(("no_resign",))
        return "C3"

    async def retry_ko(*_args):
        calls.append(("retry_ko",))
        return "D3"

    async def check_capture_foul(*_args, **_kwargs):
        calls.append(("capture_foul",))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(*_args):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="resign",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=no_resign_move,
        retry_avoiding_ko=retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is True
    assert game.winner == "B"
    assert game.moves == []
    assert calls == [
        ("send", {
            "type": "game_over",
            "winner": "B",
            "score": None,
            "reason": "ai_resign",
        }),
    ]


def test_finalize_ai_move_resign_without_card_ends_game() -> None:
    asyncio.run(_finalize_ai_move_resign_without_card_ends_game())


async def _finalize_ai_move_resign_with_card_uses_no_resign_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def no_resign_move(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "C3"

    async def check_capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card="suboptimal",
        gtp_move="RESIGN",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=no_resign_move,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is False
    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("no_resign", True, "W"),
        ("capture_foul", "W", 0, False),
        ("prepare",),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach",),
    ]


def test_finalize_ai_move_resign_with_card_uses_no_resign_move() -> None:
    asyncio.run(_finalize_ai_move_resign_with_card_uses_no_resign_move())


async def _finalize_ai_move_retries_ko_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("x"), payload.get("y")))

    async def retry_ko(game_arg, color):
        calls.append(("retry_ko", game_arg is game, color))
        return "D3"

    async def check_capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("retry_ko", True, "W"),
        ("capture_foul", "W", 0, False),
        ("prepare",),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "D3", 3, 2),
        ("coach",),
    ]


def test_finalize_ai_move_retries_ko_move() -> None:
    asyncio.run(_finalize_ai_move_retries_ko_move())


async def _finalize_ai_move_double_pass_scores_without_coach_turn() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("score")))

    async def check_capture_foul(*_args, **_kwargs):
        calls.append(("capture_foul",))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= W+0.5"

    async def run_coach_turn(*_args):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="pass",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is True
    assert game.winner == "W"
    assert game.moves[-1] == ("W", "pass")
    assert calls == [
        ("capture_foul",),
        ("prepare",),
        ("send", "game_state", None, None),
        ("engine", "final_score"),
        ("send", "ai_move", "pass", None),
        ("send", "game_over", None, "W+0.5"),
    ]


def test_finalize_ai_move_double_pass_scores_without_coach_turn() -> None:
    asyncio.run(_finalize_ai_move_double_pass_scores_without_coach_turn())


async def _finalize_ai_move_erosion_updates_komi_after_capture() -> None:
    game = GoGame(size=3, komi=0.0, player_color="B")
    game.board = [
        [0, 2, 0],
        [2, 1, 2],
        [0, 0, 0],
    ]
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def check_capture_foul(_game, _send_fn, _offender, captured, *, ultimate):
        calls.append(("capture_foul", captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card="erosion",
        gtp_move="B1",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.board[1][1] == 0
    assert game.captures["W"] == 1
    assert game.komi == gameplay_config.ROGUE_EROSION_SHIFT
    assert ("engine", f"komi {gameplay_config.ROGUE_EROSION_SHIFT}") in calls
    assert calls[:5] == [
        ("capture_foul", 1, False),
        ("prepare",),
        ("engine", f"komi {gameplay_config.ROGUE_EROSION_SHIFT}"),
        ("send", "rogue_event"),
        ("send", "game_state"),
    ]


def test_finalize_ai_move_erosion_updates_komi_after_capture() -> None:
    asyncio.run(_finalize_ai_move_erosion_updates_komi_after_capture())


async def _finalize_forced_ai_pass_sends_legacy_payloads() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append((
            "send",
            payload["type"],
            payload.get("gtp"),
            payload.get("color"),
            payload.get("msg"),
        ))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    await finalize_forced_ai_pass(
        game,
        send,
        color="W",
        message="forced pass",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert game.moves[-1] == ("W", "pass")
    assert game.passed["W"] is True
    assert game.game_over is False
    assert game.current_player == "B"
    assert calls == [
        ("engine", "play W pass"),
        ("prepare", "B"),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "pass", "W", None),
        ("send", "rogue_event", None, None, "forced pass"),
    ]


def test_finalize_forced_ai_pass_sends_legacy_payloads() -> None:
    asyncio.run(_finalize_forced_ai_pass_sends_legacy_payloads())


async def _try_finalize_forced_ai_stone_sends_legacy_payloads() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append((
            "send",
            payload["type"],
            payload.get("gtp"),
            payload.get("color"),
            payload.get("x"),
            payload.get("y"),
            payload.get("msg"),
        ))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    succeeded = await try_finalize_forced_ai_stone(
        game,
        send,
        color="W",
        gtp_move="D3",
        coord=(3, 2),
        message="forced stone",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert succeeded is True
    assert game.board[2][3] == 2
    assert game.moves[-1] == ("W", "D3")
    assert game.passed["W"] is False
    assert game.current_player == "B"
    assert calls == [
        ("engine", "play W D3"),
        ("prepare", "B"),
        ("send", "game_state", None, None, None, None, None),
        ("send", "ai_move", "D3", "W", 3, 2, None),
        ("send", "rogue_event", None, None, None, None, "forced stone"),
    ]


def test_try_finalize_forced_ai_stone_sends_legacy_payloads() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_sends_legacy_payloads())


async def _try_finalize_forced_ai_stone_skips_state_on_engine_error() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "? illegal move"

    succeeded = await try_finalize_forced_ai_stone(
        game,
        send,
        color="W",
        gtp_move="D3",
        coord=(3, 2),
        message="forced stone",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert succeeded is False
    assert game.board[2][3] == 0
    assert game.moves == []
    assert calls == [("engine", "play W D3")]


def test_try_finalize_forced_ai_stone_skips_state_on_engine_error() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_skips_state_on_engine_error())


async def _server_ai_move_dice_delegates_to_forced_pass() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "dice"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["message"],
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_pass = s.finalize_forced_ai_pass
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.finalize_forced_ai_pass = fake_forced_pass
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.finalize_forced_ai_pass = original_forced_pass

    assert calls == [
        ("sync", True),
        (
            "forced_pass",
            True,
            True,
            "W",
            "掷骰触发，AI 这手选择虚手",
            True,
            True,
        ),
    ]


def test_server_ai_move_dice_delegates_to_forced_pass() -> None:
    asyncio.run(_server_ai_move_dice_delegates_to_forced_pass())


async def _server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "exchange"
    game.rogue_skip_ai = True
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["message"],
            game.rogue_skip_ai,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_forced_pass = s.finalize_forced_ai_pass
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.finalize_forced_ai_pass = fake_forced_pass
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.finalize_forced_ai_pass = original_forced_pass

    assert calls == [
        ("sync", True),
        (
            "forced_pass",
            True,
            True,
            "W",
            "乾坤挪移生效，AI 本回合虚手并把回合交还给你",
            False,
            True,
            True,
        ),
    ]


def test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass() -> None:
    asyncio.run(_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass())


async def _server_ai_move_mirror_delegates_to_forced_stone() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "mirror"
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_stone = s.try_finalize_forced_ai_stone
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.try_finalize_forced_ai_stone = fake_forced_stone
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.try_finalize_forced_ai_stone = original_forced_stone

    assert calls == [
        ("sync", True),
        (
            "forced_stone",
            True,
            True,
            "W",
            "D4",
            (3, 1),
            "镜像触发，AI 在对称点 D4 落子",
            True,
            True,
        ),
    ]


def test_server_ai_move_mirror_delegates_to_forced_stone() -> None:
    asyncio.run(_server_ai_move_mirror_delegates_to_forced_stone())


async def _server_ai_move_mirror_helper_false_falls_back_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "mirror"
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["gtp_move"],
        ))
        return False

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_stone = s.try_finalize_forced_ai_stone
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.try_finalize_forced_ai_stone = original_forced_stone
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("forced_stone", True, True, "D4"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_mirror_helper_false_falls_back_to_normal_move() -> None:
    asyncio.run(_server_ai_move_mirror_helper_false_falls_back_to_normal_move())


async def _try_apply_puppet_ai_move_success_finishes_and_updates_uses() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.rogue_uses["puppet"] = 2
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("uses")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            color,
            card,
            gtp_move,
            rogue_msg,
            game.rogue_uses["puppet"],
        ))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert game.rogue_puppet_target is None
    assert game.rogue_uses["puppet"] == 1
    assert calls == [
        ("engine", "play W C3"),
        (
            "finish",
            True,
            True,
            "W",
            "puppet",
            "C3",
            "🎭 傀儡术生效，AI 被迫落子于 C3",
            1,
        ),
        ("send", "rogue_uses_update", {"puppet": 1}),
    ]


def test_try_apply_puppet_ai_move_success_finishes_and_updates_uses() -> None:
    asyncio.run(_try_apply_puppet_ai_move_success_finishes_and_updates_uses())


async def _try_apply_puppet_ai_move_occupied_target_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.board[2][2] = 1
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert calls == [
        ("send", "rogue_event", "🎭 傀儡术目标 C3 已被占用，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_occupied_target_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_occupied_target_falls_back())


async def _try_apply_puppet_ai_move_illegal_target_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert calls == [
        ("send", "rogue_event", "🎭 傀儡术目标 C3 当前不合法，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_illegal_target_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_illegal_target_falls_back())


async def _try_apply_puppet_ai_move_engine_error_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.rogue_uses["puppet"] = 1
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "? illegal move"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert game.rogue_uses["puppet"] == 1
    assert calls == [
        ("engine", "play W C3"),
        ("send", "rogue_event", "🎭 傀儡术目标 C3 执行失败，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_engine_error_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_engine_error_falls_back())


async def _server_ai_move_puppet_delegates_to_puppet_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = (2, 2)
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "puppet",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["target"],
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            callable(kwargs["run_engine_command"]),
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow

    assert calls == [
        ("sync", True),
        (
            "puppet",
            True,
            True,
            "W",
            "puppet",
            (2, 2),
            True,
            True,
            True,
        ),
    ]


def test_server_ai_move_puppet_delegates_to_puppet_flow() -> None:
    asyncio.run(_server_ai_move_puppet_delegates_to_puppet_flow())


async def _server_ai_move_puppet_helper_false_falls_back_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = (2, 2)
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "puppet",
            game_arg is game,
            send_fn is send,
            kwargs["target"],
        ))
        game.rogue_puppet_target = None
        return False

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("puppet", True, True, (2, 2)),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_puppet_helper_false_falls_back_to_normal_move() -> None:
    asyncio.run(_server_ai_move_puppet_helper_false_falls_back_to_normal_move())


async def _server_ai_move_puppet_without_target_skips_puppet_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = None
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(*_args, **_kwargs):
        calls.append(("puppet",))
        return True

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_puppet_without_target_skips_puppet_flow() -> None:
    asyncio.run(_server_ai_move_puppet_without_target_skips_puppet_flow())


async def _server_finish_ai_move_delegates_to_finalize_flow() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_finalize(game_arg, send_fn, **kwargs):
        calls.append((
            "finalize",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["no_resign_move"] is s._ai_move_no_resign,
            kwargs["retry_avoiding_ko"] is s._ai_retry_avoiding_ko,
            kwargs["check_capture_foul"] is s._check_capture_foul,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_coach_turn_if_needed"] is s._run_coach_turn_if_needed,
            callable(kwargs["run_engine_command"]),
        ))

    original_finalize = s.finalize_ai_move
    s.finalize_ai_move = fake_finalize
    try:
        await s._finish_ai_move(game, send, "W", "suboptimal", "D4", "message")
    finally:
        s.finalize_ai_move = original_finalize

    assert calls == [(
        "finalize",
        True,
        True,
        "W",
        "suboptimal",
        "D4",
        "message",
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )]


def test_server_finish_ai_move_delegates_to_finalize_flow() -> None:
    asyncio.run(_server_finish_ai_move_delegates_to_finalize_flow())


if __name__ == "__main__":
    test_finalize_ai_move_places_stone_and_sends_message()
    test_finalize_ai_move_resign_without_card_ends_game()
    test_finalize_ai_move_resign_with_card_uses_no_resign_move()
    test_finalize_ai_move_retries_ko_move()
    test_finalize_ai_move_double_pass_scores_without_coach_turn()
    test_finalize_ai_move_erosion_updates_komi_after_capture()
    test_finalize_forced_ai_pass_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_skips_state_on_engine_error()
    test_server_ai_move_dice_delegates_to_forced_pass()
    test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass()
    test_server_ai_move_mirror_delegates_to_forced_stone()
    test_server_ai_move_mirror_helper_false_falls_back_to_normal_move()
    test_try_apply_puppet_ai_move_success_finishes_and_updates_uses()
    test_try_apply_puppet_ai_move_occupied_target_falls_back()
    test_try_apply_puppet_ai_move_illegal_target_falls_back()
    test_try_apply_puppet_ai_move_engine_error_falls_back()
    test_server_ai_move_puppet_delegates_to_puppet_flow()
    test_server_ai_move_puppet_helper_false_falls_back_to_normal_move()
    test_server_ai_move_puppet_without_target_skips_puppet_flow()
    test_server_finish_ai_move_delegates_to_finalize_flow()
    print("ai_move_flow_smoke_test passed")
