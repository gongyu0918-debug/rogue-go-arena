from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parents[3]
UI_EXIT_HEADER = "X-Rogue-Go-Ui-Exit-Token"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


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


def post_desktop_exit_status(base_url: str, token: str | None) -> int:
    headers = {}
    if token:
        headers[UI_EXIT_HEADER] = token
    request = urllib.request.Request(base_url + "/desktop_exit", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


async def start_two_player_game(base_url: str) -> dict:
    ws_url = base_url.replace("http://", "ws://") + "/ws/desktop-exit-smoke"
    async with websockets.connect(ws_url, open_timeout=10) as ws:
        await ws.send(
            json.dumps(
                {
                    "action": "new_game",
                    "size": 9,
                    "komi": 6.5,
                    "player_color": "B",
                    "level": "18k",
                    "two_player": True,
                }
            )
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic()))
            if message.get("type") == "game_start":
                return message
    raise TimeoutError("two-player game_start was not received")


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    log_path = Path(tempfile.gettempdir()) / f"rogue-go-desktop-exit-{port}.log"
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
            initial_status = wait_for_status(base_url, process)
            token = initial_status.get("desktop_exit_token")
            no_token_status = post_desktop_exit_status(base_url, token=None)
            before_game_status = post_desktop_exit_status(base_url, token=token)
            game_start = asyncio.run(start_two_player_game(base_url))
            active_status = wait_for_status(base_url, process)
            exit_status = post_desktop_exit_status(base_url, token=active_status.get("desktop_exit_token"))
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=8)

    assert initial_status["desktop_exit_available"] is False
    assert token
    assert no_token_status == 403
    assert before_game_status == 409
    assert game_start["type"] == "game_start"
    assert active_status["desktop_exit_available"] is True
    assert active_status["active_games_count"] >= 1
    assert exit_status == 200
    assert process.returncode == 0
    assert not port_open(port)

    print(
        json.dumps(
            {
                "status": "passed",
                "port": port,
                "returncode": process.returncode,
                "before_game_status": before_game_status,
                "exit_status": exit_status,
                "log": str(log_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
