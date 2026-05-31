from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.shadow_rogue_ai_turn_flow import (
    ShadowRogueAiTurnDeps,
    try_finish_shadow_rogue_ai_turn_event,
)


async def smoke_shadow_flow_injects_turn_plan_and_runtime_deps() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        ai_move_count=5,
    )
    ai_plan = SimpleNamespace(visits=222, time_limit=3.5)

    async def send(payload):
        sent.append(payload)

    def roll_random():
        calls.append(("roll",))
        return 0.1

    def choose_restriction(game_arg, color, ai_count):
        calls.append(("restriction", game_arg is game, color, ai_count))
        return SimpleNamespace(points=[(1, 1)], message="shadow")

    async def choose_allowed(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, tuple(points)))
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
            kwargs["choose_restriction"] is choose_restriction,
            kwargs["choose_allowed_move"] is choose_allowed,
            kwargs["finish_ai_move"] is finish_ai_move,
        ))
        kwargs["roll_random"]()
        restriction = kwargs["choose_restriction"](game_arg, kwargs["color"], kwargs["ai_move_count"])
        await kwargs["choose_allowed_move"](
            game_arg,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
            restriction.points,
        )
        await kwargs["finish_ai_move"](
            game_arg,
            send_fn,
            kwargs["color"],
            kwargs["card"],
            "D4",
            restriction.message,
        )
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = ShadowRogueAiTurnDeps(
        try_finish_shadow_restriction_move=try_finish,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed,
        finish_ai_move=finish_ai_move,
    )

    result = await try_finish_shadow_rogue_ai_turn_event(
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
            "shadow",
            {"shadow"},
            5,
            222,
            3.5,
            True,
            True,
            True,
            True,
        ),
        ("roll",),
        ("restriction", True, "W", 5),
        ("allowed", True, "W", 222, 3.5, ((1, 1),)),
        ("finish", True, True, "W", "shadow", "D4", "shadow"),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_wrapper_resolves_shadow_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="B", card="shadow", rogue_cards={"shadow"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=111, time_limit=2.5)

    async def send(payload):
        sent.append(payload)

    def roll_random():
        calls.append(("roll",))
        return 0.0

    def shadow_followup(game_arg, color, ai_count, **kwargs):
        calls.append((
            "shadow_followup",
            game_arg is game,
            color,
            ai_count,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
        ))
        return SimpleNamespace(points=[(2, 2)], message="shadow follow")

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
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        kwargs["roll_random"]()
        restriction = kwargs["choose_restriction"](game_arg, kwargs["color"], kwargs["ai_move_count"])
        calls.append(("restriction_result", restriction.points, restriction.message))
        return True

    original_try = s.try_finish_shadow_restriction_move
    original_random = s.random.random
    original_shadow = s.shadow_followup_points
    try:
        s.try_finish_shadow_restriction_move = try_finish
        s.random.random = roll_random
        s.shadow_followup_points = shadow_followup

        result = await s._try_finish_shadow_rogue_ai_turn(
            game,
            send,
            turn,
            ai_plan,
        )
    finally:
        s.try_finish_shadow_restriction_move = original_try
        s.random.random = original_random
        s.shadow_followup_points = original_shadow

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "B",
            "shadow",
            {"shadow"},
            2,
            111,
            2.5,
            True,
            True,
            True,
        ),
        ("roll",),
        ("shadow_followup", True, "B", 2, True),
        ("restriction_result", [(2, 2)], "shadow follow"),
    ]
    assert sent == []


async def main() -> None:
    await smoke_shadow_flow_injects_turn_plan_and_runtime_deps()
    await smoke_server_wrapper_resolves_shadow_runtime_deps_late()
    print("shadow rogue ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
