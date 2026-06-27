from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.runtime.status_payload import build_status_payload


def main() -> int:
    snapshot = {
        "phase": "ready",
        "message": "ready",
        "active_backend": "CUDA",
        "active_backend_exe": "katago_cuda.exe",
        "active_model": "model_large.bin.gz",
        "last_error": None,
        "attempts": [{"backend": "CUDA"}],
        "candidates": [{"label": "CUDA"}],
        "initializing": False,
        "log_tail": [{"message": "ready"}],
        "nvidia_detected": True,
        "idle_timeout_seconds": 300.0,
        "idle_seconds": 12.5,
        "idle_auto_release": True,
    }
    payload = build_status_payload(
        server_rev="rev-test",
        host="127.0.0.1",
        port=8000,
        access_urls={
            "local": ["http://localhost:8000", "http://127.0.0.1:8000"],
            "lan": [],
        },
        engine_ready=True,
        engine_snapshot=snapshot,
        exe_exists=True,
        model_exists=True,
        selected_model_name="model_large.bin.gz",
        no_katago=False,
        cpu_mode=False,
        static_ready=True,
        card_config_payload={"source": "base", "errors": []},
        active_games_count=2,
        desktop_exit_available=True,
        desktop_exit_token="ui-exit-token",
    )

    assert list(payload) == [
        "server_rev",
        "host",
        "port",
        "access_urls",
        "katago_ready",
        "katago_exe",
        "katago_model",
        "katago_model_name",
        "katago_model_loaded",
        "no_katago",
        "cpu_mode",
        "static_ready",
        "card_config",
        "card_config_errors",
        "engine_phase",
        "engine_message",
        "engine_backend",
        "engine_backend_exe",
        "engine_model",
        "engine_last_error",
        "engine_attempts",
        "engine_candidates",
        "engine_initializing",
        "engine_log_tail",
        "nvidia_detected",
        "engine_idle_timeout_seconds",
        "engine_idle_seconds",
        "engine_idle_auto_release",
        "active_games_count",
        "desktop_exit_available",
        "desktop_exit_token",
    ]
    assert payload["server_rev"] == "rev-test"
    assert payload["katago_ready"] is True
    assert payload["katago_model_loaded"] is True
    assert payload["engine_backend"] == "CUDA"
    assert payload["engine_attempts"] == [{"backend": "CUDA"}]
    assert payload["card_config"] == "base"
    assert payload["card_config_errors"] == []
    assert payload["nvidia_detected"] is True
    assert payload["engine_idle_timeout_seconds"] == 300.0
    assert payload["engine_idle_seconds"] == 12.5
    assert payload["engine_idle_auto_release"] is True
    assert payload["active_games_count"] == 2
    assert payload["desktop_exit_available"] is True
    assert payload["desktop_exit_token"] == "ui-exit-token"

    idle_payload = build_status_payload(
        server_rev="rev-test",
        host="0.0.0.0",
        port=8123,
        access_urls={"local": [], "lan": ["http://192.168.1.2:8123"]},
        engine_ready=False,
        engine_snapshot={"active_model": "model_large.bin.gz"},
        exe_exists=False,
        model_exists=False,
        selected_model_name=None,
        no_katago=True,
        cpu_mode=True,
        static_ready=False,
        card_config_payload={},
    )
    assert idle_payload["katago_model_loaded"] is False
    assert idle_payload["card_config"] is None
    assert idle_payload["card_config_errors"] == []
    assert idle_payload["engine_phase"] is None
    assert idle_payload["nvidia_detected"] is None
    assert idle_payload["engine_idle_timeout_seconds"] is None
    assert idle_payload["active_games_count"] == 0
    assert idle_payload["desktop_exit_available"] is False
    assert "desktop_exit_token" not in idle_payload

    print("status payload smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
