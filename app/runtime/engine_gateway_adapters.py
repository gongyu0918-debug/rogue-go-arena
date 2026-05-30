from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.service_bindings import (
    EngineGatewayBinding,
    bind_engine_gateway_runtime,
    send_engine_command as send_bound_engine_command,
    sync_engine_komi as sync_bound_engine_komi,
)


@dataclass(frozen=True)
class EngineGatewayRuntime:
    gateway: Any
    binding: EngineGatewayBinding


def bind_engine_gateway(runtime: EngineGatewayRuntime) -> None:
    bind_engine_gateway_runtime(runtime.gateway, runtime.binding)


async def send_engine_command(runtime: EngineGatewayRuntime, command: str) -> str:
    return await send_bound_engine_command(runtime.gateway, command, runtime.binding)


async def sync_engine_komi(runtime: EngineGatewayRuntime, game: Any) -> None:
    await sync_bound_engine_komi(runtime.gateway, game, runtime.binding)
