from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json
from dataclasses import dataclass

from fastapi import WebSocketDisconnect

from app.runtime.ws_session import run_websocket_game_session


@dataclass
class FakeGame:
    moves: list
    game_over: bool = False


class FakeActiveGames:
    def __init__(self):
        self.game = FakeGame(moves=[])
        self.pruned = False
        self.get_calls = []
        self.touches = []

    def prune(self):
        self.pruned = True

    def get(self, game_id, *, touch=False):
        self.get_calls.append((game_id, touch))
        return self.game

    def touch(self, game_id):
        self.touches.append(game_id)


class FakeWebSocket:
    def __init__(self, messages, *, send_failure: str | None = None):
        self.messages = list(messages)
        self.send_failure = send_failure
        self.accepted = False
        self.sent = []
        self.send_attempts = 0

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self.messages:
            raise WebSocketDisconnect(code=1000)
        return self.messages.pop(0)

    async def send_text(self, text):
        self.send_attempts += 1
        if self.send_failure:
            raise RuntimeError(self.send_failure)
        self.sent.append(json.loads(text))


class FakeContext:
    def __init__(self, game_id, game, send, do_analysis_bg):
        self.game_id = game_id
        self.game = game
        self.send = send
        self.do_analysis_bg = do_analysis_bg


async def main():
    await smoke_happy_path_analysis_send()
    await smoke_invalid_json_reports_error_and_keeps_session_open()
    await smoke_json_array_reports_error_and_keeps_session_open()
    await smoke_unknown_action_reports_error()
    await smoke_stale_analysis_suppressed()
    await smoke_closed_socket_suppresses_later_sends()
    print("ws session smoke test: OK")


async def smoke_happy_path_analysis_send():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket([json.dumps({"action": "ping"})])

    async def analyze_position(game):
        return {"winrate": 0.62, "score": 3.5, "top_moves": [], "analysis_ready": True}

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_ping(ctx, data):
        await ctx.send({"type": "pong", "gameId": ctx.game_id})
        await ctx.do_analysis_bg(ctx.game)

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": handle_ping},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert websocket.accepted
    assert active_games.pruned
    assert active_games.get_calls == [("session-1", True)]
    assert active_games.touches == ["session-1", "session-1"]
    assert websocket.sent == [
        {"type": "pong", "gameId": "session-1"},
        {
            "type": "analysis",
            "winrate": 0.62,
            "score": 3.5,
            "top_moves": [],
            "analysis_ready": True,
        },
    ]


async def smoke_invalid_json_reports_error_and_keeps_session_open():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket(["not-json", json.dumps({"action": "ping"})])

    async def analyze_position(game):
        raise AssertionError("analysis should not run in this smoke")

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_ping(ctx, data):
        await ctx.send({"type": "pong"})

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": handle_ping},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert websocket.sent == [
        {"type": "error", "message": "消息格式错误：不是有效的 JSON"},
        {"type": "pong"},
    ]
    assert active_games.touches == ["session-1", "session-1"]


async def smoke_json_array_reports_error_and_keeps_session_open():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket([json.dumps([]), json.dumps({"action": "ping"})])

    async def analyze_position(game):
        raise AssertionError("analysis should not run in this smoke")

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_ping(ctx, data):
        await ctx.send({"type": "pong"})

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": handle_ping},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert websocket.sent == [
        {"type": "error", "message": "消息格式错误：JSON 必须是对象"},
        {"type": "pong"},
    ]
    assert active_games.touches == ["session-1", "session-1"]


async def smoke_unknown_action_reports_error():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket([json.dumps({"action": "missing_action"})])

    async def analyze_position(game):
        raise AssertionError("analysis should not run in this smoke")

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": lambda _ctx, _data: None},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert websocket.sent == [{"type": "error", "message": "未知操作: missing_action"}]
    assert active_games.touches == ["session-1"]


async def smoke_stale_analysis_suppressed():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket([json.dumps({"action": "ping"})])

    async def analyze_position(game):
        game.moves.append("newer move")
        return {"winrate": 0.91, "score": 12.0, "top_moves": [], "analysis_ready": True}

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_ping(ctx, data):
        await ctx.send({"type": "pong", "gameId": ctx.game_id})
        await ctx.do_analysis_bg(ctx.game)

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": handle_ping},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert active_games.touches == ["session-1"]
    assert websocket.sent == [{"type": "pong", "gameId": "session-1"}]


async def smoke_closed_socket_suppresses_later_sends():
    active_games = FakeActiveGames()
    websocket = FakeWebSocket(
        [json.dumps({"action": "closed"})],
        send_failure="WebSocket is not connected. Need to call accept first.",
    )
    second_send_blocked = False

    async def analyze_position(game):
        raise AssertionError("analysis should not run in this smoke")

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_closed(ctx, data):
        nonlocal second_send_blocked
        try:
            await ctx.send({"type": "first"})
        except WebSocketDisconnect:
            pass
        try:
            await ctx.send({"type": "second"})
        except WebSocketDisconnect:
            second_send_blocked = True

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"closed": handle_closed},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )

    assert websocket.send_attempts == 1
    assert websocket.sent == []
    assert active_games.touches == []
    assert second_send_blocked


if __name__ == "__main__":
    asyncio.run(main())
