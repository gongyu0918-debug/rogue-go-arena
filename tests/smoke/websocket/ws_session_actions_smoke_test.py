from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import time
from types import SimpleNamespace
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_session_actions import (
    claim_engine_session,
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
        self.stopped = False

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        return "="

    def set_visits(self, visits: int) -> None:
        self.visits.append(visits)

    def stop(self) -> None:
        self.stopped = True
        self.ready = False


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
        self.synced_games = []
        self.GoGame = GoGame
        self.gtp_to_coord = gtp_to_coord

    def restore_game(self):
        if self.game is None:
            self.game = self.active_games.get(self.game_id, touch=True)
        return self.game

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def do_analysis(self, game):
        if getattr(self, "analysis_error", None) is not None:
            raise self.analysis_error
        self.analysis_calls.append(game)
        return {"analysis_ready": True, "moves": len(game.moves)}

    async def run_in_executor(self, func, *args):
        self.run_calls.append((getattr(func, "__name__", str(func)), args))
        return func(*args)

    def get_game_visits(self, level: str, move_count: int, mode: str = "normal") -> int:
        self.visits_calls.append((level, move_count, mode))
        return 321

    def engine_state_snapshot(self) -> dict:
        snapshots = getattr(self, "engine_snapshots", None)
        if snapshots:
            return snapshots.pop(0)
        default_snapshot = getattr(self, "default_engine_snapshot", None)
        if default_snapshot is not None:
            return dict(default_snapshot)
        return {"phase": "ready" if self.engine.ready else "idle", "message": "idle"}

    def start_engine_background(self, reason: str) -> None:
        self.start_calls = getattr(self, "start_calls", [])
        self.start_calls.append(reason)

    def rogue_has(self, _game, card_id: str) -> bool:
        return card_id == "quickthink" and getattr(self, "quickthink", False)

    def challenge_remaining(self, _game, kind: str) -> int:
        assert kind == "hint"
        return getattr(self, "hint_remaining", 1)

    async def sync_board_to_katago(self, game) -> None:
        if getattr(self, "sync_error", None) is not None:
            raise self.sync_error
        self.synced_games.append(game)


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
    assert load_ctx.engine.commands == []
    assert isinstance(load_ctx.analysis_calls[0], GoGame)
    assert load_ctx.analysis_calls[0].current_player == "B"
    assert load_ctx.synced_games == [load_ctx.game]
    assert load_ctx.sent == [{"type": "analysis", "analysis_ready": True, "moves": 2}]

    failing_analysis_ctx = FakeContext(SimpleNamespace())
    failing_analysis_ctx.analysis_error = RuntimeError("simulated analysis failure")
    try:
        await handle_load_position(
            failing_analysis_ctx,
            {"size": 9, "komi": 6.5, "moves": [("B", "E5")]},
        )
    except RuntimeError as exc:
        assert "analysis failure" in str(exc)
    else:
        raise AssertionError("analysis failure must propagate")
    assert failing_analysis_ctx.synced_games == [failing_analysis_ctx.game]

    failing_restore_ctx = FakeContext(SimpleNamespace())
    failing_restore_ctx.sync_error = RuntimeError("simulated restore failure")
    try:
        await handle_load_position(
            failing_restore_ctx,
            {"size": 9, "komi": 6.5, "moves": [("B", "E5")]},
        )
    except RuntimeError as exc:
        assert "restore failure" in str(exc)
    else:
        raise AssertionError("restore failure must propagate")
    assert failing_restore_ctx.engine.stopped is True
    assert failing_restore_ctx.engine.ready is False
    assert failing_restore_ctx.start_calls == ["load_position_restore"]

    bad_load_ctx = FakeContext(SimpleNamespace())
    await handle_load_position(
        bad_load_ctx,
        {
            "size": 9,
            "komi": 6.5,
            "moves": [("B", "A1\nquit")],
        },
    )
    assert bad_load_ctx.engine.commands == []
    assert bad_load_ctx.errors == ["复盘棋谱包含无效着手"]

    invalid_cases = [
        ({"size": 20, "komi": 6.5, "moves": []}, "复盘棋盘尺寸无效"),
        ({"size": 9, "komi": float("nan"), "moves": []}, "复盘贴目设置无效"),
        ({"size": 9, "komi": 6.5, "moves": "B E5"}, "复盘棋谱格式无效"),
        (
            {
                "size": 5,
                "komi": 6.5,
                "moves": [("W", "A2"), ("W", "B1"), ("B", "A1")],
            },
            "复盘棋谱包含非法着手",
        ),
    ]
    for payload, error in invalid_cases:
        invalid_ctx = FakeContext(SimpleNamespace())

        await handle_load_position(invalid_ctx, payload)

        assert invalid_ctx.engine.commands == []
        assert invalid_ctx.analysis_calls == []
        assert invalid_ctx.errors == [error]


async def smoke_engine_wait_exits_when_startup_is_cancelled() -> None:
    ctx = FakeContext(engine_ready=False)
    ctx.engine_snapshots = [
        {"phase": "idle", "message": "idle"},
        {"phase": "initializing", "message": "starting"},
        {"phase": "initializing", "message": "starting"},
        {"phase": "idle", "message": "cancelled"},
        {"phase": "idle", "message": "cancelled"},
    ]
    ctx.default_engine_snapshot = {"phase": "idle", "message": "cancelled"}

    ready = await wait_for_engine_ready(ctx, "game_start")

    assert ready is False
    assert ctx.start_calls == ["game_start"]
    assert [payload["type"] for payload in ctx.sent] == ["engine_not_ready", "engine_not_ready"]
    assert ctx.errors == ["cancelled"]


async def smoke_engine_claim_handoff_allows_only_one_waiter() -> None:
    engine = FakeEngine()
    old_token = object()
    engine.active_game_id = "old-owner"
    engine.active_game_connection_token = old_token
    engine.active_game_claimed_at = time.time() - 10
    engine.active_connection_tokens = set()
    owner_game = SimpleNamespace(game_over=False)
    first = FakeContext(owner_game)
    second = FakeContext(owner_game)
    for game_id, ctx in (("first-claim", first), ("second-claim", second)):
        ctx.game_id = game_id
        ctx.connection_token = object()
        ctx.engine = engine
        ctx.active_games = FakeActiveGames(owner_game)

    results = await asyncio.gather(claim_engine_session(first), claim_engine_session(second))

    assert sorted(results) == [False, True]
    assert engine.active_game_id in {"first-claim", "second-claim"}
    assert sum(len(ctx.errors) for ctx in (first, second)) == 1


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
    await smoke_engine_wait_exits_when_startup_is_cancelled()
    await smoke_engine_claim_handoff_allows_only_one_waiter()
    smoke_ws_action_handlers_keep_public_action_names()
    smoke_session_action_annotations_resolve_runtime_context()
    print("ws session actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
