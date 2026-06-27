from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from app.runtime.engine_control_api import is_loopback_client
from app.runtime.gpu_info import CachedGpuInfo, runtime_gpu_info_payload
from app.runtime.sgf_export import build_sgf_export_response
from app.runtime.status_endpoint import build_runtime_status_payload


@dataclass(frozen=True)
class RuntimeInfoRoutesBinding:
    server_rev: str
    host: str
    port: int
    get_access_urls: Callable[[str, int], dict[str, list[str]]]
    engine: Any
    engine_runtime: Any
    engine_state_snapshot: Callable[[], dict[str, Any]]
    card_config_service: Any
    no_katago: bool
    static_dir: Path
    gpu_detector: CachedGpuInfo
    run_in_executor: Callable[..., Awaitable[Any]]
    large_model_path: Path
    active_games: Any
    generate_sgf: Callable[[Any], str]
    desktop_exit_token: str | None


RuntimeInfoRoutesBindingProvider = Callable[[], RuntimeInfoRoutesBinding]


def build_runtime_info_router(
    binding_provider: RuntimeInfoRoutesBindingProvider,
) -> APIRouter:
    router = APIRouter()

    @router.get("/status")
    async def get_status(request: Request):
        binding = binding_provider()
        local_exit_token = (
            binding.desktop_exit_token
            if is_loopback_client(request.client.host if request.client else None)
            else None
        )
        return build_runtime_status_payload(
            server_rev=binding.server_rev,
            host=binding.host,
            port=binding.port,
            get_access_urls=binding.get_access_urls,
            engine=binding.engine,
            engine_runtime=binding.engine_runtime,
            engine_state_snapshot=binding.engine_state_snapshot,
            card_config_service=binding.card_config_service,
            no_katago=binding.no_katago,
            static_index_path=binding.static_dir / "index.html",
            active_games=binding.active_games,
            desktop_exit_token=local_exit_token,
        )

    @router.get("/gpu")
    async def get_gpu_info():
        binding = binding_provider()
        return await runtime_gpu_info_payload(
            detector=binding.gpu_detector,
            run_in_executor=binding.run_in_executor,
            cpu_mode_fn=lambda: binding_provider().engine_runtime.cpu_mode,
            large_model_path=binding.large_model_path,
        )

    @router.get("/sgf/{game_id}")
    async def export_sgf(game_id: str):
        binding = binding_provider()
        return build_sgf_export_response(
            game_id=game_id,
            active_games=binding.active_games,
            generate_sgf=binding.generate_sgf,
        )

    return router
