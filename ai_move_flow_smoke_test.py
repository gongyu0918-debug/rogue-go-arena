from __future__ import annotations

import asyncio

import app.config.gameplay as gameplay_config
import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import finalize_ai_move, finalize_forced_ai_pass


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
    test_server_ai_move_dice_delegates_to_forced_pass()
    test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass()
    test_server_finish_ai_move_delegates_to_finalize_flow()
    print("ai_move_flow_smoke_test passed")
