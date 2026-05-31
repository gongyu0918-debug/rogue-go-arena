from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.runtime.ai_move_service_adapters import AiMoveServiceRuntime
from app.runtime.engine_gateway_adapters import EngineGatewayRuntime
from app.runtime.service_bindings import AiMoveServiceBinding, EngineGatewayBinding


@dataclass(frozen=True)
class EngineGatewayDependencies:
    engine: Any
    base_dir: Path
    get_game_visits: Callable[..., Any]
    gtp_to_coord: Callable[..., Any]
    run_in_executor: Callable[..., Any]
    log_fn: Callable[[str], None]
    traceback_fn: Callable[[], None]


@dataclass(frozen=True)
class AiMoveServiceDependencies:
    engine: Any
    run_in_executor: Callable[..., Any]
    engine_log: Callable[[str], None]
    coord_to_gtp: Callable[..., Any]
    gtp_to_coord: Callable[..., Any]


def build_engine_gateway(
    dependencies: EngineGatewayDependencies,
    gateway_cls: Callable[..., Any],
) -> Any:
    return gateway_cls(
        engine=dependencies.engine,
        base_dir=dependencies.base_dir,
        get_game_visits=dependencies.get_game_visits,
        gtp_to_coord=dependencies.gtp_to_coord,
        run_in_executor=dependencies.run_in_executor,
        log_fn=dependencies.log_fn,
        traceback_fn=dependencies.traceback_fn,
    )


def build_engine_gateway_binding(
    dependencies: EngineGatewayDependencies,
) -> EngineGatewayBinding:
    return EngineGatewayBinding(
        engine=dependencies.engine,
        get_game_visits=dependencies.get_game_visits,
        gtp_to_coord=dependencies.gtp_to_coord,
        run_in_executor=dependencies.run_in_executor,
        log_fn=dependencies.log_fn,
        traceback_fn=dependencies.traceback_fn,
    )


def build_engine_gateway_runtime(
    gateway: Any,
    dependencies: EngineGatewayDependencies,
) -> EngineGatewayRuntime:
    return EngineGatewayRuntime(
        gateway=gateway,
        binding=build_engine_gateway_binding(dependencies),
    )


def build_ai_move_service(
    dependencies: AiMoveServiceDependencies,
    service_cls: Callable[..., Any],
) -> Any:
    return service_cls(
        engine=dependencies.engine,
        run_in_executor=dependencies.run_in_executor,
        engine_log=dependencies.engine_log,
        coord_to_gtp=dependencies.coord_to_gtp,
        gtp_to_coord=dependencies.gtp_to_coord,
    )


def build_ai_move_service_binding(
    dependencies: AiMoveServiceDependencies,
) -> AiMoveServiceBinding:
    return AiMoveServiceBinding(
        engine=dependencies.engine,
        run_in_executor=dependencies.run_in_executor,
    )


def build_ai_move_service_runtime(
    service: Any,
    dependencies: AiMoveServiceDependencies,
) -> AiMoveServiceRuntime:
    return AiMoveServiceRuntime(
        service=service,
        binding=build_ai_move_service_binding(dependencies),
    )
