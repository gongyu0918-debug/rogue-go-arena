from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.runtime.engine_control_api import is_loopback_client
from app.runtime.config_api import (
    balance_payload,
    card_config_payload,
    card_config_schema,
    reset_balance_request,
    reset_card_config_request,
    save_balance_request,
    save_card_config_request,
)


@dataclass(frozen=True)
class ConfigRoutesBinding:
    card_config_service: Any
    get_balance_editor_payload: Callable[[], dict[str, Any]]
    save_balance_overrides: Callable[[dict[str, Any]], dict[str, Any]]
    reset_balance_overrides: Callable[[], dict[str, Any]]


ConfigRoutesBindingProvider = Callable[[], ConfigRoutesBinding]


def require_loopback_write(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if not is_loopback_client(client_host):
        raise HTTPException(status_code=403, detail="config writes are only available from localhost")


def build_config_router(binding_provider: ConfigRoutesBindingProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/api/card-config")
    async def get_card_config_payload():
        binding = binding_provider()
        return card_config_payload(binding.card_config_service)

    @router.get("/api/card-config/schema")
    async def get_card_config_schema():
        binding = binding_provider()
        return card_config_schema(binding.card_config_service)

    @router.post("/api/card-config")
    async def save_card_config_payload(request: Request):
        require_loopback_write(request)
        binding = binding_provider()
        return await save_card_config_request(
            request,
            card_config_service=binding.card_config_service,
        )

    @router.post("/api/card-config/reset")
    async def reset_card_config_payload(request: Request):
        require_loopback_write(request)
        binding = binding_provider()
        return reset_card_config_request(binding.card_config_service)

    @router.get("/api/balance")
    async def get_balance_lab_payload():
        binding = binding_provider()
        return balance_payload(binding.get_balance_editor_payload)

    @router.post("/api/balance")
    async def save_balance_lab_payload(request: Request):
        require_loopback_write(request)
        binding = binding_provider()
        return await save_balance_request(
            request,
            save_balance_overrides=binding.save_balance_overrides,
        )

    @router.post("/api/balance/reset")
    async def reset_balance_lab_payload(request: Request):
        require_loopback_write(request)
        binding = binding_provider()
        return reset_balance_request(binding.reset_balance_overrides)

    return router
