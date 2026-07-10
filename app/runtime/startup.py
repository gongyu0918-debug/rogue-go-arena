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
        idle_timeout_seconds: float = 300.0,
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
        self._idle_timeout_seconds = max(0.0, float(idle_timeout_seconds or 0.0))
        self._idle_stop_event = threading.Event()
        self._idle_thread: Optional[threading.Thread] = None
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
            "idle_timeout_seconds": self._idle_timeout_seconds,
            "idle_seconds": 0.0,
            "idle_auto_release": self._idle_timeout_seconds > 0,
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
            snapshot["idle_timeout_seconds"] = self._idle_timeout_seconds
            snapshot["idle_auto_release"] = self._idle_timeout_seconds > 0
            snapshot["idle_seconds"] = self.engine.idle_age() if self.engine.ready else 0.0
            snapshot["attempts"] = [dict(item) for item in self._state.get("attempts", [])]
            snapshot["candidates"] = list(self._state.get("candidates", []))
            snapshot["log_tail"] = [dict(item) for item in self._event_log]
            snapshot["initializing"] = snapshot.get("phase") == "initializing"
            snapshot["ready"] = snapshot.get("phase") == "ready"
            return snapshot

    @property
    def idle_timeout_seconds(self) -> float:
        with self._state_lock:
            return self._idle_timeout_seconds

    def set_idle_timeout_seconds(self, seconds: float) -> float:
        value = max(0.0, float(seconds or 0.0))
        with self._state_lock:
            self._idle_timeout_seconds = value
            self._state["idle_timeout_seconds"] = value
            self._state["idle_auto_release"] = value > 0
            self._state["updated_at"] = time.time()
        self.log_event(
            "Idle engine release disabled"
            if value <= 0
            else f"Idle engine release set to {int(value)}s"
        )
        return value

    def _idle_monitor_interval(self) -> float:
        timeout = self.idle_timeout_seconds
        if timeout <= 0:
            return 10.0
        return min(30.0, max(0.5, timeout / 6.0))

    def _run_idle_monitor(self) -> None:
        while not self._idle_stop_event.wait(self._idle_monitor_interval()):
            if self.no_katago:
                continue
            timeout = self.idle_timeout_seconds
            if timeout <= 0:
                continue
            snapshot = self.snapshot()
            if snapshot.get("phase") != "ready":
                continue
            if self.engine.stop_if_idle(timeout, reason="auto_release"):
                self._set_cpu_mode(False)
                self._set_state(
                    phase="stopped",
                    message=(
                        f"KataGo 已因空闲 {int(timeout)} 秒自动释放，"
                        "下一次需要 AI 时会自动重新加载"
                    ),
                    active_backend=None,
                    active_backend_exe=None,
                    last_error=None,
                    idle_seconds=0.0,
                )
                self.log_event(f"KataGo auto-released after {int(timeout)}s idle")

    def _ensure_idle_monitor(self) -> None:
        if self.no_katago:
            return
        if self._idle_thread and self._idle_thread.is_alive():
            return
        self._idle_stop_event.clear()
        self._idle_thread = threading.Thread(
            target=self._run_idle_monitor,
            name="katago-idle-monitor",
            daemon=True,
        )
        self._idle_thread.start()

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
        seen = set()
        for candidate in (
            self.paths.user_model_large,
            self.paths.model_large,
            self.paths.model_default,
            self.paths.model_small,
        ):
            if candidate.exists():
                key = str(candidate.resolve()).casefold()
                if key in seen:
                    continue
                seen.add(key)
                models.append(candidate)
        return models

    def models_for_candidate(self, candidate: dict, models: list[Path]) -> list[Path]:
        """Order model attempts by backend capability.

        CUDA can usually benefit from a large model. CPU and older OpenCL systems
        should become playable quickly, so they try compact/default models before
        spending startup time on large models.
        """
        if candidate.get("cpu_mode"):
            preferred = (
                self.paths.model_small,
                self.paths.model_default,
                self.paths.user_model_large,
                self.paths.model_large,
            )
        elif candidate.get("backend") == "opencl":
            preferred = (
                self.paths.model_default,
                self.paths.model_small,
                self.paths.user_model_large,
                self.paths.model_large,
            )
        else:
            preferred = (
                self.paths.user_model_large,
                self.paths.model_large,
                self.paths.model_default,
                self.paths.model_small,
            )

        available_by_key = {str(path.resolve()).casefold(): path for path in models}
        ordered: list[Path] = []
        seen: set[str] = set()
        for path in preferred:
            key = str(path.resolve()).casefold()
            if key in available_by_key and key not in seen:
                ordered.append(available_by_key[key])
                seen.add(key)
        for path in models:
            key = str(path.resolve()).casefold()
            if key not in seen:
                ordered.append(path)
                seen.add(key)
        return ordered

    def build_startup_attempt_plan(
        self,
        candidates: list[dict],
        models: list[Path],
    ) -> list[tuple[dict, Path]]:
        """Build a fallback plan that gives CPU a timely chance.

        CUDA keeps the normal high-performance priority. OpenCL gets one
        preferred model attempt before CPU is tried, because broken OpenCL
        stacks are common on older machines and should not block the CPU path
        behind every model combination.
        """
        plan: list[tuple[dict, Path]] = []
        deferred_gpu: list[tuple[dict, Path]] = []
        deferred_cpu: list[tuple[dict, Path]] = []
        cpu_candidates: list[tuple[dict, list[Path]]] = []

        def add_once(target: list[tuple[dict, Path]], candidate: dict, model: Path) -> None:
            key = (id(candidate), str(model.resolve()).casefold())
            for existing_candidate, existing_model in plan + deferred_gpu + deferred_cpu + target:
                existing_key = (id(existing_candidate), str(existing_model.resolve()).casefold())
                if existing_key == key:
                    return
            target.append((candidate, model))

        for candidate in candidates:
            ordered_models = self.models_for_candidate(candidate, models)
            if not ordered_models:
                continue

            if candidate.get("cpu_mode"):
                cpu_candidates.append((candidate, ordered_models))
                continue

            if candidate.get("backend") == "opencl":
                add_once(plan, candidate, ordered_models[0])
                for model in ordered_models[1:]:
                    add_once(deferred_gpu, candidate, model)
                continue

            for model in ordered_models:
                add_once(plan, candidate, model)

        for candidate, ordered_models in cpu_candidates:
            for model in ordered_models[:2]:
                add_once(plan, candidate, model)
            for model in ordered_models[2:]:
                add_once(deferred_cpu, candidate, model)

        plan.extend(deferred_gpu)
        plan.extend(deferred_cpu)
        return plan

    def has_model_files(self) -> bool:
        return any(
            path.exists()
            for path in (
                self.paths.user_model_large,
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

    @staticmethod
    def _driver_version_code(version: str) -> Optional[int]:
        try:
            parts = version.strip().split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return major * 100 + minor
        except (TypeError, ValueError, IndexError):
            return None

    def _get_nvidia_driver_version_code(self) -> Optional[int]:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            ).decode("utf-8", errors="replace").strip().splitlines()
            if not out:
                return None
            first = out[0].strip()
            return self._driver_version_code(first)
        except Exception:
            return None

    def _cuda_backend_supported(self) -> bool:
        if not self.has_nvidia_gpu():
            return False
        driver_code = self._get_nvidia_driver_version_code()
        if driver_code is None or driver_code < 57261:
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
                    "backend": "cuda",
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
                    "backend": "cuda",
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
                    "backend": "opencl",
                    "cpu_mode": False,
                    "label": "OpenCL",
                    "startup_timeout": 180.0,
                    "stall_timeout": 60.0,
                }
            )
        if self.paths.cpu_exe.exists():
            candidates.append(
                {
                    "exe": self.paths.cpu_exe,
                    "config": self.paths.cpu_config if self.paths.cpu_config.exists() else self.paths.config,
                    "backend": "cpu",
                    "cpu_mode": True,
                    "label": "CPU",
                    "startup_timeout": 120.0,
                    "stall_timeout": 45.0,
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

    def _validate_ready_engine(self, label: str, model: Path) -> None:
        """Reject engines that start but fail on a tiny real search."""
        probe_commands = (
            "boardsize 9",
            "clear_board",
            "komi 7.5",
            "kata-set-param maxVisits 4",
            "kata-set-param maxTime 2",
            "genmove B",
            "genmove W",
            "clear_board",
            "kata-set-param maxTime 1e20",
        )
        for command in probe_commands:
            response = self.engine.send_command(command, timeout=12.0)
            if response.startswith("?"):
                raise RuntimeError(
                    f"{label} + {model.name} failed post-start probe {command!r}: {response}"
                )
            time.sleep(0.2)
            if not self.engine.is_alive():
                raise RuntimeError(
                    f"{label} + {model.name} exited during post-start probe {command!r}"
                )

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

            attempt_plan = self.build_startup_attempt_plan(candidates, models)
            first_candidate, first_model = attempt_plan[0]
            attempts = []
            self._set_state(
                phase="initializing",
                message=f"正在准备 {first_candidate['label']} + {first_model.name}",
                active_backend=first_candidate["label"],
                active_backend_exe=first_candidate["exe"].name,
                active_model=first_model.name,
                last_error=None,
                attempts=attempts,
                candidates=[
                    f"{item['label']} + {model.name}"
                    for item, model in attempt_plan
                ],
                nvidia_detected=has_gpu,
            )
            self.log_event(f"{trigger}: available models {', '.join(model.name for model in models)}")

            total_attempts = len(attempt_plan)
            current_attempt = 0
            for candidate, model in attempt_plan:
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
                    self.engine.ready = False
                    self._validate_ready_engine(label, model)
                    if not self._token_is_current(token):
                        self.engine.stop()
                        self.log_event(f"{trigger}: startup cancelled after {label} became ready")
                        return
                    attempt["status"] = "ready"
                    self._set_cpu_mode(is_cpu)
                    self.engine.ready = True
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
        self._ensure_idle_monitor()
        with self._state_lock:
            if self._start_thread and self._start_thread.is_alive():
                return False, "KataGo is already initializing"
        if force_restart:
            self._set_cpu_mode(False)
            self.engine.stop()

        with self._state_lock:
            if self._start_thread and self._start_thread.is_alive():
                return False, "KataGo is already initializing"
            self._start_token += 1
            token = self._start_token
            thread = threading.Thread(
                target=self._run_engine_startup,
                args=(trigger, token),
                daemon=True,
            )
            self._state.update(
                {
                    "phase": "initializing",
                    "message": "KataGo 正在后台启动",
                    "active_backend": None,
                    "active_backend_exe": None,
                    "last_error": None,
                    "updated_at": time.time(),
                }
            )
            self._start_thread = thread
        thread.start()
        return True, "started"

    def handle_app_startup(self) -> None:
        if self.no_katago:
            self.log_fn("[Server] KataGo disabled (--no-katago). Free-play mode.")
            return
        self._ensure_idle_monitor()
        started, reason = self.start_background("startup")
        if started:
            self.log_fn("[Server] KataGo initialization scheduled in background")
        else:
            self.log_fn(f"[Server] KataGo background init skipped: {reason}")

    def handle_app_shutdown(self) -> None:
        self._idle_stop_event.set()
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
