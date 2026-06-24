from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.runtime.app_shell import AppShellBinding
from app.runtime.config_routes import ConfigRoutesBinding
from app.runtime.control_routes import RuntimeControlRoutesBinding
from app.runtime.gpu_info import CachedGpuInfo
from app.runtime.info_routes import RuntimeInfoRoutesBinding
from app.runtime.static_page_routes import StaticPageRoutesBinding


@dataclass(frozen=True)
class AppShellDependencies:
    static_dir: Path
    engine_runtime: Any
    log_fn: Callable[[str], None]


@dataclass(frozen=True)
class StaticPageRoutesDependencies:
    static_dir: Path


@dataclass(frozen=True)
class ConfigRoutesDependencies:
    card_config_service: Any
    get_balance_editor_payload: Callable[[], dict[str, Any]]
    save_balance_overrides: Callable[[dict[str, Any]], dict[str, Any]]
    reset_balance_overrides: Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class RuntimeControlRoutesDependencies:
    rank_labels: Mapping[str, str]
    engine_runtime: Any
    run_in_executor: Callable[..., Awaitable[Any]]
    save_idle_timeout_seconds: Callable[[Any], float]
    shutdown_server: Callable[[], dict[str, Any]]
    control_token: str | None


@dataclass(frozen=True)
class RuntimeInfoRoutesDependencies:
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


def build_app_shell_binding(dependencies: AppShellDependencies) -> AppShellBinding:
    return AppShellBinding(
        static_dir=dependencies.static_dir,
        engine_runtime=dependencies.engine_runtime,
        log_fn=dependencies.log_fn,
    )


def build_static_page_routes_binding(
    dependencies: StaticPageRoutesDependencies,
) -> StaticPageRoutesBinding:
    return StaticPageRoutesBinding(static_dir=dependencies.static_dir)


def build_config_routes_binding(
    dependencies: ConfigRoutesDependencies,
) -> ConfigRoutesBinding:
    return ConfigRoutesBinding(
        card_config_service=dependencies.card_config_service,
        get_balance_editor_payload=dependencies.get_balance_editor_payload,
        save_balance_overrides=dependencies.save_balance_overrides,
        reset_balance_overrides=dependencies.reset_balance_overrides,
    )


def build_runtime_control_routes_binding(
    dependencies: RuntimeControlRoutesDependencies,
) -> RuntimeControlRoutesBinding:
    return RuntimeControlRoutesBinding(
        rank_labels=dependencies.rank_labels,
        engine_runtime=dependencies.engine_runtime,
        run_in_executor=dependencies.run_in_executor,
        save_idle_timeout_seconds=dependencies.save_idle_timeout_seconds,
        shutdown_server=dependencies.shutdown_server,
        control_token=dependencies.control_token,
    )


def build_runtime_info_routes_binding(
    dependencies: RuntimeInfoRoutesDependencies,
) -> RuntimeInfoRoutesBinding:
    return RuntimeInfoRoutesBinding(
        server_rev=dependencies.server_rev,
        host=dependencies.host,
        port=dependencies.port,
        get_access_urls=dependencies.get_access_urls,
        engine=dependencies.engine,
        engine_runtime=dependencies.engine_runtime,
        engine_state_snapshot=dependencies.engine_state_snapshot,
        card_config_service=dependencies.card_config_service,
        no_katago=dependencies.no_katago,
        static_dir=dependencies.static_dir,
        gpu_detector=dependencies.gpu_detector,
        run_in_executor=dependencies.run_in_executor,
        large_model_path=dependencies.large_model_path,
        active_games=dependencies.active_games,
        generate_sgf=dependencies.generate_sgf,
    )
