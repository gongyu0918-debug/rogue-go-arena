from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.runtime.ws_routes import WebSocketRoutesBinding
from app.runtime.ws_session import ActionHandler, AnalysisFn


@dataclass(frozen=True)
class WebSocketRoutesRuntimeFns:
    active_games: Any
    action_handlers: Mapping[str | None, ActionHandler]
    analyze_position: AnalysisFn
    websocket_context_binding: Callable[[], Any]


@dataclass(frozen=True)
class WebSocketRoutesDependencies:
    runtime: WebSocketRoutesRuntimeFns


def build_websocket_routes_binding(
    dependencies: WebSocketRoutesDependencies,
) -> WebSocketRoutesBinding:
    return WebSocketRoutesBinding(
        active_games=dependencies.runtime.active_games,
        action_handlers=dependencies.runtime.action_handlers,
        analyze_position=dependencies.runtime.analyze_position,
        websocket_context_binding=dependencies.runtime.websocket_context_binding,
    )
