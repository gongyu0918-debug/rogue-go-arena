from __future__ import annotations

from collections.abc import Awaitable, Callable
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


SyncBoardFn = Callable[[Any], Awaitable[None]]


def bind_engine_gateway(runtime: EngineGatewayRuntime) -> None:
    bind_engine_gateway_runtime(runtime.gateway, runtime.binding)


async def send_engine_command(runtime: EngineGatewayRuntime, command: str) -> str:
    return await send_bound_engine_command(runtime.gateway, command, runtime.binding)


async def sync_engine_komi(runtime: EngineGatewayRuntime, game: Any) -> None:
    await sync_bound_engine_komi(runtime.gateway, game, runtime.binding)


def sync_board_locked(runtime: EngineGatewayRuntime, game: Any) -> str:
    bind_engine_gateway(runtime)
    return runtime.gateway.sync_board_locked(game)


def gtp_safe_sync_sgf_path(runtime: EngineGatewayRuntime, game: Any) -> str:
    bind_engine_gateway(runtime)
    return runtime.gateway.gtp_safe_sync_sgf_path(game)


async def sync_board(runtime: EngineGatewayRuntime, game: Any) -> None:
    bind_engine_gateway(runtime)
    await runtime.gateway.sync_board(game)


def empty_analysis_result(runtime: EngineGatewayRuntime) -> dict[str, Any]:
    return runtime.gateway.empty_analysis_result()


async def analyze_current_position(
    runtime: EngineGatewayRuntime,
    game: Any,
    color: str | None = None,
    *,
    sync_board: SyncBoardFn | None = None,
) -> dict[str, Any]:
    bind_engine_gateway(runtime)
    return await runtime.gateway.analyze_current_position(
        game,
        color=color,
        sync_board=sync_board,
    )


async def estimate_side_winrate(
    runtime: EngineGatewayRuntime,
    game: Any,
    color: str,
    *,
    sync_board: SyncBoardFn | None = None,
) -> float:
    bind_engine_gateway(runtime)
    return await runtime.gateway.estimate_side_winrate(
        game,
        color,
        sync_board=sync_board,
    )


async def pick_analysis_point(
    runtime: EngineGatewayRuntime,
    game: Any,
    color: str,
    *,
    start_index: int = 0,
) -> tuple[int, int] | None:
    bind_engine_gateway(runtime)
    return await runtime.gateway.pick_analysis_point(
        game,
        color,
        start_index=start_index,
    )
