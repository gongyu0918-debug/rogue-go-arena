from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.runtime.desktop_exit import active_game_count, desktop_exit_available
from app.runtime.status_payload import build_status_payload


def build_runtime_status_payload(
    *,
    server_rev: str,
    host: str,
    port: int,
    get_access_urls: Callable[[str, int], dict[str, list[str]]],
    engine: Any,
    engine_runtime: Any,
    engine_state_snapshot: Callable[[], dict[str, Any]],
    card_config_service: Any,
    no_katago: bool,
    static_index_path: Path,
    active_games: Any | None = None,
    desktop_exit_token: str | None = None,
) -> dict[str, Any]:
    snapshot = engine_state_snapshot()
    model_exists = engine_runtime.has_model_files()
    exe_exists = engine_runtime.has_engine_binaries()
    selected_model = engine_runtime.select_model()
    card_config_payload = card_config_service.get_payload()
    game_count = active_game_count(active_games) if active_games is not None else 0
    exit_available = desktop_exit_available(
        engine_ready=bool(engine.ready),
        engine_snapshot=snapshot,
        active_games_count=game_count,
    )
    return build_status_payload(
        server_rev=server_rev,
        host=host,
        port=port,
        access_urls=get_access_urls(host, port),
        engine_ready=engine.ready,
        engine_snapshot=snapshot,
        exe_exists=exe_exists,
        model_exists=model_exists,
        selected_model_name=selected_model.name if selected_model else None,
        no_katago=no_katago,
        cpu_mode=engine_runtime.cpu_mode,
        static_ready=static_index_path.exists(),
        card_config_payload=card_config_payload,
        active_games_count=game_count,
        desktop_exit_available=exit_available,
        desktop_exit_token=desktop_exit_token,
    )
