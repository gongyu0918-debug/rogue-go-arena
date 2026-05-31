from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter

from app.runtime.engine_control_api import restart_katago_request, stop_katago_request
from app.runtime.rank_api import build_rank_options


@dataclass(frozen=True)
class RuntimeControlRoutesBinding:
    rank_labels: Mapping[str, str]
    engine_runtime: Any
    run_in_executor: Callable[..., Awaitable[Any]]


RuntimeControlRoutesBindingProvider = Callable[[], RuntimeControlRoutesBinding]


def build_runtime_control_router(
    binding_provider: RuntimeControlRoutesBindingProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get("/ranks")
    async def get_ranks():
        return build_rank_options(binding_provider().rank_labels)

    @router.post("/stop_katago")
    async def stop_katago():
        """Stop the KataGo engine while keeping the server running."""
        binding = binding_provider()
        return await stop_katago_request(
            engine_runtime=binding.engine_runtime,
            run_in_executor=binding.run_in_executor,
        )

    @router.post("/restart_katago")
    async def restart_katago():
        """Restart the KataGo engine."""
        return restart_katago_request(
            engine_runtime=binding_provider().engine_runtime,
        )

    return router
