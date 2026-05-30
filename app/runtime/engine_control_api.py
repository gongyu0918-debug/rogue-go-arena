from __future__ import annotations

from collections.abc import Awaitable, Callable
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
