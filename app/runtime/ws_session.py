from __future__ import annotations

import asyncio
import json
import traceback
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.callback_types import SendFn

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
    send_lock = asyncio.Lock()

    active_games.prune()
    game = active_games.get(game_id, touch=True)

    async def send(data: dict[str, Any]) -> None:
        nonlocal websocket_closed
        async with send_lock:
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
            except Exception:
                websocket_closed = True
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
    engine = getattr(context, "engine", None)
    connection_token = object()
    context.connection_token = connection_token
    connection_tokens = getattr(engine, "active_connection_tokens", None)
    if isinstance(connection_tokens, set):
        connection_tokens.add(connection_token)

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                data = json_loads(raw_message)
            except json.JSONDecodeError as exc:
                log_fn(f"[WS {game_id}] Invalid JSON message: {exc}")
                await send_error("消息格式错误：不是有效的 JSON")
                continue
            if not isinstance(data, dict):
                await send_error("消息格式错误：JSON 必须是对象")
                continue
            action = data.get("action")
            try:
                context.game = game
                handler = action_handlers.get(action)
                if handler is not None:
                    await handler(context, data)
                    game = context.game
                    continue

                await send_error(f"未知操作: {action}")
                continue

            except WebSocketDisconnect:
                raise
            except Exception as e:
                log_fn(f"[WS {game_id}] Action error ({action}): {e}")
                traceback_fn()
                try:
                    await send_error("处理出错，请重试")
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log_fn(f"[WS {game_id}] Fatal error: {e}")
        try:
            await send({"type": "error", "message": "服务器错误，请重启游戏后再试"})
        except Exception:
            pass
    finally:
        if isinstance(connection_tokens, set):
            connection_tokens.discard(connection_token)
        if (
            engine is not None
            and getattr(engine, "active_game_id", None) == game_id
            and getattr(engine, "active_game_connection_token", None) == connection_token
            and active_games.get(game_id) is None
        ):
            engine.active_game_id = None
            engine.active_game_connection_token = None
            engine.active_game_claimed_at = 0.0
