from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.control_routes import RuntimeControlRoutesBinding, build_runtime_control_router
from app.runtime.engine_control_api import (
    is_loopback_client,
    restart_katago_request,
    shutdown_server_request,
    stop_katago_request,
)


class FakeEngineRuntime:
    def __init__(self) -> None:
        self.calls = []
        self.idle_timeout_seconds = 300.0

    def stop_via_api(self) -> dict:
        self.calls.append("stop")
        return {"ok": True, "action": "stop"}

    def restart_via_api(self) -> dict:
        self.calls.append("restart")
        return {"ok": True, "action": "restart"}

    def set_idle_timeout_seconds(self, seconds: float) -> float:
        self.calls.append(("idle", seconds))
        self.idle_timeout_seconds = seconds
        return seconds


def endpoint_for(routes, path: str, method: str):
    for route in routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


async def smoke_engine_control_helpers_preserve_stop_executor_and_restart_sync() -> None:
    runtime = FakeEngineRuntime()
    executor_calls = []

    async def inline_executor(func, *args):
        executor_calls.append((func, args))
        return func(*args)

    stopped = await stop_katago_request(
        engine_runtime=runtime,
        run_in_executor=inline_executor,
    )
    restarted = restart_katago_request(engine_runtime=runtime)

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert runtime.calls == ["stop", "restart"]
    assert executor_calls == [(runtime.stop_via_api, ())]


def smoke_shutdown_helper_rejects_non_localhost_clients() -> None:
    calls = []

    def shutdown_server() -> dict:
        calls.append("shutdown")
        return {"ok": True, "action": "shutdown"}

    assert is_loopback_client("127.0.0.1")
    assert is_loopback_client("::1")
    assert is_loopback_client("localhost")
    assert not is_loopback_client("192.168.0.12")
    assert shutdown_server_request(client_host="127.0.0.1", shutdown_server=shutdown_server) == {
        "ok": True,
        "action": "shutdown",
    }
    assert shutdown_server_request(client_host="192.168.0.12", shutdown_server=shutdown_server) == {
        "ok": False,
        "error": "shutdown is only available from localhost",
    }
    assert calls == ["shutdown"]


async def smoke_engine_control_router_resolves_runtime_deps_late() -> None:
    runtime = FakeEngineRuntime()
    executor_calls = []

    async def inline_executor(func, *args):
        executor_calls.append((func, args))
        return func(*args)

    current = {"runtime": runtime}
    shutdown_calls = []

    def binding_provider():
        return RuntimeControlRoutesBinding(
            rank_labels={},
            engine_runtime=current["runtime"],
            run_in_executor=inline_executor,
            save_idle_timeout_seconds=lambda value: float(value),
            shutdown_server=lambda: shutdown_calls.append("shutdown") or {"ok": True, "action": "shutdown"},
        )

    router = build_runtime_control_router(binding_provider)
    stop_endpoint = endpoint_for(router.routes, "/stop_katago", "POST")
    restart_endpoint = endpoint_for(router.routes, "/restart_katago", "POST")
    shutdown_endpoint = endpoint_for(router.routes, "/shutdown", "POST")
    get_idle_endpoint = endpoint_for(router.routes, "/engine_idle_timeout", "GET")
    set_idle_endpoint = endpoint_for(router.routes, "/engine_idle_timeout", "POST")
    stopped = await stop_endpoint()
    restarted = await restart_endpoint()
    shutdown = await shutdown_endpoint(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")))
    idle_before = await get_idle_endpoint()
    idle_saved = await set_idle_endpoint({"seconds": 120})

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert shutdown == {"ok": True, "action": "shutdown"}
    assert idle_before == {"ok": True, "seconds": 300.0, "enabled": True}
    assert idle_saved == {"ok": True, "seconds": 120.0, "enabled": True}
    assert runtime.calls == ["stop", "restart", ("idle", 120.0)]
    assert executor_calls == [(runtime.stop_via_api, ())]
    assert shutdown_calls == ["shutdown"]
    assert stop_endpoint.__doc__ == "Stop the KataGo engine while keeping the server running."
    assert restart_endpoint.__doc__ == "Restart the KataGo engine."


async def smoke_server_engine_control_routes_resolve_runtime_deps_late() -> None:
    runtime = FakeEngineRuntime()
    executor_calls = []

    async def inline_executor(func, *args):
        executor_calls.append((func, args))
        return func(*args)

    original_runtime = s.engine_runtime
    original_executor = s.run_in_executor
    original_save_idle = s.save_idle_timeout_seconds
    original_shutdown = s.request_server_shutdown
    shutdown_calls = []
    try:
        s.engine_runtime = runtime
        s.run_in_executor = inline_executor
        s.save_idle_timeout_seconds = lambda _path, value: float(value)
        s.request_server_shutdown = lambda: shutdown_calls.append("shutdown") or {"ok": True, "action": "shutdown"}

        assert s._runtime_control_routes_binding().engine_runtime is runtime
        stop_endpoint = endpoint_for(s.app.routes, "/stop_katago", "POST")
        restart_endpoint = endpoint_for(s.app.routes, "/restart_katago", "POST")
        shutdown_endpoint = endpoint_for(s.app.routes, "/shutdown", "POST")
        set_idle_endpoint = endpoint_for(s.app.routes, "/engine_idle_timeout", "POST")
        stopped = await stop_endpoint()
        restarted = await restart_endpoint()
        shutdown = await shutdown_endpoint(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")))
        idle_saved = await set_idle_endpoint({"seconds": 0})
    finally:
        s.engine_runtime = original_runtime
        s.run_in_executor = original_executor
        s.save_idle_timeout_seconds = original_save_idle
        s.request_server_shutdown = original_shutdown

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert shutdown == {"ok": True, "action": "shutdown"}
    assert idle_saved == {"ok": True, "seconds": 0.0, "enabled": False}
    assert runtime.calls == ["stop", "restart", ("idle", 0.0)]
    assert executor_calls == [(runtime.stop_via_api, ())]
    assert shutdown_calls == ["shutdown"]
    assert stop_endpoint.__doc__ == "Stop the KataGo engine while keeping the server running."
    assert restart_endpoint.__doc__ == "Restart the KataGo engine."


async def main() -> None:
    await smoke_engine_control_helpers_preserve_stop_executor_and_restart_sync()
    smoke_shutdown_helper_rejects_non_localhost_clients()
    await smoke_engine_control_router_resolves_runtime_deps_late()
    await smoke_server_engine_control_routes_resolve_runtime_deps_late()
    print("engine control api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
