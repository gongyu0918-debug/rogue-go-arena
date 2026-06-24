from __future__ import annotations

from collections.abc import Awaitable, Callable
import ipaddress
from typing import Any


ExecutorFn = Callable[..., Awaitable[Any]]


async def stop_katago_request(
    *,
    engine_runtime: Any,
    run_in_executor: ExecutorFn,
) -> dict[str, Any]:
    return await run_in_executor(engine_runtime.stop_via_api)


def restart_katago_request(*, engine_runtime: Any) -> dict[str, Any]:
    return engine_runtime.restart_via_api()


def is_loopback_client(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def shutdown_server_request(*, client_host: str | None, shutdown_server: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if not is_loopback_client(client_host):
        return {"ok": False, "error": "shutdown is only available from localhost"}
    return shutdown_server()
