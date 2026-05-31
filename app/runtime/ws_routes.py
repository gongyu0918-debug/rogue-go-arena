from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket

from app.runtime.ws_context_adapters import build_websocket_action_context_from_binding
from app.runtime.ws_session import ActionHandler, AnalysisFn, run_websocket_game_session


@dataclass(frozen=True)
class WebSocketRoutesBinding:
    active_games: Any
    action_handlers: Mapping[str | None, ActionHandler]
    analyze_position: AnalysisFn
    websocket_context_binding: Callable[[], Any]


WebSocketRoutesBindingProvider = Callable[[], WebSocketRoutesBinding]


def build_websocket_router(binding_provider: WebSocketRoutesBindingProvider) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws/{game_id}")
    async def websocket_endpoint(websocket: WebSocket, game_id: str):
        binding = binding_provider()

        def make_context(game, send, send_error, do_analysis, do_analysis_bg):
            return build_websocket_action_context_from_binding(
                game_id=game_id,
                game=game,
                send=send,
                send_error=send_error,
                do_analysis=do_analysis,
                do_analysis_bg=do_analysis_bg,
                binding=binding_provider().websocket_context_binding(),
            )

        await run_websocket_game_session(
            websocket,
            game_id,
            active_games=binding.active_games,
            action_handlers=binding.action_handlers,
            analyze_position=binding.analyze_position,
            make_context=make_context,
        )

    return router
