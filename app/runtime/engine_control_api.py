from __future__ import annotations

from collections.abc import Awaitable, Callable
import ipaddress
import secrets
from typing import Any


ExecutorFn = Callable[..., Awaitable[Any]]
CONTROL_TOKEN_HEADER = "x-rogue-go-control-token"


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


def control_request_authorized(
    *,
    client_host: str | None,
    request_token: str | None,
    expected_token: str | None,
) -> dict[str, Any]:
    if not is_loopback_client(client_host):
        return {"ok": False, "error": "control actions are only available from localhost"}
    if not expected_token:
        return {"ok": False, "error": "control token is not configured"}
    if not secrets.compare_digest(request_token or "", expected_token):
        return {"ok": False, "error": "invalid control token"}
    return {"ok": True}


def shutdown_server_request(
    *,
    client_host: str | None,
    request_token: str | None,
    expected_token: str | None,
    shutdown_server: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    allowed = control_request_authorized(
        client_host=client_host,
        request_token=request_token,
        expected_token=expected_token,
    )
    if not allowed.get("ok"):
        return allowed
    return shutdown_server()
