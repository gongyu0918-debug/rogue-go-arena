from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional


class KataGoEngine:
    def __init__(
        self,
        *,
        default_exe: Path,
        default_config: Path,
        default_model: Path,
        log_fn: Callable[[str], None],
        ensure_dirs_fn: Callable[[], None],
        coord_parser: Callable[[str, int], Optional[tuple[int, int]]],
    ):
        self.default_exe = default_exe
        self.default_config = default_config
        self.default_model = default_model
        self.log = log_fn
        self.ensure_dirs = ensure_dirs_fn
        self.coord_parser = coord_parser

        self.process: Optional[subprocess.Popen] = None
        self.response_queue = queue.Queue()
        self.analysis_lines = []
        self.ownership_data: list = []
        self.analysis_lock = threading.Lock()
        self.command_lock = threading.Lock()
        self.is_analyzing = False
        self.current_visits = 800
        self.ready = False
        self.stderr_lines = []
        self.stderr_callback = None
        self.last_stderr_time = 0.0

    def start(
        self,
        exe=None,
        config=None,
        model=None,
        startup_timeout: float = 120.0,
        stall_timeout: float = 45.0,
        stderr_callback=None,
    ):
        _exe = exe or self.default_exe
        _cfg = config or self.default_config
        _model = model or self.default_model
        if not Path(_exe).exists():
            raise FileNotFoundError(f"KataGo not found: {_exe}")
        if not Path(_model).exists():
            raise FileNotFoundError(f"Model not found: {_model}")

        self.ready = False
        self.stderr_lines = []
        self.stderr_callback = stderr_callback
        self.last_stderr_time = time.time()
        self.process = None
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break

        cmd = [str(_exe), "gtp", "-model", str(_model), "-config", str(_cfg)]
        self.ensure_dirs()
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
        except OSError as e:
            raise RuntimeError(f"Failed to launch {_exe.name}: {e}") from e
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

        deadline = time.time() + startup_timeout
        found_ready = False
        last_progress_bucket = -1
        while time.time() < deadline:
            if self.process.poll() is not None:
                err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
                raise RuntimeError(
                    f"{Path(_exe).name} exited with code {self.process.returncode}: {err}"
                )
            for line in self.stderr_lines:
                if "GTP ready" in line:
                    found_ready = True
                    break
            if found_ready:
                break
            if (
                stall_timeout > 0
                and self.last_stderr_time
                and time.time() - self.last_stderr_time > stall_timeout
            ):
                err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
                self.stop()
                raise RuntimeError(
                    f"{Path(_exe).name} stalled for {int(stall_timeout)}s without new output: {err}"
                )
            elapsed = int(startup_timeout - max(0.0, deadline - time.time()))
            progress_bucket = elapsed // 10
            if (
                self.stderr_callback
                and elapsed >= 10
                and progress_bucket > last_progress_bucket
            ):
                last_progress_bucket = progress_bucket
                self.stderr_callback(
                    f"{Path(_exe).name} ゛婓場宎趙笢ㄛ眒脹渾 {elapsed}s"
                )
            time.sleep(0.3)

        if not found_ready:
            err = "\n".join(self.stderr_lines[-10:]) if self.stderr_lines else "no output"
            self.stop()
            raise RuntimeError(
                f"{Path(_exe).name} did not become ready within {int(startup_timeout)}s: {err}"
            )

        try:
            self.process.stdin.write(b"name\n")
            self.process.stdin.flush()
            resp = self.response_queue.get(timeout=10)
            self.ready = True
            self.log(f"[KataGo] Started: {resp}")
        except queue.Empty:
            self.log("[KataGo] Warning: no ready signal received, assuming OK")
            self.ready = True

    def _read_stdout(self):
        current_response = []
        for raw_line in self.process.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            if self.is_analyzing and line.startswith("info "):
                with self.analysis_lock:
                    self.analysis_lines.append(line)
            elif self.is_analyzing and line.startswith("ownership "):
                vals = line.split()[1:]
                try:
                    with self.analysis_lock:
                        self.ownership_data = [float(v) for v in vals]
                except Exception:
                    pass
            else:
                if line.startswith("=") or line.startswith("?"):
                    current_response = [line]
                elif line == "" and current_response:
                    self.response_queue.put("\n".join(current_response))
                    current_response = []
                elif current_response:
                    current_response.append(line)

    def _read_stderr(self):
        for raw_line in self.process.stderr:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            self.last_stderr_time = time.time()
            self.stderr_lines.append(line)
            self.stderr_lines = self.stderr_lines[-200:]
            self.log(f"[KataGo stderr] {line}")
            if self.stderr_callback:
                try:
                    self.stderr_callback(line)
                except Exception:
                    pass

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _drain_response_queue(self, wait: float = 0.0) -> int:
        drained = 0
        deadline = time.time() + wait
        while True:
            timeout = max(0.0, deadline - time.time())
            try:
                if wait > 0 and time.time() < deadline:
                    self.response_queue.get(timeout=timeout)
                else:
                    self.response_queue.get_nowait()
                drained += 1
            except queue.Empty:
                break
        return drained

    def _send_command_locked(self, cmd: str, timeout: float = 60.0) -> str:
        if not self.process:
            return "? not started"
        if self.process.poll() is not None:
            self.log(f"[KataGo] Process dead (exit {self.process.poll()}), disabling engine")
            self.ready = False
            return "? process dead"
        try:
            with self.analysis_lock:
                self.is_analyzing = False
            self.process.stdin.write((cmd + "\n").encode())
            self.process.stdin.flush()
        except (OSError, ValueError, BrokenPipeError) as e:
            self.log(f"[KataGo] stdin write error: {e}, disabling engine")
            self.ready = False
            return "? write error"
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return "? timeout"

    def send_command(self, cmd: str, timeout: float = 60.0) -> str:
        with self.command_lock:
            return self._send_command_locked(cmd, timeout)

    def set_visits(self, visits: int):
        self.current_visits = visits
        max_visits = 10000000 if visits == 0 else visits
        self.send_command(f"kata-set-param maxVisits {max_visits}")

    def analyze(
        self,
        color: str,
        visits: int,
        interval: int = 50,
        duration: float = 1.8,
        extra_args: Optional[list[str]] = None,
    ) -> tuple:
        if not self.process or self.process.poll() is not None:
            return [], []

        with self.command_lock:
            original_visits = self.current_visits
            analysis_max_visits = 10000000 if visits == 0 else visits
            self._drain_response_queue(wait=0.05)

            if original_visits != visits:
                self.current_visits = visits
                resp = self._send_command_locked(
                    f"kata-set-param maxVisits {analysis_max_visits}",
                    timeout=10.0,
                )
                if resp.startswith("?"):
                    self.log(f"[Analysis] set_visits failed: {resp}")

            with self.analysis_lock:
                self.analysis_lines = []
                self.ownership_data = []
                self.is_analyzing = True

            cmd_parts = ["kata-analyze", color, str(interval)]
            if extra_args:
                cmd_parts.extend(extra_args)
            cmd = " ".join(cmd_parts)
            self.log(f"[Analysis] sending: {cmd}")
            self.process.stdin.write((cmd + "\n").encode())
            self.process.stdin.flush()

            time.sleep(duration)

            try:
                self.process.stdin.write(b"stop\n")
                self.process.stdin.flush()
            except (OSError, ValueError, BrokenPipeError) as exc:
                self.log(f"[Analysis] stop failed: {exc}")

            time.sleep(0.25)
            with self.analysis_lock:
                self.is_analyzing = False
                lines = list(self.analysis_lines)
                ownership = list(self.ownership_data)

            drained = self._drain_response_queue(wait=0.4)
            if drained:
                self.log(f"[Analysis] drained {drained} sync responses")

            if original_visits != visits:
                self.current_visits = original_visits
                restore_max_visits = 10000000 if original_visits == 0 else original_visits
                restore_resp = self._send_command_locked(
                    f"kata-set-param maxVisits {restore_max_visits}",
                    timeout=10.0,
                )
                if restore_resp.startswith("?"):
                    self.log(f"[Analysis] restore visits failed: {restore_resp}")

            self.log(
                f"[Analysis] collected {len(lines)} info lines, {len(ownership)} ownership vals"
            )
            return lines, ownership

    def parse_analysis(
        self,
        lines: list,
        ownership: list,
        size: int = 19,
        to_move_color: str = "B",
    ) -> dict:
        moves = []
        root_winrate = 0.5
        root_score = 0.0

        latest_line = ""
        for line in reversed(lines):
            if line.startswith("info "):
                latest_line = line
                break

        if not latest_line:
            return {
                "winrate": 0.5,
                "score": 0.0,
                "top_moves": [],
                "ownership": ownership,
                "analysis_color": to_move_color,
                "analysis_ready": False,
            }

        segments = [
            segment.strip()
            for segment in re.split(r"(?=info move )", latest_line)
            if segment.strip().startswith("info move ")
        ]

        for segment in segments:
            parts = segment.split()
            fields = {}
            i = 1
            while i < len(parts) - 1:
                key = parts[i]
                if key == "pv":
                    break
                fields[key] = parts[i + 1]
                i += 2

            move_gtp = fields.get("move")
            if not move_gtp:
                continue
            try:
                visits = int(fields.get("visits", 0))
                wr = float(fields.get("winrate", 0.5))
                score_mean = float(fields.get("scoreMean", 0.0))
                order = int(fields.get("order", 999))
            except (ValueError, TypeError):
                self.log(f"[Analysis] parse error for segment: {segment[:120]}")
                continue

            if order == 0:
                root_winrate = wr
                root_score = score_mean
            if move_gtp.upper() != "PASS":
                coord = self.coord_parser(move_gtp, size)
                if coord:
                    moves.append(
                        {
                            "x": coord[0],
                            "y": coord[1],
                            "winrate": round(wr, 3),
                            "black_winrate": round(
                                wr if to_move_color == "B" else 1.0 - wr,
                                3,
                            ),
                            "visits": visits,
                            "gtp": move_gtp,
                            "order": order,
                        }
                    )

        root_match = re.search(
            r"\brootInfo\b(.*?)(?=\bownership\b|\bownershipStdev\b|$)",
            latest_line,
        )
        if root_match:
            root_fields = {}
            root_parts = root_match.group(1).split()
            i = 0
            while i < len(root_parts) - 1:
                root_fields[root_parts[i]] = root_parts[i + 1]
                i += 2
            try:
                root_winrate = float(root_fields.get("winrate", root_winrate))
                root_score = float(
                    root_fields.get("scoreLead", root_fields.get("scoreMean", root_score))
                )
            except (TypeError, ValueError):
                pass

        if not ownership:
            ownership_match = re.search(r"\bownership\b(.*?)(?=\bownershipStdev\b|$)", latest_line)
            if ownership_match:
                vals = ownership_match.group(1).split()
                expected = size * size
                try:
                    ownership = [float(v) for v in vals[:expected]]
                except ValueError:
                    ownership = []

        if ownership and to_move_color == "W":
            ownership = [-v for v in ownership]

        moves.sort(key=lambda m: m["order"])
        black_winrate = root_winrate if to_move_color == "B" else 1.0 - root_winrate
        black_score = root_score if to_move_color == "B" else -root_score
        return {
            "winrate": round(black_winrate, 3),
            "score": round(black_score, 1),
            "top_moves": moves[:8],
            "ownership": ownership,
            "analysis_color": to_move_color,
            "analysis_ready": bool(moves or root_match),
        }

    def stop(self):
        if self.process:
            try:
                self.send_command("quit", timeout=3)
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.ready = False
        self.stderr_callback = None

    def restart(self):
        self.stop()
        time.sleep(0.5)
        self.start()

