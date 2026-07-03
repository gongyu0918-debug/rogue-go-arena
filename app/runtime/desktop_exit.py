from __future__ import annotations

from collections.abc import Mapping
import secrets
from typing import Any

from app.runtime.engine_control_api import is_loopback_client


UI_EXIT_TOKEN_HEADER = "x-rogue-go-ui-exit-token"
ACTIVE_ENGINE_PHASES = {"initializing", "ready"}


def active_game_count(active_games: Any) -> int:
    prune = getattr(active_games, "prune", None)
    if callable(prune):
        prune()
    count = getattr(active_games, "count", None)
    if callable(count):
        return int(count())
    games = getattr(active_games, "_games", None)
    return len(games) if isinstance(games, dict) else 0


def desktop_exit_available(
    *,
    engine_ready: bool,
    engine_snapshot: Mapping[str, Any],
    active_games_count: int,
) -> bool:
    phase = str(engine_snapshot.get("phase") or "")
    return bool(active_games_count > 0 or engine_ready or phase in ACTIVE_ENGINE_PHASES)


def ui_exit_request_authorized(
    *,
    client_host: str | None,
    request_token: str | None,
    expected_token: str | None,
) -> dict[str, Any]:
    if not is_loopback_client(client_host):
        return {"ok": False, "error": "desktop exit is only available from localhost"}
    if not expected_token:
        return {"ok": False, "error": "desktop exit token is not configured"}
    if not secrets.compare_digest(request_token or "", expected_token):
        return {"ok": False, "error": "invalid desktop exit token"}
    return {"ok": True}
