"""
GoAI Launcher - Control panel for the KataGo Go AI server.
"""
import csv
import ctypes
import glob
import io
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import platform
import urllib.error
import urllib.request
import webbrowser
import zipfile
from collections import deque
from tkinter import scrolledtext, messagebox
from urllib.parse import urlencode

SERVER_PORT = 8000
LOOPBACK_HOST = "127.0.0.1"
LAN_HOST = "0.0.0.0"
SERVER_URL = f"http://{LOOPBACK_HOST}:{SERVER_PORT}"
EXPECTED_SERVER_REV = "20260423-puppet-flow-fix"
KATAGO_REPO = "lightvector/KataGo"
LAN_FIREWALL_RULE_NAME = "GoAI_LAN_8000"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)


def _launcher_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _find_server_base() -> str:
    roots = [
        _launcher_dir(),
        os.path.dirname(_launcher_dir()),
        os.getcwd(),
    ]
    seen = set()
    for root in roots:
        if not root or root in seen:
            continue
        seen.add(root)
        if (
            os.path.exists(os.path.join(root, "server.py"))
            and os.path.isdir(os.path.join(root, "static"))
            and os.path.isdir(os.path.join(root, "katago"))
        ):
            return root
    return _launcher_dir()


def _python_command() -> str:
    if not getattr(sys, "frozen", False):
        return sys.executable

    base_exec = getattr(sys, "_base_executable", "")
    if base_exec and os.path.exists(base_exec):
        if os.path.abspath(base_exec) != os.path.abspath(sys.executable):
            return base_exec

    for candidate in ("python", "py", "python3"):
        try:
            subprocess.run(
                [candidate, "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return candidate
        except Exception:
            pass

    return "python"


LAUNCHER_DIR = _launcher_dir()
BASE_DIR = _find_server_base()
SERVER_SCRIPT = os.path.join(BASE_DIR, "server.py")
PYTHON = _python_command()
USER_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "GoAI")
USER_KATAGO_DIR = os.path.join(USER_DATA_DIR, "katago")


def _creationflags_no_window() -> int:
    return CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


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


def _ensure_user_katago_dir():
    os.makedirs(USER_KATAGO_DIR, exist_ok=True)
    return USER_KATAGO_DIR


def _upgrade_model_dest():
    return os.path.join(USER_KATAGO_DIR, "model_large.bin.gz")


def _upgrade_cuda_dest():
    return os.path.join(USER_KATAGO_DIR, "katago_cuda.exe")


def _installed_model_dest():
    return os.path.join(BASE_DIR, "katago", "model_large.bin.gz")


def _installed_cuda_dest():
    return os.path.join(BASE_DIR, "katago", "katago_cuda.exe")


def _installed_cuda_runtime_ready() -> bool:
    katago_dir = os.path.join(BASE_DIR, "katago")
    has_cublas = os.path.exists(os.path.join(katago_dir, "cublas64_12.dll"))
    has_cudart = os.path.exists(os.path.join(katago_dir, "cudart64_12.dll"))
    has_cudnn = any(
        os.path.exists(os.path.join(katago_dir, name))
        for name in ("cudnn64_9.dll", "cudnn64_8.dll")
    )
    return has_cublas and has_cudart and has_cudnn


def _upgrade_installed() -> bool:
    has_model = (
        os.path.exists(_installed_model_dest())
    )
    has_cuda = (
        os.path.exists(_installed_cuda_dest()) and _installed_cuda_runtime_ready()
    )
    return has_model and has_cuda


def _activate_staged_upgrade(staged_path: str, installed_path: str) -> tuple[bool, str]:
    if not os.path.exists(staged_path):
        return False, "staged_missing"
    os.makedirs(os.path.dirname(installed_path), exist_ok=True)
    shutil.copyfile(staged_path, installed_path)
    return True, installed_path

# Packaged server exe (preferred — no Python dependency on target machine)
_SERVER_EXE = os.path.join(BASE_DIR, "GoAI_Server", "GoAI_Server.exe")
if not os.path.exists(_SERVER_EXE):
    _SERVER_EXE = os.path.join(BASE_DIR, "GoAI_Server.exe")
USE_SERVER_EXE = os.path.exists(_SERVER_EXE)

# ── Launcher Theme ──────────────────────────────────────────────────────────
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 640
BG = "#0C1116"
BG2 = "#10171E"
BG3 = "#1A232C"
PANEL = "#0E151B"
PANEL_ALT = "#121B23"
BORDER = "#27414C"
GOLD = "#D7B35C"
GREEN = "#2E8B70"
RED = "#B75A58"
PLUM = "#6F54B8"
TEXT = "#F3EFE7"
MUTED = "#9FAAB3"
ACCENT = "#6FD7D1"
LOG_BG = "#071017"
LOG_TEXT = "#92DED6"

BUTTON_STYLES = {
    "primary": {"bg": GOLD, "fg": "#16110A", "activebackground": "#E4C46D"},
    "success": {"bg": GREEN, "fg": TEXT, "activebackground": "#39A383"},
    "danger": {"bg": RED, "fg": TEXT, "activebackground": "#C66967"},
    "neutral": {"bg": BG3, "fg": TEXT, "activebackground": "#26323D"},
    "plum": {"bg": PLUM, "fg": TEXT, "activebackground": "#7D62C9"},
    "disabled": {"bg": "#2A333A", "fg": "#73818A", "activebackground": "#2A333A"},
}



class GoAILauncher:
    def __init__(self):
        self.server_proc = None
        self._running = False
        self._ui_queue: queue.Queue = queue.Queue()
        self._server_log_tail = deque(maxlen=30)
        self._status_monitor_stop = threading.Event()
        self._last_engine_signature = None
        self._log_visible = False
        self._background_photo = None
        self._server_active = False
        self._engine_phase = "idle"
        self._active_server_host = LOOPBACK_HOST

        self.root = tk.Tk()
        self.root.title("GoAI 启动器")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self._status_var = tk.StringVar(value="服务器未启动")
        self._status_hint_var = tk.StringVar(value="")
        self._mode_var = tk.StringVar(value="未启动")
        self._ai_status_var = tk.StringVar(value="启动时开启")
        self._address_var = tk.StringVar(value=SERVER_URL)
        self._lan_address_var = tk.StringVar(value="未开启")
        self._network_hint_var = tk.StringVar(value="默认仅本机可访问")
        self._lan_enabled = tk.BooleanVar(value=False)

        ico = os.path.join(BASE_DIR, "goai.ico")
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._drain_ui_queue)
        # Run environment checks after UI is ready
        self.root.after(200, self._check_environment)

    def _set_widget_alpha(self, widget: tk.Widget, alpha: int = 232):
        if os.name != "nt":
            return
        try:
            hwnd = widget.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            LWA_ALPHA = 0x00000002
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            user32.SetLayeredWindowAttributes(hwnd, 0, max(0, min(255, alpha)), LWA_ALPHA)
        except Exception:
            pass

    def _make_card(self, parent, *, bg=PANEL, alpha: int = 228):
        frame = tk.Frame(
            parent,
            bg=bg,
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        self.root.after(0, lambda w=frame, a=alpha: self._set_widget_alpha(w, a))
        return frame

    def _apply_button_style(self, button: tk.Widget, variant: str, *, text: str | None = None, state: str | None = None):
        style = BUTTON_STYLES.get(variant, BUTTON_STYLES["neutral"])
        button.configure(
            bg=style["bg"],
            fg=style["fg"],
            activebackground=style["activebackground"],
            activeforeground=style["fg"],
            disabledforeground=BUTTON_STYLES["disabled"]["fg"],
            highlightbackground=style["bg"],
        )
        if text is not None:
            button.configure(text=text)
        if state is not None:
            button.configure(state=state)

    def _make_button(
        self,
        parent,
        *,
        text: str,
        command,
        variant: str = "neutral",
        width: int | None = 12,
        font_size: int = 10,
    ):
        button_kwargs = {
            "parent": parent,
            "text": text,
            "font": ("Microsoft YaHei", font_size, "bold"),
            "relief": "flat",
            "borderwidth": 0,
            "cursor": "hand2",
            "padx": 10,
            "pady": 9,
            "command": command,
        }
        if width is not None:
            button_kwargs["width"] = width
        button = tk.Button(
            button_kwargs.pop("parent"),
            **button_kwargs,
        )
        self._apply_button_style(button, variant)
        return button

    def _set_log_visibility(self, visible: bool):
        self._log_visible = visible
        if visible:
            self._summary_card.place_forget()
            self._log_panel.place(x=28, y=348, width=664, height=232)
            if not self._log_body.winfo_manager():
                self._log_body.pack(fill="both", expand=True, padx=14, pady=(56, 14))
            self._apply_button_style(self._log_toggle_btn, "neutral", text="收起日志")
        else:
            if self._log_body.winfo_manager():
                self._log_body.pack_forget()
            self._summary_card.place(x=28, y=348, width=664, height=156)
            self._log_panel.place(x=28, y=524, width=664, height=56)
            self._apply_button_style(self._log_toggle_btn, "neutral", text="运行日志")

    def _toggle_log_panel(self):
        self._set_log_visibility(not self._log_visible)

    @staticmethod
    def _is_loopback_host(host: str | None) -> bool:
        host = (host or "").strip().lower()
        return host in {"127.0.0.1", "localhost", "::1"}

    def _desired_bind_host(self) -> str:
        return LAN_HOST if self._lan_enabled.get() else LOOPBACK_HOST

    def _refresh_network_fields(
        self,
        *,
        local_url: str | None = None,
        lan_url: str | None = None,
        running: bool | None = None,
        host: str | None = None,
    ):
        def _do():
            active = self._server_active if running is None else running
            active_host = self._active_server_host if host is None else host
            if local_url:
                self._address_var.set(local_url)

            if lan_url:
                self._lan_address_var.set(lan_url)
            elif active and not self._is_loopback_host(active_host):
                self._lan_address_var.set("未发现局域网地址")
            elif self._lan_enabled.get():
                self._lan_address_var.set("启动服务后显示")
            else:
                self._lan_address_var.set("未开启")

            if active and not self._is_loopback_host(active_host):
                lan_text = self._lan_address_var.get()
                if lan_text.startswith("http://"):
                    self._network_hint_var.set(f"局域网共享中 · {lan_text}")
                else:
                    self._network_hint_var.set("局域网共享中 · 正在探测入口")
            elif self._lan_enabled.get():
                self._network_hint_var.set("局域网模式待生效，启动后自动放行端口并显示入口")
            else:
                self._network_hint_var.set("默认仅本机可访问")

        self._call_in_ui(_do)
        self._sync_lan_button()

    def _sync_lan_button(self):
        def _update():
            if not hasattr(self, "_lan_btn"):
                return
            active_lan = self._server_active and not self._is_loopback_host(self._active_server_host)
            pending_lan = (not self._server_active) and self._lan_enabled.get()
            enabled = active_lan or pending_lan
            if enabled:
                text = "局域网共享中" if active_lan else "局域网待生效"
                variant = "success"
            else:
                text = "允许局域网"
                variant = "neutral"
            state = "disabled" if self._running else "normal"
            self._apply_button_style(self._lan_btn, variant, text=text, state=state)

        self._call_in_ui(_update)

    def _delete_lan_firewall_rule(self) -> bool:
        if os.name != "nt":
            return False
        try:
            completed = subprocess.run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={LAN_FIREWALL_RULE_NAME}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
                creationflags=_creationflags_no_window(),
            )
            return completed.returncode == 0
        except Exception:
            return False

    def _ensure_lan_firewall_rule(self) -> bool:
        if os.name != "nt":
            return False

        def _run_netsh(args: list[str]) -> bool:
            try:
                completed = subprocess.run(
                    ["netsh", *args],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                    check=False,
                    creationflags=_creationflags_no_window(),
                )
                return completed.returncode == 0
            except Exception:
                return False

        self._delete_lan_firewall_rule()
        add_args = [
            "advfirewall", "firewall", "add", "rule",
            f"name={LAN_FIREWALL_RULE_NAME}",
            "dir=in",
            "action=allow",
            "profile=private",
            "protocol=TCP",
            f"localport={SERVER_PORT}",
        ]
        if _run_netsh(add_args):
            return True

        ps_args = ",".join("'" + part.replace("'", "''") + "'" for part in add_args)
        ps_cmd = (
            "Start-Process -FilePath 'netsh' "
            f"-ArgumentList @({ps_args}) -Verb RunAs -Wait -WindowStyle Hidden"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=45,
                check=False,
                creationflags=_creationflags_no_window(),
            )
            return completed.returncode == 0
        except Exception:
            return False

    def _restart_for_network_mode(self):
        if self._running:
            self._log_msg("服务启动中，网络模式会在下次重启后生效", GOLD)
            return

        if not self._server_active:
            mode = "局域网共享" if self._lan_enabled.get() else "仅本机访问"
            self._log_msg(f"已切换为{mode}，下次启动服务时生效", GOLD)
            self._refresh_network_fields()
            return

        def _restart():
            self._log_msg("正在重启服务以应用新的访问模式…", GOLD)
            self._stop_server()
            time.sleep(0.8)
            self._start_server()

        threading.Thread(target=_restart, daemon=True).start()

    def _toggle_lan_access(self):
        enabled = not self._lan_enabled.get()
        self._lan_enabled.set(enabled)
        self._refresh_network_fields()

        if enabled:
            self._log_msg("已开启局域网共享模式，其他设备可通过局域网入口访问", GOLD)

            def _prepare_lan():
                if self._ensure_lan_firewall_rule():
                    self._log_msg(f"已放行 Windows 私有网络 {SERVER_PORT} 端口", GREEN)
                else:
                    self._log_msg("未能自动放行 Windows 防火墙，局域网访问可能受限", GOLD)

            threading.Thread(target=_prepare_lan, daemon=True).start()
        else:
            self._log_msg("已切回仅本机访问模式", GOLD)

            def _restore_local_only():
                if self._delete_lan_firewall_rule():
                    self._log_msg(f"已收回 Windows 私有网络 {SERVER_PORT} 端口放行", GREEN)

            threading.Thread(target=_restore_local_only, daemon=True).start()

        self._restart_for_network_mode()

    def _sync_ai_toggle_button(self):
        def _update():
            if self._running and not self._server_active:
                self._ai_status_var.set("启动中")
                self._apply_button_style(self._ai_toggle_btn, "disabled", text="AI 启动中", state="disabled")
                return
            if not self._server_active:
                enabled = bool(self._ai_enabled.get())
                self._ai_status_var.set("启动时开启" if enabled else "启动时关闭")
                self._apply_button_style(
                    self._ai_toggle_btn,
                    "success" if enabled else "neutral",
                    text="AI 已开启" if enabled else "AI 已关闭",
                    state="normal",
                )
                return
            if self._engine_phase == "initializing":
                self._ai_status_var.set("启动中")
                self._apply_button_style(self._ai_toggle_btn, "disabled", text="AI 启动中", state="disabled")
            elif self._model_running:
                self._ai_status_var.set("AI 已就绪")
                self._apply_button_style(self._ai_toggle_btn, "plum", text="关闭 AI", state="normal")
            else:
                self._ai_status_var.set("AI 已关闭")
                self._apply_button_style(self._ai_toggle_btn, "success", text="启动 AI", state="normal")

        self._call_in_ui(_update)

    def _toggle_ai_control(self):
        if self._server_active:
            self._toggle_model()
            return
        self._ai_enabled.set(not self._ai_enabled.get())
        self._log_msg(
            "已设置为启动时加载 AI" if self._ai_enabled.get() else "已设置为纯对弈启动",
            GOLD,
        )
        self._sync_ai_toggle_button()

    def _build_ui(self):
        bg_art = os.path.join(BASE_DIR, "launcher_bg_app.png")
        if os.path.exists(bg_art):
            try:
                self._background_photo = tk.PhotoImage(file=bg_art)
                tk.Label(
                    self.root,
                    image=self._background_photo,
                    bd=0,
                    highlightthickness=0,
                ).place(x=0, y=0, width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
            except Exception:
                pass

        hero = self._make_card(self.root, alpha=224)
        hero.place(x=28, y=24, width=664, height=190)

        tk.Label(
            hero,
            text="GOAI LAUNCHER",
            font=("Consolas", 10, "bold"),
            fg=ACCENT,
            bg=PANEL,
        ).place(x=24, y=18)
        tk.Label(
            hero,
            text="围棋对弈场",
            font=("Microsoft YaHei", 27, "bold"),
            fg=TEXT,
            bg=PANEL,
        ).place(x=22, y=40)
        tk.Label(
            hero,
            textvariable=self._status_hint_var,
            font=("Microsoft YaHei", 9),
            fg=MUTED,
            bg=PANEL,
        ).place(x=24, y=86)

        status_box = tk.Frame(hero, bg=BG3, padx=12, pady=7)
        status_box.place(x=24, y=112)
        self.root.after(0, lambda: self._set_widget_alpha(status_box, 236))
        self._dot_canvas = tk.Canvas(
            status_box,
            width=14,
            height=14,
            bg=BG3,
            highlightthickness=0,
        )
        self._dot_canvas.pack(side="left", padx=(0, 6))
        self._dot = self._dot_canvas.create_oval(2, 2, 12, 12, fill=RED, outline="")
        tk.Label(
            status_box,
            textvariable=self._status_var,
            font=("Microsoft YaHei", 11, "bold"),
            fg=TEXT,
            bg=BG3,
        ).pack(side="left")

        action_panel = tk.Frame(hero, bg=PANEL)
        action_panel.place(x=392, y=24, width=242, height=152)

        action_grid = tk.Frame(action_panel, bg=PANEL)
        action_grid.pack(fill="both", expand=True)
        action_grid.grid_columnconfigure(0, weight=1, uniform="hero-actions")
        action_grid.grid_columnconfigure(1, weight=1, uniform="hero-actions")
        action_grid.grid_rowconfigure(0, weight=1)
        action_grid.grid_rowconfigure(1, weight=1)
        action_grid.grid_rowconfigure(2, weight=1)

        self._start_btn = self._make_button(
            action_grid,
            text="启动服务",
            command=self._start_server,
            variant="primary",
            width=None,
            font_size=11,
        )
        self._start_btn.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._stop_btn = self._make_button(
            action_grid,
            text="停止服务",
            command=self._stop_server,
            variant="danger",
            width=None,
            font_size=10,
        )
        self._stop_btn.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(8, 0))
        self._stop_btn.configure(state="disabled")
        self._open_btn = self._make_button(
            action_grid,
            text="打开页面",
            command=self._open_browser,
            variant="success",
            width=None,
            font_size=10,
        )
        self._open_btn.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(8, 0))
        self._open_btn.configure(state="disabled")
        self._lan_btn = self._make_button(
            action_grid,
            text="允许局域网",
            command=self._toggle_lan_access,
            variant="neutral",
            width=None,
            font_size=10,
        )
        self._lan_btn.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(8, 0))

        controls = self._make_card(self.root, bg=PANEL_ALT, alpha=224)
        controls.place(x=28, y=228, width=664, height=104)

        tk.Label(
            controls,
            text="AI 与性能",
            font=("Microsoft YaHei", 12, "bold"),
            fg=TEXT,
            bg=PANEL_ALT,
        ).place(x=22, y=18)

        self._ai_enabled = tk.BooleanVar(value=True)
        control_actions = tk.Frame(controls, bg=PANEL_ALT)
        control_actions.place(x=22, y=52, width=620, height=38)
        for col in range(2):
            control_actions.grid_columnconfigure(col, weight=1, uniform="control-actions")
        self._model_running = True
        self._ai_toggle_btn = self._make_button(
            control_actions,
            text="AI 已开启",
            command=self._toggle_ai_control,
            variant="success",
            width=None,
            font_size=10,
        )
        self._ai_toggle_btn.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._stop_model_btn = self._ai_toggle_btn
        self._update_btn = None

        self._upgrade_btn = self._make_button(
            control_actions,
            text="性能升级包",
            command=self._show_upgrade_dialog,
            variant="primary",
            width=None,
            font_size=10,
        )
        self._upgrade_btn.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._upgrade_hint = None

        if _upgrade_installed():
            self._apply_button_style(self._upgrade_btn, "neutral", text="✓ 已安装升级包", state="disabled")
        else:
            self._apply_button_style(self._upgrade_btn, "primary")
            self._apply_upgrade_button_policy()
        self._sync_ai_toggle_button()

        self._summary_card = self._make_card(self.root, alpha=224)
        self._summary_card.place(x=28, y=348, width=664, height=156)
        tk.Label(
            self._summary_card,
            text="快速概览",
            font=("Microsoft YaHei", 12, "bold"),
            fg=TEXT,
            bg=PANEL,
        ).pack(anchor="w", padx=22, pady=(16, 6))

        summary_body = tk.Frame(self._summary_card, bg=PANEL)
        summary_body.pack(fill="both", expand=True, padx=22, pady=(0, 14))

        def add_row(label_text: str, variable: tk.StringVar):
            row = tk.Frame(summary_body, bg=PANEL)
            row.pack(fill="x", pady=4)
            tk.Label(
                row,
                text=label_text,
                font=("Microsoft YaHei", 9, "bold"),
                fg=GOLD,
                bg=PANEL,
                width=9,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                textvariable=variable,
                font=("Microsoft YaHei", 9),
                fg=MUTED,
                bg=PANEL,
                wraplength=500,
                justify="left",
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        add_row("服务状态", self._mode_var)
        add_row("AI 状态", self._ai_status_var)
        add_row("本机入口", self._address_var)
        add_row("局域网入口", self._lan_address_var)

        self._log_panel = self._make_card(self.root, bg=PANEL_ALT, alpha=220)
        self._log_toggle_btn = self._make_button(
            self._log_panel,
            text="运行日志",
            command=self._toggle_log_panel,
            variant="neutral",
            width=10,
            font_size=9,
        )
        self._log_toggle_btn.place(x=530, y=9, width=118, height=36)

        self._log_body = tk.Frame(self._log_panel, bg=PANEL_ALT)
        self._log = scrolledtext.ScrolledText(
            self._log_body,
            font=("Consolas", 9),
            bg=LOG_BG,
            fg=LOG_TEXT,
            insertbackground=LOG_TEXT,
            relief="flat",
            wrap="word",
            state="disabled",
            selectbackground="#144A56",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self._log.pack(fill="both", expand=True)

        tk.Label(
            self.root,
            text="GoAI © 2026 · 桌面启动器",
            font=("Microsoft YaHei", 8),
            fg="#D7D0C4",
            bg=BG,
        ).place(x=30, y=606)
        self._quit_btn = self._make_button(
            self.root,
            text="退出",
            command=self._on_close,
            variant="neutral",
            width=7,
            font_size=9,
        )
        self._quit_btn.place(x=618, y=600, width=74, height=30)

        self._set_log_visibility(False)
        self._refresh_network_fields()

    def _log_msg(self, msg: str, color: str = "#58a6ff"):
        self._server_log_tail.append(msg)
        def _do():
            self._log.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self._log.insert("end", f"[{ts}] ", "ts")
            self._log.insert("end", msg + "\n", "msg")
            self._log.tag_config("ts", foreground="#555")
            self._log.tag_config("msg", foreground=color)
            self._log.see("end")
            self._log.configure(state="disabled")
        self._call_in_ui(_do)

    # ── Environment Detection ──────────────────────────────────────────────
    def _check_environment(self):
        """Run environment checks on startup and log results."""
        threading.Thread(target=self._env_check_worker, daemon=True).start()

    def _env_check_worker(self):
        self._log_msg("━━━ 环境检测 ━━━", GOLD)
        self._activate_staged_upgrades()

        # 1. Check server exe / Python availability
        if USE_SERVER_EXE:
            self._log_msg(f"✓ 服务器引擎: GoAI_Server.exe (已打包, 无需Python)", GREEN)
        else:
            try:
                out = subprocess.check_output(
                    [PYTHON, "--version"],
                    timeout=5, stderr=subprocess.STDOUT,
                    creationflags=0x08000000,
                ).decode("utf-8", errors="replace").strip()
                self._log_msg(f"✓ Python: {out}", GREEN)
            except Exception:
                self._log_msg("✗ 未检测到 Python — 需要安装 Python 或使用打包版本", RED)

        # 2. Check KataGo files
        katago_cuda = os.path.join(BASE_DIR, "katago", "katago.exe")
        katago_cuda2 = _installed_cuda_dest()
        katago_cuda_user = _upgrade_cuda_dest()
        katago_opencl = os.path.join(BASE_DIR, "katago", "katago_opencl.exe")
        katago_cpu = os.path.join(BASE_DIR, "katago", "katago_cpu.exe")
        katago_model = os.path.join(BASE_DIR, "katago", "model.bin.gz")
        katago_model_large_user = _upgrade_model_dest()
        has_cuda_engine = (
            os.path.exists(katago_cuda)
            or os.path.exists(katago_cuda2)
            or os.path.exists(katago_cuda_user)
        )
        has_opencl_engine = os.path.exists(katago_opencl)
        if has_cuda_engine:
            self._log_msg("✓ KataGo 引擎 (CUDA): 已找到", GREEN)
            if _installed_cuda_runtime_ready():
                self._log_msg("  CUDA 运行库: 已就绪", GREEN)
            elif os.path.exists(katago_cuda2):
                self._log_msg("  CUDA 升级文件已存在，但缺少 CUDA/cuDNN 运行库，当前不会启用", GOLD)
            if os.path.exists(katago_cuda2):
                self._log_msg(f"  升级引擎: {katago_cuda2}", MUTED)
            elif os.path.exists(katago_cuda_user):
                self._log_msg(f"  已缓存待激活: {katago_cuda_user}", MUTED)
        if has_opencl_engine:
            self._log_msg("✓ KataGo 引擎 (OpenCL): 已找到 — 支持所有显卡", GREEN)
        if not has_cuda_engine and not has_opencl_engine:
            self._log_msg("⚠ KataGo GPU 引擎: 未找到", GOLD)
        if os.path.exists(katago_cpu):
            self._log_msg("✓ KataGo 引擎 (CPU): 已找到 — 无显卡也可对弈", GREEN)
        else:
            self._log_msg("⚠ KataGo 引擎 (CPU): 未找到 (katago/katago_cpu.exe)", GOLD)
        if os.path.exists(katago_model):
            sz = os.path.getsize(katago_model) / 1024 / 1024
            self._log_msg(f"✓ KataGo 模型: 已找到 ({sz:.0f}MB)", GREEN)
        else:
            self._log_msg("✗ KataGo 模型: 未找到 (katago/model.bin.gz)", RED)
        if os.path.exists(_installed_model_dest()):
            sz = os.path.getsize(_installed_model_dest()) / 1024 / 1024
            self._log_msg(f"✓ 升级大模型: 已激活 ({sz:.0f}MB)", GREEN)
            self._log_msg(f"  升级模型: {_installed_model_dest()}", MUTED)
        elif os.path.exists(katago_model_large_user):
            sz = os.path.getsize(katago_model_large_user) / 1024 / 1024
            self._log_msg(f"✓ 升级大模型: 已缓存 ({sz:.0f}MB)", GREEN)
            self._log_msg(f"  待激活文件: {katago_model_large_user}", MUTED)

        # 3. Check NVIDIA GPU and driver
        gpu_name, gpu_vram, driver_ver = self._detect_nvidia_gpu()
        if gpu_name:
            self._log_msg(f"✓ NVIDIA 显卡: {gpu_name} ({gpu_vram}MB 显存)", GREEN)
            gpu_note = gpu_name if not driver_ver else f"{gpu_name} · 驱动 {driver_ver}"
            self._call_in_ui(lambda note=gpu_note: self._status_hint_var.set(note))

            # Check driver version for CUDA 12 compatibility
            if driver_ver:
                self._log_msg(f"  驱动版本: {driver_ver}", "#58a6ff")
                try:
                    major = int(driver_ver.split(".")[0])
                    if major >= 528:
                        self._log_msg("✓ 驱动版本满足 CUDA 12 要求 (≥527.41)", GREEN)
                    elif major >= 520:
                        self._log_msg("⚠ 驱动版本较旧，建议升级至 ≥527.41 以支持 CUDA 12", GOLD)
                    else:
                        self._log_msg("✗ 驱动版本过旧，需升级至 ≥527.41 以支持 CUDA 12", RED)
                        self._log_msg("  请访问 https://www.nvidia.com/drivers 下载最新驱动", "#58a6ff")
                except ValueError:
                    pass

            # GPU performance tier
            tier, tier_label = self._classify_gpu(gpu_name, gpu_vram)
            tier_colors = {4: GREEN, 3: "#58a6ff", 2: GOLD, 1: RED}
            self._log_msg(f"  显卡性能评级: {tier_label}", tier_colors.get(tier, MUTED))
            tier_tips = {
                4: "所有段位均可流畅运行",
                3: "业余5段及以下流畅, 高段位可能稍慢",
                2: "业余1段及以下流畅, 更高段位推理较慢",
                1: "级位流畅, 段位推理可能较慢, 建议使用Rogue/大招模式",
            }
            self._log_msg(f"  {tier_tips.get(tier, '')}", MUTED)
        else:
            self._log_msg("⚠ 未检测到 NVIDIA 显卡", GOLD)
            if os.path.exists(katago_cpu):
                self._log_msg("  将使用 CPU 引擎运行 (级位对弈流畅，段位较慢)", "#58a6ff")
                self._log_msg("  Rogue/大招模式已优化，CPU 也能流畅运行", GREEN)
                self._call_in_ui(lambda: self._status_hint_var.set("未检测到 NVIDIA 显卡，将优先使用 CPU / OpenCL"))
            else:
                self._log_msg("  未找到 CPU 引擎，可取消勾选 AI 进入纯对弈模式", GOLD)

        # 4. Check CUDA DLLs bundled (only relevant when CUDA engine present)
        if has_cuda_engine:
            cuda_dll = os.path.join(BASE_DIR, "katago", "cudart64_12.dll")
            if os.path.exists(cuda_dll):
                self._log_msg("✓ CUDA 运行库: 已内置 (无需单独安装CUDA)", GREEN)
            else:
                self._log_msg("⚠ CUDA 运行库: 未在 katago/ 中找到", GOLD)

        # 5. Check static files
        idx = os.path.join(BASE_DIR, "static", "index.html")
        if os.path.exists(idx):
            self._log_msg("✓ 前端页面: 已就绪", GREEN)
        else:
            self._log_msg("✗ 前端页面: 未找到 (static/index.html)", RED)

        self._log_msg("━━━ 环境检测完成 ━━━", GOLD)

    def _activate_staged_upgrades(self):
        staged_model = _upgrade_model_dest()
        staged_cuda = _upgrade_cuda_dest()
        installed_model = _installed_model_dest()
        installed_cuda = _installed_cuda_dest()

        if os.path.exists(staged_model) and not os.path.exists(installed_model):
            try:
                _, target = _activate_staged_upgrade(staged_model, installed_model)
                self._log_msg(f"✓ 已激活本地大模型升级包: {target}", GREEN)
            except Exception as exc:
                self._log_msg(
                    "✗ 无法激活大模型升级包，当前安装目录不可写。建议安装到默认位置后重试。",
                    RED,
                )
                self._log_msg(f"  详细错误: {exc}", MUTED)

        if os.path.exists(staged_cuda) and not os.path.exists(installed_cuda):
            self._log_msg(
                "⚠ 检测到旧版 CUDA 升级缓存，需重新下载新版升级包以补齐 DLL 依赖。",
                GOLD,
            )

    @staticmethod
    def _resolve_nvidia_smi():
        candidates = []
        which_path = shutil.which("nvidia-smi")
        if which_path:
            candidates.append(which_path)

        program_w6432 = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
        if program_w6432:
            candidates.append(
                os.path.join(program_w6432, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            )

        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidates.extend(
            [
                os.path.join(system_root, "System32", "nvidia-smi.exe"),
                os.path.join(system_root, "Sysnative", "nvidia-smi.exe"),
            ]
        )

        driver_store = os.path.join(system_root, "System32", "DriverStore", "FileRepository")
        if os.path.isdir(driver_store):
            candidates.extend(
                glob.glob(os.path.join(driver_store, "nv*_amd64*", "nvidia-smi.exe"))
            )

        seen = set()
        for path in candidates:
            if not path:
                continue
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def _normalize_nvidia_driver_version(raw_version: str | None):
        raw = (raw_version or "").strip()
        if not raw:
            return None
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 5:
            tail = digits[-5:]
            return f"{int(tail[:-2])}.{tail[-2:]}"
        return raw

    @classmethod
    def _detect_nvidia_gpu_via_cim(cls):
        commands = [
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                (
                    "$gpu = Get-CimInstance Win32_VideoController | "
                    "Where-Object { $_.Name -match 'NVIDIA' } | "
                    "Select-Object -First 1 Name, AdapterRAM, DriverVersion | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                (
                    "Get-CimInstance Win32_VideoController | "
                    "Where-Object { $_.Name -match 'NVIDIA' } | "
                    "Select-Object -First 1 Name, AdapterRAM, DriverVersion"
                ),
            ],
        ]
        for cmd in commands:
            try:
                out = subprocess.check_output(
                    cmd,
                    timeout=10,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=_creationflags_no_window(),
                ).strip()
            except Exception:
                continue
            if not out:
                continue
            if out.startswith("{"):
                try:
                    data = json.loads(out)
                except json.JSONDecodeError:
                    data = {}
                name = (data.get("Name") or "").strip()
                vram_raw = data.get("AdapterRAM")
                driver = cls._normalize_nvidia_driver_version(data.get("DriverVersion"))
                try:
                    vram = int(vram_raw or 0) // (1024 * 1024)
                except Exception:
                    vram = 0
                if name:
                    return name, max(0, vram), driver
                continue

            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 2 and lines[0].startswith("Name"):
                name = lines[1]
                driver = None
                for line in lines[2:]:
                    if re.match(r"^\d+\.\d+\.\d+\.\d+$", line):
                        driver = cls._normalize_nvidia_driver_version(line)
                        break
                if name:
                    return name, 0, driver
        return None, 0, None

    @staticmethod
    def _detect_nvidia_gpu():
        """Detect NVIDIA GPU reliably on Windows.

        Prefer nvidia-smi when available to get the public driver version and VRAM.
        Fall back to Win32_VideoController when nvidia-smi is missing from PATH.
        """
        smi_path = GoAILauncher._resolve_nvidia_smi()
        if smi_path:
            try:
                out = subprocess.check_output(
                    [
                        smi_path,
                        "--query-gpu=name,memory.total,driver_version",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=10,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=_creationflags_no_window(),
                ).strip()
                if out:
                    parts = out.splitlines()[0].split(",")
                    name = parts[0].strip()
                    vram = int(float(parts[1].strip())) if len(parts) > 1 else 0
                    driver = parts[2].strip() if len(parts) > 2 else None
                    return name, vram, driver
            except Exception:
                pass

        return GoAILauncher._detect_nvidia_gpu_via_cim()

    @staticmethod
    def _classify_gpu(name: str, vram: int):
        """Classify GPU into performance tiers. Returns (tier_number, label)."""
        patterns = [
            (r"RTX\s*50[789]0|RTX\s*5090|RTX\s*4090|RTX\s*4080|RTX\s*3090|A100|H100", 4, "高端旗舰"),
            (r"RTX\s*40[67]0|RTX\s*3080|RTX\s*3070|RTX\s*2080|RTX\s*2070|GTX\s*1080\s*Ti", 4, "高端旗舰"),
            (r"RTX\s*4060|RTX\s*4050|RTX\s*3060|RTX\s*3050|RTX\s*2060", 3, "中高端"),
            (r"GTX\s*1070|GTX\s*1660|GTX\s*1650|GTX\s*1080(?!\s*Ti)", 3, "中高端"),
            (r"GTX\s*1060|GTX\s*1050|GTX\s*980|GTX\s*970", 2, "入门级"),
            (r"GTX\s*950|GTX\s*750|GT\s*1030|GT\s*730|MX", 1, "低端"),
        ]
        for pat, tier, label in patterns:
            if re.search(pat, name, re.IGNORECASE):
                return tier, label
        # Fallback by VRAM
        if vram >= 10000:
            return 4, "高端旗舰"
        if vram >= 6000:
            return 3, "中高端"
        if vram >= 3000:
            return 2, "入门级"
        return 1, "低端"

    @staticmethod
    def _detect_video_controller_names():
        commands = [
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            ["wmic", "path", "win32_VideoController", "get", "name"],
        ]
        for cmd in commands:
            try:
                out = subprocess.check_output(
                    cmd,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
            except Exception:
                continue
            names = []
            for raw in out.splitlines():
                line = raw.strip()
                if not line or line.lower() == "name":
                    continue
                names.append(line)
            if names:
                return names
        return []

    @staticmethod
    def _detect_cpu_name():
        commands = [
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name",
            ],
            ["wmic", "cpu", "get", "name"],
        ]
        for cmd in commands:
            try:
                out = subprocess.check_output(
                    cmd,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
            except Exception:
                continue
            for raw in out.splitlines():
                line = raw.strip()
                if not line or line.lower() == "name":
                    continue
                return line
        return platform.processor() or ""

    @staticmethod
    def _classify_cpu(name: str):
        upper = (name or "").upper()
        if not upper:
            return 2, "未知"
        if re.search(r"CELERON|PENTIUM|ATHLON SILVER|J\d{4}|N[34567]\d{2}|A4-|A6-", upper):
            return 1, "偏弱"
        if re.search(r"I3-|I5-2|I5-3|I7-2|I7-3|FX-|A8-|A10-", upper):
            return 1, "偏弱"
        if re.search(r"I5-4|I5-5|I5-6|I7-4|I7-5|I7-6|RYZEN 3", upper):
            return 2, "一般"
        if re.search(r"I5-7|I5-8|I5-9|I7-7|I7-8|I7-9|RYZEN 5|RYZEN 7", upper):
            return 3, "良好"
        if re.search(r"I7-1\d|I9-|ULTRA 7|ULTRA 9|RYZEN 9", upper):
            return 4, "较强"
        return 2, "一般"

    @staticmethod
    def _has_discrete_gpu(video_names):
        for name in video_names:
            upper = name.upper()
            if re.search(r"NVIDIA.*(RTX|GTX|QUADRO|TESLA)|RADEON\s+RX|RADEON PRO|ARC\s+A", upper):
                return True
        return False

    @staticmethod
    def _is_integrated_only(video_names):
        if not video_names:
            return True
        return not GoAILauncher._has_discrete_gpu(video_names)

    def _get_upgrade_policy(self):
        gpu_name, gpu_vram, driver_ver = self._detect_nvidia_gpu()
        video_names = self._detect_video_controller_names()
        cpu_name = self._detect_cpu_name()
        cpu_tier, cpu_label = self._classify_cpu(cpu_name)
        has_discrete_gpu = self._has_discrete_gpu(video_names)
        integrated_only = self._is_integrated_only(video_names)

        if integrated_only:
            return {
                "allowed": False,
                "reason": "当前设备主要为核显环境。为了保证对弈稳定性，性能升级包已暂时关闭。",
                "detail": f"显卡: {', '.join(video_names) or '未识别'}；CPU: {cpu_name or '未识别'} ({cpu_label})",
            }
        if cpu_tier <= 1:
            return {
                "allowed": False,
                "reason": "当前设备整体性能偏弱。为了避免升级后更慢或出现启动问题，性能升级包已暂时关闭。",
                "detail": f"CPU: {cpu_name or '未识别'} ({cpu_label})",
            }
        if gpu_name and driver_ver:
            return {
                "allowed": True,
                "reason": "",
                "detail": f"NVIDIA {gpu_name} / 驱动 {driver_ver}",
            }
        if has_discrete_gpu:
            return {
                "allowed": True,
                "reason": "",
                "detail": f"显卡: {', '.join(video_names)}；CPU: {cpu_name or '未识别'} ({cpu_label})",
            }
        return {
            "allowed": False,
            "reason": "当前设备暂不建议安装性能升级包，继续使用默认轻量模式会更稳妥。",
            "detail": f"显卡: {', '.join(video_names) or '未识别'}；CPU: {cpu_name or '未识别'} ({cpu_label})",
        }

    def _apply_upgrade_button_policy(self):
        policy = self._get_upgrade_policy()
        self._upgrade_policy = policy
        if policy["allowed"]:
            self._apply_button_style(self._upgrade_btn, "primary", text="性能升级包", state="normal")
            self._upgrade_btn.config(cursor="hand2")
        else:
            self._apply_button_style(self._upgrade_btn, "disabled", text="升级不可用", state="disabled")
            self._upgrade_btn.config(cursor="arrow")

    def _set_status(self, running: bool, text: str, summary_text: str | None = None):
        def _do():
            self._server_active = running
            self._dot_canvas.itemconfig(self._dot, fill=GREEN if running else RED)
            self._status_var.set(text)
            self._mode_var.set(summary_text or text)
            self._start_btn.config(state="disabled" if running else "normal")
            self._stop_btn.config(state="normal" if running else "disabled")
            self._open_btn.config(state="normal" if running else "disabled")
        self._call_in_ui(_do)
        self._refresh_network_fields(running=running)
        self._sync_ai_toggle_button()

    def _refresh_model_btn_state(self):
        """Query server for actual KataGo status and update button accordingly."""
        def _query():
            try:
                status = self._fetch_status(timeout=3)
                katago_ready = status and status.get("katago_ready", False)
                phase = status.get("engine_phase") if status else None
                self._engine_phase = phase or "idle"
                self._model_running = katago_ready
                self._sync_ai_toggle_button()
            except Exception:
                pass
        threading.Thread(target=_query, daemon=True).start()

    def _call_in_ui(self, func):
        if threading.current_thread() is threading.main_thread():
            func()
        else:
            self._ui_queue.put(func)

    def _frontend_url(self) -> str:
        return f"{SERVER_URL}/?{urlencode({'rev': EXPECTED_SERVER_REV, 'ts': int(time.time())})}"

    def _wait_frontend_ready(self, timeout=12.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self._fetch_status(timeout=2)
            if status and status.get("server_rev") == EXPECTED_SERVER_REV and status.get("static_ready"):
                try:
                    with urllib.request.urlopen(self._frontend_url(), timeout=4) as resp:
                        content = resp.read().decode("utf-8", errors="replace")
                    if "board-canvas" in content and "main-layout" in content:
                        return True
                except Exception:
                    pass
            time.sleep(0.5)
        return False

    def _open_browser(self):
        threading.Thread(target=lambda: webbrowser.open(self._frontend_url()), daemon=True).start()

    def _drain_ui_queue(self):
        while True:
            try:
                func = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func()
            except Exception:
                pass
        try:
            self.root.after(50, self._drain_ui_queue)
        except Exception:
            pass

    @staticmethod
    def _port_open(port=SERVER_PORT, timeout=1.0) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _fetch_status(timeout=1.5):
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/status", timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError, OSError):
            return None

    @staticmethod
    def _listener_pids(port=SERVER_PORT):
        try:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception:
            return []

        pids = []
        needle = f":{port}"
        for line in out.splitlines():
            line = line.strip()
            if not line.startswith("TCP"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            if parts[1].endswith(needle) and parts[3].upper() == "LISTENING":
                try:
                    pids.append(int(parts[4]))
                except ValueError:
                    pass
        return sorted(set(pids))

    @staticmethod
    def _pid_image_name(pid: int) -> str:
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            ).strip()
        except Exception:
            return ""
        if not out or out.startswith("INFO:"):
            return ""
        try:
            return next(iter(csv.reader([out])))[0].lower()
        except Exception:
            return ""

    def _stop_stale_server_on_port(self, port=SERVER_PORT) -> bool:
        stopped_any = False
        for pid in self._listener_pids(port):
            if self.server_proc and pid == self.server_proc.pid:
                continue
            image_name = self._pid_image_name(pid)
            if not (
                image_name.startswith("python")
                or image_name in {"goai.exe", "goai_server.exe"}
            ):
                continue
            try:
                subprocess.check_call(
                    ["taskkill", "/PID", str(pid), "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                stopped_any = True
                self._log_msg(f"已停止旧服务进程 PID {pid}", GOLD)
            except Exception:
                # Permission denied — retry with elevated privileges
                try:
                    subprocess.check_call(
                        ["powershell", "-NoProfile", "-Command",
                         f"Start-Process taskkill -ArgumentList '/PID','{pid}','/F' -Verb RunAs -Wait"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                    stopped_any = True
                    self._log_msg(f"已停止旧服务进程 PID {pid}（管理员权限）", GOLD)
                except Exception as e2:
                    self._log_msg(f"停止旧服务失败 PID {pid}: {e2}", RED)
        return stopped_any

    def _process_status_payload(self, status, emit_log=True):
        if not status:
            return

        host = status.get("host") or LOOPBACK_HOST
        self._active_server_host = host
        phase = status.get("engine_phase") or ("ready" if status.get("katago_ready") else "idle")
        backend = status.get("engine_backend")
        model = status.get("engine_model")
        message = status.get("engine_message") or ""
        last_error = status.get("engine_last_error") or ""
        signature = (phase, backend, model, message, last_error)

        if phase == "ready":
            self._engine_phase = "ready"
            self._set_status(True, "服务器运行中", "运行中")
            self._model_running = True
        elif phase == "initializing":
            self._engine_phase = "initializing"
            self._set_status(True, "服务器启动中", "启动中")
            self._model_running = False
        elif phase in {"failed", "stopped"} or status.get("no_katago"):
            self._engine_phase = phase or "stopped"
            self._set_status(True, "服务器运行中", "运行中")
            self._model_running = False
        else:
            self._engine_phase = phase or "idle"
            self._set_status(True, "服务器运行中", "运行中")

        local_urls = (status.get("access_urls") or {}).get("local") or [SERVER_URL]
        lan_urls = (status.get("access_urls") or {}).get("lan") or []
        self._refresh_network_fields(
            local_url=local_urls[0],
            lan_url=lan_urls[0] if lan_urls else None,
            running=True,
            host=host,
        )

        if emit_log and signature != self._last_engine_signature:
            if phase == "initializing":
                if "opencl" in (backend or "").lower() or "opencl" in message.lower() or "tuning" in message.lower():
                    self._log_msg("正在初始化 OpenCL，首次启动可能较慢，请稍候", GOLD)
                elif message:
                    self._log_msg(message, GOLD)
            elif phase == "ready":
                ready_msg = f"KataGo 已就绪: {backend or '引擎'}"
                if model:
                    ready_msg += f" / {model}"
                self._log_msg(ready_msg, GREEN)
            elif phase == "failed":
                self._log_msg("KataGo 启动失败，已回退为纯对弈模式", RED)
                if last_error:
                    self._log_msg(last_error, RED)
            elif phase == "stopped":
                self._log_msg("KataGo 已停止，当前为纯对弈模式", GOLD)
            self._last_engine_signature = signature

        self._sync_ai_toggle_button()

    def _start_status_monitor(self):
        self._status_monitor_stop.set()
        self._status_monitor_stop = threading.Event()

        def _monitor():
            while not self._status_monitor_stop.is_set():
                status = self._fetch_status(timeout=2)
                if status and status.get("server_rev") == EXPECTED_SERVER_REV:
                    self._process_status_payload(status, emit_log=True)
                elif self.server_proc and self.server_proc.poll() is not None:
                    break
                time.sleep(1.0)

        threading.Thread(target=_monitor, daemon=True).start()

    def _pump_server_output(self):
        if not self.server_proc or not self.server_proc.stdout:
            return
        for raw in self.server_proc.stdout:
            line = raw.rstrip()
            if not line:
                continue
            lower = line.lower()
            if "traceback" in lower or "error" in lower or "exception" in lower:
                color = RED
            elif "opencl" in lower or "initializ" in lower or "tuning" in lower:
                color = GOLD
            elif "ready" in lower or "started" in lower:
                color = GREEN
            else:
                color = "#aaa"
            self._log_msg(line, color)

        if self.server_proc and self.server_proc.poll() is not None:
            self._status_monitor_stop.set()
            self._active_server_host = LOOPBACK_HOST
            self._set_status(False, "服务器已停止", "未启动")
            self._log_msg(f"服务器进程已结束 (code={self.server_proc.returncode})", MUTED)

    def _log_failure_tail(self, prefix: str):
        self._log_msg(prefix, RED)
        for line in list(self._server_log_tail)[-10:]:
            if line == prefix:
                continue
            self._log_msg(line, "#aaa")

    def _start_server(self):
        if self._running:
            return
        self._running = True
        self._engine_phase = "booting"
        ai_enabled = bool(self._ai_enabled.get())
        desired_host = self._desired_bind_host()
        mode_label = "局域网共享" if desired_host == LAN_HOST else "仅本机访问"
        self._set_status(False, "服务器启动中…", "启动中")
        self._sync_lan_button()
        self._log_msg(f"正在启动 GoAI 服务器（{mode_label}）", GOLD)

        def _run():
            status = self._fetch_status()
            if (
                status
                and status.get("server_rev") == EXPECTED_SERVER_REV
                and (status.get("host") or LOOPBACK_HOST) == desired_host
            ):
                self._log_msg("检测到新版本服务已在运行，直接连接", GREEN)
                self._process_status_payload(status, emit_log=True)
                self._start_status_monitor()
                if self._wait_frontend_ready():
                    self._open_browser()
                else:
                    self._log_msg("服务已运行，但页面尚未确认就绪，可点击“打开页面”重试", GOLD)
                self._running = False
                self._sync_lan_button()
                return
            if status and status.get("server_rev") == EXPECTED_SERVER_REV:
                self._log_msg("检测到现有服务的访问模式与当前设置不同，准备重启", GOLD)

            if self._port_open(SERVER_PORT, 0.5):
                self._log_msg(f"检测到 {SERVER_PORT} 端口已被占用，尝试替换旧服务", GOLD)
                self._stop_stale_server_on_port(SERVER_PORT)
                time.sleep(1.0)

            if USE_SERVER_EXE:
                cmd = [_SERVER_EXE]
            else:
                cmd = [PYTHON, SERVER_SCRIPT]
            cmd.extend(["--host", desired_host])
            if not ai_enabled:
                cmd.append("--no-katago")
            try:
                try:
                    self.server_proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=BASE_DIR,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        creationflags=_server_creationflags(),
                        startupinfo=_server_startupinfo(),
                    )
                except OSError:
                    self.server_proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=BASE_DIR,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        creationflags=_creationflags_no_window(),
                        startupinfo=_server_startupinfo(),
                    )
            except Exception as e:
                self._log_msg(f"启动失败: {e}", RED)
                self._running = False
                self._engine_phase = "idle"
                self._active_server_host = LOOPBACK_HOST
                self._set_status(False, "启动失败", "未启动")
                self._sync_lan_button()
                return

            threading.Thread(target=self._pump_server_output, daemon=True).start()

            ready = False
            for _ in range(240):
                if self.server_proc.poll() is not None:
                    self._log_failure_tail(
                        f"服务器进程已退出 (code={self.server_proc.returncode})"
                    )
                    break
                status = self._fetch_status()
                if status and status.get("server_rev") == EXPECTED_SERVER_REV:
                    ready = True
                    self._process_status_payload(status, emit_log=True)
                    break
                time.sleep(0.5)

            if ready:
                self._log_msg("HTTP 服务已就绪，自动打开浏览器", GREEN)
                self._start_status_monitor()
                if self._wait_frontend_ready():
                    self._open_browser()
                else:
                    self._log_msg("HTTP 已启动，但页面尚未确认就绪，可点击“打开页面”重试", GOLD)
            else:
                if self.server_proc.poll() is None:
                    self._log_failure_tail(f"服务器未能在预期时间内监听 {SERVER_PORT} 端口")
                else:
                    self._log_msg("服务器启动失败，请查看上方日志", RED)
                self._active_server_host = LOOPBACK_HOST
                self._set_status(False, "启动失败", "未启动")
                self._engine_phase = "idle"
                self._running = False
                self._sync_lan_button()
                return

            self._running = False
            self._sync_ai_toggle_button()
            self._sync_lan_button()

        threading.Thread(target=_run, daemon=True).start()

    def _stop_server(self):
        self._status_monitor_stop.set()
        stopped_external = False
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=5)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None
        elif self._port_open(SERVER_PORT, 0.5):
            stopped_external = self._stop_stale_server_on_port(SERVER_PORT)
        self._running = False
        self._server_active = False
        self._active_server_host = LOOPBACK_HOST
        self._engine_phase = "idle"
        self._model_running = False
        self._set_status(False, "服务器已停止", "未启动")
        self._log_msg("已停止服务器" if stopped_external or not self._port_open(SERVER_PORT, 0.5) else "服务器停止请求已发送", GOLD)

    def _toggle_model(self):
        """Toggle the KataGo engine on/off via the server's API."""
        self._apply_button_style(self._stop_model_btn, "disabled", state="disabled")

        if self._model_running:
            # ── Stop model ──
            def _do_stop():
                try:
                    req = urllib.request.Request(
                        f"{SERVER_URL}/stop_katago", method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                    if result.get("ok"):
                        self._model_running = False
                        self._log_msg("已关闭 KataGo 模型，仅支持双人对局", GOLD)
                        self._call_in_ui(lambda: (
                            self._apply_button_style(self._stop_model_btn, "success", text="启动 AI", state="normal"),
                        ))
                    else:
                        self._log_msg(f"关闭模型失败: {result.get('error', '未知错误')}", RED)
                        self._call_in_ui(
                            lambda: self._apply_button_style(
                                self._stop_model_btn,
                                "plum" if self._model_running else "success",
                                state="normal",
                            )
                        )
                except Exception as e:
                    self._log_msg(f"关闭模型请求失败: {e}", RED)
                    self._call_in_ui(
                        lambda: self._apply_button_style(
                            self._stop_model_btn,
                            "plum" if self._model_running else "success",
                            state="normal",
                        )
                    )
            threading.Thread(target=_do_stop, daemon=True).start()
        else:
            # ── Start model ──
            def _do_start():
                self._log_msg("正在启动 KataGo 模型…", GOLD)
                try:
                    req = urllib.request.Request(
                        f"{SERVER_URL}/restart_katago", method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                    if result.get("ok"):
                        self._model_running = True
                        self._log_msg("KataGo 模型已启动", GREEN)
                        self._call_in_ui(lambda: (
                            self._apply_button_style(self._stop_model_btn, "plum", text="关闭 AI", state="normal"),
                        ))
                    else:
                        self._log_msg(f"启动模型失败: {result.get('error', '未知错误')}", RED)
                        self._call_in_ui(
                            lambda: self._apply_button_style(
                                self._stop_model_btn,
                                "success" if not self._model_running else "plum",
                                state="normal",
                            )
                        )
                except Exception as e:
                    self._log_msg(f"启动模型请求失败: {e}", RED)
                    self._call_in_ui(
                        lambda: self._apply_button_style(
                            self._stop_model_btn,
                            "success" if not self._model_running else "plum",
                            state="normal",
                        )
                    )
            threading.Thread(target=_do_start, daemon=True).start()

    def _check_katago_update(self):
        """Check GitHub for the latest KataGo release and offer to update."""
        self._log_msg("引擎更新入口已禁用，当前版本优先保证兼容性与稳定性。", GOLD)
        return
        if self._update_btn:
            self._update_btn.config(state="disabled")
        self._log_msg("正在检查 KataGo 更新…", GOLD)

        def _do():
            try:
                api_url = f"https://api.github.com/repos/{KATAGO_REPO}/releases/latest"
                req = urllib.request.Request(api_url, headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GoAI-Launcher",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    release = json.loads(resp.read().decode("utf-8"))

                tag = release.get("tag_name", "")
                name = release.get("name", tag)
                self._log_msg(f"最新版本: {name}", GREEN)

                # Find CUDA Windows x64 asset
                asset_url = None
                asset_name = None
                for asset in release.get("assets", []):
                    aname = asset.get("name", "").lower()
                    if ("cuda" in aname and "windows" in aname
                            and "x64" in aname and aname.endswith(".zip")):
                        asset_url = asset.get("browser_download_url")
                        asset_name = asset.get("name")
                        break

                # Fallback: look for opencl windows build
                if not asset_url:
                    for asset in release.get("assets", []):
                        aname = asset.get("name", "").lower()
                        if ("opencl" in aname and "windows" in aname
                                and aname.endswith(".zip")):
                            asset_url = asset.get("browser_download_url")
                            asset_name = asset.get("name")
                            break

                if not asset_url:
                    self._log_msg("未找到适用的 Windows CUDA/OpenCL 版本", RED)
                    self._call_in_ui(lambda: self._update_btn and self._update_btn.config(state="normal"))
                    return

                # Detect current version
                katago_exe = os.path.join(BASE_DIR, "katago", "katago.exe")
                current_ver = ""
                if os.path.exists(katago_exe):
                    try:
                        out = subprocess.check_output(
                            [katago_exe, "version"],
                            text=True, timeout=5, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW
                            if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                        ).strip()
                        current_ver = out
                    except Exception:
                        current_ver = "未知"

                self._log_msg(f"当前版本: {current_ver or '未安装'}", "#aaa")
                self._log_msg(f"可下载: {asset_name}", "#aaa")

                # Ask user to confirm
                def _ask():
                    ok = messagebox.askyesno(
                        "KataGo 更新",
                        f"发现新版本 KataGo:\n\n"
                        f"当前: {current_ver or '未安装'}\n"
                        f"最新: {name}\n"
                        f"文件: {asset_name}\n\n"
                        f"是否下载并更新？\n"
                        f"（更新前请先停止服务器）",
                        parent=self.root,
                    )
                    if ok:
                        threading.Thread(
                            target=self._download_katago_update,
                            args=(asset_url, asset_name, tag),
                            daemon=True,
                        ).start()
                    else:
                        if self._update_btn:
                            self._update_btn.config(state="normal")

                self._call_in_ui(_ask)

            except Exception as e:
                self._log_msg(f"检查更新失败: {e}", RED)
                self._call_in_ui(lambda: self._update_btn and self._update_btn.config(state="normal"))

        threading.Thread(target=_do, daemon=True).start()

    def _download_katago_update(self, url: str, filename: str, tag: str):
        """Download and install a KataGo update (exe + all DLLs together)."""
        katago_dir = os.path.join(BASE_DIR, "katago")
        backup_dir = os.path.join(BASE_DIR, "katago_backup")

        try:
            # ── Step 1: Download ──
            self._log_msg(f"正在下载 {filename}…", GOLD)
            req = urllib.request.Request(url, headers={"User-Agent": "GoAI-Launcher"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunks = []
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        self._call_in_ui(
                            lambda p=pct: self._status_var.set(f"下载中… {p}%")
                        )

            data = b"".join(chunks)
            mb = len(data) / 1024 / 1024
            self._log_msg(f"下载完成 ({mb:.1f} MB)", GREEN)

            # ── Step 2: Backup model + config (they're large / user-specific) ──
            preserve = {}  # basename -> bytes
            for keep_name in ("model.bin.gz", "config.cfg", "default_gtp.cfg"):
                keep_path = os.path.join(katago_dir, keep_name)
                if os.path.exists(keep_path):
                    preserve[keep_name] = keep_path  # just remember path

            # Backup entire katago dir
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir, ignore_errors=True)
            self._log_msg("正在备份旧版本…", GOLD)
            shutil.copytree(katago_dir, backup_dir)

            # ── Step 3: Extract ALL files from zip (exe + DLLs + configs) ──
            self._log_msg("正在解压更新…", GOLD)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Find the subdirectory prefix in the zip (e.g. "katago-v1.16.5-cuda12-...")
                entries = zf.namelist()
                exe_entry = None
                for entry in entries:
                    if os.path.basename(entry).lower() == "katago.exe":
                        exe_entry = entry
                        break

                if not exe_entry:
                    self._log_msg("ZIP 中未找到 katago.exe，更新取消", RED)
                    return

                # Remove old exe and DLLs (but keep model/config)
                for f in os.listdir(katago_dir):
                    fp = os.path.join(katago_dir, f)
                    if f.lower().endswith((".exe", ".dll", ".exe.bak", ".exe.new")):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass

                # Extract all files from zip into katago dir
                extracted = 0
                for entry in entries:
                    basename = os.path.basename(entry)
                    if not basename:
                        continue  # skip directories
                    # Only extract exe, dll, and cfg files
                    ext = basename.lower().rsplit(".", 1)[-1] if "." in basename else ""
                    if ext not in ("exe", "dll", "cfg", "txt"):
                        continue
                    # Don't overwrite our preserved model/config
                    if basename in preserve:
                        continue
                    dst_path = os.path.join(katago_dir, basename)
                    with zf.open(entry) as src, open(dst_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted += 1

                self._log_msg(f"已更新 {extracted} 个文件", GREEN)

            # ── Step 4: Verify new exe works ──
            self._log_msg("正在验证新版本…", GOLD)
            try:
                out = subprocess.check_output(
                    [os.path.join(katago_dir, "katago.exe"), "version"],
                    text=True, timeout=10, stderr=subprocess.STDOUT,
                    cwd=katago_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                ).strip()
                self._log_msg(f"新版本验证通过: {out}", GREEN)
            except Exception as e:
                self._log_msg(f"新版本验证失败: {e}", RED)
                self._log_msg("正在恢复旧版本…", GOLD)
                # Restore from backup
                shutil.rmtree(katago_dir, ignore_errors=True)
                shutil.copytree(backup_dir, katago_dir)
                self._log_msg("已恢复旧版本", GOLD)
                return

            self._log_msg(f"KataGo 已更新到 {tag}，请重新启动服务器", GREEN)
            self._call_in_ui(lambda: self._status_var.set(f"已更新到 {tag}"))

        except Exception as e:
            self._log_msg(f"更新失败: {e}", RED)
            # Restore from backup
            if os.path.exists(backup_dir) and os.path.exists(katago_dir):
                try:
                    shutil.rmtree(katago_dir, ignore_errors=True)
                    shutil.copytree(backup_dir, katago_dir)
                    self._log_msg("已恢复旧版本", GOLD)
                except Exception:
                    self._log_msg("恢复失败，请手动从 katago_backup 目录恢复", RED)
        finally:
            self._call_in_ui(lambda: self._update_btn and self._update_btn.config(state="normal"))

    # ── Performance Upgrade ─────────────────────────────────────────────────
    LARGE_MODEL_INDEX_URL = "https://katagotraining.org/networks/"
    LARGE_MODEL_SIZE_MB = 256  # approximate
    CUDA_KATAGO_URL_PATTERN = (
        "https://github.com/lightvector/KataGo/releases/download/v1.16.4/"
        "katago-v1.16.4-cuda12.5-cudnn8.9.7-windows-x64.zip"
    )

    def _show_upgrade_dialog(self):
        """Show upgrade options dialog."""
        policy = getattr(self, "_upgrade_policy", None) or self._get_upgrade_policy()
        self._upgrade_policy = policy
        if not policy.get("allowed"):
            messagebox.showinfo(
                "性能升级包",
                f"{policy['reason']}\n\n{policy['detail']}\n\n如果只是想稳定对弈，继续使用当前默认轻量版即可。",
                parent=self.root,
            )
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("性能升级包")
        dlg.geometry("480x380")
        dlg.resizable(False, False)
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.grab_set()

        ico = os.path.join(BASE_DIR, "goai.ico")
        if os.path.exists(ico):
            try:
                dlg.iconbitmap(ico)
            except Exception:
                pass

        tk.Label(dlg, text="⬆ 性能升级包", font=("Microsoft YaHei", 14, "bold"),
                 fg=GOLD, bg=BG).pack(pady=(20, 5))
        tk.Label(dlg, text="下载更强的模型和引擎，大幅提升 AI 棋力",
                 font=("Microsoft YaHei", 9), fg=MUTED, bg=BG).pack(pady=(0, 15))

        # Options frame
        opt_frame = tk.Frame(dlg, bg=BG2, padx=15, pady=15)
        opt_frame.pack(fill="x", padx=20)

        # Option 1: Large model
        self._upgrade_model_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opt_frame,
            text="大尺寸模型 (b28c512, ~256MB下载)",
            variable=self._upgrade_model_var,
            font=("Microsoft YaHei", 10), fg=TEXT, bg=BG2,
            activeforeground=TEXT, activebackground=BG2, selectcolor=BG3,
        ).pack(anchor="w", pady=2)
        tk.Label(opt_frame,
                 text="   棋力从业余高段提升至职业水平，OpenCL/CUDA 通用",
                 font=("Microsoft YaHei", 8), fg=MUTED, bg=BG2).pack(anchor="w")

        # Option 2: CUDA engine
        has_nvidia, _, driver_ver = self._detect_nvidia_gpu()
        cuda_ok = False
        if has_nvidia and driver_ver:
            try:
                cuda_ok = int(driver_ver.split(".")[0]) >= 528
            except ValueError:
                pass

        self._upgrade_cuda_var = tk.BooleanVar(value=cuda_ok)
        cuda_chk = tk.Checkbutton(
            opt_frame,
            text="CUDA 引擎 (仅 NVIDIA 显卡, ~5MB下载)",
            variable=self._upgrade_cuda_var,
            font=("Microsoft YaHei", 10), fg=TEXT, bg=BG2,
            activeforeground=TEXT, activebackground=BG2, selectcolor=BG3,
        )
        cuda_chk.pack(anchor="w", pady=(10, 2))
        if not has_nvidia:
            cuda_chk.config(state="disabled")
            self._upgrade_cuda_var.set(False)
            cuda_hint = "   未检测到 NVIDIA 显卡，无法使用 CUDA"
        elif not cuda_ok:
            cuda_hint = f"   驱动 {driver_ver}，建议更新至 ≥528 以支持 CUDA 12"
        else:
            cuda_hint = f"   检测到 {has_nvidia}，驱动 {driver_ver} ✓"
        tk.Label(opt_frame, text=cuda_hint,
                 font=("Microsoft YaHei", 8), fg=MUTED, bg=BG2).pack(anchor="w")

        # Note
        tk.Label(dlg,
                 text="注: 下载需联网，大模型约需 1~3 分钟 (取决于网速)",
                 font=("Microsoft YaHei", 8), fg=MUTED, bg=BG).pack(pady=(15, 5))

        # Buttons
        btn_frame = tk.Frame(dlg, bg=BG)
        btn_frame.pack(pady=10)
        tk.Button(
            btn_frame, text="开始下载", width=12,
            font=("Microsoft YaHei", 10, "bold"),
            fg="#000", bg=GOLD, activeforeground="#000", activebackground="#E5C040",
            relief="flat", borderwidth=0, cursor="hand2", pady=6,
            command=lambda: self._start_upgrade(dlg)
        ).pack(side="left", padx=10)
        tk.Button(
            btn_frame, text="取消", width=8,
            font=("Microsoft YaHei", 10),
            fg=TEXT, bg=BG3, activeforeground=TEXT, activebackground="#3D3D3D",
            relief="flat", borderwidth=0, cursor="hand2", pady=6,
            command=dlg.destroy
        ).pack(side="left", padx=10)

    def _start_upgrade(self, dlg):
        policy = getattr(self, "_upgrade_policy", None) or self._get_upgrade_policy()
        self._upgrade_policy = policy
        if not policy.get("allowed"):
            dlg.destroy()
            messagebox.showinfo(
                "性能升级包",
                f"{policy['reason']}\n\n{policy['detail']}",
                parent=self.root,
            )
            self._apply_upgrade_button_policy()
            return
        dlg.destroy()
        want_model = self._upgrade_model_var.get()
        want_cuda = self._upgrade_cuda_var.get()
        if not want_model and not want_cuda:
            return
        self._apply_button_style(self._upgrade_btn, "disabled", text="下载中...", state="disabled")
        threading.Thread(
            target=self._upgrade_worker,
            args=(want_model, want_cuda),
            daemon=True,
        ).start()

    def _upgrade_worker(self, want_model, want_cuda):
        staged_dir = _ensure_user_katago_dir()
        success = True

        if want_model:
            staged_dest = _upgrade_model_dest()
            install_dest = _installed_model_dest()
            if os.path.exists(install_dest):
                self._log_msg("大模型已存在，跳过下载", GOLD)
            else:
                self._log_msg(f"正在下载大模型 (~{self.LARGE_MODEL_SIZE_MB}MB)...", GOLD)
                try:
                    model_url = self._resolve_large_model_url()
                    self._log_msg(
                        f"  官方模型源: {os.path.basename(model_url)}",
                        MUTED,
                    )
                    self._download_with_progress(
                        model_url,
                        staged_dest + ".tmp",
                        referer=self.LARGE_MODEL_INDEX_URL,
                    )
                    _activate_staged_upgrade(staged_dest + ".tmp", install_dest)
                    if os.path.exists(staged_dest + ".tmp"):
                        os.remove(staged_dest + ".tmp")
                    sz = os.path.getsize(install_dest) / 1024 / 1024
                    self._log_msg(f"✓ 大模型下载完成 ({sz:.0f}MB)", GREEN)
                    self._log_msg(f"  已安装到: {install_dest}", MUTED)
                except Exception as e:
                    self._log_msg(f"✗ 大模型下载失败: {e}", RED)
                    if os.path.exists(staged_dest + ".tmp"):
                        os.remove(staged_dest + ".tmp")
                    self._log_msg("  若当前目录不可写，请重新安装到默认位置后再升级", MUTED)
                    success = False

        if want_cuda:
            staged_exe = _upgrade_cuda_dest()
            install_exe = _installed_cuda_dest()
            if os.path.exists(install_exe) and _installed_cuda_runtime_ready():
                self._log_msg("CUDA 引擎已存在，跳过下载", GOLD)
            else:
                self._log_msg("正在下载 CUDA 引擎...", GOLD)
                try:
                    cuda_url, asset_name = self._resolve_cuda_engine_url()
                    self._log_msg(f"  官方引擎源: {asset_name}", MUTED)
                    zip_path = os.path.join(staged_dir, "cuda_tmp.zip")
                    self._download_with_progress(cuda_url, zip_path)

                    import zipfile
                    with zipfile.ZipFile(zip_path) as zf:
                        names = [os.path.basename(name) for name in zf.namelist() if os.path.basename(name)]
                        lower_names = {name.lower() for name in names}
                        bundle_has_runtime = (
                            "cublas64_12.dll" in lower_names
                            and "cudart64_12.dll" in lower_names
                            and any(name.startswith("cudnn64_") for name in lower_names)
                        )
                        local_has_runtime = _installed_cuda_runtime_ready()
                        if not bundle_has_runtime and not local_has_runtime:
                            os.remove(zip_path)
                            self._log_msg("✗ CUDA 升级包不可用：官方压缩包未包含 CUDA/cuDNN 运行库", RED)
                            self._log_msg("  当前轻量版会继续使用 OpenCL/CPU；若要启用 CUDA，需要单独提供完整运行库包", MUTED)
                            success = False
                            raise RuntimeError("官方 CUDA 压缩包缺少运行库，已取消安装")

                        extracted_files = []
                        for name in zf.namelist():
                            base_name = os.path.basename(name)
                            if not base_name:
                                continue
                            lower = base_name.lower()
                            if lower == "katago.exe":
                                target_path = install_exe
                            elif lower.endswith(".dll") and (
                                lower.startswith("cublas")
                                or lower.startswith("cudart")
                                or lower.startswith("cudnn")
                                or lower.startswith("nvblas")
                            ):
                                target_path = os.path.join(BASE_DIR, "katago", base_name)
                            else:
                                continue
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, "wb") as f:
                                f.write(zf.read(name))
                            extracted_files.append(os.path.basename(target_path))

                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                    if os.path.exists(install_exe) and _installed_cuda_runtime_ready():
                        self._log_msg("✓ CUDA 引擎下载完成", GREEN)
                        self._log_msg(
                            f"  已安装 {len(extracted_files)} 个 CUDA 运行文件到: {os.path.join(BASE_DIR, 'katago')}",
                            "#58a6ff")
                    else:
                        self._log_msg("✗ 未在压缩包中找到 katago.exe", RED)
                        success = False
                except Exception as e:
                    if "官方 CUDA 压缩包缺少运行库" not in str(e):
                        self._log_msg(f"✗ CUDA 引擎下载失败: {e}", RED)
                        self._log_msg("  若当前目录不可写，请重新安装到默认位置后再升级", MUTED)
                        success = False

        if success:
            self._log_msg("━━━ 升级完成！重启服务后生效 ━━━", GOLD)
        fully_installed = _upgrade_installed()
        self._call_in_ui(
            lambda: self._apply_button_style(
                self._upgrade_btn,
                "disabled" if fully_installed else "primary",
                text="✓ 已安装升级包" if fully_installed else "性能升级包",
                state="disabled" if fully_installed else "normal",
            )
        )
        if success:
            self._log_msg(f"升级文件已安装到 {os.path.join(BASE_DIR, 'katago')}", MUTED)

    def _resolve_large_model_url(self):
        req = urllib.request.Request(
            self.LARGE_MODEL_INDEX_URL,
            headers={"User-Agent": "GoAI/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "ignore")
        matches = re.findall(
            r"https://media\.katagotraining\.org/uploaded/networks/models/"
            r"kata1/[^\"']*b28c512[^\"']*\.bin\.gz",
            html,
            flags=re.IGNORECASE,
        )
        if not matches:
            raise RuntimeError("未能从官方页面解析到大模型下载链接")
        matches = sorted(set(matches), reverse=True)
        return matches[0]

    def _resolve_cuda_engine_url(self):
        try:
            api_url = f"https://api.github.com/repos/{KATAGO_REPO}/releases/latest"
            req = urllib.request.Request(
                api_url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "GoAI-Launcher",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                release = json.loads(resp.read().decode("utf-8"))
            candidates = []
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                lower = name.lower()
                if (
                    "cuda" in lower
                    and "windows" in lower
                    and "x64" in lower
                    and lower.endswith(".zip")
                ):
                    version_score = 0
                    match = re.search(r"cuda(\d+)\.(\d+)", lower)
                    if match:
                        version_score = int(match.group(1)) * 100 + int(match.group(2))
                    bs50_penalty = 1 if "+bs50" in lower else 0
                    candidates.append((bs50_penalty, -version_score, name, asset.get("browser_download_url")))
            if candidates:
                candidates.sort()
                _, _, name, url = candidates[0]
                return url, name
        except Exception as exc:
            self._log_msg(f"  获取最新 CUDA 引擎链接失败，改用内置备用链接: {exc}", GOLD)
        return self.CUDA_KATAGO_URL_PATTERN, os.path.basename(self.CUDA_KATAGO_URL_PATTERN)

    def _download_with_progress(self, url, dest, referer=None):
        """Download a file with progress logging."""
        headers = {"User-Agent": "GoAI/1.0"}
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            total_mb = total / 1024 / 1024 if total else 0
            downloaded = 0
            last_pct = -1
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded * 100 / total)
                        if pct >= last_pct + 10:  # log every 10%
                            last_pct = pct
                            dl_mb = downloaded / 1024 / 1024
                            self._log_msg(
                                f"  下载进度: {dl_mb:.0f}/{total_mb:.0f}MB ({pct}%)",
                                MUTED)

    def _on_close(self):
        self._stop_server()
        self.root.destroy()

    def run(self):
        self._log_msg("GoAI 启动器就绪，点击“启动”开始", GOLD)
        self.root.mainloop()


if __name__ == "__main__":
    app = GoAILauncher()
    app.run()
