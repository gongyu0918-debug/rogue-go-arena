from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.forced_rogue_ai_turn_flow import (
    ForcedRogueAiTurnDeps,
    try_finish_forced_rogue_ai_turn_event,
)


async def smoke_forced_flow_injects_turn_and_runtime_deps() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="W",
        card="mirror",
        rogue_cards={"dice", "mirror"},
    )

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    def roll_random():
        calls.append(("roll",))
        return 0.25

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (1, 2)

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return "D4"

    def mirror_coord(x, y, size):
        calls.append(("mirror", x, y, size))
        return (7, 6)

    def prepare_modifiers(game_arg):
        calls.append(("prepare", game_arg is game))

    async def forced_pass(game_arg, send_fn, **kwargs):
        calls.append(("pass", game_arg is game, send_fn is send, kwargs["run_engine_command"] is run_engine))

    async def forced_stone(game_arg, send_fn, **kwargs):
        calls.append(("stone", game_arg is game, send_fn is send, kwargs["run_engine_command"] is run_engine))
        return True

    async def puppet(game_arg, send_fn, **kwargs):
        calls.append(("puppet", game_arg is game, send_fn is send, kwargs["run_engine_command"] is run_engine))
        return True

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg=None):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    async def try_finish(game_arg, send_fn, **kwargs):
        calls.append((
            "try",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["roll_random"] is roll_random,
            kwargs["dice_pass_chance"],
            kwargs["mirror_chance"],
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["mirror_coord"] is mirror_coord,
            kwargs["prepare_player_turn_modifiers"] is prepare_modifiers,
            kwargs["run_engine_command"] is run_engine,
            kwargs["finalize_forced_pass"] is forced_pass,
            kwargs["finalize_forced_stone"] is forced_stone,
            kwargs["apply_puppet_move"] is puppet,
            kwargs["finish_ai_move"] is finish_ai_move,
        ))
        kwargs["roll_random"]()
        kwargs["gtp_to_coord"]("C3", 9)
        kwargs["coord_to_gtp"](3, 3, 9)
        kwargs["mirror_coord"](1, 2, 9)
        kwargs["prepare_player_turn_modifiers"](game_arg)
        await kwargs["finalize_forced_pass"](game_arg, send_fn, run_engine_command=kwargs["run_engine_command"])
        await kwargs["finalize_forced_stone"](game_arg, send_fn, run_engine_command=kwargs["run_engine_command"])
        await kwargs["apply_puppet_move"](game_arg, send_fn, run_engine_command=kwargs["run_engine_command"])
        await kwargs["finish_ai_move"](game_arg, send_fn, kwargs["color"], kwargs["card"], "D4", "forced")
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = ForcedRogueAiTurnDeps(
        try_finish_forced_rogue_ai_move=try_finish,
        roll_random=roll_random,
        dice_pass_chance=0.5,
        mirror_chance=0.75,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        mirror_coord=mirror_coord,
        prepare_player_turn_modifiers=prepare_modifiers,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=finish_ai_move,
    )

    result = await try_finish_forced_rogue_ai_turn_event(
        game,
        send,
        turn,
        run_engine,
        deps,
    )

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "W",
            "mirror",
            {"dice", "mirror"},
            True,
            0.5,
            0.75,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
        ("roll",),
        ("gtp", "C3", 9),
        ("coord", 3, 3, 9),
        ("mirror", 1, 2, 9),
        ("prepare", True),
        ("pass", True, True, True),
        ("stone", True, True, True),
        ("puppet", True, True, True),
        ("finish", True, True, "W", "mirror", "D4", "forced"),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_wrapper_resolves_forced_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="B", card="dice", rogue_cards={"dice"})

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    def roll_random():
        calls.append(("roll",))
        return 0.1

    async def try_finish(game_arg, send_fn, **kwargs):
        calls.append((
            "try",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["roll_random"] is roll_random,
            kwargs["dice_pass_chance"],
            kwargs["mirror_chance"],
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["mirror_coord"] is s._mirror_coord,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_engine_command"] is run_engine,
            kwargs["finalize_forced_pass"] is s.finalize_forced_ai_pass,
            kwargs["finalize_forced_stone"] is s.try_finalize_forced_ai_stone,
            kwargs["apply_puppet_move"] is s.try_apply_puppet_ai_move,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_try = s.try_finish_forced_rogue_ai_move
    original_random = s.random.random
    original_dice = s.ROGUE_DICE_PASS_CHANCE
    original_mirror = s.ROGUE_MIRROR_CHANCE
    try:
        s.try_finish_forced_rogue_ai_move = try_finish
        s.random.random = roll_random
        s.ROGUE_DICE_PASS_CHANCE = 0.33
        s.ROGUE_MIRROR_CHANCE = 0.44

        result = await s._try_finish_forced_rogue_ai_turn(
            game,
            send,
            turn,
            run_engine,
        )
    finally:
        s.try_finish_forced_rogue_ai_move = original_try
        s.random.random = original_random
        s.ROGUE_DICE_PASS_CHANCE = original_dice
        s.ROGUE_MIRROR_CHANCE = original_mirror

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "B",
            "dice",
            {"dice"},
            True,
            0.33,
            0.44,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        )
    ]
    assert sent == []


async def main() -> None:
    await smoke_forced_flow_injects_turn_and_runtime_deps()
    await smoke_server_wrapper_resolves_forced_runtime_deps_late()
    print("forced rogue ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
