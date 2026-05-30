from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.rogue_effects import RogueBoardEffectResult
from app.runtime.rogue_move_effect_adapters import (
    AiRogueResponseEffectBinding,
    PlayerRogueMoveEffectBinding,
    apply_ai_rogue_response_effects,
    apply_player_rogue_move_effects,
    build_ai_rogue_response_effect_deps,
    build_player_rogue_move_effect_deps,
)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def smoke_player_binding_maps_every_field() -> None:
    binding = PlayerRogueMoveEffectBinding(
        has_rogue=lambda _game, card: card == "erosion",
        erosion_shift=0.75,
        sync_engine_komi=fake_async,
        apply_board_effects=fake_sync,
        coord_to_gtp=fake_sync,
        gtp_to_coord=fake_sync,
        engine_ready=lambda: True,
        sync_board_to_katago=fake_async,
        challenge_apply_trap_bonus=fake_async,
        trigger_five_in_row=fake_async,
        trigger_last_stand=fake_async,
        challenge_maybe_reduce_ai_level=fake_async,
    )

    deps = build_player_rogue_move_effect_deps(binding)

    assert deps.has_rogue(None, "erosion") is True
    assert deps.has_rogue(None, "fog") is False
    assert deps.erosion_shift == 0.75
    assert deps.sync_engine_komi is fake_async
    assert deps.apply_board_effects is fake_sync
    assert deps.coord_to_gtp is fake_sync
    assert deps.gtp_to_coord is fake_sync
    assert deps.engine_ready() is True
    assert deps.sync_board_to_katago is fake_async
    assert deps.challenge_apply_trap_bonus is fake_async
    assert deps.trigger_five_in_row is fake_async
    assert deps.trigger_last_stand is fake_async
    assert deps.challenge_maybe_reduce_ai_level is fake_async


def smoke_ai_binding_maps_every_field() -> None:
    binding = AiRogueResponseEffectBinding(
        apply_board_effects=fake_sync,
        coord_to_gtp=fake_sync,
        shuffle_points=fake_sync,
        engine_ready=lambda: False,
        sync_board_to_katago=fake_async,
    )

    deps = build_ai_rogue_response_effect_deps(binding)

    assert deps.apply_board_effects is fake_sync
    assert deps.coord_to_gtp is fake_sync
    assert deps.shuffle_points is fake_sync
    assert deps.engine_ready() is False
    assert deps.sync_board_to_katago is fake_async


async def smoke_player_adapter_uses_binding_and_sends_events() -> None:
    game = SimpleNamespace(two_player=False, player_color="B", komi=7.5)
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def has_rogue(game_arg, card):
        calls.append(("has", game_arg is game, card))
        return card in {"erosion", "five_in_row"}

    async def sync_komi(game_arg):
        calls.append(("sync_komi", game_arg is game, game_arg.komi))

    def board_effects(game_arg, **kwargs):
        calls.append((
            "board",
            game_arg is game,
            kwargs["x"],
            kwargs["y"],
            kwargs["color"],
            kwargs["captured"],
        ))
        return RogueBoardEffectResult(True, ["board"], ["trap-source"])

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def trap(game_arg, send_fn, source):
        calls.append(("trap", game_arg is game, send_fn is send, source))
        await send_fn({"type": "rogue_event", "msg": "trap"})

    async def five(game_arg, send_fn, color):
        calls.append(("five", game_arg is game, send_fn is send, color))
        await send_fn({"type": "rogue_event", "msg": "five"})

    async def last(_game, _send, _color, _center):
        calls.append("last")

    async def reduce(game_arg, send_fn):
        calls.append(("reduce", game_arg is game, send_fn is send))
        await send_fn({"type": "rogue_event", "msg": "reduce"})

    await apply_player_rogue_move_effects(
        game,
        send,
        x=3,
        y=4,
        color="B",
        captured=2,
        binding=PlayerRogueMoveEffectBinding(
            has_rogue=has_rogue,
            erosion_shift=0.5,
            sync_engine_komi=sync_komi,
            apply_board_effects=board_effects,
            coord_to_gtp=fake_sync,
            gtp_to_coord=fake_sync,
            engine_ready=lambda: True,
            sync_board_to_katago=sync_board,
            challenge_apply_trap_bonus=trap,
            trigger_five_in_row=five,
            trigger_last_stand=last,
            challenge_maybe_reduce_ai_level=reduce,
        ),
    )

    assert game.komi == 6.5
    assert calls == [
        ("has", True, "erosion"),
        ("sync_komi", True, 6.5),
        ("board", True, 3, 4, "B", 2),
        ("sync_board", True),
        ("trap", True, True, "trap-source"),
        ("has", True, "five_in_row"),
        ("five", True, True, "B"),
        ("has", True, "last_stand"),
        ("reduce", True, True),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "蚕食触发：提掉 2 子，当前贴目变为 6.5"},
        {"type": "rogue_event", "msg": "board"},
        {"type": "rogue_event", "msg": "trap"},
        {"type": "rogue_event", "msg": "five"},
        {"type": "rogue_event", "msg": "reduce"},
    ]


async def smoke_ai_adapter_uses_binding_and_sends_events() -> None:
    game = SimpleNamespace()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def board_effects(game_arg, **kwargs):
        calls.append((
            "board",
            game_arg is game,
            kwargs["x"],
            kwargs["y"],
            kwargs["coord_to_gtp"] is fake_sync,
            kwargs["shuffle_points"] is fake_sync,
        ))
        return RogueBoardEffectResult(True, ["ai board"], [])

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    await apply_ai_rogue_response_effects(
        game,
        send,
        x=1,
        y=2,
        color="W",
        binding=AiRogueResponseEffectBinding(
            apply_board_effects=board_effects,
            coord_to_gtp=fake_sync,
            shuffle_points=fake_sync,
            engine_ready=lambda: True,
            sync_board_to_katago=sync_board,
        ),
    )

    assert calls == [("board", True, 1, 2, True, True), ("sync_board", True)]
    assert sent == [{"type": "rogue_event", "msg": "ai board"}]


async def smoke_server_wrappers_resolve_current_runtime() -> None:
    game = SimpleNamespace(two_player=False, player_color="B", komi=7.5)
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def has_rogue(game_arg, card):
        calls.append(("has", game_arg is game, card))
        return card == "erosion"

    async def sync_komi(game_arg):
        calls.append(("sync_komi", game_arg is game, game_arg.komi))

    def player_board(game_arg, **kwargs):
        calls.append((
            "player_board",
            game_arg is game,
            kwargs["coord_to_gtp"] is fake_sync,
            kwargs["gtp_to_coord"] is fake_sync,
        ))
        return RogueBoardEffectResult(False, ["player board"], [])

    def ai_board(game_arg, **kwargs):
        calls.append((
            "ai_board",
            game_arg is game,
            kwargs["coord_to_gtp"] is fake_sync,
            kwargs["shuffle_points"] is fake_sync,
        ))
        return RogueBoardEffectResult(True, ["ai board"], [])

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def trap(_game, _send, source):
        calls.append(("trap", source))

    async def five(_game, _send, color):
        calls.append(("five", color))

    async def last(_game, _send, color, center):
        calls.append(("last", color, center))

    async def reduce(game_arg, send_fn):
        calls.append(("reduce", game_arg is game, send_fn is send))

    originals = {
        "_rogue_has": s._rogue_has,
        "ROGUE_EROSION_SHIFT": s.ROGUE_EROSION_SHIFT,
        "_sync_engine_komi": s._sync_engine_komi,
        "apply_player_rogue_board_effects": s.apply_player_rogue_board_effects,
        "apply_ai_rogue_response_board_effects": s.apply_ai_rogue_response_board_effects,
        "coord_to_gtp": s.coord_to_gtp,
        "gtp_to_coord": s.gtp_to_coord,
        "engine_ready": s.engine.ready,
        "_sync_board_to_katago": s._sync_board_to_katago,
        "_challenge_apply_trap_bonus": s._challenge_apply_trap_bonus,
        "_trigger_rogue_five_in_row": s._trigger_rogue_five_in_row,
        "_trigger_rogue_last_stand": s._trigger_rogue_last_stand,
        "_challenge_maybe_reduce_ai_level": s._challenge_maybe_reduce_ai_level,
        "random_shuffle": s.random.shuffle,
    }

    try:
        s._rogue_has = has_rogue
        s.ROGUE_EROSION_SHIFT = 0.25
        s._sync_engine_komi = sync_komi
        s.apply_player_rogue_board_effects = player_board
        s.apply_ai_rogue_response_board_effects = ai_board
        s.coord_to_gtp = fake_sync
        s.gtp_to_coord = fake_sync
        s.engine.ready = True
        s._sync_board_to_katago = sync_board
        s._challenge_apply_trap_bonus = trap
        s._trigger_rogue_five_in_row = five
        s._trigger_rogue_last_stand = last
        s._challenge_maybe_reduce_ai_level = reduce
        s.random.shuffle = fake_sync

        player_binding = s._player_rogue_move_effect_binding()
        player_deps = build_player_rogue_move_effect_deps(player_binding)
        ai_binding = s._ai_rogue_response_effect_binding()
        ai_deps = build_ai_rogue_response_effect_deps(ai_binding)

        assert player_binding.has_rogue is has_rogue
        assert player_binding.erosion_shift == 0.25
        assert player_binding.sync_engine_komi is sync_komi
        assert player_deps.apply_board_effects is player_board
        assert player_deps.coord_to_gtp is fake_sync
        assert player_deps.gtp_to_coord is fake_sync
        assert player_deps.engine_ready() is True
        assert player_deps.sync_board_to_katago is sync_board
        assert player_deps.challenge_apply_trap_bonus is trap
        assert player_deps.trigger_five_in_row is five
        assert player_deps.trigger_last_stand is last
        assert player_deps.challenge_maybe_reduce_ai_level is reduce
        assert ai_binding.apply_board_effects is ai_board
        assert ai_deps.coord_to_gtp is fake_sync
        assert ai_deps.shuffle_points is fake_sync
        assert ai_deps.engine_ready() is True
        assert ai_deps.sync_board_to_katago is sync_board

        await s._apply_player_rogue_move_effects(game, send, 4, 5, "B", 4)
        await s._apply_ai_rogue_response_effects(game, send, 6, 7, "W")
    finally:
        s._rogue_has = originals["_rogue_has"]
        s.ROGUE_EROSION_SHIFT = originals["ROGUE_EROSION_SHIFT"]
        s._sync_engine_komi = originals["_sync_engine_komi"]
        s.apply_player_rogue_board_effects = originals["apply_player_rogue_board_effects"]
        s.apply_ai_rogue_response_board_effects = originals["apply_ai_rogue_response_board_effects"]
        s.coord_to_gtp = originals["coord_to_gtp"]
        s.gtp_to_coord = originals["gtp_to_coord"]
        s.engine.ready = originals["engine_ready"]
        s._sync_board_to_katago = originals["_sync_board_to_katago"]
        s._challenge_apply_trap_bonus = originals["_challenge_apply_trap_bonus"]
        s._trigger_rogue_five_in_row = originals["_trigger_rogue_five_in_row"]
        s._trigger_rogue_last_stand = originals["_trigger_rogue_last_stand"]
        s._challenge_maybe_reduce_ai_level = originals["_challenge_maybe_reduce_ai_level"]
        s.random.shuffle = originals["random_shuffle"]

    assert game.komi == 6.5
    assert calls == [
        ("has", True, "erosion"),
        ("sync_komi", True, 6.5),
        ("player_board", True, True, True),
        ("has", True, "five_in_row"),
        ("has", True, "last_stand"),
        ("reduce", True, True),
        ("ai_board", True, True, True),
        ("sync_board", True),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "蚕食触发：提掉 4 子，当前贴目变为 6.5"},
        {"type": "rogue_event", "msg": "player board"},
        {"type": "rogue_event", "msg": "ai board"},
    ]


async def main() -> None:
    smoke_player_binding_maps_every_field()
    smoke_ai_binding_maps_every_field()
    await smoke_player_adapter_uses_binding_and_sends_events()
    await smoke_ai_adapter_uses_binding_and_sends_events()
    await smoke_server_wrappers_resolve_current_runtime()
    print("rogue move effect adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
