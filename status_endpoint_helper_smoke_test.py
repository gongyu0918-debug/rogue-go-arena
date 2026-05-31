from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

import server as s
from app.runtime.status_endpoint import build_runtime_status_payload


class FakeEngineRuntime:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.cpu_mode = True

    def has_model_files(self) -> bool:
        self.calls.append("has_model_files")
        return True

    def has_engine_binaries(self) -> bool:
        self.calls.append("has_engine_binaries")
        return False

    def select_model(self):
        self.calls.append("select_model")
        return SimpleNamespace(name="model_small.bin.gz")


class FakeCardConfigService:
    def __init__(self, calls: list) -> None:
        self.calls = calls

    def get_payload(self) -> dict:
        self.calls.append("card_payload")
        return {"source": "user", "errors": ["warn"]}


def smoke_status_helper_collects_runtime_state_in_existing_order() -> None:
    calls = []

    def snapshot() -> dict:
        calls.append("snapshot")
        return {
            "active_model": "model_small.bin.gz",
            "phase": "ready",
            "message": "ready",
            "active_backend": "CPU",
            "active_backend_exe": "katago_cpu.exe",
            "last_error": None,
            "attempts": [{"status": "ready"}],
            "candidates": ["CPU + model_small.bin.gz"],
            "initializing": False,
            "log_tail": [{"message": "ok"}],
            "nvidia_detected": False,
        }

    def urls(host: str, port: int) -> dict[str, list[str]]:
        calls.append(("urls", host, port))
        return {"local": [f"http://{host}:{port}"], "lan": []}

    with tempfile.TemporaryDirectory() as temp_dir:
        static_index = Path(temp_dir) / "index.html"
        static_index.write_text("ok", encoding="utf-8")

        payload = build_runtime_status_payload(
            server_rev="rev",
            host="127.0.0.1",
            port=8123,
            get_access_urls=urls,
            engine=SimpleNamespace(ready=True),
            engine_runtime=FakeEngineRuntime(calls),
            engine_state_snapshot=snapshot,
            card_config_service=FakeCardConfigService(calls),
            no_katago=False,
            static_index_path=static_index,
        )

    assert calls == [
        "snapshot",
        "has_model_files",
        "has_engine_binaries",
        "select_model",
        "card_payload",
        ("urls", "127.0.0.1", 8123),
    ]
    assert payload["server_rev"] == "rev"
    assert payload["katago_ready"] is True
    assert payload["katago_model"] is True
    assert payload["katago_exe"] is False
    assert payload["katago_model_name"] == "model_small.bin.gz"
    assert payload["katago_model_loaded"] is True
    assert payload["cpu_mode"] is True
    assert payload["static_ready"] is True
    assert payload["card_config"] == "user"
    assert payload["card_config_errors"] == ["warn"]
    assert payload["engine_phase"] == "ready"
    assert payload["access_urls"] == {"local": ["http://127.0.0.1:8123"], "lan": []}


def endpoint_for(path: str, method: str = "GET"):
    for route in s.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


async def smoke_server_status_wrapper_resolves_runtime_deps_late() -> None:
    calls = []

    def snapshot() -> dict:
        calls.append("snapshot")
        return {
            "phase": "idle",
            "message": "idle",
            "active_backend": None,
            "active_backend_exe": None,
            "active_model": None,
            "last_error": None,
            "attempts": [],
            "candidates": [],
            "initializing": False,
            "log_tail": [],
            "nvidia_detected": True,
        }

    def urls(host: str, port: int) -> dict[str, list[str]]:
        calls.append(("urls", host, port))
        return {"local": [f"http://localhost:{port}", f"http://{host}:{port}"], "lan": []}

    original_engine = s.engine
    original_runtime = s.engine_runtime
    original_snapshot = s._engine_state_snapshot
    original_card_config_service = s.card_config_service
    original_get_access_urls = s.get_access_urls
    original_static_dir = s.STATIC_DIR
    original_no_katago = s.NO_KATAGO
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir)
            static_dir.mkdir(exist_ok=True)

            s.engine = SimpleNamespace(ready=False)
            s.engine_runtime = FakeEngineRuntime(calls)
            s._engine_state_snapshot = snapshot
            s.card_config_service = FakeCardConfigService(calls)
            s.get_access_urls = urls
            s.STATIC_DIR = static_dir
            s.NO_KATAGO = True

            binding = s._runtime_info_routes_binding()
            assert binding.engine is s.engine
            assert binding.engine_runtime is s.engine_runtime
            assert binding.card_config_service is s.card_config_service
            assert binding.static_dir == static_dir
            payload = await endpoint_for("/status")()
    finally:
        s.engine = original_engine
        s.engine_runtime = original_runtime
        s._engine_state_snapshot = original_snapshot
        s.card_config_service = original_card_config_service
        s.get_access_urls = original_get_access_urls
        s.STATIC_DIR = original_static_dir
        s.NO_KATAGO = original_no_katago

    assert calls == [
        "snapshot",
        "has_model_files",
        "has_engine_binaries",
        "select_model",
        "card_payload",
        ("urls", s.SERVER_HOST, s.SERVER_PORT),
    ]
    assert payload["no_katago"] is True
    assert payload["katago_ready"] is False
    assert payload["static_ready"] is False
    assert payload["nvidia_detected"] is True


async def main() -> None:
    smoke_status_helper_collects_runtime_state_in_existing_order()
    await smoke_server_status_wrapper_resolves_runtime_deps_late()
    print("status endpoint helper smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
