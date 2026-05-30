from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EngineGatewayBinding:
    engine: Any
    get_game_visits: Any
    gtp_to_coord: Any
    run_in_executor: Any
    log_fn: Any
    traceback_fn: Any


@dataclass(frozen=True)
class AiMoveServiceBinding:
    engine: Any
    run_in_executor: Any


def bind_engine_gateway_runtime(gateway: Any, binding: EngineGatewayBinding) -> None:
    gateway.bind_runtime(
        engine=binding.engine,
        get_game_visits=binding.get_game_visits,
        gtp_to_coord=binding.gtp_to_coord,
        run_in_executor=binding.run_in_executor,
        log_fn=binding.log_fn,
        traceback_fn=binding.traceback_fn,
    )


async def send_engine_command(
    gateway: Any,
    command: str,
    binding: EngineGatewayBinding,
) -> str:
    bind_engine_gateway_runtime(gateway, binding)
    return await gateway.send_command(command)


async def sync_engine_komi(
    gateway: Any,
    game: Any,
    binding: EngineGatewayBinding,
) -> None:
    bind_engine_gateway_runtime(gateway, binding)
    await gateway.sync_komi(game)


def bind_ai_move_service_runtime(service: Any, binding: AiMoveServiceBinding) -> None:
    service.bind_runtime(
        engine=binding.engine,
        run_in_executor=binding.run_in_executor,
    )
