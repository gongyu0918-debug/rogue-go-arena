from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json
from types import SimpleNamespace

from fastapi import WebSocketDisconnect
from starlette.routing import WebSocketRoute

import server as s
from app.runtime.ws_context import WEBSOCKET_CONTEXT_FIELD_NAMES
from app.runtime.ws_context_adapters import WebSocketContextBinding
from app.runtime.ws_routes import WebSocketRoutesBinding, build_websocket_router
from app.runtime.ws_routes_runtime import (
    WebSocketRoutesDependencies,
    WebSocketRoutesRuntimeFns,
    build_websocket_routes_binding,
)


class FakeGame:
    def __init__(self) -> None:
        self.moves = []
        self.game_over = False


class FakeActiveGames:
    def __init__(self, game: FakeGame, on_get=None) -> None:
        self.game = game
        self.on_get = on_get
        self.calls = []
        self.touches = []

    def prune(self) -> None:
        self.calls.append(("prune",))

    def get(self, game_id: str, *, touch: bool = False):
        self.calls.append(("get", game_id, touch))
        if self.on_get:
            self.on_get()
        return self.game

    def touch(self, game_id: str) -> None:
        self.touches.append(game_id)


class FakeWebSocket:
    def __init__(self, messages) -> None:
        self.messages = list(messages)
        self.accepted = False
        self.sent = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if not self.messages:
            raise WebSocketDisconnect(code=1000)
        return self.messages.pop(0)

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def endpoint_for(routes, path: str):
    for route in routes:
        if getattr(route, "path", None) == path and isinstance(route, WebSocketRoute):
            return route.endpoint
    raise AssertionError(f"missing route {path}")


def make_ws_binding(active_games_marker) -> WebSocketContextBinding:
    values = {
        name: SimpleNamespace(name=name)
        for name in WEBSOCKET_CONTEXT_FIELD_NAMES
    }
    values["active_games"] = active_games_marker
    return WebSocketContextBinding(**values)


def smoke_websocket_routes_runtime_builder_maps_every_field() -> None:
    active_games = object()
    handlers = {"ping": object()}

    async def analyze_position(_game):
        return {"score": 0}

    def websocket_context_binding():
        return make_ws_binding(active_games)

    binding = build_websocket_routes_binding(
        WebSocketRoutesDependencies(
            runtime=WebSocketRoutesRuntimeFns(
                active_games=active_games,
                action_handlers=handlers,
                analyze_position=analyze_position,
                websocket_context_binding=websocket_context_binding,
            ),
        )
    )

    assert binding.active_games is active_games
    assert binding.action_handlers is handlers
    assert binding.analyze_position is analyze_position
    assert binding.websocket_context_binding is websocket_context_binding


async def smoke_websocket_router_preserves_session_and_context_late_binding() -> None:
    game = FakeGame()
    before_context = object()
    after_context = object()
    current = {"context_binding": make_ws_binding(before_context)}

    def switch_context_binding() -> None:
        current["context_binding"] = make_ws_binding(after_context)

    active_games = FakeActiveGames(game, on_get=switch_context_binding)
    seen_context_markers = []
    analyze_calls = []

    async def analyze_position(_game):
        analyze_calls.append(_game is game)
        return {"winrate": 0.5, "score": 0, "top_moves": []}

    async def handle_ping(ctx, _data):
        seen_context_markers.append(ctx.active_games)
        analysis = await ctx.do_analysis(ctx.game)
        await ctx.send({
            "type": "pong",
            "game_id": ctx.game_id,
            "score": analysis["score"],
        })

    def binding_provider() -> WebSocketRoutesBinding:
        return WebSocketRoutesBinding(
            active_games=active_games,
            action_handlers={"ping": handle_ping},
            analyze_position=analyze_position,
            websocket_context_binding=lambda: current["context_binding"],
        )

    router = build_websocket_router(binding_provider)
    websocket = FakeWebSocket([json.dumps({"action": "ping"})])

    await endpoint_for(router.routes, "/ws/{game_id}")(websocket, "route-session")

    assert websocket.accepted is True
    assert websocket.sent == [{"type": "pong", "game_id": "route-session", "score": 0}]
    assert active_games.calls == [("prune",), ("get", "route-session", True)]
    assert active_games.touches == ["route-session"]
    assert seen_context_markers == [after_context]
    assert analyze_calls == [True]


def smoke_server_websocket_route_maps_current_runtime_objects() -> None:
    binding = s._websocket_routes_binding()

    assert binding.active_games is s.active_games
    assert binding.action_handlers is s.WS_ACTION_HANDLERS
    assert binding.analyze_position is s._analyze_current_position
    assert binding.websocket_context_binding is s._ws_context_binding

    endpoint = endpoint_for(s.app.routes, "/ws/{game_id}")
    assert endpoint.__module__ == "app.runtime.ws_routes"


async def main() -> None:
    smoke_websocket_routes_runtime_builder_maps_every_field()
    await smoke_websocket_router_preserves_session_and_context_late_binding()
    smoke_server_websocket_route_maps_current_runtime_objects()
    print("ws routes smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
