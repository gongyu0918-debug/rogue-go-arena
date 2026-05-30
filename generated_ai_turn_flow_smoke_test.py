from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.generated_ai_turn_flow import (
    GeneratedAiTurnDeps,
    try_finish_generated_ai_turn_event,
)


async def smoke_generated_turn_flow_computes_forbidden_and_injects_deps() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="W",
        card="fog",
        rogue_cards={"fog", "gravity"},
        ai_move_count=3,
    )
    ai_plan = SimpleNamespace(visits=321, time_limit=4.5)
    candidate_deps = object()
    preparation_deps = object()
    finish_deps = object()

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    def challenge_zone_points(game_arg, points):
        calls.append(("zone", game_arg is game, tuple(points)))
        return list(points)

    def rogue_forbidden_points(game_arg, rogue_cards, ai_move_count, **kwargs):
        calls.append((
            "forbidden",
            game_arg is game,
            rogue_cards,
            ai_move_count,
            kwargs["challenge_zone_points"] is challenge_zone_points,
        ))
        kwargs["challenge_zone_points"](game_arg, [(1, 1)])
        return [(2, 2), (3, 3)]

    def candidate_factory():
        calls.append(("candidate_factory",))
        return candidate_deps

    def preparation_factory():
        calls.append(("preparation_factory",))
        return preparation_deps

    def finish_factory(engine_command):
        calls.append(("finish_factory", engine_command is run_engine))
        return finish_deps

    async def try_finish(game_arg, send_fn, **kwargs):
        calls.append((
            "try_finish",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["forbidden"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["candidate_deps"] is candidate_deps,
            kwargs["preparation_deps"] is preparation_deps,
            kwargs["finish_deps"] is finish_deps,
        ))
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    deps = GeneratedAiTurnDeps(
        rogue_forbidden_points=rogue_forbidden_points,
        challenge_zone_points=challenge_zone_points,
        try_finish_generated_ai_move=try_finish,
        candidate_deps=candidate_factory,
        preparation_deps=preparation_factory,
        finish_deps=finish_factory,
    )

    result = await try_finish_generated_ai_turn_event(
        game,
        send,
        turn,
        ai_plan,
        run_engine,
        deps,
    )

    assert result is True
    assert calls == [
        ("forbidden", True, {"fog", "gravity"}, 3, True),
        ("zone", True, ((1, 1),)),
        ("candidate_factory",),
        ("preparation_factory",),
        ("finish_factory", True),
        (
            "try_finish",
            True,
            True,
            "W",
            "fog",
            {"fog", "gravity"},
            [(2, 2), (3, 3)],
            321,
            4.5,
            True,
            True,
            True,
        ),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_wrapper_resolves_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(
        color="B",
        card="gravity",
        rogue_cards={"gravity"},
        ai_move_count=2,
    )
    ai_plan = SimpleNamespace(visits=99, time_limit=1.5)

    async def send(payload):
        sent.append(payload)

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    def challenge_zone_points(game_arg, points):
        calls.append(("zone", game_arg is game, tuple(points)))
        return list(points)

    def rogue_forbidden_points(game_arg, rogue_cards, ai_move_count, **kwargs):
        calls.append((
            "forbidden",
            game_arg is game,
            rogue_cards,
            ai_move_count,
            kwargs["challenge_zone_points"] is challenge_zone_points,
        ))
        kwargs["challenge_zone_points"](game_arg, [(4, 4)])
        return [(5, 5)]

    async def try_finish(game_arg, send_fn, **kwargs):
        calls.append((
            "try_finish",
            game_arg is game,
            send_fn is send,
            kwargs["forbidden"],
            kwargs["candidate_deps"].choose_candidate is s.choose_ai_move_candidate,
            kwargs["preparation_deps"].prepare_move is s.prepare_generated_ai_move,
            kwargs["finish_deps"].run_double_pass_command is run_engine,
        ))
        return True

    original_candidate_binding = s._generated_ai_move_candidate_binding
    original_preparation_binding = s._generated_ai_move_preparation_binding
    original_finish_binding = s._generated_ai_move_finish_binding

    def candidate_binding():
        calls.append(("candidate_binding",))
        return original_candidate_binding()

    def preparation_binding():
        calls.append(("preparation_binding",))
        return original_preparation_binding()

    def finish_binding(engine_command):
        calls.append(("finish_binding", engine_command is run_engine))
        return original_finish_binding(engine_command)

    originals = {
        "rogue_forbidden_points": s.rogue_forbidden_points,
        "_challenge_zone_points": s._challenge_zone_points,
        "try_finish_generated_ai_move": s.try_finish_generated_ai_move,
        "_generated_ai_move_candidate_binding": s._generated_ai_move_candidate_binding,
        "_generated_ai_move_preparation_binding": s._generated_ai_move_preparation_binding,
        "_generated_ai_move_finish_binding": s._generated_ai_move_finish_binding,
    }
    try:
        s.rogue_forbidden_points = rogue_forbidden_points
        s._challenge_zone_points = challenge_zone_points
        s.try_finish_generated_ai_move = try_finish
        s._generated_ai_move_candidate_binding = candidate_binding
        s._generated_ai_move_preparation_binding = preparation_binding
        s._generated_ai_move_finish_binding = finish_binding

        result = await s._try_finish_generated_ai_turn(
            game,
            send,
            turn,
            ai_plan,
            run_engine,
        )
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert result is True
    assert calls == [
        ("forbidden", True, {"gravity"}, 2, True),
        ("zone", True, ((4, 4),)),
        ("candidate_binding",),
        ("preparation_binding",),
        ("finish_binding", True),
        ("try_finish", True, True, [(5, 5)], True, True, True),
    ]
    assert sent == []


async def main() -> None:
    await smoke_generated_turn_flow_computes_forbidden_and_injects_deps()
    await smoke_server_wrapper_resolves_runtime_deps_late()
    print("generated ai turn flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
