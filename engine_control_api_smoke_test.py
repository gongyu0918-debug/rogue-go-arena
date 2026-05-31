from __future__ import annotations

import asyncio

import server as s
from app.runtime.control_routes import RuntimeControlRoutesBinding, build_runtime_control_router
from app.runtime.engine_control_api import restart_katago_request, stop_katago_request


class FakeEngineRuntime:
    def __init__(self) -> None:
        self.calls = []

    def stop_via_api(self) -> dict:
        self.calls.append("stop")
        return {"ok": True, "action": "stop"}

    def restart_via_api(self) -> dict:
        self.calls.append("restart")
        return {"ok": True, "action": "restart"}


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


async def smoke_engine_control_router_resolves_runtime_deps_late() -> None:
    runtime = FakeEngineRuntime()
    executor_calls = []

    async def inline_executor(func, *args):
        executor_calls.append((func, args))
        return func(*args)

    current = {"runtime": runtime}

    def binding_provider():
        return RuntimeControlRoutesBinding(
            rank_labels={},
            engine_runtime=current["runtime"],
            run_in_executor=inline_executor,
        )

    router = build_runtime_control_router(binding_provider)
    stop_endpoint = endpoint_for(router.routes, "/stop_katago", "POST")
    restart_endpoint = endpoint_for(router.routes, "/restart_katago", "POST")
    stopped = await stop_endpoint()
    restarted = await restart_endpoint()

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert runtime.calls == ["stop", "restart"]
    assert executor_calls == [(runtime.stop_via_api, ())]
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
    try:
        s.engine_runtime = runtime
        s.run_in_executor = inline_executor

        assert s._runtime_control_routes_binding().engine_runtime is runtime
        stop_endpoint = endpoint_for(s.app.routes, "/stop_katago", "POST")
        restart_endpoint = endpoint_for(s.app.routes, "/restart_katago", "POST")
        stopped = await stop_endpoint()
        restarted = await restart_endpoint()
    finally:
        s.engine_runtime = original_runtime
        s.run_in_executor = original_executor

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert runtime.calls == ["stop", "restart"]
    assert executor_calls == [(runtime.stop_via_api, ())]
    assert stop_endpoint.__doc__ == "Stop the KataGo engine while keeping the server running."
    assert restart_endpoint.__doc__ == "Restart the KataGo engine."


async def main() -> None:
    await smoke_engine_control_helpers_preserve_stop_executor_and_restart_sync()
    await smoke_engine_control_router_resolves_runtime_deps_late()
    await smoke_server_engine_control_routes_resolve_runtime_deps_late()
    print("engine control api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
