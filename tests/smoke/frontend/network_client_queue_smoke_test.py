from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    network_client = (ROOT / "static" / "js" / "network_client.js").read_text(encoding="utf-8")
    app_bootstrap = (ROOT / "static" / "js" / "app_bootstrap.js").read_text(encoding="utf-8")

    required_network_markers = [
        "const pendingMessages = []",
        "const MAX_PENDING_MESSAGES",
        "function flushPendingWS()",
        "function clearPendingWS()",
        "pendingMessages.push(data)",
        "window.clearPendingWS = clearPendingWS",
        "window.flushPendingWS = flushPendingWS",
    ]
    required_bootstrap_markers = [
        "const flushed = flushPendingWS();",
        "if (!gameState && !flushed) sendWS({ action: \"reconnect\" });",
    ]
    missing = [
        marker
        for marker in required_network_markers
        if marker not in network_client
    ] + [
        marker
        for marker in required_bootstrap_markers
        if marker not in app_bootstrap
    ]
    if missing:
        raise AssertionError(f"missing WebSocket queue markers: {missing}")

    print("network_client_queue_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
