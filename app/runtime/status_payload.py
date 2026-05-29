from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_status_payload(
    *,
    server_rev: str,
    host: str,
    port: int,
    access_urls: Mapping[str, list[str]],
    engine_ready: bool,
    engine_snapshot: Mapping[str, Any],
    exe_exists: bool,
    model_exists: bool,
    selected_model_name: str | None,
    no_katago: bool,
    cpu_mode: bool,
    static_ready: bool,
    card_config_payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "server_rev": server_rev,
        "host": host,
        "port": port,
        "access_urls": dict(access_urls),
        "katago_ready": engine_ready,
        "katago_exe": exe_exists,
        "katago_model": model_exists,
        "katago_model_name": selected_model_name,
        "katago_model_loaded": bool(engine_ready and engine_snapshot.get("active_model")),
        "no_katago": no_katago,
        "cpu_mode": cpu_mode,
        "static_ready": static_ready,
        "card_config": card_config_payload.get("source"),
        "card_config_errors": card_config_payload.get("errors", []),
        "engine_phase": engine_snapshot.get("phase"),
        "engine_message": engine_snapshot.get("message"),
        "engine_backend": engine_snapshot.get("active_backend"),
        "engine_backend_exe": engine_snapshot.get("active_backend_exe"),
        "engine_model": engine_snapshot.get("active_model"),
        "engine_last_error": engine_snapshot.get("last_error"),
        "engine_attempts": engine_snapshot.get("attempts"),
        "engine_candidates": engine_snapshot.get("candidates"),
        "engine_initializing": engine_snapshot.get("initializing"),
        "engine_log_tail": engine_snapshot.get("log_tail"),
        "nvidia_detected": engine_snapshot.get("nvidia_detected"),
    }
