from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from collections.abc import Callable
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
import sys

import launcher


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


@contextmanager
def patched(**replacements: Callable[..., Any]):
    originals = {name: getattr(launcher, name) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(launcher, name, value)
        yield
    finally:
        for name, value in originals.items():
            setattr(launcher, name, value)


def smoke_default_port_is_used_when_free() -> None:
    calls = []

    with patched(
        _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: None,
        _port_open=lambda port=launcher.SERVER_PORT, timeout=1.0: False,
        _pick_free_port=lambda: (_ for _ in ()).throw(AssertionError("unexpected alternate port")),
        _start_server=lambda port=launcher.SERVER_PORT: calls.append(("start", port)) or True,
        _wait_frontend_ready=lambda timeout=90.0, server_url=launcher.SERVER_URL: calls.append(("wait", server_url)) or True,
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL, shutdown_on_close=False: calls.append(("open", url, shell, server_url, shutdown_on_close)) or True,
    ):
        assert launcher.run_native_client(shell="browser") == 0

    assert calls[0] == ("start", launcher.SERVER_PORT)
    assert calls[1] == ("wait", launcher.SERVER_URL)
    assert calls[2][0] == "open"
    assert calls[2][1].startswith(launcher.SERVER_URL + "/?")
    assert calls[2][3] == launcher.SERVER_URL
    assert calls[2][4] is False


def smoke_conflicting_default_port_uses_alternate_port() -> None:
    calls = []
    alternate_port = 62123
    alternate_url = launcher._server_url(alternate_port)

    with patched(
        _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: None,
        _port_open=lambda port=launcher.SERVER_PORT, timeout=1.0: calls.append(("port_open", port)) or (port == launcher.SERVER_PORT),
        _request_server_shutdown=lambda server_url=launcher.SERVER_URL: False,
        _stop_stale_server_on_port=lambda port=launcher.SERVER_PORT: calls.append(("stop_stale", port)),
        _pick_free_port=lambda: calls.append(("pick_free", alternate_port)) or alternate_port,
        _start_server=lambda port=launcher.SERVER_PORT: calls.append(("start", port)) or True,
        _wait_frontend_ready=lambda timeout=90.0, server_url=launcher.SERVER_URL: calls.append(("wait", server_url)) or True,
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL, shutdown_on_close=False: calls.append(("open", url, shell, server_url, shutdown_on_close)) or True,
    ):
        assert launcher.run_native_client(shell="browser") == 0

    assert ("stop_stale", launcher.SERVER_PORT) in calls
    assert ("pick_free", alternate_port) in calls
    assert ("start", alternate_port) in calls
    assert ("wait", alternate_url) in calls
    open_calls = [call for call in calls if call[0] == "open"]
    assert len(open_calls) == 1
    assert open_calls[0][1].startswith(alternate_url + "/?")
    assert open_calls[0][3] == alternate_url
    assert open_calls[0][4] is False


def smoke_stale_server_uses_graceful_shutdown_before_kill() -> None:
    calls = []

    with patched(
        _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: {"server_rev": launcher.EXPECTED_SERVER_REV},
        _request_server_shutdown=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)) or True,
        _wait_for_port_closed=lambda port=launcher.SERVER_PORT, timeout=5.0: calls.append(("wait_closed", port, timeout)) or True,
        _listener_pids=lambda port=launcher.SERVER_PORT: (_ for _ in ()).throw(AssertionError("unexpected taskkill path")),
    ):
        launcher._stop_stale_server_on_port(launcher.SERVER_PORT)

    assert calls == [
        ("shutdown", launcher.SERVER_URL),
        ("wait_closed", launcher.SERVER_PORT, 5.0),
    ]


def smoke_unknown_port_service_is_not_sent_shutdown() -> None:
    calls = []

    with patched(
        _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: None,
        _request_server_shutdown=lambda server_url=launcher.SERVER_URL: (_ for _ in ()).throw(
            AssertionError("unexpected shutdown request to unknown service")
        ),
        _listener_pids=lambda port=launcher.SERVER_PORT: calls.append(("listener_pids", port)) or [],
    ):
        launcher._stop_stale_server_on_port(launcher.SERVER_PORT)

    assert calls == [("listener_pids", launcher.SERVER_PORT)]


def smoke_existing_matching_server_is_reused() -> None:
    calls = []

    def fetch_status(timeout=1.5, server_url=launcher.SERVER_URL):
        calls.append(("fetch", timeout, server_url))
        return {"server_rev": launcher.EXPECTED_SERVER_REV, "static_ready": True}

    with patched(
        _fetch_status=fetch_status,
        _port_open=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected port probe")),
        _start_server=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected server start")),
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL, shutdown_on_close=False: calls.append(("open", url, shell, server_url, shutdown_on_close)) or True,
    ):
        assert launcher.run_native_client(shell="browser") == 0

    assert calls[0] == ("fetch", 1.5, launcher.SERVER_URL)
    assert calls[1][0] == "open"
    assert calls[1][1].startswith(launcher.SERVER_URL + "/?")
    assert calls[1][3] == launcher.SERVER_URL
    assert calls[1][4] is False


def smoke_ready_failure_cleans_started_server() -> None:
    calls = []
    process = FakeProcess()
    original_showerror = launcher.messagebox.showerror
    launcher.messagebox.showerror = lambda *args, **kwargs: calls.append(("showerror", args))

    try:
        with patched(
            _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: None,
            _port_open=lambda port=launcher.SERVER_PORT, timeout=1.0: False,
            _start_server=lambda port=launcher.SERVER_PORT: calls.append(("start", port)) or process,
            _wait_frontend_ready=lambda timeout=90.0, server_url=launcher.SERVER_URL: calls.append(("wait", server_url)) or False,
            _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
        ):
            assert launcher.run_native_client(shell="webview") == 1
    finally:
        launcher.messagebox.showerror = original_showerror

    assert ("shutdown", launcher.SERVER_URL) in calls
    assert process.terminated


def smoke_open_failure_cleans_started_server() -> None:
    calls = []
    process = FakeProcess()

    with patched(
        _fetch_status=lambda timeout=1.5, server_url=launcher.SERVER_URL: None,
        _port_open=lambda port=launcher.SERVER_PORT, timeout=1.0: False,
        _start_server=lambda port=launcher.SERVER_PORT: calls.append(("start", port)) or process,
        _wait_frontend_ready=lambda timeout=90.0, server_url=launcher.SERVER_URL: calls.append(("wait", server_url)) or True,
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL, shutdown_on_close=False: calls.append(("open", shutdown_on_close)) or False,
        _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
    ):
        assert launcher.run_native_client(shell="webview") == 1

    assert ("open", True) in calls
    assert ("shutdown", launcher.SERVER_URL) in calls
    assert process.terminated


def smoke_window_close_shuts_down_runtime_on_selected_port() -> None:
    calls = []
    selected_url = launcher._server_url(62124)

    fake_webview = SimpleNamespace(
        create_window=lambda *args, **kwargs: calls.append(("webview_create", args, kwargs)),
        start=lambda *args, **kwargs: calls.append(("webview_start", args, kwargs)),
    )
    original_webview = sys.modules.get("webview")
    sys.modules["webview"] = fake_webview
    try:
        with patched(
            _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
        ):
            assert launcher._open_webview_window(
                selected_url + "/?rev=test",
                selected_url,
                shutdown_on_close=True,
            )
    finally:
        if original_webview is None:
            sys.modules.pop("webview", None)
        else:
            sys.modules["webview"] = original_webview

    assert ("shutdown", selected_url) in calls


def smoke_reused_webview_window_does_not_shutdown_runtime() -> None:
    calls = []
    selected_url = launcher._server_url(62125)

    fake_webview = SimpleNamespace(
        create_window=lambda *args, **kwargs: calls.append(("webview_create", args, kwargs)),
        start=lambda *args, **kwargs: calls.append(("webview_start", args, kwargs)),
    )
    original_webview = sys.modules.get("webview")
    sys.modules["webview"] = fake_webview
    try:
        with patched(
            _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
        ):
            assert launcher._open_webview_window(selected_url + "/?rev=test", selected_url)
    finally:
        if original_webview is None:
            sys.modules.pop("webview", None)
        else:
            sys.modules["webview"] = original_webview

    assert not any(call[0] == "shutdown" for call in calls)


def smoke_webview_api_closes_owned_window() -> None:
    calls = []
    selected_url = launcher._server_url(62127)

    class FakeWindow:
        def __init__(self) -> None:
            self.destroyed = False

        def destroy(self) -> None:
            self.destroyed = True
            calls.append(("window_destroy",))

    fake_window = FakeWindow()

    def create_window(*args, **kwargs):
        calls.append(("webview_create", args, kwargs))
        return fake_window

    fake_webview = SimpleNamespace(
        create_window=create_window,
        start=lambda *args, **kwargs: calls.append(("webview_start", args, kwargs)),
    )
    original_webview = sys.modules.get("webview")
    sys.modules["webview"] = fake_webview
    try:
        assert launcher._open_webview_window(selected_url + "/?rev=test", selected_url)
    finally:
        if original_webview is None:
            sys.modules.pop("webview", None)
        else:
            sys.modules["webview"] = original_webview

    create_call = next(call for call in calls if call[0] == "webview_create")
    js_api = create_call[2].get("js_api")
    assert js_api is not None
    assert js_api.close_window() == {"ok": True, "action": "window_destroy"}
    assert fake_window.destroyed


def smoke_edge_window_shutdown_tracks_ownership() -> None:
    calls = []
    selected_url = launcher._server_url(62126)

    class FakeProfileDir:
        def mkdir(self, *args, **kwargs):
            calls.append(("profile_mkdir", args, kwargs))

        def __str__(self) -> str:
            return "fake-edge-profile"

    class FakeEdgeProcess:
        def wait(self):
            calls.append(("edge_wait",))

    with patched(
        _find_edge_exe=lambda: "msedge.exe",
        _creationflags_no_window=lambda: 0,
        _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
        EDGE_PROFILE_DIR=FakeProfileDir(),
    ):
        original_popen = launcher.subprocess.Popen
        launcher.subprocess.Popen = lambda *args, **kwargs: calls.append(("edge_popen", args, kwargs)) or FakeEdgeProcess()
        try:
            assert launcher._open_edge_app_window(
                selected_url + "/?rev=test",
                selected_url,
                shutdown_on_close=True,
            )
            assert ("shutdown", selected_url) in calls
            calls.clear()
            assert launcher._open_edge_app_window(selected_url + "/?rev=test", selected_url)
            assert not any(call[0] == "shutdown" for call in calls)
        finally:
            launcher.subprocess.Popen = original_popen


def smoke_browser_fallback_only_stops_katago() -> None:
    calls = []
    original_startfile = getattr(launcher.os, "startfile", None)
    original_showinfo = launcher.messagebox.showinfo
    launcher.os.startfile = lambda url: calls.append(("startfile", url))
    launcher.messagebox.showinfo = lambda *args, **kwargs: calls.append(("showinfo", args))
    try:
        with patched(
            _shutdown_desktop_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)),
            _stop_katago_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("stop_katago", server_url)),
        ):
            assert launcher._open_system_browser(launcher.SERVER_URL + "/?rev=test", launcher.SERVER_URL)
    finally:
        launcher.messagebox.showinfo = original_showinfo
        if original_startfile is not None:
            launcher.os.startfile = original_startfile

    assert ("stop_katago", launcher.SERVER_URL) in calls
    assert not any(call[0] == "shutdown" for call in calls)


def smoke_shutdown_runtime_falls_back_to_stop_katago_for_old_servers() -> None:
    calls = []

    with patched(
        _request_server_shutdown=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)) or False,
        _stop_katago_runtime=lambda server_url=launcher.SERVER_URL: calls.append(("stop_katago", server_url)),
    ):
        launcher._shutdown_desktop_runtime(launcher.SERVER_URL)

    assert calls == [
        ("shutdown", launcher.SERVER_URL),
        ("stop_katago", launcher.SERVER_URL),
    ]


def main() -> int:
    smoke_default_port_is_used_when_free()
    smoke_conflicting_default_port_uses_alternate_port()
    smoke_stale_server_uses_graceful_shutdown_before_kill()
    smoke_unknown_port_service_is_not_sent_shutdown()
    smoke_existing_matching_server_is_reused()
    smoke_ready_failure_cleans_started_server()
    smoke_open_failure_cleans_started_server()
    smoke_window_close_shuts_down_runtime_on_selected_port()
    smoke_reused_webview_window_does_not_shutdown_runtime()
    smoke_webview_api_closes_owned_window()
    smoke_edge_window_shutdown_tracks_ownership()
    smoke_browser_fallback_only_stops_katago()
    smoke_shutdown_runtime_falls_back_to_stop_katago_for_old_servers()
    print("launcher port conflict smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
