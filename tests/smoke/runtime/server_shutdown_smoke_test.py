from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_status(base_url: str, process: subprocess.Popen, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(base_url + "/status", timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"server did not expose /status: {last_error}")


def post_shutdown(base_url: str) -> dict:
    request = urllib.request.Request(base_url + "/shutdown", method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    log_path = Path(tempfile.gettempdir()) / f"rogue-go-shutdown-{port}.log"
    process = None
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "server.py",
                "--no-katago",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        try:
            status = wait_for_status(base_url, process)
            shutdown = post_shutdown(base_url)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)

    assert status["server_rev"] == "20260624-desktop-server-shutdown"
    assert status["no_katago"] is True
    assert shutdown == {"ok": True, "action": "shutdown"}
    assert process.returncode == 0

    print(
        json.dumps(
            {
                "status": "passed",
                "port": port,
                "returncode": process.returncode,
                "log": str(log_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
