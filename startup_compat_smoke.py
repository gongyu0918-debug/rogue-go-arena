from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.runtime.startup import EnginePaths, EngineStartupManager


class DummyEngine:
    ready = False

    def stop(self) -> None:
        return None


class OpenClFailsCpuWorksEngine:
    ready = False

    def __init__(self) -> None:
        self.attempts: list[tuple[str, str]] = []
        self.stopped = 0
        self.alive = False

    def start(
        self,
        exe: Path,
        _config: Path,
        model: Path,
        startup_timeout: float = 120.0,
        stall_timeout: float = 45.0,
        stderr_callback=None,
    ) -> None:
        self.attempts.append((exe.name, model.name))
        if exe.name == "katago_opencl.exe":
            raise RuntimeError("simulated broken OpenCL runtime")
        self.alive = True
        self.ready = True

    def send_command(self, _command: str, timeout: float = 60.0) -> str:
        return "="

    def is_alive(self) -> bool:
        return self.alive

    def stop(self) -> None:
        self.alive = False
        self.ready = False
        self.stopped += 1


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def make_manager(root: Path, engine=None) -> tuple[EngineStartupManager, EnginePaths]:
    paths = EnginePaths(
        base_dir=root,
        cuda_exe=touch(root / "katago" / "katago_cuda.exe"),
        legacy_exe=touch(root / "katago" / "katago.exe"),
        opencl_exe=touch(root / "katago" / "katago_opencl.exe"),
        cpu_exe=touch(root / "katago" / "katago_cpu.exe"),
        config=touch(root / "katago" / "config.cfg"),
        cpu_config=touch(root / "katago" / "config_cpu.cfg"),
        model_large=touch(root / "katago" / "model_large.bin.gz"),
        model_default=touch(root / "katago" / "model.bin.gz"),
        model_small=touch(root / "katago" / "model_b18.bin.gz"),
        user_model_large=touch(root / "user" / "katago" / "model_large.bin.gz"),
    )
    manager = EngineStartupManager(
        engine or DummyEngine(),
        paths=paths,
        no_katago=False,
        log_fn=lambda _message: None,
    )
    return manager, paths


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        manager, paths = make_manager(Path(tmp))
        models = manager.available_models()

        cpu_order = manager.models_for_candidate({"backend": "cpu", "label": "CPU", "cpu_mode": True}, models)
        opencl_order = manager.models_for_candidate({"backend": "opencl", "label": "OpenCL", "cpu_mode": False}, models)
        cuda_order = manager.models_for_candidate({"backend": "cuda", "label": "CUDA", "cpu_mode": False}, models)

        assert cpu_order[:4] == [
            paths.model_small,
            paths.model_default,
            paths.user_model_large,
            paths.model_large,
        ]
        assert opencl_order[:4] == [
            paths.model_default,
            paths.model_small,
            paths.user_model_large,
            paths.model_large,
        ]
        assert cuda_order[:4] == [
            paths.user_model_large,
            paths.model_large,
            paths.model_default,
            paths.model_small,
        ]

        manager.has_nvidia_gpu = lambda: False
        has_gpu, candidates = manager.build_candidates()
        assert has_gpu is False
        labels = [candidate["label"] for candidate in candidates]
        assert labels == ["OpenCL", "CPU"]
        assert candidates[0]["startup_timeout"] >= 180.0
        assert candidates[1]["startup_timeout"] >= 120.0

        plan = manager.build_startup_attempt_plan(candidates, models)
        plan_labels = [(candidate["label"], model.name) for candidate, model in plan]
        assert plan_labels[:3] == [
            ("OpenCL", "model.bin.gz"),
            ("CPU", "model_b18.bin.gz"),
            ("CPU", "model.bin.gz"),
        ]

    with tempfile.TemporaryDirectory() as tmp:
        engine = OpenClFailsCpuWorksEngine()
        manager, _paths = make_manager(Path(tmp), engine)
        manager.has_nvidia_gpu = lambda: False
        token = manager._next_token()
        manager._run_engine_startup("smoke", token)
        snapshot = manager.snapshot()
        actual_attempts = [(item["exe"], item["model"]) for item in snapshot["attempts"]]
        assert actual_attempts[:2] == [
            ("katago_opencl.exe", "model.bin.gz"),
            ("katago_cpu.exe", "model_b18.bin.gz"),
        ]
        assert snapshot["phase"] == "ready"
        assert snapshot["active_backend"] == "CPU"
        assert manager.cpu_mode is True

        print(json.dumps({
            "status": "passed",
            "cpu_order": [path.name for path in cpu_order],
            "opencl_order": [path.name for path in opencl_order],
            "cuda_order": [path.name for path in cuda_order],
            "candidate_labels_without_nvidia": labels,
            "fallback_attempts": actual_attempts,
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
