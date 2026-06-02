from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.restriction_rogue_ai_turn_flow import (
    RestrictionRogueAiTurnDeps,
    try_finish_restriction_rogue_ai_turn_event,
)


async def smoke_restriction_flow_injects_turn_plan_and_runtime_deps() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="W",
        card="lowline",
        rogue_cards={"tengen", "lowline"},
        ai_move_count=4,
    )
    ai_plan = SimpleNamespace(visits=456, time_limit=7.5)

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    def choose_tengen(game_arg, ai_count):
        calls.append(("tengen", game_arg is game, ai_count))
        return None

    def tengen_followup(game_arg, ai_count):
        calls.append(("followup", game_arg is game, ai_count))
        return None

    def gravity(game_arg, ai_count):
        calls.append(("gravity", game_arg is game, ai_count))
        return None

    def lowline(game_arg, ai_count):
        calls.append(("lowline", game_arg is game, ai_count))
        return None

    def sansan(game_arg, ai_count):
        calls.append(("sansan", game_arg is game, ai_count))
        return None

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return "D4"

    async def finalize_stone(game_arg, send_fn, **kwargs):
        calls.append(("stone", game_arg is game, send_fn is send, kwargs["run_engine_command"] is run_engine))
        return True

    def prepare_modifiers(game_arg):
        calls.append(("prepare", game_arg is game))

    async def choose_allowed(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, tuple(points)))
        return "D4"

    async def choose_avoid(game_arg, color, visits, time_limit, points):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, tuple(points)))
        return "E5"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg=None):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    async def check_capture_foul(*_args, **_kwargs):
        return None

    async def finish_allowed(game_arg, send_fn, **kwargs):
        calls.append(("finish_allowed", game_arg is game, send_fn is send, kwargs["choose_allowed_move"] is choose_allowed))
        return False

    async def finish_sansan(game_arg, send_fn, **kwargs):
        calls.append(("finish_sansan", game_arg is game, send_fn is send, kwargs["choose_avoid_move"] is choose_avoid))
        return False

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
            kwargs["choose_tengen_target"] is choose_tengen,
            kwargs["tengen_followup_points"] is tengen_followup,
            kwargs["gravity_allowed_points"] is gravity,
            kwargs["lowline_allowed_points"] is lowline,
            kwargs["sansan_opening_restriction"] is sansan,
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["finalize_forced_stone"] is finalize_stone,
            kwargs["prepare_player_turn_modifiers"] is prepare_modifiers,
            kwargs["check_capture_foul"] is check_capture_foul,
            kwargs["run_engine_command"] is run_engine,
            kwargs["choose_allowed_move"] is choose_allowed,
            kwargs["choose_avoid_move"] is choose_avoid,
            kwargs["finish_ai_move"] is finish_ai_move,
            kwargs["finish_allowed_restriction_move"] is finish_allowed,
            kwargs["finish_sansan_restriction_move"] is finish_sansan,
        ))
        kwargs["choose_tengen_target"](game_arg, kwargs["ai_move_count"])
        kwargs["tengen_followup_points"](game_arg, kwargs["ai_move_count"])
        kwargs["gravity_allowed_points"](game_arg, kwargs["ai_move_count"])
        kwargs["lowline_allowed_points"](game_arg, kwargs["ai_move_count"])
        kwargs["sansan_opening_restriction"](game_arg, kwargs["ai_move_count"])
        kwargs["coord_to_gtp"](3, 3, 9)
        await kwargs["finalize_forced_stone"](game_arg, send_fn, run_engine_command=kwargs["run_engine_command"])
        kwargs["prepare_player_turn_modifiers"](game_arg)
        await kwargs["choose_allowed_move"](game_arg, kwargs["color"], kwargs["visits"], kwargs["time_limit"], [(1, 1)])
        await kwargs["choose_avoid_move"](game_arg, kwargs["color"], kwargs["visits"], kwargs["time_limit"], [(2, 2)])
        await kwargs["finish_ai_move"](game_arg, send_fn, kwargs["color"], kwargs["card"], "D4", "restricted")
        await kwargs["finish_allowed_restriction_move"](game_arg, send_fn, choose_allowed_move=kwargs["choose_allowed_move"])
        await kwargs["finish_sansan_restriction_move"](game_arg, send_fn, choose_avoid_move=kwargs["choose_avoid_move"])
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = RestrictionRogueAiTurnDeps(
        try_finish_rogue_restriction_ai_move=try_finish,
        choose_tengen_target=choose_tengen,
        tengen_followup_points=tengen_followup,
        gravity_allowed_points=gravity,
        lowline_allowed_points=lowline,
        sansan_opening_restriction=sansan,
        coord_to_gtp=coord_to_gtp,
        finalize_forced_stone=finalize_stone,
        prepare_player_turn_modifiers=prepare_modifiers,
        check_capture_foul=check_capture_foul,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=choose_avoid,
        finish_ai_move=finish_ai_move,
        finish_allowed_restriction_move=finish_allowed,
        finish_sansan_restriction_move=finish_sansan,
    )

    result = await try_finish_restriction_rogue_ai_turn_event(
        game,
        send,
        turn,
        ai_plan,
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
            "lowline",
            {"tengen", "lowline"},
            4,
            456,
            7.5,
            True,
            True,
            True,
            True,
            True,
            True,
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
        ("tengen", True, 4),
        ("followup", True, 4),
        ("gravity", True, 4),
        ("lowline", True, 4),
        ("sansan", True, 4),
        ("coord", 3, 3, 9),
        ("stone", True, True, True),
        ("prepare", True),
        ("allowed", True, "W", 456, 7.5, ((1, 1),)),
        ("avoid", True, "W", 456, 7.5, ((2, 2),)),
        ("finish", True, True, "W", "lowline", "D4", "restricted"),
        ("finish_allowed", True, True, True),
        ("finish_sansan", True, True, True),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_wrapper_resolves_restriction_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="B", card="gravity", rogue_cards={"gravity"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=111, time_limit=2.5)

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

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
            kwargs["choose_tengen_target"] is s.choose_tengen_target,
            kwargs["tengen_followup_points"] is s.tengen_followup_points,
            kwargs["gravity_allowed_points"] is s.gravity_allowed_points,
            kwargs["lowline_allowed_points"] is s.lowline_allowed_points,
            kwargs["sansan_opening_restriction"] is s.sansan_opening_restriction,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["finalize_forced_stone"] is s.try_finalize_forced_ai_stone,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["check_capture_foul"] is s._check_capture_foul,
            kwargs["run_engine_command"] is run_engine,
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["choose_avoid_move"] is s._ai_move_avoid_points,
            kwargs["finish_ai_move"] is s._finish_ai_move,
            kwargs["finish_allowed_restriction_move"] is s.try_finish_allowed_restriction_move,
            kwargs["finish_sansan_restriction_move"] is s.try_finish_sansan_restriction_move,
        ))
        return True

    original_try = s.try_finish_rogue_restriction_ai_move
    try:
        s.try_finish_rogue_restriction_ai_move = try_finish
        result = await s._try_finish_rogue_restriction_ai_turn(
            game,
            send,
            turn,
            ai_plan,
            run_engine,
        )
    finally:
        s.try_finish_rogue_restriction_ai_move = original_try

    assert result is True
    assert calls == [
        (
            "try",
            True,
            True,
            "B",
            "gravity",
            {"gravity"},
            2,
            111,
            2.5,
            True,
            True,
            True,
            True,
            True,
            True,
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
    await smoke_restriction_flow_injects_turn_plan_and_runtime_deps()
    await smoke_server_wrapper_resolves_restriction_runtime_deps_late()
    print("restriction rogue ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
