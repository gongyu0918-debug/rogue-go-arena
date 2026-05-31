from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

from app.gameplay.ai_turn_flow import AiTurnFlowDeps, run_ai_turn


class DummyGame:
    def __init__(self, *, game_over: bool = False) -> None:
        self.game_over = game_over


async def smoke_guard_skips_when_game_over_or_engine_not_ready() -> None:
    calls = []

    async def sync_board(_game):
        calls.append("sync")

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=lambda _game: calls.append("snapshot"),
        try_finish_forced=lambda *_args: calls.append("forced"),
        plan_search=lambda *_args: calls.append("plan"),
        refresh_fog_restriction=lambda *_args: calls.append("fog"),
        try_finish_restriction=lambda *_args: calls.append("restriction"),
        try_finish_shadow=lambda *_args: calls.append("shadow"),
        try_finish_suboptimal=lambda *_args: calls.append("suboptimal"),
        try_finish_generated=lambda *_args: calls.append("generated"),
    )

    await run_ai_turn(DummyGame(game_over=True), lambda _payload: None, deps)
    assert calls == []

    deps = AiTurnFlowDeps(
        **{**deps.__dict__, "engine_ready": lambda: False}
    )
    await run_ai_turn(DummyGame(), lambda _payload: None, deps)
    assert calls == []


async def smoke_full_order_reaches_generated_move() -> None:
    game = DummyGame()
    sent = []
    calls = []
    turn = SimpleNamespace(rogue_cards={"fog"}, move_count=3, ai_move_count=1)
    plan = SimpleNamespace(visits=123, time_limit=4.5)

    async def send(payload):
        sent.append(payload)

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def snapshot(game_arg):
        calls.append(("snapshot", game_arg is game))
        return turn

    async def forced(game_arg, send_fn, turn_arg):
        calls.append(("forced", game_arg is game, send_fn is send, turn_arg is turn))
        return False

    def plan_search(game_arg, turn_arg):
        calls.append(("plan", game_arg is game, turn_arg is turn))
        return plan

    async def fog(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("fog", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))

    async def restriction(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("restriction", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def shadow(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("shadow", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def suboptimal(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("suboptimal", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def generated(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("generated", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=snapshot,
        try_finish_forced=forced,
        plan_search=plan_search,
        refresh_fog_restriction=fog,
        try_finish_restriction=restriction,
        try_finish_shadow=shadow,
        try_finish_suboptimal=suboptimal,
        try_finish_generated=generated,
    )

    await run_ai_turn(game, send, deps)

    assert calls == [
        ("sync", True),
        ("snapshot", True),
        ("forced", True, True, True),
        ("plan", True, True),
        ("fog", True, True, True, True),
        ("restriction", True, True, True, True),
        ("shadow", True, True, True, True),
        ("suboptimal", True, True, True, True),
        ("generated", True, True, True, True),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_short_circuits_before_plan_when_forced_finishes() -> None:
    game = DummyGame()
    calls = []

    async def send(_payload):
        calls.append("send")

    async def sync_board(_game):
        calls.append("sync")

    def snapshot(_game):
        calls.append("snapshot")
        return SimpleNamespace()

    async def forced(_game, _send, _turn):
        calls.append("forced")
        return True

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=snapshot,
        try_finish_forced=forced,
        plan_search=lambda *_args: calls.append("plan"),
        refresh_fog_restriction=lambda *_args: calls.append("fog"),
        try_finish_restriction=lambda *_args: calls.append("restriction"),
        try_finish_shadow=lambda *_args: calls.append("shadow"),
        try_finish_suboptimal=lambda *_args: calls.append("suboptimal"),
        try_finish_generated=lambda *_args: calls.append("generated"),
    )

    await run_ai_turn(game, send, deps)

    assert calls == ["sync", "snapshot", "forced"]


async def smoke_short_circuits_after_restriction_finishes() -> None:
    game = DummyGame()
    calls = []

    async def sync_board(_game):
        calls.append("sync")

    async def forced(_game, _send, _turn):
        calls.append("forced")
        return False

    async def fog(_game, _send, _turn, _plan):
        calls.append("fog")

    async def restriction(_game, _send, _turn, _plan):
        calls.append("restriction")
        return True

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=lambda _game: calls.append("snapshot") or SimpleNamespace(),
        try_finish_forced=forced,
        plan_search=lambda *_args: calls.append("plan") or SimpleNamespace(),
        refresh_fog_restriction=fog,
        try_finish_restriction=restriction,
        try_finish_shadow=lambda *_args: calls.append("shadow"),
        try_finish_suboptimal=lambda *_args: calls.append("suboptimal"),
        try_finish_generated=lambda *_args: calls.append("generated"),
    )

    await run_ai_turn(game, lambda _payload: None, deps)

    assert calls == ["sync", "snapshot", "forced", "plan", "fog", "restriction"]


async def smoke_short_circuits_after_shadow_finishes() -> None:
    game = DummyGame()
    calls = []

    async def sync_board(_game):
        calls.append("sync")

    async def forced(_game, _send, _turn):
        calls.append("forced")
        return False

    async def fog(_game, _send, _turn, _plan):
        calls.append("fog")

    async def restriction(_game, _send, _turn, _plan):
        calls.append("restriction")
        return False

    async def shadow(_game, _send, _turn, _plan):
        calls.append("shadow")
        return True

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=lambda _game: calls.append("snapshot") or SimpleNamespace(),
        try_finish_forced=forced,
        plan_search=lambda *_args: calls.append("plan") or SimpleNamespace(),
        refresh_fog_restriction=fog,
        try_finish_restriction=restriction,
        try_finish_shadow=shadow,
        try_finish_suboptimal=lambda *_args: calls.append("suboptimal"),
        try_finish_generated=lambda *_args: calls.append("generated"),
    )

    await run_ai_turn(game, lambda _payload: None, deps)

    assert calls == ["sync", "snapshot", "forced", "plan", "fog", "restriction", "shadow"]


async def smoke_short_circuits_after_suboptimal_finishes() -> None:
    game = DummyGame()
    calls = []

    async def sync_board(_game):
        calls.append("sync")

    async def forced(_game, _send, _turn):
        calls.append("forced")
        return False

    async def fog(_game, _send, _turn, _plan):
        calls.append("fog")

    async def restriction(_game, _send, _turn, _plan):
        calls.append("restriction")
        return False

    async def shadow(_game, _send, _turn, _plan):
        calls.append("shadow")
        return False

    async def suboptimal(_game, _send, _turn, _plan):
        calls.append("suboptimal")
        return True

    deps = AiTurnFlowDeps(
        engine_ready=lambda: True,
        sync_board_to_katago=sync_board,
        snapshot_turn=lambda _game: calls.append("snapshot") or SimpleNamespace(),
        try_finish_forced=forced,
        plan_search=lambda *_args: calls.append("plan") or SimpleNamespace(),
        refresh_fog_restriction=fog,
        try_finish_restriction=restriction,
        try_finish_shadow=shadow,
        try_finish_suboptimal=suboptimal,
        try_finish_generated=lambda *_args: calls.append("generated"),
    )

    await run_ai_turn(game, lambda _payload: None, deps)

    assert calls == [
        "sync",
        "snapshot",
        "forced",
        "plan",
        "fog",
        "restriction",
        "shadow",
        "suboptimal",
    ]


async def main() -> None:
    await smoke_guard_skips_when_game_over_or_engine_not_ready()
    await smoke_full_order_reaches_generated_move()
    await smoke_short_circuits_before_plan_when_forced_finishes()
    await smoke_short_circuits_after_restriction_finishes()
    await smoke_short_circuits_after_shadow_finishes()
    await smoke_short_circuits_after_suboptimal_finishes()
    print("ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
