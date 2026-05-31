from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

from fastapi import WebSocketDisconnect

import server as s
from app.runtime.observer_adapters import (
    AiObserverLoopBinding,
    ObserverDoublePassBinding,
    ObserverMovePlacementBinding,
    apply_observer_ai_move_to_board,
    build_ai_observer_loop_deps,
    finish_observer_double_pass,
    run_ai_observer_loop,
)
from app.runtime.observer_runtime import (
    ObserverDependencies,
    ObserverMoveFns,
    ObserverRuntimeFns,
    ObserverTuning,
    build_ai_observer_loop_binding,
    build_observer_double_pass_binding,
    build_observer_move_placement_binding,
)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def fake_gtp_to_coord(_move: str, _size: int):
    return (1, 2)


def fake_other_gtp_to_coord(_move: str, _size: int):
    return (3, 4)


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
        return {"current_player": self.current_player}


def smoke_loop_binding_maps_every_field() -> None:
    binding = AiObserverLoopBinding(
        engine_ready=lambda: True,
        sync_board=fake_async,
        get_game_visits=lambda _level, _move_count: 120,
        generate_ai_style_move=fake_async,
        is_suspicious_ai_pass=lambda *_args: False,
        pick_nonpass_fallback_move=fake_async,
        place_ai_move_on_board=fake_sync,
        finish_double_pass=fake_async,
        sleep=fake_async,
        opening_move_threshold=30,
    )

    deps = build_ai_observer_loop_deps(binding)

    assert deps.engine_ready() is True
    assert deps.sync_board is fake_async
    assert deps.get_game_visits("5k", 0) == 120
    assert deps.generate_ai_style_move is fake_async
    assert deps.is_suspicious_ai_pass(None, "D4", "B") is False
    assert deps.pick_nonpass_fallback_move is fake_async
    assert deps.place_ai_move_on_board is fake_sync
    assert deps.finish_double_pass is fake_async
    assert deps.sleep is fake_async
    assert deps.opening_move_threshold == 30


def smoke_observer_runtime_builders_group_dependencies() -> None:
    async def run_engine_command(command: str) -> str:
        return f"engine:{command}"

    async def sync_board(*_args, **_kwargs):
        return None

    async def sleep(_delay: float):
        return None

    def get_visits(_level: str, _move_count: int) -> int:
        return 222

    async def generate_style(*_args, **_kwargs):
        return "D4"

    def is_suspicious(*_args, **_kwargs) -> bool:
        return True

    async def pick_fallback(*_args, **_kwargs):
        return "E5"

    def place_auxiliary(*_args, **_kwargs):
        return SimpleNamespace(coord=(4, 4))

    def place_observer(*_args, **_kwargs):
        return SimpleNamespace(coord=(5, 5))

    async def finish_double_pass(*_args, **_kwargs):
        return False

    dependencies = ObserverDependencies(
        runtime=ObserverRuntimeFns(
            engine_ready=lambda: True,
            sync_board=sync_board,
            run_engine_command=run_engine_command,
            gtp_to_coord=fake_other_gtp_to_coord,
            sleep=sleep,
        ),
        moves=ObserverMoveFns(
            get_game_visits=get_visits,
            generate_ai_style_move=generate_style,
            is_suspicious_ai_pass=is_suspicious,
            pick_nonpass_fallback_move=pick_fallback,
            place_auxiliary_move=place_auxiliary,
            place_ai_move_on_board=place_observer,
            finish_double_pass=finish_double_pass,
        ),
        tuning=ObserverTuning(opening_move_threshold=44),
    )

    double_pass = build_observer_double_pass_binding(dependencies)
    placement = build_observer_move_placement_binding(dependencies)
    loop = build_ai_observer_loop_binding(dependencies)

    assert double_pass.run_engine_command is run_engine_command
    assert placement.gtp_to_coord is fake_other_gtp_to_coord
    assert placement.place_auxiliary_move is place_auxiliary
    assert loop.engine_ready() is True
    assert loop.sync_board is sync_board
    assert loop.get_game_visits is get_visits
    assert loop.generate_ai_style_move is generate_style
    assert loop.is_suspicious_ai_pass is is_suspicious
    assert loop.pick_nonpass_fallback_move is pick_fallback
    assert loop.place_ai_move_on_board is place_observer
    assert loop.finish_double_pass is finish_double_pass
    assert loop.sleep is sleep
    assert loop.opening_move_threshold == 44


async def smoke_double_pass_adapter_delegates() -> None:
    game = FakeGame()
    game.passed = {"B": True, "W": True}
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    async def run_engine(command: str) -> str:
        calls.append(("engine", command))
        return "= B+2.5"

    result = await finish_observer_double_pass(
        game,
        send,
        ObserverDoublePassBinding(run_engine_command=run_engine),
    )

    assert result is True
    assert game.game_over is True
    assert game.winner == "B"
    assert calls == [("engine", "final_score")]
    assert sent == [{"type": "game_over", "winner": "B", "score": "B+2.5", "reason": "double_pass"}]


def smoke_move_placement_adapter_delegates() -> None:
    game = FakeGame()
    calls = []

    def place(game_arg, color, gtp_move, coord):
        calls.append((game_arg is game, color, gtp_move, coord))
        return SimpleNamespace(coord=coord, captured=0)

    result = apply_observer_ai_move_to_board(
        game,
        "W",
        "D4",
        ObserverMovePlacementBinding(
            gtp_to_coord=fake_gtp_to_coord,
            place_auxiliary_move=place,
        ),
    )

    assert result.coord == (1, 2)
    assert calls == [(True, "W", "D4", (1, 2))]


async def smoke_loop_adapter_delegates() -> None:
    game = FakeGame()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def get_visits(level, move_count):
        calls.append(("visits", level, move_count))
        return 90

    async def generate(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "D4"

    def place(game_arg, color, gtp_move):
        calls.append(("place", game_arg is game, color, gtp_move))
        game_arg.moves.append((color, gtp_move))
        return SimpleNamespace(coord=(3, 5))

    async def finish(_game, _send):
        calls.append(("finish",))
        return False

    async def sleep(delay):
        calls.append(("sleep", delay))
        game.ai_observer = False

    await run_ai_observer_loop(
        game,
        send,
        AiObserverLoopBinding(
            engine_ready=lambda: True,
            sync_board=sync_board,
            get_game_visits=get_visits,
            generate_ai_style_move=generate,
            is_suspicious_ai_pass=lambda *_args: False,
            pick_nonpass_fallback_move=fake_async,
            place_ai_move_on_board=place,
            finish_double_pass=finish,
            sleep=sleep,
            opening_move_threshold=30,
        ),
    )

    assert sent[0] == {"type": "ai_move", "gtp": "D4", "color": "B", "x": 3, "y": 5}
    assert sent[1] == {"type": "game_state", "current_player": "W"}
    assert calls == [
        ("sync", True),
        ("visits", "5k", 0),
        ("generate", True, "B", 90, 4.0),
        ("place", True, "B", "D4"),
        ("finish",),
        ("sleep", 0.35),
    ]


async def smoke_adapter_propagates_disconnect_and_server_wrapper_swallows_it() -> None:
    game = FakeGame()
    calls = []

    async def send(_payload):
        calls.append(("send",))
        raise WebSocketDisconnect(code=1006)

    async def generate(*_args):
        return "D4"

    def place(_game, _color, _move):
        return SimpleNamespace(coord=(3, 5))

    binding = AiObserverLoopBinding(
        engine_ready=lambda: True,
        sync_board=lambda _game: asyncio.sleep(0),
        get_game_visits=lambda _level, _move_count: 90,
        generate_ai_style_move=generate,
        is_suspicious_ai_pass=lambda *_args: False,
        pick_nonpass_fallback_move=fake_async,
        place_ai_move_on_board=place,
        finish_double_pass=fake_async,
        sleep=fake_async,
        opening_move_threshold=30,
    )

    try:
        await run_ai_observer_loop(game, send, binding)
    except WebSocketDisconnect as exc:
        assert exc.code == 1006
    else:
        raise AssertionError("adapter should propagate WebSocketDisconnect")

    originals = {
        "_ai_observer_loop_binding": s._ai_observer_loop_binding,
    }
    try:
        s._ai_observer_loop_binding = lambda: binding
        await s._run_ai_observer_loop(game, send)
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert calls == [("send",), ("send",)]


def smoke_server_bindings_resolve_current_runtime() -> None:
    def place_auxiliary(*_args, **_kwargs):
        return SimpleNamespace(source="auxiliary")

    def place_observer(*_args, **_kwargs):
        return SimpleNamespace(source="observer")

    originals = {
        "_send_engine_command": s._send_engine_command,
        "gtp_to_coord": s.gtp_to_coord,
        "_place_auxiliary_ai_move_on_board": s._place_auxiliary_ai_move_on_board,
        "engine_ready": s.engine.ready,
        "_sync_board_to_katago": s._sync_board_to_katago,
        "get_game_visits": s.get_game_visits,
        "_generate_ai_style_move": s._generate_ai_style_move,
        "_is_suspicious_ai_pass": s._is_suspicious_ai_pass,
        "_pick_nonpass_fallback_move": s._pick_nonpass_fallback_move,
        "_apply_observer_ai_move_to_board": s._apply_observer_ai_move_to_board,
        "_finish_observer_double_pass": s._finish_observer_double_pass,
        "OPENING_MOVE_THRESHOLD": s.OPENING_MOVE_THRESHOLD,
    }
    try:
        s._send_engine_command = fake_async
        s.gtp_to_coord = fake_gtp_to_coord
        s._place_auxiliary_ai_move_on_board = place_auxiliary
        s.engine.ready = True
        s._sync_board_to_katago = fake_async
        s.get_game_visits = lambda _level, _move_count: 123
        s._generate_ai_style_move = fake_async
        s._is_suspicious_ai_pass = lambda *_args: False
        s._pick_nonpass_fallback_move = fake_async
        s._apply_observer_ai_move_to_board = place_observer
        s._finish_observer_double_pass = fake_async
        s.OPENING_MOVE_THRESHOLD = 45

        double_pass = s._observer_double_pass_binding()
        placement = s._observer_move_placement_binding()
        loop = s._ai_observer_loop_binding()

        assert double_pass.run_engine_command is fake_async
        assert placement.gtp_to_coord is fake_gtp_to_coord
        assert placement.place_auxiliary_move is place_auxiliary
        assert loop.engine_ready() is True
        assert loop.sync_board is fake_async
        assert loop.get_game_visits("5k", 0) == 123
        assert loop.generate_ai_style_move is fake_async
        assert loop.is_suspicious_ai_pass(None, "D4", "B") is False
        assert loop.pick_nonpass_fallback_move is fake_async
        assert loop.place_ai_move_on_board is place_observer
        assert loop.finish_double_pass is fake_async
        assert loop.sleep is s.asyncio.sleep
        assert loop.opening_move_threshold == 45
    finally:
        for name, value in originals.items():
            if name == "engine_ready":
                s.engine.ready = value
            else:
                setattr(s, name, value)


def main() -> None:
    smoke_loop_binding_maps_every_field()
    smoke_observer_runtime_builders_group_dependencies()
    asyncio.run(smoke_double_pass_adapter_delegates())
    smoke_move_placement_adapter_delegates()
    asyncio.run(smoke_loop_adapter_delegates())
    asyncio.run(smoke_adapter_propagates_disconnect_and_server_wrapper_swallows_it())
    smoke_server_bindings_resolve_current_runtime()
    print("observer adapters smoke test: OK")


if __name__ == "__main__":
    main()
