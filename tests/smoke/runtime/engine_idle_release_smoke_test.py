from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import shutil
import time
import uuid
from pathlib import Path

from app.runtime.engine import KataGoEngine
from app.runtime.engine_idle_settings import (
    DEFAULT_IDLE_TIMEOUT_SECONDS,
    load_idle_timeout_seconds,
    save_idle_timeout_seconds,
)


class FakeStdin:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def write(self, payload: bytes) -> None:
        self.commands.append(payload.decode("utf-8").strip())

    def flush(self) -> None:
        return None


class FakeProcess:
    def __init__(self) -> None:
        self.stdin = FakeStdin()
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if not self.terminated and not self.killed else 0

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True


def make_engine() -> KataGoEngine:
    return KataGoEngine(
        default_exe=Path("katago.exe"),
        default_config=Path("config.cfg"),
        default_model=Path("model.bin.gz"),
        log_fn=lambda _message: None,
        ensure_dirs_fn=lambda: None,
        coord_parser=lambda _move, _size: None,
    )


def smoke_engine_stops_only_after_idle_timeout() -> None:
    engine = make_engine()
    process = FakeProcess()
    engine.process = process
    engine.ready = True
    engine.mark_activity(time.time())

    assert engine.stop_if_idle(60.0) is False
    assert process.terminated is False

    engine.mark_activity(time.time() - 120)
    engine.response_queue.put("=")
    assert engine.stop_if_idle(60.0) is True
    assert process.stdin.commands == ["quit"]
    assert process.terminated is True
    assert engine.ready is False


def smoke_idle_timeout_settings_roundtrip() -> None:
    tmp_dir = Path("output") / "test-temp" / f"engine-idle-{uuid.uuid4().hex}"
    settings_path = tmp_dir / "settings.json"
    try:
        assert load_idle_timeout_seconds(settings_path) == DEFAULT_IDLE_TIMEOUT_SECONDS
        assert save_idle_timeout_seconds(settings_path, 120) == 120.0
        assert load_idle_timeout_seconds(settings_path) == 120.0
        assert save_idle_timeout_seconds(settings_path, 0) == 0.0
        assert load_idle_timeout_seconds(settings_path) == 0.0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    smoke_engine_stops_only_after_idle_timeout()
    smoke_idle_timeout_settings_roundtrip()
    print("engine idle release smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
