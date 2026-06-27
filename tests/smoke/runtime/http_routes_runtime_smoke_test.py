from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from pathlib import Path

import server as s
from app.runtime.http_routes_runtime import (
    AppShellDependencies,
    ConfigRoutesDependencies,
    RuntimeControlRoutesDependencies,
    RuntimeInfoRoutesDependencies,
    StaticPageRoutesDependencies,
    build_app_shell_binding,
    build_config_routes_binding,
    build_runtime_control_routes_binding,
    build_runtime_info_routes_binding,
    build_static_page_routes_binding,
)


def make_sync(name: str):
    def _fn(*_args, **_kwargs):
        return name

    return _fn


def smoke_http_route_runtime_builders_map_every_field() -> None:
    static_dir = Path("static-root")
    engine_runtime = object()
    log_fn = make_sync("log")

    app_shell = build_app_shell_binding(
        AppShellDependencies(
            static_dir=static_dir,
            engine_runtime=engine_runtime,
            log_fn=log_fn,
        )
    )
    assert app_shell.static_dir == static_dir
    assert app_shell.engine_runtime is engine_runtime
    assert app_shell.log_fn is log_fn

    static_pages = build_static_page_routes_binding(
        StaticPageRoutesDependencies(static_dir=static_dir)
    )
    assert static_pages.static_dir == static_dir

    card_config_service = object()
    get_balance_editor_payload = make_sync("balance-payload")
    save_balance_overrides = make_sync("save-balance")
    reset_balance_overrides = make_sync("reset-balance")
    config = build_config_routes_binding(
        ConfigRoutesDependencies(
            card_config_service=card_config_service,
            get_balance_editor_payload=get_balance_editor_payload,
            save_balance_overrides=save_balance_overrides,
            reset_balance_overrides=reset_balance_overrides,
        )
    )
    assert config.card_config_service is card_config_service
    assert config.get_balance_editor_payload is get_balance_editor_payload
    assert config.save_balance_overrides is save_balance_overrides
    assert config.reset_balance_overrides is reset_balance_overrides

    rank_labels = {"1d": "1 dan"}
    engine = object()
    run_in_executor = make_sync("executor")
    save_idle_timeout_seconds = make_sync("save-idle")
    shutdown_server = make_sync("shutdown-server")
    desktop_shutdown_server = make_sync("desktop-shutdown-server")
    control_token = "smoke-control-token"
    ui_exit_token = "smoke-ui-exit-token"
    active_games = object()
    control = build_runtime_control_routes_binding(
        RuntimeControlRoutesDependencies(
            rank_labels=rank_labels,
            engine=engine,
            engine_runtime=engine_runtime,
            run_in_executor=run_in_executor,
            save_idle_timeout_seconds=save_idle_timeout_seconds,
            shutdown_server=shutdown_server,
            desktop_shutdown_server=desktop_shutdown_server,
            control_token=control_token,
            ui_exit_token=ui_exit_token,
            active_games=active_games,
        )
    )
    assert control.rank_labels is rank_labels
    assert control.engine is engine
    assert control.engine_runtime is engine_runtime
    assert control.run_in_executor is run_in_executor
    assert control.save_idle_timeout_seconds is save_idle_timeout_seconds
    assert control.shutdown_server is shutdown_server
    assert control.desktop_shutdown_server is desktop_shutdown_server
    assert control.control_token is control_token
    assert control.ui_exit_token is ui_exit_token
    assert control.active_games is active_games

    server_rev = "rev-test"
    host = "127.0.0.1"
    port = 9876
    get_access_urls = make_sync("urls")
    engine = object()
    engine_state_snapshot = make_sync("engine-state")
    gpu_detector = object()
    large_model_path = Path("model.bin")
    active_games = object()
    generate_sgf = make_sync("sgf")
    desktop_exit_token = "info-ui-exit-token"
    info = build_runtime_info_routes_binding(
        RuntimeInfoRoutesDependencies(
            server_rev=server_rev,
            host=host,
            port=port,
            get_access_urls=get_access_urls,
            engine=engine,
            engine_runtime=engine_runtime,
            engine_state_snapshot=engine_state_snapshot,
            card_config_service=card_config_service,
            no_katago=True,
            static_dir=static_dir,
            gpu_detector=gpu_detector,
            run_in_executor=run_in_executor,
            large_model_path=large_model_path,
            active_games=active_games,
            generate_sgf=generate_sgf,
            desktop_exit_token=desktop_exit_token,
        )
    )
    assert info.server_rev == server_rev
    assert info.host == host
    assert info.port == port
    assert info.get_access_urls is get_access_urls
    assert info.engine is engine
    assert info.engine_runtime is engine_runtime
    assert info.engine_state_snapshot is engine_state_snapshot
    assert info.card_config_service is card_config_service
    assert info.no_katago is True
    assert info.static_dir == static_dir
    assert info.gpu_detector is gpu_detector
    assert info.run_in_executor is run_in_executor
    assert info.large_model_path == large_model_path
    assert info.active_games is active_games
    assert info.generate_sgf is generate_sgf
    assert info.desktop_exit_token is desktop_exit_token


def smoke_server_http_route_dependencies_resolve_current_runtime() -> None:
    originals = {
        "STATIC_DIR": s.STATIC_DIR,
        "engine_runtime": s.engine_runtime,
        "log": s.log,
        "card_config_service": s.card_config_service,
        "get_balance_editor_payload": s.get_balance_editor_payload,
        "save_balance_overrides": s.save_balance_overrides,
        "reset_balance_overrides": s.reset_balance_overrides,
        "RANK_LABELS": s.RANK_LABELS,
        "run_in_executor": s.run_in_executor,
        "request_server_shutdown": s.request_server_shutdown,
        "CONTROL_TOKEN": s.CONTROL_TOKEN,
        "DESKTOP_EXIT_TOKEN": s.DESKTOP_EXIT_TOKEN,
        "SERVER_REV": s.SERVER_REV,
        "SERVER_HOST": s.SERVER_HOST,
        "SERVER_PORT": s.SERVER_PORT,
        "get_access_urls": s.get_access_urls,
        "engine": s.engine,
        "_engine_state_snapshot": s._engine_state_snapshot,
        "NO_KATAGO": s.NO_KATAGO,
        "_gpu_detector": s._gpu_detector,
        "KATAGO_MODEL_LARGE": s.KATAGO_MODEL_LARGE,
        "active_games": s.active_games,
        "generate_sgf": s.generate_sgf,
    }
    static_dir = Path("patched-static")
    engine_runtime = object()
    log_fn = make_sync("patched-log")
    card_config_service = object()
    get_balance_editor_payload = make_sync("patched-balance")
    save_balance_overrides = make_sync("patched-save")
    reset_balance_overrides = make_sync("patched-reset")
    rank_labels = {"5k": "5 kyu"}
    run_in_executor = make_sync("patched-executor")
    shutdown_server = make_sync("patched-shutdown")
    control_token = "patched-control-token"
    desktop_exit_token = "patched-ui-exit-token"
    get_access_urls = make_sync("patched-urls")
    engine = object()
    engine_state_snapshot = make_sync("patched-state")
    gpu_detector = object()
    large_model_path = Path("patched-model.bin")
    active_games = object()
    generate_sgf = make_sync("patched-sgf")

    try:
        s.STATIC_DIR = static_dir
        s.engine_runtime = engine_runtime
        s.log = log_fn
        s.card_config_service = card_config_service
        s.get_balance_editor_payload = get_balance_editor_payload
        s.save_balance_overrides = save_balance_overrides
        s.reset_balance_overrides = reset_balance_overrides
        s.RANK_LABELS = rank_labels
        s.run_in_executor = run_in_executor
        s.request_server_shutdown = shutdown_server
        s.CONTROL_TOKEN = control_token
        s.DESKTOP_EXIT_TOKEN = desktop_exit_token
        s.SERVER_REV = "patched-rev"
        s.SERVER_HOST = "0.0.0.0"
        s.SERVER_PORT = 5432
        s.get_access_urls = get_access_urls
        s.engine = engine
        s._engine_state_snapshot = engine_state_snapshot
        s.NO_KATAGO = True
        s._gpu_detector = gpu_detector
        s.KATAGO_MODEL_LARGE = large_model_path
        s.active_games = active_games
        s.generate_sgf = generate_sgf

        app_shell = s._app_shell_binding()
        assert app_shell.static_dir == static_dir
        assert app_shell.engine_runtime is engine_runtime
        assert app_shell.log_fn is log_fn

        static_pages = s._static_page_routes_binding()
        assert static_pages.static_dir == static_dir

        config = s._config_routes_binding()
        assert config.card_config_service is card_config_service
        assert config.get_balance_editor_payload is get_balance_editor_payload
        assert config.save_balance_overrides is save_balance_overrides
        assert config.reset_balance_overrides is reset_balance_overrides

        control = s._runtime_control_routes_binding()
        assert control.rank_labels is rank_labels
        assert control.engine is s.engine
        assert control.engine_runtime is engine_runtime
        assert control.run_in_executor is run_in_executor
        assert control.shutdown_server is shutdown_server
        assert control.control_token is control_token
        assert control.ui_exit_token is desktop_exit_token
        assert control.active_games is s.active_games

        info = s._runtime_info_routes_binding()
        assert info.server_rev == "patched-rev"
        assert info.host == "0.0.0.0"
        assert info.port == 5432
        assert info.get_access_urls is get_access_urls
        assert info.engine is engine
        assert info.engine_runtime is engine_runtime
        assert info.engine_state_snapshot is engine_state_snapshot
        assert info.card_config_service is card_config_service
        assert info.no_katago is True
        assert info.static_dir == static_dir
        assert info.gpu_detector is gpu_detector
        assert info.run_in_executor is run_in_executor
        assert info.large_model_path == large_model_path
        assert info.active_games is active_games
        assert info.generate_sgf is generate_sgf
        assert info.desktop_exit_token is desktop_exit_token
    finally:
        for name, value in originals.items():
            setattr(s, name, value)


def main() -> None:
    smoke_http_route_runtime_builders_map_every_field()
    smoke_server_http_route_dependencies_resolve_current_runtime()
    print("http routes runtime smoke test: OK")


if __name__ == "__main__":
    main()
