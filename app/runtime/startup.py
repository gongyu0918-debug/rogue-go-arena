from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

from .engine import KataGoEngine


_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class EnginePaths:
    base_dir: Path
    cuda_exe: Path
    legacy_exe: Path
    opencl_exe: Path
    cpu_exe: Path
    config: Path
    cpu_config: Path
    model_large: Path
    model_default: Path
    model_small: Path
    user_model_large: Path


class EngineStartupManager:
    def __init__(
        self,
        engine: KataGoEngine,
        *,
        paths: EnginePaths,
        no_katago: bool,
        log_fn: Callable[[str], None],
    ) -> None:
        self.engine = engine
        self.paths = paths
        self.no_katago = no_katago
        self.log_fn = log_fn
        self._state_lock = threading.Lock()
        self._start_thread: Optional[threading.Thread] = None
        self._start_token = 0
        self._cpu_mode = False
        self._event_log = deque(maxlen=120)
        self._state = {
            "phase": "disabled" if no_katago else "idle",
            "message": "KataGo disabled" if no_katago else "KataGo not started yet",
            "active_backend": None,
            "active_backend_exe": None,
            "active_model": None,
            "last_error": None,
            "attempts": [],
            "candidates": [],
            "nvidia_detected": False,
            "updated_at": time.time(),
        }

    @property
    def cpu_mode(self) -> bool:
        with self._state_lock:
            return self._cpu_mode

    def log_event(self, message: str) -> None:
        stamped = f"[Engine] {message}"
        with self._state_lock:
            self._event_log.append(
                {
                    "ts": time.strftime("%H:%M:%S"),
                    "message": stamped,
                }
            )
        self.log_fn(stamped)

    def _set_state(self, **changes) -> None:
        with self._state_lock:
            self._state.update(changes)
            self._state["updated_at"] = time.time()

    def snapshot(self) -> dict:
        with self._state_lock:
            snapshot = dict(self._state)
            snapshot["attempts"] = [dict(item) for item in self._state.get("attempts", [])]
            snapshot["candidates"] = list(self._state.get("candidates", []))
            snapshot["log_tail"] = [dict(item) for item in self._event_log]
            snapshot["initializing"] = snapshot.get("phase") == "initializing"
            snapshot["ready"] = snapshot.get("phase") == "ready"
            return snapshot

    def _next_token(self) -> int:
        with self._state_lock:
            self._start_token += 1
            return self._start_token

    def _token_is_current(self, token: int) -> bool:
        with self._state_lock:
            return token == self._start_token

    def select_model(self) -> Optional[Path]:
        for candidate in (
            self.paths.user_model_large,
            self.paths.model_large,
            self.paths.model_default,
            self.paths.model_small,
        ):
            if candidate.exists():
                return candidate
        return None

    def available_models(self) -> list[Path]:
        models = []
        for candidate in (
            self.paths.model_large,
            self.paths.model_default,
            self.paths.model_small,
        ):
            if candidate.exists():
                models.append(candidate)
        return models

    def has_model_files(self) -> bool:
        return any(
            path.exists()
            for path in (
                self.paths.model_large,
                self.paths.model_default,
                self.paths.model_small,
            )
        )

    def has_engine_binaries(self) -> bool:
        return any(
            path.exists()
            for path in (
                self.paths.cuda_exe,
                self.paths.legacy_exe,
                self.paths.opencl_exe,
                self.paths.cpu_exe,
            )
        )

    def has_nvidia_gpu(self) -> bool:
        try:
            subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            )
            return True
        except Exception:
            return False

    def _get_nvidia_driver_major(self) -> Optional[int]:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            ).decode("utf-8", errors="replace").strip().splitlines()
            if not out:
                return None
            first = out[0].strip()
            major = first.split(".")[0]
            return int(major)
        except Exception:
            return None

    def _cuda_backend_supported(self) -> bool:
        if not self.has_nvidia_gpu():
            return False
        major = self._get_nvidia_driver_major()
        if major is None or major < 528:
            return False
        cuda_runtime_ready = all(
            path.exists()
            for path in (
                self.paths.base_dir / "katago" / "cublas64_12.dll",
                self.paths.base_dir / "katago" / "cudart64_12.dll",
            )
        ) and any(
            (self.paths.base_dir / "katago" / name).exists()
            for name in ("cudnn64_9.dll", "cudnn64_8.dll")
        )
        return cuda_runtime_ready

    def build_candidates(self) -> tuple[bool, list[dict]]:
        has_gpu = self.has_nvidia_gpu()
        cuda_ok = self._cuda_backend_supported()
        candidates = []
        if cuda_ok and self.paths.cuda_exe.exists():
            candidates.append(
                {
                    "exe": self.paths.cuda_exe,
                    "config": self.paths.config,
                    "cpu_mode": False,
                    "label": "CUDA(升级包)",
                    "startup_timeout": 60.0,
                    "stall_timeout": 20.0,
                }
            )
        if cuda_ok and self.paths.legacy_exe.exists():
            candidates.append(
                {
                    "exe": self.paths.legacy_exe,
                    "config": self.paths.config,
                    "cpu_mode": False,
                    "label": "CUDA",
                    "startup_timeout": 60.0,
                    "stall_timeout": 20.0,
                }
            )
        if self.paths.opencl_exe.exists():
            candidates.append(
                {
                    "exe": self.paths.opencl_exe,
                    "config": self.paths.config,
                    "cpu_mode": False,
                    "label": "OpenCL",
                    "startup_timeout": 150.0,
                    "stall_timeout": 45.0,
                }
            )
        if self.paths.cpu_exe.exists():
            candidates.append(
                {
                    "exe": self.paths.cpu_exe,
                    "config": self.paths.cpu_config if self.paths.cpu_config.exists() else self.paths.config,
                    "cpu_mode": True,
                    "label": "CPU",
                    "startup_timeout": 45.0,
                    "stall_timeout": 20.0,
                }
            )
        return has_gpu, candidates

    def _progress_callback(self, label: str, token: int, line: str) -> None:
        if not self._token_is_current(token):
            return
        with self._state_lock:
            if self._state.get("phase") != "initializing":
                return
        lower_line = line.lower()
        if "gtp ready" in lower_line:
            self._set_state(message=f"{label} 引擎已返回 GTP ready")
            return
        if "opencl" in lower_line or "tuning" in lower_line:
            self._set_state(message=f"{label} 初始化中: {line[:180]}")
            return
        if "cuda" in lower_line or "cudnn" in lower_line:
            self._set_state(message=f"{label} 初始化中: {line[:180]}")
            return

    def _run_engine_startup(self, trigger: str, token: int) -> None:
        try:
            if self.no_katago:
                self._set_cpu_mode(False)
                self._set_state(
                    phase="disabled",
                    message="KataGo disabled by --no-katago",
                    active_backend=None,
                    active_backend_exe=None,
                    active_model=None,
                    last_error=None,
                    attempts=[],
                    candidates=[],
                    nvidia_detected=False,
                )
                self.log_event(f"{trigger}: KataGo disabled, skip startup")
                return

            models = self.available_models()
            if not models:
                self._set_cpu_mode(False)
                self._set_state(
                    phase="failed",
                    message="未找到 KataGo 模型，当前仅支持纯对弈",
                    active_backend=None,
                    active_backend_exe=None,
                    active_model=None,
                    last_error="No KataGo model found",
                    attempts=[],
                    candidates=[],
                    nvidia_detected=False,
                )
                self.log_event(f"{trigger}: no model found")
                return

            has_gpu, candidates = self.build_candidates()
            if not candidates:
                self._set_cpu_mode(False)
                self._set_state(
                    phase="failed",
                    message="未找到任何 KataGo 引擎，当前仅支持纯对弈",
                    active_backend=None,
                    active_backend_exe=None,
                    active_model=models[0].name,
                    last_error="No KataGo engine found",
                    attempts=[],
                    candidates=[],
                    nvidia_detected=has_gpu,
                )
                self.log_event(f"{trigger}: no engine found")
                return

            attempts = []
            self._set_state(
                phase="initializing",
                message=f"正在准备模型 {models[0].name}",
                active_backend=None,
                active_backend_exe=None,
                active_model=models[0].name,
                last_error=None,
                attempts=attempts,
                candidates=[f"{item['label']} + {model.name}" for item in candidates for model in models],
                nvidia_detected=has_gpu,
            )
            self.log_event(f"{trigger}: available models {', '.join(model.name for model in models)}")

            total_attempts = len(candidates) * len(models)
            current_attempt = 0
            for candidate in candidates:
                for model in models:
                    current_attempt += 1
                    if not self._token_is_current(token):
                        self.log_event(f"{trigger}: startup cancelled before {candidate['label']}")
                        return

                    exe = candidate["exe"]
                    cfg = candidate["config"]
                    is_cpu = candidate["cpu_mode"]
                    label = candidate["label"]
                    attempt = {
                        "label": f"{label} + {model.name}",
                        "exe": exe.name,
                        "config": cfg.name,
                        "model": model.name,
                        "status": "starting",
                    }
                    attempts.append(attempt)
                    self._set_state(
                        phase="initializing",
                        message=f"尝试启动 {label} + {model.name} ({current_attempt}/{total_attempts})",
                        active_backend=label,
                        active_backend_exe=exe.name,
                        active_model=model.name,
                        last_error=None,
                        attempts=attempts,
                        nvidia_detected=has_gpu,
                    )
                    self.log_event(f"Trying {label}: {exe.name} with {model.name}")
                    try:
                        self.engine.start(
                            exe,
                            cfg,
                            model,
                            startup_timeout=float(candidate.get("startup_timeout", 120.0)),
                            stall_timeout=float(candidate.get("stall_timeout", 45.0)),
                            stderr_callback=lambda line, current_label=label: self._progress_callback(
                                current_label, token, line
                            ),
                        )
                        if not self._token_is_current(token):
                            self.engine.stop()
                            self.log_event(f"{trigger}: startup cancelled after {label} became ready")
                            return
                        attempt["status"] = "ready"
                        self._set_cpu_mode(is_cpu)
                        self._set_state(
                            phase="ready",
                            message=f"{label} 引擎已就绪",
                            active_backend=label,
                            active_backend_exe=exe.name,
                            active_model=model.name,
                            last_error=None,
                            attempts=attempts,
                            nvidia_detected=has_gpu,
                        )
                        self.log_event(f"{label} ready with model {model.name}")
                        return
                    except Exception as exc:
                        attempt["status"] = "failed"
                        attempt["error"] = str(exc)
                        self._set_cpu_mode(False)
                        self.log_event(f"{label} with {model.name} failed: {exc}")
                        self.engine.stop()
                        if not self._token_is_current(token):
                            self.log_event(f"{trigger}: startup cancelled after {label} failure")
                            return
                        has_more = current_attempt < total_attempts
                        self._set_state(
                            phase="initializing" if has_more else "failed",
                            message=(
                                f"{label} + {model.name} 启动失败，正在尝试下一个组合"
                                if has_more
                                else "所有引擎启动失败，当前仅支持纯对弈"
                            ),
                            active_backend=label,
                            active_backend_exe=exe.name,
                            active_model=model.name,
                            last_error=str(exc),
                            attempts=attempts,
                            nvidia_detected=has_gpu,
                        )

            self._set_cpu_mode(False)
            self._set_state(
                phase="failed",
                message="所有引擎启动失败，当前仅支持纯对弈",
                last_error=self._state.get("last_error"),
                attempts=attempts,
                nvidia_detected=has_gpu,
            )
        finally:
            with self._state_lock:
                if self._start_thread is threading.current_thread():
                    self._start_thread = None

    def start_background(self, trigger: str, force_restart: bool = False) -> tuple[bool, str]:
        if force_restart:
            self._set_cpu_mode(False)
            self.engine.stop()

        with self._state_lock:
            if self._start_thread and self._start_thread.is_alive():
                return False, "KataGo is already initializing"

        token = self._next_token()
        thread = threading.Thread(
            target=self._run_engine_startup,
            args=(trigger, token),
            daemon=True,
        )
        with self._state_lock:
            self._start_thread = thread
        thread.start()
        return True, "started"

    def handle_app_startup(self) -> None:
        if self.no_katago:
            self.log_fn("[Server] KataGo disabled (--no-katago). Free-play mode.")
            return
        started, reason = self.start_background("startup")
        if started:
            self.log_fn("[Server] KataGo initialization scheduled in background")
        else:
            self.log_fn(f"[Server] KataGo background init skipped: {reason}")

    def handle_app_shutdown(self) -> None:
        self._next_token()
        self.engine.stop()

    def stop_via_api(self) -> dict:
        snapshot = self.snapshot()
        if snapshot.get("phase") not in {"ready", "initializing"} and not self.engine.ready:
            return {"ok": False, "error": "KataGo is not running"}
        self._next_token()
        self.engine.stop()
        self._set_cpu_mode(False)
        self._set_state(
            phase="stopped",
            message="KataGo 已停止，当前为纯对弈模式",
            active_backend=None,
            active_backend_exe=None,
            last_error=None,
        )
        self.log_fn("[Server] KataGo engine stopped via API")
        return {"ok": True}

    def restart_via_api(self) -> dict:
        if self.no_katago:
            return {"ok": False, "error": "KataGo is disabled (--no-katago)"}
        model = self.select_model()
        _, candidates = self.build_candidates()
        if not model:
            return {"ok": False, "error": "KataGo model not found"}
        if not candidates:
            return {"ok": False, "error": "KataGo engine not found"}
        started, reason = self.start_background("api_restart", force_restart=True)
        snapshot = self.snapshot()
        if started:
            self.log_fn("[Server] KataGo restart scheduled in background")
            phase = snapshot.get("phase")
            message = snapshot.get("message")
            if phase in {None, "stopped"}:
                phase = "initializing"
                message = "KataGo 正在后台重启"
            return {
                "ok": True,
                "phase": phase,
                "message": message,
            }
        return {
            "ok": False,
            "error": reason,
            "phase": snapshot.get("phase"),
            "message": snapshot.get("message"),
        }

    def _set_cpu_mode(self, value: bool) -> None:
        with self._state_lock:
            self._cpu_mode = value
