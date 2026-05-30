from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parent


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def read_status(base_url: str) -> dict:
    with urllib.request.urlopen(base_url + "/status", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_status(base_url: str, process: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early with code {process.returncode}")
        try:
            read_status(base_url)
            return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"server did not expose /status: {last_error}")


async def recv_until(ws, predicate, *, timeout: float):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for websocket message")
        msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        if predicate(msg):
            return msg


async def exercise_websocket(base_ws: str) -> dict:
    game_id = "ws-session-" + uuid.uuid4().hex[:8]
    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            "action": "new_game",
            "size": 5,
            "komi": 7.5,
            "handicap": 0,
            "player_color": "B",
            "level": "5k",
            "two_player": True,
            "ai_observer": False,
            "rogue": False,
            "ai_rogue": False,
            "ultimate": False,
            "challenge_beta": False,
        }))
        start = await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=10)
        await ws.send(json.dumps({"action": "play", "x": 0, "y": 0}))
        state = await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10)

    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({"action": "reconnect"}))
        reconnect = await recv_until(ws, lambda m: m.get("type") == "reconnected", timeout=10)

    assert start["size"] == 5
    assert state["board"][0][0] == 1
    assert reconnect["board"][0][0] == 1
    return {
        "game_id": game_id,
        "start_type": start["type"],
        "state_type": state["type"],
        "reconnect_type": reconnect["type"],
        "status": "passed",
    }


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    base_ws = f"ws://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    log_path = Path(tempfile.gettempdir()) / f"rogue-go-websocket-{port}.log"
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
            wait_for_status(base_url, process)
            result = asyncio.run(exercise_websocket(base_ws))
        finally:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)

    print(json.dumps({"status": "passed", "port": port, "log": str(log_path), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
