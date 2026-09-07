from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import argparse
import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import webview

from launcher import _DesktopWindowApi


class ProbeApi(_DesktopWindowApi):
    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0

    def close_window(self) -> dict:
        self.close_calls += 1
        return super().close_window()


def probe_frontend(window, expected_major: str | None, report: dict) -> None:
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            ready = window.evaluate_js(
                "typeof render === 'function' && typeof syncWoodSelect === 'function' && "
                "typeof window.pywebview?.api?.close_window === 'function' && "
                "document.querySelector('#sel-size')?.dataset.woodEnhanced === '1'"
            )
            if ready:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("WebView frontend did not finish loading")
        script = Path(__file__).with_name("webview_frontend_probe.js").read_text(encoding="utf-8")
        for width, height in [(1100, 720), (1500, 960)]:
            window.resize(width, height)
            time.sleep(0.3)
            result = window.evaluate_js(script)
            match = re.search(r"Edg/(\d+)\.", result["userAgent"])
            if not match or (expected_major and match.group(1) != expected_major):
                raise RuntimeError(f"Unexpected WebView version: {result['userAgent']}")
            report["cases"].append(result)
        window.evaluate_js("setTimeout(() => window.pywebview.api.close_window(), 50); true")
    except Exception as exc:
        report["error"] = str(exc)
        window.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frontend checks inside an actual WebView2 host.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8890/")
    parser.add_argument("--runtime-dir", default="")
    parser.add_argument("--expected-major", default="")
    parser.add_argument("--output", default="output/webview-native-compat.json")
    args = parser.parse_args()
    if urlparse(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Use the local test server")
    if args.runtime_dir:
        runtime_dir = Path(args.runtime_dir).resolve(strict=True)
        if not (runtime_dir / "msedgewebview2.exe").is_file():
            raise ValueError("The pinned WebView2 executable is missing")
        webview.settings["WEBVIEW2_RUNTIME_PATH"] = str(runtime_dir)
    logging.getLogger("pywebview").setLevel(logging.CRITICAL)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = output.parent / f"webview-profile-{uuid.uuid4().hex}"
    report = {"base_url": args.base_url, "runtime_dir": args.runtime_dir,
              "expected_major": args.expected_major, "cases": []}
    api = ProbeApi()
    window = webview.create_window("rogue-go-arena compatibility smoke", args.base_url,
                                   js_api=api, width=1100, height=720)
    api.bind(window)
    timer = threading.Timer(50, lambda: os._exit(99))
    timer.daemon = True
    timer.start()
    try:
        webview.start(probe_frontend, (window, args.expected_major or None, report),
                      gui="edgechromium", private_mode=True, storage_path=str(profile))
    finally:
        timer.cancel()
    report["host_close_calls"] = api.close_calls
    report["ok"] = len(report["cases"]) == 2 and api.close_calls == 1 and "error" not in report
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
