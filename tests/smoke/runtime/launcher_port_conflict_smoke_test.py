from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from collections.abc import Callable
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
import sys

import launcher


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
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL: calls.append(("open", url, shell, server_url)) or True,
    ):
        assert launcher.run_native_client(shell="browser") == 0

    assert calls[0] == ("start", launcher.SERVER_PORT)
    assert calls[1] == ("wait", launcher.SERVER_URL)
    assert calls[2][0] == "open"
    assert calls[2][1].startswith(launcher.SERVER_URL + "/?")
    assert calls[2][3] == launcher.SERVER_URL


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
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL: calls.append(("open", url, shell, server_url)) or True,
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


def smoke_stale_server_uses_graceful_shutdown_before_kill() -> None:
    calls = []

    with patched(
        _request_server_shutdown=lambda server_url=launcher.SERVER_URL: calls.append(("shutdown", server_url)) or True,
        _wait_for_port_closed=lambda port=launcher.SERVER_PORT, timeout=5.0: calls.append(("wait_closed", port, timeout)) or True,
        _listener_pids=lambda port=launcher.SERVER_PORT: (_ for _ in ()).throw(AssertionError("unexpected taskkill path")),
    ):
        launcher._stop_stale_server_on_port(launcher.SERVER_PORT)

    assert calls == [
        ("shutdown", launcher.SERVER_URL),
        ("wait_closed", launcher.SERVER_PORT, 5.0),
    ]


def smoke_existing_matching_server_is_reused() -> None:
    calls = []

    def fetch_status(timeout=1.5, server_url=launcher.SERVER_URL):
        calls.append(("fetch", timeout, server_url))
        return {"server_rev": launcher.EXPECTED_SERVER_REV, "static_ready": True}

    with patched(
        _fetch_status=fetch_status,
        _port_open=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected port probe")),
        _start_server=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected server start")),
        _open_native_client_window=lambda url, shell, server_url=launcher.SERVER_URL: calls.append(("open", url, shell, server_url)) or True,
    ):
        assert launcher.run_native_client(shell="browser") == 0

    assert calls[0] == ("fetch", 1.5, launcher.SERVER_URL)
    assert calls[1][0] == "open"
    assert calls[1][1].startswith(launcher.SERVER_URL + "/?")
    assert calls[1][3] == launcher.SERVER_URL


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
            assert launcher._open_webview_window(selected_url + "/?rev=test", selected_url)
    finally:
        if original_webview is None:
            sys.modules.pop("webview", None)
        else:
            sys.modules["webview"] = original_webview

    assert ("shutdown", selected_url) in calls


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
    smoke_existing_matching_server_is_reused()
    smoke_window_close_shuts_down_runtime_on_selected_port()
    smoke_shutdown_runtime_falls_back_to_stop_katago_for_old_servers()
    print("launcher port conflict smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
