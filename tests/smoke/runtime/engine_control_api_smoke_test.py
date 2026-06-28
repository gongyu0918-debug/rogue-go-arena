from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.control_routes import RuntimeControlRoutesBinding, build_runtime_control_router
from app.runtime.desktop_exit import UI_EXIT_TOKEN_HEADER
from app.runtime.engine_control_api import (
    CONTROL_TOKEN_HEADER,
    control_request_authorized,
    is_loopback_client,
    restart_katago_request,
    shutdown_server_request,
    stop_katago_request,
)


class FakeEngineRuntime:
    def __init__(self) -> None:
        self.calls = []
        self.idle_timeout_seconds = 300.0

    def snapshot(self) -> dict:
        return {"phase": "ready"}

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


CONTROL_TOKEN = "smoke-control-token"


def fake_request(
    host: str = "127.0.0.1",
    token: str | None = CONTROL_TOKEN,
    header: str = CONTROL_TOKEN_HEADER,
) -> SimpleNamespace:
    headers = {}
    if token is not None:
        headers[header] = token
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


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


def smoke_control_helper_requires_localhost_and_token() -> None:
    calls = []

    def shutdown_server() -> dict:
        calls.append("shutdown")
        return {"ok": True, "action": "shutdown"}

    assert is_loopback_client("127.0.0.1")
    assert is_loopback_client("::1")
    assert is_loopback_client("localhost")
    assert not is_loopback_client("192.168.0.12")
    assert control_request_authorized(
        client_host="127.0.0.1",
        request_token=CONTROL_TOKEN,
        expected_token=CONTROL_TOKEN,
    ) == {"ok": True}
    assert control_request_authorized(
        client_host="127.0.0.1",
        request_token=None,
        expected_token=CONTROL_TOKEN,
    ) == {"ok": False, "error": "invalid control token"}
    assert control_request_authorized(
        client_host="127.0.0.1",
        request_token=CONTROL_TOKEN,
        expected_token="",
    ) == {"ok": False, "error": "control token is not configured"}
    assert shutdown_server_request(
        client_host="127.0.0.1",
        request_token=CONTROL_TOKEN,
        expected_token=CONTROL_TOKEN,
        shutdown_server=shutdown_server,
    ) == {
        "ok": True,
        "action": "shutdown",
    }
    assert shutdown_server_request(
        client_host="192.168.0.12",
        request_token=CONTROL_TOKEN,
        expected_token=CONTROL_TOKEN,
        shutdown_server=shutdown_server,
    ) == {
        "ok": False,
        "error": "control actions are only available from localhost",
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
    desktop_shutdown_calls = []

    def binding_provider():
        return RuntimeControlRoutesBinding(
            rank_labels={},
            engine=SimpleNamespace(ready=True),
            engine_runtime=current["runtime"],
            run_in_executor=inline_executor,
            save_idle_timeout_seconds=lambda value: float(value),
            shutdown_server=lambda: shutdown_calls.append("shutdown") or {"ok": True, "action": "shutdown"},
            desktop_shutdown_server=lambda: desktop_shutdown_calls.append("desktop-shutdown") or {"ok": True, "action": "shutdown"},
            control_token=CONTROL_TOKEN,
            ui_exit_token="smoke-ui-exit-token",
            active_games=SimpleNamespace(count=lambda: 0, prune=lambda: None),
        )

    router = build_runtime_control_router(binding_provider)
    stop_endpoint = endpoint_for(router.routes, "/stop_katago", "POST")
    restart_endpoint = endpoint_for(router.routes, "/restart_katago", "POST")
    shutdown_endpoint = endpoint_for(router.routes, "/shutdown", "POST")
    desktop_exit_endpoint = endpoint_for(router.routes, "/desktop_exit", "POST")
    get_idle_endpoint = endpoint_for(router.routes, "/engine_idle_timeout", "GET")
    set_idle_endpoint = endpoint_for(router.routes, "/engine_idle_timeout", "POST")
    stop_denied = None
    restart_denied = None
    try:
        await stop_endpoint(fake_request(token=None))
    except Exception as exc:
        stop_denied = exc
    try:
        await restart_endpoint(fake_request(token=None))
    except Exception as exc:
        restart_denied = exc
    stopped = await stop_endpoint(fake_request())
    restarted = await restart_endpoint(fake_request())
    shutdown_denied = None
    try:
        await shutdown_endpoint(fake_request(token=None))
    except Exception as exc:
        shutdown_denied = exc
    shutdown = await shutdown_endpoint(fake_request())
    desktop_exit_denied = None
    try:
        await desktop_exit_endpoint(fake_request(token=None, header=UI_EXIT_TOKEN_HEADER))
    except Exception as exc:
        desktop_exit_denied = exc
    desktop_exit_remote_denied = None
    try:
        await desktop_exit_endpoint(fake_request(host="192.168.0.12", token="smoke-ui-exit-token", header=UI_EXIT_TOKEN_HEADER))
    except Exception as exc:
        desktop_exit_remote_denied = exc
    desktop_exit = await desktop_exit_endpoint(fake_request(token="smoke-ui-exit-token", header=UI_EXIT_TOKEN_HEADER))
    idle_before = await get_idle_endpoint()
    idle_denied = None
    try:
        await set_idle_endpoint(fake_request(token=None), {"seconds": 120})
    except Exception as exc:
        idle_denied = exc
    idle_saved = await set_idle_endpoint(
        fake_request(token="smoke-ui-exit-token", header=UI_EXIT_TOKEN_HEADER),
        {"seconds": 120},
    )

    assert getattr(stop_denied, "status_code", None) == 403
    assert getattr(restart_denied, "status_code", None) == 403
    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert getattr(shutdown_denied, "status_code", None) == 403
    assert shutdown == {"ok": True, "action": "shutdown"}
    assert getattr(desktop_exit_denied, "status_code", None) == 403
    assert getattr(desktop_exit_remote_denied, "status_code", None) == 403
    assert desktop_exit["ok"] is True
    assert desktop_exit["action"] == "desktop_exit"
    assert desktop_exit["shutdown"] == {"ok": True, "action": "shutdown"}
    assert idle_before == {"ok": True, "seconds": 300.0, "enabled": True}
    assert getattr(idle_denied, "status_code", None) == 403
    assert idle_saved == {"ok": True, "seconds": 120.0, "enabled": True}
    assert runtime.calls == ["stop", "restart", "stop", ("idle", 120.0)]
    assert executor_calls == [(runtime.stop_via_api, ()), (runtime.stop_via_api, ())]
    assert shutdown_calls == ["shutdown"]
    assert desktop_shutdown_calls == ["desktop-shutdown"]
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
    original_token = s.CONTROL_TOKEN
    original_ui_exit_token = s.DESKTOP_EXIT_TOKEN
    shutdown_calls = []
    try:
        s.engine_runtime = runtime
        s.run_in_executor = inline_executor
        s.save_idle_timeout_seconds = lambda _path, value: float(value)
        s.request_server_shutdown = lambda: shutdown_calls.append("shutdown") or {"ok": True, "action": "shutdown"}
        s.CONTROL_TOKEN = CONTROL_TOKEN
        s.DESKTOP_EXIT_TOKEN = "server-ui-exit-token"

        assert s._runtime_control_routes_binding().engine_runtime is runtime
        assert s._runtime_control_routes_binding().ui_exit_token == "server-ui-exit-token"
        stop_endpoint = endpoint_for(s.app.routes, "/stop_katago", "POST")
        restart_endpoint = endpoint_for(s.app.routes, "/restart_katago", "POST")
        shutdown_endpoint = endpoint_for(s.app.routes, "/shutdown", "POST")
        desktop_exit_endpoint = endpoint_for(s.app.routes, "/desktop_exit", "POST")
        set_idle_endpoint = endpoint_for(s.app.routes, "/engine_idle_timeout", "POST")
        stopped = await stop_endpoint(fake_request())
        restarted = await restart_endpoint(fake_request())
        shutdown = await shutdown_endpoint(fake_request())
        desktop_exit_remote_denied = None
        try:
            await desktop_exit_endpoint(fake_request(host="10.0.0.8", token="server-ui-exit-token", header=UI_EXIT_TOKEN_HEADER))
        except Exception as exc:
            desktop_exit_remote_denied = exc
        desktop_exit = await desktop_exit_endpoint(fake_request(token="server-ui-exit-token", header=UI_EXIT_TOKEN_HEADER))
        idle_saved = await set_idle_endpoint(fake_request(), {"seconds": 0})
    finally:
        s.engine_runtime = original_runtime
        s.run_in_executor = original_executor
        s.save_idle_timeout_seconds = original_save_idle
        s.request_server_shutdown = original_shutdown
        s.CONTROL_TOKEN = original_token
        s.DESKTOP_EXIT_TOKEN = original_ui_exit_token

    assert stopped == {"ok": True, "action": "stop"}
    assert restarted == {"ok": True, "action": "restart"}
    assert shutdown == {"ok": True, "action": "shutdown"}
    assert getattr(desktop_exit_remote_denied, "status_code", None) == 403
    assert desktop_exit["action"] == "desktop_exit"
    assert idle_saved == {"ok": True, "seconds": 0.0, "enabled": False}
    assert runtime.calls == ["stop", "restart", "stop", ("idle", 0.0)]
    assert executor_calls == [(runtime.stop_via_api, ()), (runtime.stop_via_api, ())]
    assert shutdown_calls == ["shutdown", "shutdown"]
    assert stop_endpoint.__doc__ == "Stop the KataGo engine while keeping the server running."
    assert restart_endpoint.__doc__ == "Restart the KataGo engine."


async def main() -> None:
    await smoke_engine_control_helpers_preserve_stop_executor_and_restart_sync()
    smoke_control_helper_requires_localhost_and_token()
    await smoke_engine_control_router_resolves_runtime_deps_late()
    await smoke_server_engine_control_routes_resolve_runtime_deps_late()
    print("engine control api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
