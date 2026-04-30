"""GoAI native client entrypoint.

Starts the bundled server sidecar and opens the game in a desktop WebView2
window. Edge app-window and system browser fallbacks are kept for machines
without a working WebView2 host.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlencode

SERVER_PORT = 8000
LOOPBACK_HOST = "127.0.0.1"
SERVER_URL = f"http://{LOOPBACK_HOST}:{SERVER_PORT}"
EXPECTED_SERVER_REV = "20260430-card-editor-shell"
NATIVE_WINDOW_SIZE = "1500,1000"
EDGE_PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GoAI" / "edge-app-profile"
WEBVIEW_PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GoAI" / "webview-profile"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
DESKTOP_SHELLS = {"webview", "edge", "browser"}


def _launcher_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_server_base() -> Path:
    roots = [_launcher_dir(), _launcher_dir().parent, Path.cwd()]
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (root / "server.py").exists() and (root / "static").is_dir() and (root / "katago").is_dir():
            return root
    return _launcher_dir()


BASE_DIR = _find_server_base()
SERVER_SCRIPT = BASE_DIR / "server.py"
SERVER_EXE = BASE_DIR / "GoAI_Server" / "GoAI_Server.exe"
if not SERVER_EXE.exists():
    SERVER_EXE = BASE_DIR / "GoAI_Server.exe"


def _creationflags_no_window() -> int:
    return CREATE_NO_WINDOW if os.name == "nt" else 0


def _server_creationflags() -> int:
    flags = _creationflags_no_window()
    if os.name == "nt":
        flags |= DETACHED_PROCESS
    return flags


def _server_startupinfo():
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = 0
    return startupinfo


def _frontend_url() -> str:
    return f"{SERVER_URL}/?{urlencode({'rev': EXPECTED_SERVER_REV, 'ts': int(time.time())})}"


def _window_size() -> tuple[int, int]:
    try:
        width_text, height_text = NATIVE_WINDOW_SIZE.split(",", 1)
        return int(width_text), int(height_text)
    except Exception:
        return 1500, 1000


def _fetch_status(timeout=1.5) -> dict | None:
    try:
        with urllib.request.urlopen(f"{SERVER_URL}/status", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, OSError):
        return None


def _port_open(port=SERVER_PORT, timeout=1.0) -> bool:
    try:
        with socket.create_connection((LOOPBACK_HOST, port), timeout=timeout):
            return True
    except OSError:
        return False


def _listener_pids(port=SERVER_PORT) -> list[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags_no_window(),
        )
    except Exception:
        return []
    pids: list[int] = []
    needle = f":{port}"
    for line in out.splitlines():
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(needle) and parts[3].upper() == "LISTENING":
            try:
                pids.append(int(parts[4]))
            except ValueError:
                pass
    return sorted(set(pids))


def _pid_image_name(pid: int) -> str:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_creationflags_no_window(),
        ).strip()
    except Exception:
        return ""
    if not out or out.startswith("INFO:"):
        return ""
    return out.split(",", 1)[0].strip('"').lower()


def _stop_stale_server_on_port(port=SERVER_PORT) -> None:
    for pid in _listener_pids(port):
        image_name = _pid_image_name(pid)
        if not (image_name.startswith("python") or image_name in {"goai.exe", "goai_server.exe"}):
            continue
        try:
            subprocess.check_call(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_creationflags_no_window(),
            )
        except Exception:
            pass


def _find_edge_exe() -> str | None:
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return shutil.which("msedge")


def _stop_katago_runtime() -> None:
    try:
        req = urllib.request.Request(f"{SERVER_URL}/stop_katago", method="POST")
        with urllib.request.urlopen(req, timeout=2):
            pass
    except Exception:
        pass


def _open_webview_window(url: str) -> bool:
    try:
        import webview
    except Exception:
        return False

    width, height = _window_size()
    try:
        WEBVIEW_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        webview.create_window(
            "GoAI",
            url,
            width=width,
            height=height,
            min_size=(1100, 720),
            background_color="#111318",
            text_select=True,
        )
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(WEBVIEW_PROFILE_DIR),
            icon=str(BASE_DIR / "goai.ico"),
        )
        _stop_katago_runtime()
        return True
    except Exception:
        return False


def _open_edge_app_window(url: str) -> bool:
    edge = _find_edge_exe()
    if edge:
        try:
            EDGE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                [
                    edge,
                    f"--app={url}",
                    "--new-window",
                    f"--window-size={NATIVE_WINDOW_SIZE}",
                    f"--user-data-dir={EDGE_PROFILE_DIR}",
                    "--disable-features=msEdgeSidebarV2",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_creationflags_no_window(),
            )
            proc.wait()
            _stop_katago_runtime()
            return True
        except Exception:
            pass
    return False


def _open_system_browser(url: str) -> bool:
    try:
        os.startfile(url)
        return True
    except Exception:
        return False


def _open_native_client_window(url: str, shell: str) -> bool:
    if shell == "webview" and _open_webview_window(url):
        return True
    if shell in {"webview", "edge"} and _open_edge_app_window(url):
        return True
    return _open_system_browser(url)


def _wait_frontend_ready(timeout=90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _fetch_status(timeout=2)
        if status and status.get("server_rev") == EXPECTED_SERVER_REV and status.get("static_ready"):
            return True
        time.sleep(0.5)
    return False


def _start_server() -> bool:
    cmd = [str(SERVER_EXE)] if SERVER_EXE.exists() else [sys.executable, str(SERVER_SCRIPT)]
    cmd.extend(["--host", LOOPBACK_HOST])
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(BASE_DIR),
            creationflags=_server_creationflags(),
            startupinfo=_server_startupinfo(),
        )
        return True
    except Exception as exc:
        try:
            messagebox.showerror("GoAI", f"启动失败: {exc}")
        except Exception:
            pass
        return False


def _resolve_shell(shell: str | None) -> str:
    selected = (shell or os.environ.get("GOAI_DESKTOP_SHELL") or "webview").strip().lower()
    return selected if selected in DESKTOP_SHELLS else "webview"


def run_native_client(shell: str | None = None) -> int:
    desktop_shell = _resolve_shell(shell)
    status = _fetch_status(timeout=1.5)
    if status and status.get("server_rev") == EXPECTED_SERVER_REV:
        return 0 if _open_native_client_window(_frontend_url(), desktop_shell) else 1
    if _port_open(SERVER_PORT, 0.5):
        _stop_stale_server_on_port(SERVER_PORT)
        time.sleep(0.8)
    if not _start_server():
        return 1
    if not _wait_frontend_ready():
        try:
            messagebox.showerror("GoAI", f"服务未能在 {SERVER_PORT} 端口就绪")
        except Exception:
            pass
        return 1
    return 0 if _open_native_client_window(_frontend_url(), desktop_shell) else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the GoAI desktop client.")
    parser.add_argument(
        "--shell",
        choices=sorted(DESKTOP_SHELLS),
        default=None,
        help="Desktop shell to use: webview uses WebView2, edge uses Edge app mode.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run_native_client(shell=_parse_args().shell))
