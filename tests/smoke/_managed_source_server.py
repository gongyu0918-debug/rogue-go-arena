from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTROL_TOKEN = "managed-source-server-smoke-token"
CONTROL_TOKEN_HEADER = "X-Rogue-Go-Control-Token"


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(base_url: str, path: str, *, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(base_url + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_json(
    base_url: str,
    path: str,
    *,
    timeout: float = 10.0,
    token: str | None = CONTROL_TOKEN,
) -> dict[str, Any] | None:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers[CONTROL_TOKEN_HEADER] = token
    request = urllib.request.Request(
        base_url + path,
        data=b"{}",
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def log_tail(log_path: Path, *, max_lines: int = 80) -> str:
    if not log_path.exists():
        return ""
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


class ManagedSourceServer:
    def __init__(
        self,
        *,
        port: int,
        no_katago: bool,
        artifact_subdir: str,
        startup_timeout: float,
    ) -> None:
        self.port = free_port() if port == 0 else port
        self.no_katago = no_katago
        self.startup_timeout = startup_timeout
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[str] | None = None
        artifact_dir = ROOT / "output" / artifact_subdir
        artifact_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = artifact_dir / f"server-{self.port}.log"

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def start(self) -> dict[str, Any]:
        if port_is_open(self.port):
            raise RuntimeError(f"port {self.port} is already in use; refusing to attach to an unknown process")

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["ROGUE_GO_ARENA_CONTROL_TOKEN"] = CONTROL_TOKEN
        args = [
            sys.executable,
            "server.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
        ]
        if self.no_katago:
            args.append("--no-katago")

        log = self.log_path.open("w", encoding="utf-8", errors="replace")
        try:
            self.process = subprocess.Popen(
                args,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                env=env,
                close_fds=True,
            )
        finally:
            log.close()
        return self.wait_for_status()

    def wait_for_status(self) -> dict[str, Any]:
        if self.process is None:
            raise RuntimeError("source server has not been started")
        deadline = time.monotonic() + self.startup_timeout
        last_error = ""
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"source server exited early with code {self.process.returncode}\n"
                    f"--- server log tail ---\n{log_tail(self.log_path)}"
                )
            try:
                return http_json(self.base_url, "/status", timeout=3)
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.25)
        raise TimeoutError(
            f"source server did not expose /status within {self.startup_timeout:.0f}s: {last_error}\n"
            f"--- server log tail ---\n{log_tail(self.log_path)}"
        )

    def stop(self) -> None:
        process = self.process
        if process is None or process.poll() is not None:
            return
        http_post_json(self.base_url, "/stop_katago", timeout=8)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    def __enter__(self) -> "ManagedSourceServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
