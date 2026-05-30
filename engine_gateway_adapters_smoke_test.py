from __future__ import annotations

import asyncio
import traceback
from types import SimpleNamespace

import server as s
from app.runtime.engine_gateway_adapters import (
    EngineGatewayRuntime,
    bind_engine_gateway,
    send_engine_command,
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
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert gateway.events == [
        ("bind", engine),
        ("bind", engine),
        ("send", "boardsize 9"),
        ("bind", engine),
        ("sync_komi", 7.5),
    ]


async def main() -> None:
    await smoke_engine_gateway_runtime_binds_before_actions()
    await smoke_server_engine_gateway_runtime_resolves_current_objects()
    print("engine gateway adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
