from __future__ import annotations

import asyncio
import json
import sys
import traceback
from contextlib import redirect_stdout
from typing import Any

from app.runtime.desktop_session import DesktopRuntimeBinding, DesktopRuntimeSession
from app.runtime.status_payload import build_status_payload


_PROTOCOL_STDOUT = sys.stdout
sys.stdout = sys.stderr

with redirect_stdout(sys.stderr):
    import server  # noqa: E402


def _worker_log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _worker_traceback() -> None:
    traceback.print_exc(file=sys.stderr)


server.engine.log = _worker_log
server.engine_runtime.log_fn = _worker_log


def _desktop_binding() -> DesktopRuntimeBinding:
    return DesktopRuntimeBinding(
        active_games=server.active_games,
        action_handlers=server.WS_ACTION_HANDLERS,
        analyze_position=server._analyze_current_position,
        websocket_context_binding=server._ws_context_binding,
        log_fn=_worker_log,
        traceback_fn=_worker_traceback,
    )


class WorkerHost:
    def __init__(self) -> None:
        self._sessions: dict[str, DesktopRuntimeSession] = {}

    def session_for(self, game_id: str) -> DesktopRuntimeSession:
        session = self._sessions.get(game_id)
        if session is None:
            session = DesktopRuntimeSession(game_id=game_id, binding=_desktop_binding())
            self._sessions[game_id] = session
        return session

    def status(self) -> dict[str, Any]:
        snapshot = server.engine_runtime.snapshot()
        selected_model = server.engine_runtime.select_model()
        card_config_payload = server.card_config_service.get_payload()
        return build_status_payload(
            server_rev=server.SERVER_REV,
            host="local",
            port=0,
            access_urls={},
            engine_ready=server.engine.ready,
            engine_snapshot=snapshot,
            exe_exists=server.engine_runtime.has_engine_binaries(),
            model_exists=server.engine_runtime.has_model_files(),
            selected_model_name=selected_model.name if selected_model else None,
            no_katago=server.NO_KATAGO,
            cpu_mode=server.engine_runtime.cpu_mode,
            static_ready=(server.STATIC_DIR / "index.html").exists(),
            card_config_payload=card_config_payload,
        )

    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        game_id = str(request.get("game_id") or "desktop")

        if command == "get_status":
            return {"result": self.status()}
        if command == "get_card_config":
            return {"result": server.card_config_service.get_payload()}
        if command == "save_card_config":
            return {"result": server.card_config_service.save_payload(request.get("config"))}
        if command == "reset_card_config":
            return {"result": server.card_config_service.reset_payload()}
        if command == "start_engine":
            started, reason = server.engine_runtime.start_background("desktop_worker")
            return {"result": {"started": started, "reason": reason, "status": self.status()}}
        if command == "stop_engine":
            return {"result": server.engine_runtime.stop_via_api()}
        if command == "export_sgf":
            game = server.active_games.get(game_id, touch=True)
            if not game:
                return {"ok": False, "error": "Game not found"}
            return {"result": {"sgf": server.generate_sgf(game)}}
        if command == "poll_events":
            return {"events": self.session_for(game_id).drain_events()}
        if command == "shutdown":
            server.engine_runtime.handle_app_shutdown()
            return {"result": {"shutdown": True}}

        if command == "send_action":
            data = request.get("data") or {}
        else:
            data = {
                key: value
                for key, value in request.items()
                if key not in {"id", "command", "game_id"}
            }
        events = await self.session_for(game_id).dispatch(data)
        return {"events": events}


def _write_response(response: dict[str, Any]) -> None:
    print(
        json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        file=_PROTOCOL_STDOUT,
        flush=True,
    )


async def main() -> int:
    host = WorkerHost()
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            server.engine_runtime.handle_app_shutdown()
            return 0
        line = line.strip()
        if not line:
            continue
        request_id: Any = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            payload = await host.handle(request)
            ok = payload.pop("ok", True)
            response = {"id": request_id, "ok": ok, **payload}
        except Exception as exc:
            _worker_log(f"[DesktopWorker] request failed: {exc}")
            _worker_traceback()
            response = {"id": request_id, "ok": False, "error": str(exc)}
        _write_response(response)
        if line and response.get("ok") and json.loads(line).get("command") == "shutdown":
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
