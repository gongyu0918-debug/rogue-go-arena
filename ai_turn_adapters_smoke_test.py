from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.ai_turn_adapters import (
    AiTurnBinding,
    build_ai_turn_flow_deps,
    run_ai_turn,
)


class DummyGame:
    def __init__(self, *, game_over: bool = False) -> None:
        self.game_over = game_over


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def smoke_binding_maps_every_field() -> None:
    binding = AiTurnBinding(
        engine_ready=lambda: True,
        sync_board_to_katago=fake_async,
        snapshot_turn=fake_sync,
        try_finish_forced=fake_async,
        plan_search=fake_sync,
        refresh_fog_restriction=fake_async,
        try_finish_restriction=fake_async,
        try_finish_shadow=fake_async,
        try_finish_suboptimal=fake_async,
        try_finish_generated=fake_async,
    )

    deps = build_ai_turn_flow_deps(binding)

    assert deps.engine_ready() is True
    assert deps.sync_board_to_katago is fake_async
    assert deps.snapshot_turn is fake_sync
    assert deps.try_finish_forced is fake_async
    assert deps.plan_search is fake_sync
    assert deps.refresh_fog_restriction is fake_async
    assert deps.try_finish_restriction is fake_async
    assert deps.try_finish_shadow is fake_async
    assert deps.try_finish_suboptimal is fake_async
    assert deps.try_finish_generated is fake_async


async def smoke_adapter_preserves_full_turn_order() -> None:
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

    await run_ai_turn(
        game,
        send,
        AiTurnBinding(
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
        ),
    )

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


async def smoke_adapter_preserves_engine_guard() -> None:
    calls = []

    async def sync_board(_game):
        calls.append("sync")

    binding = AiTurnBinding(
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

    await run_ai_turn(DummyGame(game_over=True), lambda _payload: None, binding)
    assert calls == []

    guarded = AiTurnBinding(
        **{**binding.__dict__, "engine_ready": lambda: False}
    )
    await run_ai_turn(DummyGame(), lambda _payload: None, guarded)
    assert calls == []


async def smoke_server_binding_resolves_current_runtime() -> None:
    game = DummyGame()
    sent = []
    calls = []
    turn = SimpleNamespace(rogue_cards={"fog"}, move_count=5, ai_move_count=2)
    plan = SimpleNamespace(visits=321, time_limit=6.0)

    async def send(payload):
        sent.append(payload)

    def rogue_ids():
        calls.append(("rogue_ids",))
        return ["patched-card"]

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def snapshot(game_arg, rogue_ids_fn):
        calls.append(("snapshot", game_arg is game, rogue_ids_fn is rogue_ids, rogue_ids_fn()))
        return turn

    def plan_search(game_arg, turn_arg):
        calls.append(("plan", game_arg is game, turn_arg is turn))
        return plan

    async def fog(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("fog", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))

    async def command(command_text):
        calls.append(("command", command_text))
        return "= ok"

    async def forced(game_arg, send_fn, turn_arg, run_engine_command):
        calls.append(("forced", game_arg is game, send_fn is send, turn_arg is turn))
        await run_engine_command("forced command")
        return False

    async def restriction(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
        calls.append(("restriction", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        await run_engine_command("restriction command")
        return False

    async def shadow(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("shadow", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def suboptimal(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("suboptimal", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def generated(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
        calls.append(("generated", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        await run_engine_command("generated command")
        await send_fn({"type": "ai_move", "gtp": "Q16"})
        return True

    originals = {
        "engine_ready": s.engine.ready,
        "_sync_board_to_katago": s._sync_board_to_katago,
        "snapshot_ai_turn": s.snapshot_ai_turn,
        "_rogue_card_ids": s._rogue_card_ids,
        "_try_finish_forced_rogue_ai_turn": s._try_finish_forced_rogue_ai_turn,
        "_plan_ai_turn_search": s._plan_ai_turn_search,
        "_refresh_ai_turn_fog_restriction": s._refresh_ai_turn_fog_restriction,
        "_try_finish_rogue_restriction_ai_turn": s._try_finish_rogue_restriction_ai_turn,
        "_try_finish_shadow_rogue_ai_turn": s._try_finish_shadow_rogue_ai_turn,
        "_try_finish_suboptimal_rogue_ai_turn": s._try_finish_suboptimal_rogue_ai_turn,
        "_try_finish_generated_ai_turn": s._try_finish_generated_ai_turn,
        "_send_engine_command": s._send_engine_command,
    }
    try:
        s.engine.ready = True
        s._sync_board_to_katago = sync_board
        s.snapshot_ai_turn = snapshot
        s._rogue_card_ids = rogue_ids
        s._try_finish_forced_rogue_ai_turn = forced
        s._plan_ai_turn_search = plan_search
        s._refresh_ai_turn_fog_restriction = fog
        s._try_finish_rogue_restriction_ai_turn = restriction
        s._try_finish_shadow_rogue_ai_turn = shadow
        s._try_finish_suboptimal_rogue_ai_turn = suboptimal
        s._try_finish_generated_ai_turn = generated
        s._send_engine_command = command

        binding = s._ai_turn_binding()
        deps = s._ai_turn_flow_deps()

        assert binding.engine_ready() is True
        assert deps.sync_board_to_katago is sync_board
        assert deps.plan_search is plan_search
        assert deps.refresh_fog_restriction is fog
        assert deps.try_finish_shadow is shadow
        assert deps.try_finish_suboptimal is suboptimal

        await s._ai_move(game, send)
    finally:
        s.engine.ready = originals["engine_ready"]
        s._sync_board_to_katago = originals["_sync_board_to_katago"]
        s.snapshot_ai_turn = originals["snapshot_ai_turn"]
        s._rogue_card_ids = originals["_rogue_card_ids"]
        s._try_finish_forced_rogue_ai_turn = originals["_try_finish_forced_rogue_ai_turn"]
        s._plan_ai_turn_search = originals["_plan_ai_turn_search"]
        s._refresh_ai_turn_fog_restriction = originals["_refresh_ai_turn_fog_restriction"]
        s._try_finish_rogue_restriction_ai_turn = originals["_try_finish_rogue_restriction_ai_turn"]
        s._try_finish_shadow_rogue_ai_turn = originals["_try_finish_shadow_rogue_ai_turn"]
        s._try_finish_suboptimal_rogue_ai_turn = originals["_try_finish_suboptimal_rogue_ai_turn"]
        s._try_finish_generated_ai_turn = originals["_try_finish_generated_ai_turn"]
        s._send_engine_command = originals["_send_engine_command"]

    assert calls == [
        ("sync", True),
        ("rogue_ids",),
        ("snapshot", True, True, ["patched-card"]),
        ("forced", True, True, True),
        ("command", "forced command"),
        ("plan", True, True),
        ("fog", True, True, True, True),
        ("restriction", True, True, True, True),
        ("command", "restriction command"),
        ("shadow", True, True, True, True),
        ("suboptimal", True, True, True, True),
        ("generated", True, True, True, True),
        ("command", "generated command"),
    ]
    assert sent == [{"type": "ai_move", "gtp": "Q16"}]


async def main() -> None:
    smoke_binding_maps_every_field()
    await smoke_adapter_preserves_full_turn_order()
    await smoke_adapter_preserves_engine_guard()
    await smoke_server_binding_resolves_current_runtime()
    print("ai turn adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
