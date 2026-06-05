from __future__ import annotations

from pathlib import Path

from _path_bootstrap import ensure_repo_root


ensure_repo_root(__file__)

from app.runtime.engine import KataGoEngine  # noqa: E402


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout=None) -> int:
        self.waited = True
        return 0

    def kill(self) -> None:
        self.killed = True


class FakeManagedKataGo:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.terminated_tree = False

    def terminate_tree(self, *, timeout: float = 5.0) -> None:
        self.terminated_tree = True
        self.process.terminate()
        self.process.wait(timeout=timeout)


def build_engine(logs: list[str]) -> KataGoEngine:
    return KataGoEngine(
        default_exe=Path("katago.exe"),
        default_config=Path("config.cfg"),
        default_model=Path("model.bin.gz"),
        log_fn=logs.append,
        ensure_dirs_fn=lambda: None,
        coord_parser=lambda _gtp, _size: None,
    )


def test_idle_watchdog_stops_unresponsive_katago_process() -> None:
    logs: list[str] = []
    engine = build_engine(logs)
    process = FakeProcess()
    engine.process = process  # type: ignore[assignment]
    engine.ready = True
    engine.idle_timeout_seconds = 180.0
    engine.last_activity_time = 100.0

    assert engine.stop_if_unresponsive(now=279.0) is False
    assert process.terminated is False

    assert engine.stop_if_unresponsive(now=281.0) is True
    assert process.terminated is True
    assert process.waited is True
    assert engine.process is None
    assert engine.ready is False
    assert any("No engine activity" in line for line in logs)


def test_managed_katago_termination_path_is_used() -> None:
    logs: list[str] = []
    engine = build_engine(logs)
    process = FakeProcess()
    managed = FakeManagedKataGo(process)
    engine.process = process  # type: ignore[assignment]
    engine.managed_process = managed  # type: ignore[assignment]
    engine.ready = True
    engine.idle_timeout_seconds = 1.0
    engine.last_activity_time = 10.0

    assert engine.stop_if_unresponsive(now=12.0) is True
    assert managed.terminated_tree is True
    assert process.terminated is True
    assert engine.managed_process is None
    assert engine.process is None


if __name__ == "__main__":
    test_idle_watchdog_stops_unresponsive_katago_process()
    test_managed_katago_termination_path_is_used()
    print({"ok": True})
