from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

from _path_bootstrap import ensure_repo_root


ensure_repo_root(__file__)
ROOT = Path(__file__).resolve().parents[3]


def read_line_with_timeout(stream, timeout: float = 20.0) -> str:
    result: queue.Queue[str] = queue.Queue(maxsize=1)
    thread = threading.Thread(target=lambda: result.put(stream.readline()), daemon=True)
    thread.start()
    try:
        line = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError("worker did not respond in time") from exc
    if not line:
        raise RuntimeError("worker closed stdout")
    return line


def send(proc: subprocess.Popen[str], payload: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    return json.loads(read_line_with_timeout(proc.stdout))


def listener_ports_for_pid(pid: int) -> set[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
    except Exception:
        return set()
    ports: set[int] = set()
    for line in out.splitlines():
        parts = line.strip().split()
        if len(parts) < 5 or parts[0] != "TCP" or parts[3].upper() != "LISTENING":
            continue
        try:
            if int(parts[4]) != pid:
                continue
            ports.add(int(parts[1].rsplit(":", 1)[1]))
        except ValueError:
            continue
    return ports


def main() -> None:
    worker = ROOT / "go_runtime_worker.py"
    proc = subprocess.Popen(
        [sys.executable, str(worker), "--no-katago"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    try:
        status = send(proc, {"id": "status", "command": "get_status"})
        assert status["ok"] is True
        assert status["result"]["port"] == 0
        assert status["result"]["access_urls"] == {}
        assert not ({8000, 8877} & listener_ports_for_pid(proc.pid))

        started = send(
            proc,
            {
                "id": "new",
                "game_id": "worker-smoke",
                "action": "new_game",
                "size": 9,
                "komi": 6.5,
                "two_player": True,
                "player_color": "B",
            },
        )
        assert started["ok"] is True
        assert any(event.get("type") == "game_start" for event in started.get("events", []))

        played = send(
            proc,
            {
                "id": "play",
                "game_id": "worker-smoke",
                "action": "play",
                "x": 2,
                "y": 2,
            },
        )
        assert played["ok"] is True
        assert any(event.get("type") == "game_state" for event in played.get("events", []))

        passed = send(
            proc,
            {
                "id": "pass",
                "game_id": "worker-smoke",
                "action": "pass",
            },
        )
        assert passed["ok"] is True
        assert any(event.get("type") == "game_state" for event in passed.get("events", []))

        sgf = send(
            proc,
            {
                "id": "sgf",
                "game_id": "worker-smoke",
                "command": "export_sgf",
            },
        )
        assert sgf["ok"] is True
        assert "SZ[9]" in sgf["result"]["sgf"]
        assert ";B[" in sgf["result"]["sgf"]

        stopped = send(proc, {"id": "shutdown", "command": "shutdown"})
        assert stopped["ok"] is True
        assert stopped["result"]["shutdown"] is True
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()

    print({"ok": True})


if __name__ == "__main__":
    main()
