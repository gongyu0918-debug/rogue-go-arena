from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from types import SimpleNamespace

import server as s
from app.runtime.service_bindings import (
    AiMoveServiceBinding,
    EngineGatewayBinding,
    bind_ai_move_service_runtime,
    bind_engine_gateway_runtime,
    send_engine_command,
    sync_engine_komi,
)
from app.runtime.service_runtime import (
    AiMoveServiceDependencies,
    EngineGatewayDependencies,
    build_ai_move_service,
    build_ai_move_service_binding,
    build_ai_move_service_runtime,
    build_engine_gateway,
    build_engine_gateway_binding,
    build_engine_gateway_runtime,
)


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


class FakeAiMoveService:
    def __init__(self) -> None:
        self.bind_calls = []

    def bind_runtime(self, **kwargs) -> None:
        self.bind_calls.append(kwargs)


class ConstructedGateway:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class ConstructedAiMoveService:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


async def fake_executor(func, *args):
    return func(*args)


def fake_visits(*_args):
    return 100


def fake_coord(*_args):
    return None


def fake_coord_to_gtp(*_args):
    return "gtp"


def fake_gtp_to_coord(*_args):
    return (0, 0)


def fake_log(_message: str) -> None:
    return None


def fake_traceback() -> None:
    return None


def make_engine_binding(engine) -> EngineGatewayBinding:
    return EngineGatewayBinding(
        engine=engine,
        get_game_visits=fake_visits,
        gtp_to_coord=fake_coord,
        run_in_executor=fake_executor,
        log_fn=fake_log,
        traceback_fn=fake_traceback,
    )


async def smoke_engine_gateway_binding_helpers_bind_before_actions() -> None:
    gateway = FakeGateway()
    first_engine = object()
    second_engine = object()

    bind_engine_gateway_runtime(gateway, make_engine_binding(first_engine))
    assert gateway.bind_calls[-1]["engine"] is first_engine

    result = await send_engine_command(gateway, "name", make_engine_binding(second_engine))
    assert result == "sent:name"
    assert gateway.events[-2:] == [("bind", second_engine), ("send", "name")]

    game = SimpleNamespace(komi=6.5)
    await sync_engine_komi(gateway, game, make_engine_binding(first_engine))
    assert gateway.events[-2:] == [("bind", first_engine), ("sync_komi", 6.5)]


def smoke_ai_move_service_binding_helper() -> None:
    service = FakeAiMoveService()
    engine = object()
    binding = AiMoveServiceBinding(engine=engine, run_in_executor=fake_executor)

    bind_ai_move_service_runtime(service, binding)

    assert service.bind_calls == [{
        "engine": engine,
        "run_in_executor": fake_executor,
    }]


def smoke_service_runtime_factories_group_dependencies() -> None:
    engine = object()
    base_dir = Path("runtime-root")

    engine_dependencies = EngineGatewayDependencies(
        engine=engine,
        base_dir=base_dir,
        get_game_visits=fake_visits,
        gtp_to_coord=fake_coord,
        run_in_executor=fake_executor,
        log_fn=fake_log,
        traceback_fn=fake_traceback,
    )
    gateway = build_engine_gateway(engine_dependencies, ConstructedGateway)
    gateway_binding = build_engine_gateway_binding(engine_dependencies)
    gateway_runtime = build_engine_gateway_runtime(gateway, engine_dependencies)

    assert gateway.kwargs == {
        "engine": engine,
        "base_dir": base_dir,
        "get_game_visits": fake_visits,
        "gtp_to_coord": fake_coord,
        "run_in_executor": fake_executor,
        "log_fn": fake_log,
        "traceback_fn": fake_traceback,
    }
    assert gateway_binding.engine is engine
    assert gateway_binding.get_game_visits is fake_visits
    assert gateway_runtime.gateway is gateway
    assert gateway_runtime.binding == gateway_binding

    ai_dependencies = AiMoveServiceDependencies(
        engine=engine,
        run_in_executor=fake_executor,
        engine_log=fake_log,
        coord_to_gtp=fake_coord_to_gtp,
        gtp_to_coord=fake_gtp_to_coord,
    )
    service = build_ai_move_service(ai_dependencies, ConstructedAiMoveService)
    ai_binding = build_ai_move_service_binding(ai_dependencies)
    ai_runtime = build_ai_move_service_runtime(service, ai_dependencies)

    assert service.kwargs == {
        "engine": engine,
        "run_in_executor": fake_executor,
        "engine_log": fake_log,
        "coord_to_gtp": fake_coord_to_gtp,
        "gtp_to_coord": fake_gtp_to_coord,
    }
    assert ai_binding.engine is engine
    assert ai_binding.run_in_executor is fake_executor
    assert ai_runtime.service is service
    assert ai_runtime.binding == ai_binding


async def smoke_server_runtime_service_wrappers_resolve_current_objects_late() -> None:
    originals = {
        "engine": s.engine,
        "engine_gateway": s.engine_gateway,
        "ai_move_service": s.ai_move_service,
        "run_in_executor": s.run_in_executor,
        "get_game_visits": s.get_game_visits,
        "gtp_to_coord": s.gtp_to_coord,
    }
    fake_gateway = FakeGateway()
    fake_service = FakeAiMoveService()
    engine = object()

    try:
        s.engine = engine
        s.engine_gateway = fake_gateway
        s.ai_move_service = fake_service
        s.run_in_executor = fake_executor
        s.get_game_visits = fake_visits
        s.gtp_to_coord = fake_coord

        gateway_binding = s._engine_gateway_binding()
        assert gateway_binding.engine is engine
        assert gateway_binding.run_in_executor is fake_executor
        assert gateway_binding.get_game_visits is fake_visits
        assert gateway_binding.gtp_to_coord is fake_coord
        assert gateway_binding.log_fn is print
        assert gateway_binding.traceback_fn is traceback.print_exc

        assert await s._send_engine_command("boardsize 9") == "sent:boardsize 9"
        await s._sync_engine_komi(SimpleNamespace(komi=7.5))
        assert fake_gateway.bind_calls[-1] == {
            "engine": engine,
            "get_game_visits": fake_visits,
            "gtp_to_coord": fake_coord,
            "run_in_executor": fake_executor,
            "log_fn": print,
            "traceback_fn": traceback.print_exc,
        }
        assert fake_gateway.events == [
            ("bind", engine),
            ("send", "boardsize 9"),
            ("bind", engine),
            ("sync_komi", 7.5),
        ]

        ai_binding = s._ai_move_service_binding()
        assert ai_binding.engine is engine
        assert ai_binding.run_in_executor is fake_executor
        s._bind_ai_move_service_runtime()
        assert fake_service.bind_calls == [{
            "engine": engine,
            "run_in_executor": fake_executor,
        }]
    finally:
        for name, value in originals.items():
            setattr(s, name, value)


async def main() -> None:
    await smoke_engine_gateway_binding_helpers_bind_before_actions()
    smoke_ai_move_service_binding_helper()
    smoke_service_runtime_factories_group_dependencies()
    await smoke_server_runtime_service_wrappers_resolve_current_objects_late()
    print("service bindings smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
