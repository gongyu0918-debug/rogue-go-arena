from __future__ import annotations

import logging
import os
import threading

import webview


class HostCloseApi:
    def __init__(self) -> None:
        self.window = None
        self.close_calls = 0

    def bind(self, window) -> None:
        self.window = window

    def close_window(self) -> dict:
        self.close_calls += 1
        print("HOST_CLOSE_CALLED", flush=True)
        if self.window is None:
            return {"ok": False, "error": "window unavailable"}
        self.window.destroy()
        return {"ok": True, "action": "window_destroy"}


def main() -> int:
    logging.getLogger("pywebview").setLevel(logging.CRITICAL)

    api = HostCloseApi()
    html = """
<!doctype html>
<html>
  <body style="background:#111;color:#fff;font:14px sans-serif">webview close smoke</body>
  <script>
    window.addEventListener("pywebviewready", () => {
      setTimeout(() => window.pywebview.api.close_window(), 300);
    });
  </script>
</html>
"""
    window = webview.create_window(
        "rogue-go-arena smoke",
        html=html,
        js_api=api,
        width=360,
        height=220,
    )
    api.bind(window)

    timer = threading.Timer(10, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    try:
        webview.start(gui="edgechromium", private_mode=True)
    finally:
        timer.cancel()

    assert api.close_calls == 1
    print("WEBVIEW_API_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
