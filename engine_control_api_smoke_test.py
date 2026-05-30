from __future__ import annotations

import asyncio

import server as s
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


async def smoke_server_engine_control_wrappers_resolve_runtime_deps_late() -> None:
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

        stopped = await s.stop_katago()
        restarted = await s.restart_katago()
    finally:
        s.engine_runtime = original_runtime
        s.run_in_executor = original_executor

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert runtime.calls == ["stop", "restart"]
    assert executor_calls == [(runtime.stop_via_api, ())]


async def main() -> None:
    await smoke_engine_control_helpers_preserve_stop_executor_and_restart_sync()
    await smoke_server_engine_control_wrappers_resolve_runtime_deps_late()
    print("engine control api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
