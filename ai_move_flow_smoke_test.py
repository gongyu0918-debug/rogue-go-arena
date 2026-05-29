from __future__ import annotations

import asyncio

import app.config.gameplay as gameplay_config
import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import (
    AiMoveAdjustment,
    AiMoveResolution,
    apply_slip_ai_move,
    finalize_ai_move,
    finalize_forced_ai_pass,
    resolve_ai_resign_move,
    retry_ai_move_avoiding_ko,
    try_apply_puppet_ai_move,
    try_finalize_forced_ai_stone,
    try_finish_suboptimal_rogue_move,
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
    history_len = len(game._history)
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
    assert len(game._history) == history_len + 1
    assert calls == [
        ("engine", "play W D3"),
        ("prepare", "B"),
        ("send", "game_state", None, None, None, None, None),
        ("send", "ai_move", "D3", "W", 3, 2, None),
        ("send", "rogue_event", None, None, None, None, "forced stone"),
    ]


def test_try_finalize_forced_ai_stone_sends_legacy_payloads() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_sends_legacy_payloads())


async def _try_finalize_forced_ai_stone_can_skip_history_push() -> None:
    game = GoGame(size=5, player_color="B")
    history_len = len(game._history)
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

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
        push_history=False,
    )

    assert succeeded is True
    assert game.board[2][3] == 2
    assert game.moves[-1] == ("W", "D3")
    assert len(game._history) == history_len
    assert calls == [
        ("engine", "play W D3"),
        ("prepare", "B"),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("send", "rogue_event", None),
    ]


def test_try_finalize_forced_ai_stone_can_skip_history_push() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_can_skip_history_push())


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
            kwargs.get("push_history", True),
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


async def _server_ai_move_tengen_delegates_to_forced_stone_without_history() -> None:
    class TargetPlan:
        coord = (2, 2)
        message = "天元压迫触发"

    game = GoGame(size=5, player_color="B")
    game.rogue_card = "tengen"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_choose_tengen_target(game_arg, ai_move_count):
        calls.append(("target", game_arg is game, ai_move_count))
        return TargetPlan()

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs["push_history"],
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_choose_tengen_target = s.choose_tengen_target
    original_forced_stone = s.try_finalize_forced_ai_stone
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_tengen_target = fake_choose_tengen_target
    s.try_finalize_forced_ai_stone = fake_forced_stone
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_tengen_target = original_choose_tengen_target
        s.try_finalize_forced_ai_stone = original_forced_stone

    assert calls == [
        ("sync", True),
        ("target", True, 0),
        (
            "forced_stone",
            True,
            True,
            "W",
            "C3",
            (2, 2),
            "天元压迫触发",
            False,
            True,
            True,
        ),
    ]


def test_server_ai_move_tengen_delegates_to_forced_stone_without_history() -> None:
    asyncio.run(_server_ai_move_tengen_delegates_to_forced_stone_without_history())


async def _server_ai_move_tengen_helper_false_falls_back_to_followup() -> None:
    class TargetPlan:
        coord = (2, 2)
        message = "天元压迫触发"

    class Restriction:
        points = [(0, 0)]
        message = "天元后续限制"

    game = GoGame(size=5, player_color="B")
    game.rogue_card = "tengen"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_choose_tengen_target(game_arg, ai_move_count):
        calls.append(("target", game_arg is game, ai_move_count))
        return TargetPlan()

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["gtp_move"],
            kwargs["push_history"],
        ))
        return False

    def fake_tengen_followup_points(game_arg, ai_move_count):
        calls.append(("followup", game_arg is game, ai_move_count))
        return Restriction()

    async def fake_allow_only(game_arg, color, visits, time_limit, points):
        calls.append(("allow_only", game_arg is game, color, points))
        return "C3"

    async def fake_finish(game_arg, send_fn, color, card, gtp_move, rogue_msg=None):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            color,
            card,
            gtp_move,
            rogue_msg,
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_choose_tengen_target = s.choose_tengen_target
    original_forced_stone = s.try_finalize_forced_ai_stone
    original_tengen_followup_points = s.tengen_followup_points
    original_allow_only = s._ai_move_avoid_points_allow_only
    original_finish = s._finish_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_tengen_target = fake_choose_tengen_target
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s.tengen_followup_points = fake_tengen_followup_points
    s._ai_move_avoid_points_allow_only = fake_allow_only
    s._finish_ai_move = fake_finish
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_tengen_target = original_choose_tengen_target
        s.try_finalize_forced_ai_stone = original_forced_stone
        s.tengen_followup_points = original_tengen_followup_points
        s._ai_move_avoid_points_allow_only = original_allow_only
        s._finish_ai_move = original_finish

    assert calls == [
        ("sync", True),
        ("target", True, 0),
        ("forced_stone", True, True, "C3", False),
        ("followup", True, 0),
        ("allow_only", True, "W", [(0, 0)]),
        ("finish", True, True, "W", "tengen", "C3", "天元后续限制"),
    ]


def test_server_ai_move_tengen_helper_false_falls_back_to_followup() -> None:
    asyncio.run(_server_ai_move_tengen_helper_false_falls_back_to_followup())


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


def test_apply_slip_ai_move_skips_without_card_or_playable_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result_no_card = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards=set(),
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )
    result_pass = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="pass",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result_no_card == AiMoveAdjustment("C3")
    assert result_pass == AiMoveAdjustment("pass")
    assert calls == []


def test_apply_slip_ai_move_skips_resign_without_random() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="RESIGN",
        roll_random=roll_random,
        choose_point=lambda points: points[0],
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result == AiMoveAdjustment("RESIGN")
    assert calls == []


def test_apply_slip_ai_move_skips_on_chance_miss() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return gameplay_config.ROGUE_SLIP_CHANCE

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=lambda points: points[0],
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [("random",)]


def test_apply_slip_ai_move_keeps_move_when_coord_parse_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return None

    def adjacent_points(*_args):
        calls.append(("adjacent",))
        return [(1, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def format_coord(*_args):
        calls.append(("format",))
        return "B2"

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=format_coord,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("parse", "C3", 5),
    ]


def test_apply_slip_ai_move_slips_to_legal_neighbor() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[2][1] = 1
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(1, 2), (3, 2), (2, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    game.is_legal_move = lambda x, y, color: (x, y, color) != (3, 2, "W")

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment(
        "C4",
        needs_sync=True,
        message="手滑了触发，AI 原本想下 C3，结果滑到 C4",
    )
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
        ("choice", [(2, 1)]),
    ]


def test_apply_slip_ai_move_keeps_move_when_format_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(2, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def format_coord(x, y, size):
        calls.append(("format", x, y, size))
        return None

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=format_coord,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
        ("choice", [(2, 1)]),
        ("format", 2, 1, 5),
    ]


def test_apply_slip_ai_move_keeps_move_without_legal_neighbor() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[2][1] = 1
    game.board[2][3] = 1
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(1, 2), (3, 2)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
    ]


async def _server_ai_move_slip_delegates_to_slip_adjustment() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "slip"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append((
            "slip",
            game_arg is game,
            kwargs["color"],
            "slip" in kwargs["rogue_cards"],
            kwargs["gtp_move"],
            kwargs["roll_random"] is s.random.random,
            kwargs["choose_point"] is s.random.choice,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["adjacent_points"] is s._adjacent_points,
        ))
        return AiMoveAdjustment("D3", needs_sync=True, message="slip msg")

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s._ai_retry_avoiding_ko
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s._ai_retry_avoiding_ko = lambda *_args: (_ for _ in ()).throw(AssertionError("retry should not be called"))
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s._ai_retry_avoiding_ko = original_retry
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "W", True, "C3", True, True, True, True, True),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None, None),
        ("send", "ai_move", "D3", None),
        ("send", "rogue_event", None, "slip msg"),
        ("coach", True, True),
    ]


def test_server_ai_move_slip_delegates_to_slip_adjustment() -> None:
    asyncio.run(_server_ai_move_slip_delegates_to_slip_adjustment())


async def _retry_ai_move_avoiding_ko_skips_pass_and_resign() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    pass_result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="pass",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )
    resign_result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="RESIGN",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert pass_result == AiMoveAdjustment("pass", message="slip msg")
    assert resign_result == AiMoveAdjustment("RESIGN", message="slip msg")
    assert calls == []


def test_retry_ai_move_avoiding_ko_skips_pass_and_resign() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_skips_pass_and_resign())


async def _retry_ai_move_avoiding_ko_preserves_non_ko_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: False

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="C3",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("C3", message="slip msg")
    assert calls == [("parse", "C3", 5)]


def test_retry_ai_move_avoiding_ko_preserves_non_ko_message() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_preserves_non_ko_message())


async def _retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return None

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="bad-move",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("bad-move", message="slip msg")
    assert calls == [("parse", "bad-move", 5)]


def test_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails())


async def _retry_ai_move_avoiding_ko_retries_and_clears_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="C3",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("D3", message=None)
    assert calls == [
        ("parse", "C3", 5),
        ("retry", True, "W"),
    ]


def test_retry_ai_move_avoiding_ko_retries_and_clears_message() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_retries_and_clears_message())


async def _server_ai_move_ko_guard_runs_after_slip_and_clears_message() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "slip"
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= E5"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment("C3", needs_sync=True, message="slip msg")

    async def fake_retry(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "D3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s._ai_retry_avoiding_ko
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s._ai_retry_avoiding_ko = fake_retry
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s._ai_retry_avoiding_ko = original_retry
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "E5"),
        ("retry", True, "W"),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None, None),
        ("send", "ai_move", "D3", None),
        ("coach", True, True),
    ]


def test_server_ai_move_ko_guard_runs_after_slip_and_clears_message() -> None:
    asyncio.run(_server_ai_move_ko_guard_runs_after_slip_and_clears_message())


async def _resolve_ai_resign_move_keeps_non_resign_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(_game, _color):
        calls.append(("no_resign",))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="C3",
        rogue_cards=set(),
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("C3")
    assert game.game_over is False
    assert calls == []


def test_resolve_ai_resign_move_keeps_non_resign_move() -> None:
    asyncio.run(_resolve_ai_resign_move_keeps_non_resign_move())


async def _resolve_ai_resign_move_uses_no_resign_with_rogue_card() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="RESIGN",
        rogue_cards={"suboptimal"},
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("D3")
    assert game.game_over is False
    assert calls == [("no_resign", True, "W")]


def test_resolve_ai_resign_move_uses_no_resign_with_rogue_card() -> None:
    asyncio.run(_resolve_ai_resign_move_uses_no_resign_with_rogue_card())


async def _resolve_ai_resign_move_ends_game_without_rogue_card() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(_game, _color):
        calls.append(("no_resign",))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="resign",
        rogue_cards=set(),
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("resign", completed=True)
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


def test_resolve_ai_resign_move_ends_game_without_rogue_card() -> None:
    asyncio.run(_resolve_ai_resign_move_ends_game_without_rogue_card())


async def _server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append((
            "resign",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["rogue_cards"],
            kwargs["no_resign_move"] is s._ai_move_no_resign,
        ))
        return AiMoveResolution("RESIGN", completed=True)

    def fake_slip(*_args, **_kwargs):
        calls.append(("slip",))
        return AiMoveAdjustment("C3")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip

    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("resign", True, True, "W", "RESIGN", set(), True),
    ]


def test_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete() -> None:
    asyncio.run(_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete())


async def _server_ai_move_resign_flow_replacement_continues_to_slip() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_suboptimal_flow(*_args, **_kwargs):
        calls.append(("suboptimal_flow",))
        return False

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"], "suboptimal" in kwargs["rogue_cards"]))
        return AiMoveResolution("D3")

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow",),
        ("generate", "W", True, True),
        ("resign", True, True, "RESIGN", True),
        ("slip", True, "D3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("coach", True, True),
    ]


def test_server_ai_move_resign_flow_replacement_continues_to_slip() -> None:
    asyncio.run(_server_ai_move_resign_flow_replacement_continues_to_slip())


async def _server_ai_move_real_resign_helper_rogue_replacement_continues() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_suboptimal_flow(*_args, **_kwargs):
        calls.append(("suboptimal_flow",))
        return False

    async def fake_no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_no_resign = s._ai_move_no_resign
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s._ai_move_no_resign = fake_no_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s._ai_move_no_resign = original_no_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow",),
        ("generate", "W", True, True),
        ("no_resign", True, "W"),
        ("slip", True, "D3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("coach", True, True),
    ]


def test_server_ai_move_real_resign_helper_rogue_replacement_continues() -> None:
    asyncio.run(_server_ai_move_real_resign_helper_rogue_replacement_continues())


async def _server_ai_move_real_resign_helper_plain_resign_returns() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    def fake_slip(*_args, **_kwargs):
        calls.append(("slip",))
        return AiMoveAdjustment("C3")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip

    assert game.game_over is True
    assert game.winner == "B"
    assert game.moves == []
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("send", {
            "type": "game_over",
            "winner": "B",
            "score": None,
            "reason": "ai_resign",
        }),
    ]


def test_server_ai_move_real_resign_helper_plain_resign_returns() -> None:
    asyncio.run(_server_ai_move_real_resign_helper_plain_resign_returns())


async def _try_finish_suboptimal_rogue_move_uses_nerf_backup_first() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx, end_idx):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="nerf",
        rogue_cards={"nerf", "time_press", "suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll",),
        ("choose", True, "W", 99, 0.5, 1, 5),
        ("finish", True, True, "W", "nerf", "D3", "弱化触发，AI 在多个备选点里误选了一手"),
    ]


def test_try_finish_suboptimal_rogue_move_uses_nerf_backup_first() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_uses_nerf_backup_first())


async def _try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(game_arg, color, visits, time_limit):
        calls.append(("choose", game_arg is game, color, visits, time_limit))
        return "E3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("choose", True, "W", 99, 0.5),
        ("finish", True, True, "W", "suboptimal", "E3", "次优之选触发，AI 采用了较弱备选点"),
    ]


def test_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature())


async def _try_finish_suboptimal_rogue_move_continues_after_miss_or_none() -> None:
    game = GoGame(size=5, player_color="B")
    rolls = iter([1.0, 0.0])
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        value = next(rolls)
        calls.append(("roll", value))
        return value

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx=2, end_idx=5):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        if (start_idx, end_idx) == (1, 4):
            return None
        return "E3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"nerf", "time_press", "suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll", 1.0),
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 4),
        ("choose", True, "W", 99, 0.5, 2, 5),
        ("finish", True, True, "W", "suboptimal", "E3", "次优之选触发，AI 采用了较弱备选点"),
    ]


def test_try_finish_suboptimal_rogue_move_continues_after_miss_or_none() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_continues_after_miss_or_none())


async def _try_finish_suboptimal_rogue_move_continues_after_nerf_none() -> None:
    game = GoGame(size=5, player_color="B")
    rolls = iter([0.0, 0.0])
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        value = next(rolls)
        calls.append(("roll", value))
        return value

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx, end_idx):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        if (start_idx, end_idx) == (1, 5):
            return None
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="time_press",
        rogue_cards={"nerf", "time_press"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 5),
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 4),
        ("finish", True, True, "W", "time_press", "D3", "限时压制触发，AI 仓促落在了备选点上"),
    ]


def test_try_finish_suboptimal_rogue_move_continues_after_nerf_none() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_continues_after_nerf_none())


async def _try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(*_args, **_kwargs):
        calls.append(("choose",))
        return "D3"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"nerf", "suboptimal"},
        ai_move_count=max(
            gameplay_config.ROGUE_NERF_BACKUP_AI_MOVES,
            gameplay_config.ROGUE_SUBOPTIMAL_AI_MOVES,
        ),
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert calls == []


def test_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies())


async def _server_ai_move_suboptimal_delegates_to_suboptimal_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_suboptimal_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "suboptimal_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            "suboptimal" in kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["roll_random"] is s.random.random,
            kwargs["choose_suboptimal_move"] is s._ai_move_suboptimal,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow

    assert calls == [
        ("sync", True),
        ("suboptimal_flow", True, True, "W", "suboptimal", True, 0, True, True, True, True, True),
    ]


def test_server_ai_move_suboptimal_delegates_to_suboptimal_flow() -> None:
    asyncio.run(_server_ai_move_suboptimal_delegates_to_suboptimal_flow())


async def _server_ai_move_suboptimal_flow_false_continues_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_suboptimal_flow(game_arg, send_fn, **kwargs):
        calls.append(("suboptimal_flow", game_arg is game, send_fn is send, kwargs["card"]))
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
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow", True, True, "suboptimal"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_suboptimal_flow_false_continues_to_normal_move() -> None:
    asyncio.run(_server_ai_move_suboptimal_flow_false_continues_to_normal_move())


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
    test_try_finalize_forced_ai_stone_can_skip_history_push()
    test_try_finalize_forced_ai_stone_skips_state_on_engine_error()
    test_server_ai_move_dice_delegates_to_forced_pass()
    test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass()
    test_server_ai_move_mirror_delegates_to_forced_stone()
    test_server_ai_move_mirror_helper_false_falls_back_to_normal_move()
    test_server_ai_move_tengen_delegates_to_forced_stone_without_history()
    test_server_ai_move_tengen_helper_false_falls_back_to_followup()
    test_try_apply_puppet_ai_move_success_finishes_and_updates_uses()
    test_try_apply_puppet_ai_move_occupied_target_falls_back()
    test_try_apply_puppet_ai_move_illegal_target_falls_back()
    test_try_apply_puppet_ai_move_engine_error_falls_back()
    test_server_ai_move_puppet_delegates_to_puppet_flow()
    test_server_ai_move_puppet_helper_false_falls_back_to_normal_move()
    test_server_ai_move_puppet_without_target_skips_puppet_flow()
    test_apply_slip_ai_move_skips_without_card_or_playable_move()
    test_apply_slip_ai_move_skips_resign_without_random()
    test_apply_slip_ai_move_skips_on_chance_miss()
    test_apply_slip_ai_move_keeps_move_when_coord_parse_fails()
    test_apply_slip_ai_move_slips_to_legal_neighbor()
    test_apply_slip_ai_move_keeps_move_when_format_fails()
    test_apply_slip_ai_move_keeps_move_without_legal_neighbor()
    test_server_ai_move_slip_delegates_to_slip_adjustment()
    test_retry_ai_move_avoiding_ko_skips_pass_and_resign()
    test_retry_ai_move_avoiding_ko_preserves_non_ko_message()
    test_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails()
    test_retry_ai_move_avoiding_ko_retries_and_clears_message()
    test_server_ai_move_ko_guard_runs_after_slip_and_clears_message()
    test_resolve_ai_resign_move_keeps_non_resign_move()
    test_resolve_ai_resign_move_uses_no_resign_with_rogue_card()
    test_resolve_ai_resign_move_ends_game_without_rogue_card()
    test_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete()
    test_server_ai_move_resign_flow_replacement_continues_to_slip()
    test_server_ai_move_real_resign_helper_rogue_replacement_continues()
    test_server_ai_move_real_resign_helper_plain_resign_returns()
    test_try_finish_suboptimal_rogue_move_uses_nerf_backup_first()
    test_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature()
    test_try_finish_suboptimal_rogue_move_continues_after_miss_or_none()
    test_try_finish_suboptimal_rogue_move_continues_after_nerf_none()
    test_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies()
    test_server_ai_move_suboptimal_delegates_to_suboptimal_flow()
    test_server_ai_move_suboptimal_flow_false_continues_to_normal_move()
    test_server_finish_ai_move_delegates_to_finalize_flow()
    print("ai_move_flow_smoke_test passed")
