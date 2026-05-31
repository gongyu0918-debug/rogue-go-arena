from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.ai_turn_adapters import (
    AiTurnBinding,
    build_ai_turn_flow_deps,
    run_ai_turn,
)
from app.runtime.ai_turn_runtime import (
    AiTurnDependencies,
    AiTurnRuntimeFns,
    AiTurnStepFns,
    build_ai_turn_binding,
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


async def smoke_runtime_builder_groups_turn_dependencies() -> None:
    game = DummyGame()
    sent = []
    calls = []
    turn = SimpleNamespace(rogue_cards={"suboptimal"}, move_count=4, ai_move_count=2)
    plan = SimpleNamespace(visits=456, time_limit=7.5)

    async def send(payload):
        sent.append(payload)

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def rogue_ids():
        calls.append(("rogue_ids",))
        return ["runtime-card"]

    def snapshot(game_arg, rogue_ids_fn):
        calls.append(("snapshot", game_arg is game, rogue_ids_fn is rogue_ids, rogue_ids_fn()))
        return turn

    async def run_engine(command: str):
        calls.append(("engine", command))
        return "= ok"

    async def forced(game_arg, send_fn, turn_arg, run_engine_command):
        calls.append(("forced", game_arg is game, send_fn is send, turn_arg is turn))
        await run_engine_command("forced")
        return False

    def plan_search(game_arg, turn_arg):
        calls.append(("plan", game_arg is game, turn_arg is turn))
        return plan

    async def fog(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("fog", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))

    async def restriction(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
        calls.append(("restriction", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        await run_engine_command("restriction")
        return False

    async def shadow(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("shadow", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def suboptimal(game_arg, send_fn, turn_arg, plan_arg):
        calls.append(("suboptimal", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        return False

    async def generated(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
        calls.append(("generated", game_arg is game, send_fn is send, turn_arg is turn, plan_arg is plan))
        await run_engine_command("generated")
        await send_fn({"type": "ai_move", "gtp": "D16"})
        return True

    binding = build_ai_turn_binding(
        AiTurnDependencies(
            runtime=AiTurnRuntimeFns(
                engine_ready=lambda: True,
                sync_board_to_katago=sync_board,
                snapshot_ai_turn=snapshot,
                rogue_card_ids=rogue_ids,
                run_engine_command=run_engine,
            ),
            steps=AiTurnStepFns(
                try_finish_forced=forced,
                plan_search=plan_search,
                refresh_fog_restriction=fog,
                try_finish_restriction=restriction,
                try_finish_shadow=shadow,
                try_finish_suboptimal=suboptimal,
                try_finish_generated=generated,
            ),
        )
    )

    deps = build_ai_turn_flow_deps(binding)
    assert deps.engine_ready() is True
    assert deps.sync_board_to_katago is sync_board
    assert deps.plan_search is plan_search
    assert deps.refresh_fog_restriction is fog
    assert deps.try_finish_shadow is shadow
    assert deps.try_finish_suboptimal is suboptimal

    await run_ai_turn(game, send, binding)

    assert calls == [
        ("sync", True),
        ("rogue_ids",),
        ("snapshot", True, True, ["runtime-card"]),
        ("forced", True, True, True),
        ("engine", "forced"),
        ("plan", True, True),
        ("fog", True, True, True, True),
        ("restriction", True, True, True, True),
        ("engine", "restriction"),
        ("shadow", True, True, True, True),
        ("suboptimal", True, True, True, True),
        ("generated", True, True, True, True),
        ("engine", "generated"),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D16"}]


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
        deps = build_ai_turn_flow_deps(binding)

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


async def smoke_server_binding_preserves_late_bound_wrappers() -> None:
    game = DummyGame()
    turn = SimpleNamespace(rogue_cards=set(), move_count=1, ai_move_count=0)
    plan = SimpleNamespace(visits=50, time_limit=1.0)
    calls = []

    async def send(_payload):
        return None

    def old_rogue_ids():
        calls.append(("old_rogue_ids",))
        return ["old-card"]

    def old_snapshot(_game, _rogue_ids_fn):
        calls.append(("old_snapshot",))
        return None

    async def old_command(_command_text):
        calls.append(("old_command",))
        return "= old"

    async def old_forced(*_args, **_kwargs):
        calls.append(("old_forced",))
        return False

    async def old_restriction(*_args, **_kwargs):
        calls.append(("old_restriction",))
        return False

    async def old_generated(*_args, **_kwargs):
        calls.append(("old_generated",))
        return False

    originals = {
        "snapshot_ai_turn": s.snapshot_ai_turn,
        "_rogue_card_ids": s._rogue_card_ids,
        "_try_finish_forced_rogue_ai_turn": s._try_finish_forced_rogue_ai_turn,
        "_try_finish_rogue_restriction_ai_turn": s._try_finish_rogue_restriction_ai_turn,
        "_try_finish_generated_ai_turn": s._try_finish_generated_ai_turn,
        "_send_engine_command": s._send_engine_command,
    }
    try:
        s.snapshot_ai_turn = old_snapshot
        s._rogue_card_ids = old_rogue_ids
        s._try_finish_forced_rogue_ai_turn = old_forced
        s._try_finish_rogue_restriction_ai_turn = old_restriction
        s._try_finish_generated_ai_turn = old_generated
        s._send_engine_command = old_command
        binding = s._ai_turn_binding()

        def new_rogue_ids():
            calls.append(("new_rogue_ids",))
            return ["new-card"]

        def new_snapshot(game_arg, rogue_ids_fn):
            calls.append(("new_snapshot", game_arg is game, rogue_ids_fn is new_rogue_ids, rogue_ids_fn()))
            return turn

        async def new_command(command_text):
            calls.append(("new_command", command_text))
            return "= new"

        async def new_forced(game_arg, send_fn, turn_arg, run_engine_command):
            calls.append((
                "new_forced",
                game_arg is game,
                send_fn is send,
                turn_arg is turn,
                run_engine_command is new_command,
            ))
            await run_engine_command("forced-after-binding")
            return False

        async def new_restriction(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
            calls.append((
                "new_restriction",
                game_arg is game,
                send_fn is send,
                turn_arg is turn,
                plan_arg is plan,
                run_engine_command is new_command,
            ))
            await run_engine_command("restriction-after-binding")
            return False

        async def new_generated(game_arg, send_fn, turn_arg, plan_arg, run_engine_command):
            calls.append((
                "new_generated",
                game_arg is game,
                send_fn is send,
                turn_arg is turn,
                plan_arg is plan,
                run_engine_command is new_command,
            ))
            await run_engine_command("generated-after-binding")
            return True

        s.snapshot_ai_turn = new_snapshot
        s._rogue_card_ids = new_rogue_ids
        s._try_finish_forced_rogue_ai_turn = new_forced
        s._try_finish_rogue_restriction_ai_turn = new_restriction
        s._try_finish_generated_ai_turn = new_generated
        s._send_engine_command = new_command

        assert binding.snapshot_turn(game) is turn
        assert await binding.try_finish_forced(game, send, turn) is False
        assert await binding.try_finish_restriction(game, send, turn, plan) is False
        assert await binding.try_finish_generated(game, send, turn, plan) is True
    finally:
        s.snapshot_ai_turn = originals["snapshot_ai_turn"]
        s._rogue_card_ids = originals["_rogue_card_ids"]
        s._try_finish_forced_rogue_ai_turn = originals["_try_finish_forced_rogue_ai_turn"]
        s._try_finish_rogue_restriction_ai_turn = originals["_try_finish_rogue_restriction_ai_turn"]
        s._try_finish_generated_ai_turn = originals["_try_finish_generated_ai_turn"]
        s._send_engine_command = originals["_send_engine_command"]

    assert calls == [
        ("new_rogue_ids",),
        ("new_snapshot", True, True, ["new-card"]),
        ("new_forced", True, True, True, True),
        ("new_command", "forced-after-binding"),
        ("new_restriction", True, True, True, True, True),
        ("new_command", "restriction-after-binding"),
        ("new_generated", True, True, True, True, True),
        ("new_command", "generated-after-binding"),
    ]


async def main() -> None:
    smoke_binding_maps_every_field()
    await smoke_runtime_builder_groups_turn_dependencies()
    await smoke_adapter_preserves_full_turn_order()
    await smoke_adapter_preserves_engine_guard()
    await smoke_server_binding_resolves_current_runtime()
    await smoke_server_binding_preserves_late_bound_wrappers()
    print("ai turn adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
