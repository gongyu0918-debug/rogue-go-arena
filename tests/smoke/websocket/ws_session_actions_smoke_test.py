from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_session_actions import (
    handle_load_position,
    handle_reconnect,
    handle_request_hint,
    handle_resign,
    handle_set_level,
    handle_time_expired,
    wait_for_engine_ready,
)


class FakeEngine:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.commands = []
        self.visits = []

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        return "="

    def set_visits(self, visits: int) -> None:
        self.visits.append(visits)


class FakeActiveGames:
    def __init__(self, game=None) -> None:
        self.game = game
        self.calls = []

    def get(self, game_id: str, *, touch: bool = False):
        self.calls.append((game_id, touch))
        return self.game


class FakeGame:
    def __init__(self) -> None:
        self.ai_color = "W"
        self.current_player = "B"
        self.two_player = False
        self.game_over = False
        self.winner = None
        self.level = "a3d"
        self.moves = [("B", "E5")]
        self.ultimate = False
        self.rogue_card = ""
        self.challenge_beta = False
        self.challenge_usage = {"hint": 0}

    def to_state(self):
        return {
            "winner": self.winner,
            "level": self.level,
            "challenge_usage": dict(self.challenge_usage),
        }


class FakeContext:
    def __init__(self, game=None, *, engine_ready: bool = True) -> None:
        self.game_id = "ws-session"
        self.game = game
        self.active_games = FakeActiveGames(game)
        self.engine = FakeEngine(ready=engine_ready)
        self.sent = []
        self.errors = []
        self.analysis_calls = []
        self.visits_calls = []
        self.run_calls = []
        self.GoGame = GoGame

    def restore_game(self):
        if self.game is None:
            self.game = self.active_games.get(self.game_id, touch=True)
        return self.game

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def do_analysis(self, game):
        self.analysis_calls.append(game)
        return {"analysis_ready": True, "moves": len(game.moves)}

    async def run_in_executor(self, func, *args):
        self.run_calls.append((getattr(func, "__name__", str(func)), args))
        return func(*args)

    def get_game_visits(self, level: str, move_count: int, mode: str = "normal") -> int:
        self.visits_calls.append((level, move_count, mode))
        return 321

    def rogue_has(self, _game, card_id: str) -> bool:
        return card_id == "quickthink" and getattr(self, "quickthink", False)

    def challenge_remaining(self, _game, kind: str) -> int:
        assert kind == "hint"
        return getattr(self, "hint_remaining", 1)


async def smoke_reconnect_resign_and_timeout_messages() -> None:
    game = FakeGame()
    ctx = FakeContext(game)

    await handle_reconnect(ctx, {})
    assert ctx.active_games.calls == [("ws-session", True)]
    assert ctx.sent == [
        {"type": "reconnected", "winner": None, "level": "a3d", "challenge_usage": {"hint": 0}},
        {"type": "analysis", "analysis_ready": True, "moves": 1},
    ]

    ctx.sent.clear()
    await handle_resign(ctx, {})
    assert game.game_over is True
    assert game.winner == "W"
    assert ctx.sent == [{"type": "game_over", "winner": "W", "score": None, "reason": "resign"}]

    game = FakeGame()
    ctx = FakeContext(game)
    await handle_time_expired(ctx, {"color": "W"})
    assert game.game_over is True
    assert game.winner == "B"
    assert ctx.sent == [{"type": "game_over", "winner": "B", "score": "B+T", "reason": "timeout"}]


async def smoke_hint_challenge_usage_and_quickthink_guard() -> None:
    game = FakeGame()
    game.challenge_beta = True
    ctx = FakeContext(game)

    await handle_request_hint(ctx, {})
    assert game.challenge_usage["hint"] == 1
    assert ctx.sent == [
        {"type": "game_state", "winner": None, "level": "a3d", "challenge_usage": {"hint": 1}},
        {"type": "analysis", "analysis_ready": True, "moves": 1},
    ]

    quickthink_ctx = FakeContext(FakeGame())
    quickthink_ctx.quickthink = True
    await handle_request_hint(quickthink_ctx, {})
    assert quickthink_ctx.errors == ["快速思考已禁用推荐点位，请自行判断局面"]
    assert quickthink_ctx.sent == []


async def smoke_set_level_and_load_position_use_runtime_dependencies() -> None:
    game = FakeGame()
    game.ultimate = True
    ctx = FakeContext(game)

    await handle_set_level(ctx, {"level": "p1d"})
    assert game.level == "p1d"
    assert ctx.visits_calls == [("p1d", 1, "ultimate")]
    assert ctx.engine.visits == [321]
    assert ctx.sent == [{"type": "level_set", "level": "p1d"}]

    load_ctx = FakeContext(SimpleNamespace())
    await handle_load_position(
        load_ctx,
        {
            "size": 9,
            "komi": 6.5,
            "moves": [("B", "E5"), ("W", "D4")],
        },
    )
    assert load_ctx.engine.commands == [
        "boardsize 9",
        "clear_board",
        "komi 6.5",
        "play B E5",
        "play W D4",
    ]
    assert isinstance(load_ctx.analysis_calls[0], GoGame)
    assert load_ctx.analysis_calls[0].current_player == "B"
    assert load_ctx.sent == [{"type": "analysis", "analysis_ready": True, "moves": 2}]


def smoke_ws_action_handlers_keep_public_action_names() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["reconnect"] is handle_reconnect
    assert ws_actions.WS_ACTION_HANDLERS["resign"] is handle_resign
    assert ws_actions.WS_ACTION_HANDLERS["request_hint"] is handle_request_hint
    assert ws_actions.WS_ACTION_HANDLERS["set_level"] is handle_set_level
    assert ws_actions.WS_ACTION_HANDLERS["load_position"] is handle_load_position
    assert ws_actions.WS_ACTION_HANDLERS["time_expired"] is handle_time_expired


def smoke_session_action_annotations_resolve_runtime_context() -> None:
    for handler in (
        handle_reconnect,
        handle_resign,
        handle_request_hint,
        handle_set_level,
        handle_load_position,
        handle_time_expired,
        wait_for_engine_ready,
    ):
        hints = get_type_hints(handler)
        assert hints["ctx"] is WebSocketActionContext


async def main() -> None:
    await smoke_reconnect_resign_and_timeout_messages()
    await smoke_hint_challenge_usage_and_quickthink_guard()
    await smoke_set_level_and_load_position_use_runtime_dependencies()
    smoke_ws_action_handlers_keep_public_action_names()
    smoke_session_action_annotations_resolve_runtime_context()
    print("ws session actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
