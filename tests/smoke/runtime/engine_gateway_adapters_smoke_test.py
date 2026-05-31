from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import traceback
from types import SimpleNamespace

import server as s
from app.runtime.engine_gateway_adapters import (
    EngineGatewayRuntime,
    analyze_current_position,
    bind_engine_gateway,
    empty_analysis_result,
    estimate_side_winrate,
    gtp_safe_sync_sgf_path,
    pick_analysis_point,
    send_engine_command,
    sync_board,
    sync_board_locked,
    sync_engine_komi,
)
from app.runtime.service_bindings import EngineGatewayBinding


class FakeGateway:
    def __init__(self) -> None:
        self.bind_calls = []
        self.events = []

    def bind_runtime(self, **kwargs) -> None:
        self.bind_calls.append(kwargs)
        self.events.append(("bind", kwargs["engine"]))

    async def send_command(self, command: str) -> str:
        self.events.append(("send", command))
        return f"sent:{command}"

    async def sync_komi(self, game) -> None:
        self.events.append(("sync_komi", game.komi))

    def sync_board_locked(self, game):
        self.events.append(("sync_board_locked", game.name))
        return f"sync-locked:{game.name}"

    def gtp_safe_sync_sgf_path(self, game) -> str:
        self.events.append(("gtp_safe_path", game.name))
        return f"safe/{game.name}.sgf"

    async def sync_board(self, game) -> None:
        self.events.append(("sync_board", game.name))

    def empty_analysis_result(self):
        self.events.append(("empty_analysis",))
        return {"analysis_ready": False}

    async def analyze_current_position(self, game, color=None, *, sync_board=None):
        self.events.append(("analyze_current_position", game.name, color, sync_board is not None))
        if sync_board is not None:
            await sync_board(game)
        return {"color": color}

    async def estimate_side_winrate(self, game, color, *, sync_board=None):
        self.events.append(("estimate_side_winrate", game.name, color, sync_board is not None))
        if sync_board is not None:
            await sync_board(game)
        return 0.42

    async def pick_analysis_point(self, game, color, *, start_index=0):
        self.events.append(("pick_analysis_point", game.name, color, start_index))
        return (start_index, start_index + 1)


async def fake_executor(func, *args):
    return func(*args)


def fake_visits(*_args):
    return 100


def fake_coord(*_args):
    return None


def fake_log(_message: str) -> None:
    return None


def fake_traceback() -> None:
    return None


def make_runtime(gateway: FakeGateway, engine: object) -> EngineGatewayRuntime:
    return EngineGatewayRuntime(
        gateway=gateway,
        binding=EngineGatewayBinding(
            engine=engine,
            get_game_visits=fake_visits,
            gtp_to_coord=fake_coord,
            run_in_executor=fake_executor,
            log_fn=fake_log,
            traceback_fn=fake_traceback,
        ),
    )


async def smoke_engine_gateway_runtime_binds_before_actions() -> None:
    gateway = FakeGateway()
    first_engine = object()
    second_engine = object()

    bind_engine_gateway(make_runtime(gateway, first_engine))
    assert gateway.bind_calls[-1]["engine"] is first_engine

    result = await send_engine_command(make_runtime(gateway, second_engine), "name")
    assert result == "sent:name"
    assert gateway.events[-2:] == [("bind", second_engine), ("send", "name")]

    game = SimpleNamespace(komi=6.5)
    await sync_engine_komi(make_runtime(gateway, first_engine), game)
    assert gateway.events[-2:] == [("bind", first_engine), ("sync_komi", 6.5)]


async def smoke_engine_gateway_runtime_binds_before_board_and_analysis_ops() -> None:
    gateway = FakeGateway()
    engine = object()
    runtime = make_runtime(gateway, engine)
    game = SimpleNamespace(name="game-a")
    sync_calls = []

    async def patched_sync(game_arg):
        sync_calls.append(game_arg is game)

    assert sync_board_locked(runtime, game) == "sync-locked:game-a"
    assert gtp_safe_sync_sgf_path(runtime, game) == "safe/game-a.sgf"
    await sync_board(runtime, game)
    assert empty_analysis_result(runtime) == {"analysis_ready": False}
    assert await analyze_current_position(
        runtime,
        game,
        color="W",
        sync_board=patched_sync,
    ) == {"color": "W"}
    assert await estimate_side_winrate(
        runtime,
        game,
        "B",
        sync_board=patched_sync,
    ) == 0.42
    assert await pick_analysis_point(runtime, game, "W", start_index=2) == (2, 3)

    assert sync_calls == [True, True]
    assert gateway.events == [
        ("bind", engine),
        ("sync_board_locked", "game-a"),
        ("bind", engine),
        ("gtp_safe_path", "game-a"),
        ("bind", engine),
        ("sync_board", "game-a"),
        ("empty_analysis",),
        ("bind", engine),
        ("analyze_current_position", "game-a", "W", True),
        ("bind", engine),
        ("estimate_side_winrate", "game-a", "B", True),
        ("bind", engine),
        ("pick_analysis_point", "game-a", "W", 2),
    ]


async def smoke_server_engine_gateway_runtime_resolves_current_objects() -> None:
    originals = {
        "engine": s.engine,
        "engine_gateway": s.engine_gateway,
        "run_in_executor": s.run_in_executor,
        "get_game_visits": s.get_game_visits,
        "gtp_to_coord": s.gtp_to_coord,
    }
    gateway = FakeGateway()
    engine = object()

    try:
        s.engine = engine
        s.engine_gateway = gateway
        s.run_in_executor = fake_executor
        s.get_game_visits = fake_visits
        s.gtp_to_coord = fake_coord

        runtime = s._engine_gateway_runtime()
        assert runtime.gateway is gateway
        assert runtime.binding.engine is engine
        assert runtime.binding.run_in_executor is fake_executor
        assert runtime.binding.get_game_visits is fake_visits
        assert runtime.binding.gtp_to_coord is fake_coord
        assert runtime.binding.log_fn is print
        assert runtime.binding.traceback_fn is traceback.print_exc

        s._bind_engine_gateway_runtime()
        assert await s._send_engine_command("boardsize 9") == "sent:boardsize 9"
        await s._sync_engine_komi(SimpleNamespace(komi=7.5))

        game = SimpleNamespace(name="server-game", komi=6.5)
        s._sync_board_to_katago_locked(game)
        assert s._gtp_safe_sync_sgf_path(game) == "safe/server-game.sgf"
        await s._sync_board_to_katago(game)
        assert s._empty_analysis_result() == {"analysis_ready": False}
        assert await s._analyze_current_position(game, "W") == {"color": "W"}
        assert await s._estimate_side_winrate(game, "B") == 0.42
        assert await s._pick_analysis_point(game, "W", start_index=3) == (3, 4)
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert gateway.events[:5] == [
        ("bind", engine),
        ("bind", engine),
        ("send", "boardsize 9"),
        ("bind", engine),
        ("sync_komi", 7.5),
    ]
    assert gateway.events[5:] == [
        ("bind", engine),
        ("sync_board_locked", "server-game"),
        ("bind", engine),
        ("gtp_safe_path", "server-game"),
        ("bind", engine),
        ("sync_board", "server-game"),
        ("empty_analysis",),
        ("bind", engine),
        ("analyze_current_position", "server-game", "W", True),
        ("bind", engine),
        ("sync_board", "server-game"),
        ("bind", engine),
        ("estimate_side_winrate", "server-game", "B", True),
        ("bind", engine),
        ("sync_board", "server-game"),
        ("bind", engine),
        ("pick_analysis_point", "server-game", "W", 3),
    ]


async def main() -> None:
    await smoke_engine_gateway_runtime_binds_before_actions()
    await smoke_engine_gateway_runtime_binds_before_board_and_analysis_ops()
    await smoke_server_engine_gateway_runtime_resolves_current_objects()
    print("engine gateway adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
