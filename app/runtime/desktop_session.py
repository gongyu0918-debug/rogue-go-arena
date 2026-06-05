from __future__ import annotations

import asyncio
import traceback
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.runtime.ws_context_adapters import build_websocket_action_context_from_binding


LogFn = Callable[[str], None]
TracebackFn = Callable[[], None]
ActionHandler = Callable[[Any, dict[str, Any]], Awaitable[None]]
AnalysisFn = Callable[[Any], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class DesktopRuntimeBinding:
    active_games: Any
    action_handlers: Mapping[str | None, ActionHandler]
    analyze_position: AnalysisFn
    websocket_context_binding: Callable[[], Any]
    log_fn: LogFn = print
    traceback_fn: TracebackFn = traceback.print_exc


class DesktopRuntimeSession:
    """Run the existing game action protocol without HTTP or WebSocket."""

    def __init__(self, *, game_id: str, binding: DesktopRuntimeBinding) -> None:
        self.game_id = game_id
        self.binding = binding
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def send(self, data: dict[str, Any]) -> None:
        await self._events.put(data)
        self.binding.active_games.touch(self.game_id)

    async def send_error(self, msg: str) -> None:
        await self.send({"type": "error", "message": msg})

    async def do_analysis(self, game: Any) -> dict[str, Any]:
        return await self.binding.analyze_position(game)

    async def do_analysis_bg(self, game: Any) -> None:
        try:
            move_count_before = len(game.moves)
            result = await self.do_analysis(game)
            if game.game_over or len(game.moves) != move_count_before:
                return
            await self.send({"type": "analysis", **result})
        except Exception as exc:
            self.binding.log_fn(f"[DesktopRuntime] background analysis error: {exc}")

    async def dispatch(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        self.binding.active_games.prune()
        game = self.binding.active_games.get(self.game_id, touch=True)
        action = data.get("action")
        handler = self.binding.action_handlers.get(action)
        if handler is None:
            await self.send_error(f"Unsupported action: {action}")
            return self.drain_events()

        context = build_websocket_action_context_from_binding(
            game_id=self.game_id,
            game=game,
            send=self.send,
            send_error=self.send_error,
            do_analysis=self.do_analysis,
            do_analysis_bg=self.do_analysis_bg,
            binding=self.binding.websocket_context_binding(),
        )
        try:
            await handler(context, data)
        except Exception as exc:
            self.binding.log_fn(f"[DesktopRuntime {self.game_id}] Action error ({action}): {exc}")
            self.binding.traceback_fn()
            await self.send_error(f"处理出错: {exc}")
        return self.drain_events()

    def drain_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events
