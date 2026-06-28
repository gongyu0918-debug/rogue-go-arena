from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.runtime.desktop_exit import (
    UI_EXIT_TOKEN_HEADER,
    active_game_count,
    desktop_exit_available,
    ui_exit_request_authorized,
)
from app.runtime.engine_control_api import (
    CONTROL_TOKEN_HEADER,
    control_request_authorized,
    restart_katago_request,
    shutdown_server_request,
    stop_katago_request,
)
from app.runtime.rank_api import build_rank_options


@dataclass(frozen=True)
class RuntimeControlRoutesBinding:
    rank_labels: Mapping[str, str]
    engine: Any
    engine_runtime: Any
    run_in_executor: Callable[..., Awaitable[Any]]
    save_idle_timeout_seconds: Callable[[Any], float]
    shutdown_server: Callable[[], dict[str, Any]]
    desktop_shutdown_server: Callable[[], dict[str, Any]]
    control_token: str | None
    ui_exit_token: str | None
    active_games: Any


RuntimeControlRoutesBindingProvider = Callable[[], RuntimeControlRoutesBinding]


def build_runtime_control_router(
    binding_provider: RuntimeControlRoutesBindingProvider,
) -> APIRouter:
    router = APIRouter()

    def require_control(request: Request, binding: RuntimeControlRoutesBinding) -> None:
        result = control_request_authorized(
            client_host=request.client.host if request.client else None,
            request_token=request.headers.get(CONTROL_TOKEN_HEADER),
            expected_token=binding.control_token,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=403, detail=result.get("error", "control denied"))

    @router.get("/ranks")
    async def get_ranks():
        return build_rank_options(binding_provider().rank_labels)

    @router.post("/stop_katago")
    async def stop_katago(request: Request):
        """Stop the KataGo engine while keeping the server running."""
        binding = binding_provider()
        require_control(request, binding)
        return await stop_katago_request(
            engine_runtime=binding.engine_runtime,
            run_in_executor=binding.run_in_executor,
        )

    @router.post("/restart_katago")
    async def restart_katago(request: Request):
        """Restart the KataGo engine."""
        binding = binding_provider()
        require_control(request, binding)
        return restart_katago_request(
            engine_runtime=binding.engine_runtime,
        )

    @router.post("/shutdown")
    async def shutdown_server(request: Request):
        """Stop the local desktop server process."""
        binding = binding_provider()
        result = shutdown_server_request(
            client_host=request.client.host if request.client else None,
            request_token=request.headers.get(CONTROL_TOKEN_HEADER),
            expected_token=binding.control_token,
            shutdown_server=binding.shutdown_server,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=403, detail=result.get("error", "shutdown denied"))
        return result

    @router.post("/desktop_exit")
    async def desktop_exit(request: Request):
        """Stop the engine and close the local desktop server from the game UI."""
        binding = binding_provider()
        allowed = ui_exit_request_authorized(
            client_host=request.client.host if request.client else None,
            request_token=request.headers.get(UI_EXIT_TOKEN_HEADER),
            expected_token=binding.ui_exit_token,
        )
        if not allowed.get("ok"):
            raise HTTPException(status_code=403, detail=allowed.get("error", "desktop exit denied"))

        snapshot = binding.engine_runtime.snapshot()
        game_count = active_game_count(binding.active_games)
        if not desktop_exit_available(
            engine_ready=bool(getattr(binding.engine, "ready", False)),
            engine_snapshot=snapshot,
            active_games_count=game_count,
        ):
            raise HTTPException(status_code=409, detail="desktop exit is not available before game or engine start")

        stop_result = {"ok": False, "error": "KataGo is not running"}
        if snapshot.get("phase") in {"initializing", "ready"} or bool(getattr(binding.engine, "ready", False)):
            stop_result = await stop_katago_request(
                engine_runtime=binding.engine_runtime,
                run_in_executor=binding.run_in_executor,
            )
        shutdown = binding.desktop_shutdown_server()
        return {
            "ok": bool(shutdown.get("ok")),
            "action": "desktop_exit",
            "engine": stop_result,
            "shutdown": shutdown,
        }

    @router.get("/engine_idle_timeout")
    async def get_engine_idle_timeout():
        runtime = binding_provider().engine_runtime
        return {
            "ok": True,
            "seconds": runtime.idle_timeout_seconds,
            "enabled": runtime.idle_timeout_seconds > 0,
        }

    @router.post("/engine_idle_timeout")
    async def set_engine_idle_timeout(request: Request, payload: dict[str, Any]):
        binding = binding_provider()
        control_allowed = control_request_authorized(
            client_host=request.client.host if request.client else None,
            request_token=request.headers.get(CONTROL_TOKEN_HEADER),
            expected_token=binding.control_token,
        )
        ui_allowed = ui_exit_request_authorized(
            client_host=request.client.host if request.client else None,
            request_token=request.headers.get(UI_EXIT_TOKEN_HEADER),
            expected_token=binding.ui_exit_token,
        )
        if not (control_allowed.get("ok") or ui_allowed.get("ok")):
            raise HTTPException(status_code=403, detail="engine idle timeout update denied")
        seconds = binding.save_idle_timeout_seconds(payload.get("seconds"))
        binding.engine_runtime.set_idle_timeout_seconds(seconds)
        return {
            "ok": True,
            "seconds": seconds,
            "enabled": seconds > 0,
        }

    return router
