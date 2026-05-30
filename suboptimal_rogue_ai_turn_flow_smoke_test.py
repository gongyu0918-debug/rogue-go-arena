from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.suboptimal_rogue_ai_turn_flow import (
    SuboptimalRogueAiTurnDeps,
    try_finish_suboptimal_rogue_ai_turn_event,
)


async def smoke_suboptimal_flow_injects_turn_plan_and_runtime_deps() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="W",
        card="suboptimal",
        rogue_cards={"suboptimal"},
        ai_move_count=6,
    )
    ai_plan = SimpleNamespace(visits=333, time_limit=6.5)

    async def send(payload):
        sent.append(payload)

    def roll_random():
        calls.append(("roll",))
        return 0.2

    async def choose_suboptimal(game_arg, color, visits, time_limit, start_idx=2, end_idx=5):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        return "D4"

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
            kwargs["ai_move_count"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["roll_random"] is roll_random,
            kwargs["choose_suboptimal_move"] is choose_suboptimal,
            kwargs["finish_ai_move"] is finish_ai_move,
        ))
        kwargs["roll_random"]()
        await kwargs["choose_suboptimal_move"](
            game_arg,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
        )
        await kwargs["finish_ai_move"](
            game_arg,
            send_fn,
            kwargs["color"],
            kwargs["card"],
            "D4",
            "suboptimal",
        )
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = SuboptimalRogueAiTurnDeps(
        try_finish_suboptimal_rogue_move=try_finish,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal,
        finish_ai_move=finish_ai_move,
    )

    result = await try_finish_suboptimal_rogue_ai_turn_event(
        game,
        send,
        turn,
        ai_plan,
        deps,
    )

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "W",
            "suboptimal",
            {"suboptimal"},
            6,
            333,
            6.5,
            True,
            True,
            True,
        ),
        ("roll",),
        ("choose", True, "W", 333, 6.5, 2, 5),
        ("finish", True, True, "W", "suboptimal", "D4", "suboptimal"),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_wrapper_resolves_suboptimal_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="B", card="suboptimal", rogue_cards={"suboptimal"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=111, time_limit=2.5)

    async def send(payload):
        sent.append(payload)

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal(_game, _color, _visits, _time_limit, start_idx=2, end_idx=5):
        calls.append(("choose", start_idx, end_idx))
        return "D4"

    async def finish_ai_move(_game, _send, _color, _card, _gtp_move, _rogue_msg=None):
        calls.append(("finish",))

    async def try_finish(game_arg, send_fn, **kwargs):
        calls.append((
            "try",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["roll_random"] is roll_random,
            kwargs["choose_suboptimal_move"] is choose_suboptimal,
            kwargs["finish_ai_move"] is finish_ai_move,
        ))
        kwargs["roll_random"]()
        return True

    original_try = s.try_finish_suboptimal_rogue_move
    original_random = s.random.random
    original_choose = s._ai_move_suboptimal
    original_finish = s._finish_ai_move
    try:
        s.try_finish_suboptimal_rogue_move = try_finish
        s.random.random = roll_random
        s._ai_move_suboptimal = choose_suboptimal
        s._finish_ai_move = finish_ai_move

        result = await s._try_finish_suboptimal_rogue_ai_turn(
            game,
            send,
            turn,
            ai_plan,
        )
    finally:
        s.try_finish_suboptimal_rogue_move = original_try
        s.random.random = original_random
        s._ai_move_suboptimal = original_choose
        s._finish_ai_move = original_finish

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "B",
            "suboptimal",
            {"suboptimal"},
            2,
            111,
            2.5,
            True,
            True,
            True,
        ),
        ("roll",),
    ]
    assert sent == []


async def main() -> None:
    await smoke_suboptimal_flow_injects_turn_plan_and_runtime_deps()
    await smoke_server_wrapper_resolves_suboptimal_runtime_deps_late()
    print("suboptimal rogue ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
