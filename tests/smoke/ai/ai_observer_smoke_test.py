from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

from fastapi import WebSocketDisconnect

from app.domain.coordinates import gtp_to_coord
from app.gameplay.ai_observer import (
    AiObserverLoopDeps,
    apply_observer_ai_move_to_board,
    finish_observer_double_pass,
    run_ai_observer_loop,
)


class FakeGame:
    def __init__(self) -> None:
        self.size = 9
        self.game_over = False
        self.winner = None
        self.ai_observer = True
        self.current_player = "B"
        self.ai_level_black = "5k"
        self.ai_level_white = "3k"
        self.moves = []
        self.passed = {"B": False, "W": False}
        self.history_pushes = 0

    def push_history(self) -> None:
        self.history_pushes += 1

    def to_state(self) -> dict:
        return {
            "current_player": self.current_player,
            "moves": list(self.moves),
            "history_pushes": self.history_pushes,
        }


async def smoke_single_observer_turn() -> None:
    game = FakeGame()
    calls = []
    sent = []

    async def send_fn(payload):
        sent.append(payload)

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def get_game_visits(level, move_count):
        calls.append(("visits", level, move_count))
        return 120

    async def generate_ai_style_move(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "D4"

    async def pick_fallback(*_args):
        raise AssertionError("fallback should not be used")

    def place_move(game_arg, color, gtp_move):
        calls.append(("place", game_arg is game, color, gtp_move))
        game_arg.moves.append((color, gtp_move))
        return SimpleNamespace(coord=(3, 5))

    async def finish_double_pass(game_arg, _send_fn):
        calls.append(("double_pass", game_arg is game))
        return False

    async def sleep(delay):
        calls.append(("sleep", delay))
        game.ai_observer = False

    await run_ai_observer_loop(
        game,
        send_fn,
        AiObserverLoopDeps(
            engine_ready=lambda: True,
            sync_board=sync_board,
            get_game_visits=get_game_visits,
            generate_ai_style_move=generate_ai_style_move,
            is_suspicious_ai_pass=lambda *_args: False,
            pick_nonpass_fallback_move=pick_fallback,
            run_engine_command=lambda _command: asyncio.sleep(0, result="="),
            place_ai_move_on_board=place_move,
            finish_double_pass=finish_double_pass,
            sleep=sleep,
            opening_move_threshold=30,
        ),
    )

    assert game.current_player == "W"
    assert game.history_pushes == 1
    assert sent == [
        {"type": "ai_move", "gtp": "D4", "color": "B", "x": 3, "y": 5},
        {
            "type": "game_state",
            "current_player": "W",
            "moves": [("B", "D4")],
            "history_pushes": 1,
        },
    ]
    assert calls == [
        ("sync", True),
        ("visits", "5k", 0),
        ("generate", True, "B", 120, 4.0),
        ("place", True, "B", "D4"),
        ("double_pass", True),
        ("sleep", 0.35),
    ]


async def smoke_suspicious_pass_uses_fallback() -> None:
    game = FakeGame()
    placed = []
    engine_commands = []

    async def send_fn(_payload):
        pass

    async def generate_ai_style_move(*_args):
        return "PASS"

    async def pick_fallback(game_arg, color, visits):
        assert game_arg is game
        assert color == "B"
        assert visits == 80
        assert engine_commands == ["undo"]
        return "E5"

    async def run_engine_command(command):
        engine_commands.append(command)
        return "="

    def place_move(_game, color, gtp_move):
        placed.append((color, gtp_move))
        return SimpleNamespace(coord=(4, 4))

    async def finish_double_pass(_game, _send):
        return False

    async def sleep(_delay):
        game.ai_observer = False

    await run_ai_observer_loop(
        game,
        send_fn,
        AiObserverLoopDeps(
            engine_ready=lambda: True,
            sync_board=lambda _game: asyncio.sleep(0),
            get_game_visits=lambda _level, _move_count: 80,
            generate_ai_style_move=generate_ai_style_move,
            is_suspicious_ai_pass=lambda _game, move, _color: move == "PASS",
            pick_nonpass_fallback_move=pick_fallback,
            run_engine_command=run_engine_command,
            place_ai_move_on_board=place_move,
            finish_double_pass=finish_double_pass,
            sleep=sleep,
            opening_move_threshold=30,
        ),
    )

    assert placed == [("B", "E5")]
    assert engine_commands == ["undo", "play B E5"]


async def smoke_engine_error_does_not_place_observer_move() -> None:
    game = FakeGame()
    placed = []
    sent = []

    async def send_fn(payload):
        sent.append(payload)

    async def generate_ai_style_move(*_args):
        return "? timeout"

    def place_move(_game, color, gtp_move):
        placed.append((color, gtp_move))
        return SimpleNamespace(coord=None)

    await run_ai_observer_loop(
        game,
        send_fn,
        AiObserverLoopDeps(
            engine_ready=lambda: True,
            sync_board=lambda _game: asyncio.sleep(0),
            get_game_visits=lambda _level, _move_count: 80,
            generate_ai_style_move=generate_ai_style_move,
            is_suspicious_ai_pass=lambda *_args: False,
            pick_nonpass_fallback_move=lambda *_args: asyncio.sleep(0, result=None),
            run_engine_command=lambda _command: asyncio.sleep(0, result="="),
            place_ai_move_on_board=place_move,
            finish_double_pass=lambda _game, _send: asyncio.sleep(0, result=False),
            sleep=lambda _delay: asyncio.sleep(0),
            opening_move_threshold=30,
        ),
    )

    assert placed == []
    assert game.moves == []
    assert sent == [{"type": "error", "message": "AI 引擎落子失败：? timeout"}]


async def smoke_suspicious_pass_without_fallback_keeps_pass() -> None:
    game = FakeGame()
    placed = []
    engine_commands = []

    async def send_fn(_payload):
        pass

    async def generate_ai_style_move(*_args):
        return "PASS"

    async def pick_fallback(*_args):
        return None

    async def run_engine_command(command):
        engine_commands.append(command)
        return "="

    def place_move(_game, color, gtp_move):
        placed.append((color, gtp_move))
        return SimpleNamespace(coord=None)

    async def finish_double_pass(_game, _send):
        return False

    async def sleep(_delay):
        game.ai_observer = False

    await run_ai_observer_loop(
        game,
        send_fn,
        AiObserverLoopDeps(
            engine_ready=lambda: True,
            sync_board=lambda _game: asyncio.sleep(0),
            get_game_visits=lambda _level, _move_count: 80,
            generate_ai_style_move=generate_ai_style_move,
            is_suspicious_ai_pass=lambda _game, move, _color: move == "PASS",
            pick_nonpass_fallback_move=pick_fallback,
            run_engine_command=run_engine_command,
            place_ai_move_on_board=place_move,
            finish_double_pass=finish_double_pass,
            sleep=sleep,
            opening_move_threshold=30,
        ),
    )

    assert placed == [("B", "PASS")]
    assert engine_commands == ["undo", "play B pass"]


async def smoke_disconnect_propagates_to_server_wrapper() -> None:
    game = FakeGame()

    async def send_fn(_payload):
        raise WebSocketDisconnect(code=1006)

    async def generate_ai_style_move(*_args):
        return "D4"

    async def pick_fallback(*_args):
        return None

    def place_move(_game, _color, _gtp_move):
        return SimpleNamespace(coord=(3, 5))

    try:
        await run_ai_observer_loop(
            game,
            send_fn,
            AiObserverLoopDeps(
                engine_ready=lambda: True,
                sync_board=lambda _game: asyncio.sleep(0),
                get_game_visits=lambda _level, _move_count: 80,
                generate_ai_style_move=generate_ai_style_move,
                is_suspicious_ai_pass=lambda *_args: False,
                pick_nonpass_fallback_move=pick_fallback,
                run_engine_command=lambda _command: asyncio.sleep(0, result="="),
                place_ai_move_on_board=place_move,
                finish_double_pass=lambda _game, _send: asyncio.sleep(0, result=False),
                sleep=lambda _delay: asyncio.sleep(0),
                opening_move_threshold=30,
            ),
        )
    except WebSocketDisconnect as exc:
        assert exc.code == 1006
    else:
        raise AssertionError("WebSocketDisconnect should propagate to the server wrapper")


async def smoke_finish_observer_double_pass() -> None:
    game = FakeGame()
    game.passed = {"B": True, "W": True}
    sent = []

    async def send_fn(payload):
        sent.append(payload)

    async def run_engine_command(command):
        assert command == "final_score"
        return "= W+1.5"

    assert await finish_observer_double_pass(
        game,
        send_fn,
        run_engine_command=run_engine_command,
    )
    assert game.game_over is True
    assert game.winner == "W"
    assert sent == [
        {"type": "game_over", "winner": "W", "score": "W+1.5", "reason": "double_pass"}
    ]


def smoke_apply_observer_ai_move_to_board() -> None:
    game = FakeGame()
    calls = []

    def place_auxiliary_move(game_arg, color, gtp_move, coord):
        calls.append((game_arg is game, color, gtp_move, coord))
        return SimpleNamespace(coord=coord)

    result = apply_observer_ai_move_to_board(
        game,
        "B",
        "D4",
        gtp_to_coord=gtp_to_coord,
        place_auxiliary_move=place_auxiliary_move,
    )

    assert result.coord == (3, 5)
    assert calls == [(True, "B", "D4", (3, 5))]


async def main() -> None:
    await smoke_single_observer_turn()
    await smoke_suspicious_pass_uses_fallback()
    await smoke_engine_error_does_not_place_observer_move()
    await smoke_suspicious_pass_without_fallback_keeps_pass()
    await smoke_disconnect_propagates_to_server_wrapper()
    await smoke_finish_observer_double_pass()
    smoke_apply_observer_ai_move_to_board()
    print("ai observer smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
