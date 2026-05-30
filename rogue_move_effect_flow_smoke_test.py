from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.gameplay.rogue_move_effect_flow import (
    AiRogueResponseEffectDeps,
    PlayerRogueMoveEffectDeps,
    apply_ai_rogue_response_effects_event,
    apply_player_rogue_move_effects_event,
)


class DummyGame:
    def __init__(self) -> None:
        self.two_player = False
        self.player_color = "B"
        self.komi = 7.5


async def smoke_player_flow_preserves_effect_order() -> None:
    game = DummyGame()
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    def has_rogue(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return card_id in {"erosion", "five_in_row", "last_stand"}

    async def sync_komi(game_arg):
        calls.append(("sync_komi", game_arg is game, game_arg.komi))

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return "D4"

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (1, 2)

    def apply_board_effects(game_arg, **kwargs):
        calls.append((
            "board",
            game_arg is game,
            kwargs["x"],
            kwargs["y"],
            kwargs["color"],
            kwargs["captured"],
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["gtp_to_coord"] is gtp_to_coord,
        ))
        kwargs["coord_to_gtp"](2, 3, 9)
        kwargs["gtp_to_coord"]("D4", 9)
        return SimpleNamespace(
            modified=True,
            messages=["board message"],
            trap_bonus_sources=["神之一手"],
        )

    def engine_ready():
        calls.append(("engine_ready",))
        return True

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def trap_bonus(game_arg, send_fn, source):
        calls.append(("trap", game_arg is game, send_fn is send, source))
        await send_fn({"type": "rogue_event", "msg": f"trap {source}"})

    async def five(game_arg, send_fn, color):
        calls.append(("five", game_arg is game, send_fn is send, color))
        await send_fn({"type": "rogue_event", "msg": "five"})

    async def last(game_arg, send_fn, color, center):
        calls.append(("last", game_arg is game, send_fn is send, color, center))
        await send_fn({"type": "rogue_event", "msg": "last"})

    async def reduce(game_arg, send_fn):
        calls.append(("reduce", game_arg is game, send_fn is send))
        await send_fn({"type": "rogue_event", "msg": "reduce"})

    deps = PlayerRogueMoveEffectDeps(
        has_rogue=has_rogue,
        erosion_shift=0.5,
        sync_engine_komi=sync_komi,
        apply_board_effects=apply_board_effects,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
        engine_ready=engine_ready,
        sync_board_to_katago=sync_board,
        challenge_apply_trap_bonus=trap_bonus,
        trigger_five_in_row=five,
        trigger_last_stand=last,
        challenge_maybe_reduce_ai_level=reduce,
    )

    await apply_player_rogue_move_effects_event(
        game,
        send,
        x=2,
        y=3,
        color="B",
        captured=2,
        deps=deps,
    )

    assert game.komi == 6.5
    assert calls == [
        ("has", True, "erosion"),
        ("sync_komi", True, 6.5),
        ("board", True, 2, 3, "B", 2, True, True),
        ("coord", 2, 3, 9),
        ("gtp", "D4", 9),
        ("engine_ready",),
        ("sync_board", True),
        ("trap", True, True, "神之一手"),
        ("has", True, "five_in_row"),
        ("five", True, True, "B"),
        ("has", True, "last_stand"),
        ("last", True, True, "B", (2, 3)),
        ("reduce", True, True),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "蚕食触发：提掉 2 子，当前贴目变为 6.5"},
        {"type": "rogue_event", "msg": "board message"},
        {"type": "rogue_event", "msg": "trap 神之一手"},
        {"type": "rogue_event", "msg": "five"},
        {"type": "rogue_event", "msg": "last"},
        {"type": "rogue_event", "msg": "reduce"},
    ]


async def smoke_player_flow_skips_board_sync_when_engine_not_ready() -> None:
    game = DummyGame()
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    async def unused_sync_komi(_game):
        calls.append("sync_komi")

    def apply_board_effects(_game, **_kwargs):
        return SimpleNamespace(
            modified=True,
            messages=["changed"],
            trap_bonus_sources=[],
        )

    async def sync_board(_game):
        calls.append("sync_board")

    async def unused_trap_bonus(_game, _send, _source):
        calls.append("trap")

    async def unused_five(_game, _send, _color):
        calls.append("five")

    async def unused_last(_game, _send, _color, _center):
        calls.append("last")

    async def reduce(_game, _send):
        calls.append("reduce")

    deps = PlayerRogueMoveEffectDeps(
        has_rogue=lambda _game, _card: False,
        erosion_shift=0.5,
        sync_engine_komi=unused_sync_komi,
        apply_board_effects=apply_board_effects,
        coord_to_gtp=lambda *_args: "A1",
        gtp_to_coord=lambda *_args: (0, 0),
        engine_ready=lambda: False,
        sync_board_to_katago=sync_board,
        challenge_apply_trap_bonus=unused_trap_bonus,
        trigger_five_in_row=unused_five,
        trigger_last_stand=unused_last,
        challenge_maybe_reduce_ai_level=reduce,
    )

    await apply_player_rogue_move_effects_event(
        game,
        send,
        x=0,
        y=0,
        color="B",
        captured=0,
        deps=deps,
    )

    assert calls == ["reduce"]
    assert sent == [{"type": "rogue_event", "msg": "changed"}]


async def smoke_ai_response_flow_syncs_and_sends_messages() -> None:
    game = DummyGame()
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return "C3"

    def shuffle_points(points):
        calls.append(("shuffle", list(points)))

    def apply_board_effects(game_arg, **kwargs):
        calls.append((
            "ai_board",
            game_arg is game,
            kwargs["x"],
            kwargs["y"],
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["shuffle_points"] is shuffle_points,
        ))
        kwargs["coord_to_gtp"](2, 2, 9)
        kwargs["shuffle_points"]([(1, 1)])
        return SimpleNamespace(modified=True, messages=["ai message"])

    def engine_ready():
        calls.append(("engine_ready",))
        return True

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    deps = AiRogueResponseEffectDeps(
        apply_board_effects=apply_board_effects,
        coord_to_gtp=coord_to_gtp,
        shuffle_points=shuffle_points,
        engine_ready=engine_ready,
        sync_board_to_katago=sync_board,
    )

    await apply_ai_rogue_response_effects_event(
        game,
        send,
        x=2,
        y=2,
        color="B",
        deps=deps,
    )

    assert calls == [
        ("ai_board", True, 2, 2, True, True),
        ("coord", 2, 2, 9),
        ("shuffle", [(1, 1)]),
        ("engine_ready",),
        ("sync_board", True),
    ]
    assert sent == [{"type": "rogue_event", "msg": "ai message"}]


async def main() -> None:
    await smoke_player_flow_preserves_effect_order()
    await smoke_player_flow_skips_board_sync_when_engine_not_ready()
    await smoke_ai_response_flow_syncs_and_sends_messages()
    print("rogue move effect flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
