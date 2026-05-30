from __future__ import annotations

import json
import traceback
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
SendErrorFn = Callable[[str], Awaitable[None]]
AnalysisFn = Callable[[Any], Awaitable[dict[str, Any]]]
ActionHandler = Callable[[Any, dict[str, Any]], Awaitable[None]]
ContextFactory = Callable[[Any, SendFn, SendErrorFn, AnalysisFn, Callable[[Any], Awaitable[None]]], Any]
JsonLoadsFn = Callable[[str], dict[str, Any]]
JsonDumpsFn = Callable[[dict[str, Any]], str]
LogFn = Callable[[str], None]
TracebackFn = Callable[[], None]


async def run_websocket_game_session(
    websocket: WebSocket,
    game_id: str,
    *,
    active_games: Any,
    action_handlers: Mapping[str | None, ActionHandler],
    analyze_position: AnalysisFn,
    make_context: ContextFactory,
    json_loads: JsonLoadsFn = json.loads,
    json_dumps: JsonDumpsFn = json.dumps,
    log_fn: LogFn = print,
    traceback_fn: TracebackFn = traceback.print_exc,
) -> None:
    await websocket.accept()
    websocket_closed = False

    active_games.prune()
    game = active_games.get(game_id, touch=True)

    async def send(data: dict[str, Any]) -> None:
        nonlocal websocket_closed
        if websocket_closed:
            raise WebSocketDisconnect(code=1006)
        try:
            await websocket.send_text(json_dumps(data))
            active_games.touch(game_id)
        except WebSocketDisconnect:
            websocket_closed = True
            raise
        except RuntimeError as exc:
            message = str(exc)
            if (
                "websocket.close" in message
                or "WebSocket is not connected" in message
                or "response already completed" in message
            ):
                websocket_closed = True
                raise WebSocketDisconnect(code=1006) from exc
            raise

    async def send_error(msg: str) -> None:
        await send({"type": "error", "message": msg})

    async def do_analysis(g: Any) -> dict[str, Any]:
        return await analyze_position(g)

    async def do_analysis_bg(g: Any) -> None:
        try:
            move_count_before = len(g.moves)
            result = await do_analysis(g)
            if g.game_over or len(g.moves) != move_count_before:
                return
            await send({"type": "analysis", **result})
        except WebSocketDisconnect:
            return
        except Exception as ex:
            log_fn(f"[Analysis-bg] error: {ex}")

    context = make_context(game, send, send_error, do_analysis, do_analysis_bg)

    try:
        while True:
            data = json_loads(await websocket.receive_text())
            action = data.get("action")
            try:
                context.game = game
                handler = action_handlers.get(action)
                if handler is not None:
                    await handler(context, data)
                    game = context.game
                    continue

                continue

            except WebSocketDisconnect:
                raise
            except Exception as e:
                log_fn(f"[WS {game_id}] Action error ({action}): {e}")
                traceback_fn()
                try:
                    await send_error(f"处理出错: {e}")
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log_fn(f"[WS {game_id}] Fatal error: {e}")
        try:
            await send({"type": "error", "message": f"服务器错误: {e}"})
        except Exception:
            pass
