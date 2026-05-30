from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.rogue_ai_turn_adapters import (
    ForcedRogueAiTurnBinding,
    RestrictionRogueAiTurnBinding,
    ShadowRogueAiTurnBinding,
    SuboptimalRogueAiTurnBinding,
    build_forced_rogue_ai_turn_deps,
    build_restriction_rogue_ai_turn_deps,
    build_shadow_rogue_ai_turn_deps,
    build_suboptimal_rogue_ai_turn_deps,
    try_finish_forced_rogue_ai_turn,
    try_finish_restriction_rogue_ai_turn,
    try_finish_shadow_rogue_ai_turn,
    try_finish_suboptimal_rogue_ai_turn,
)


async def fake_async(*_args, **_kwargs):
    return True


def fake_sync(*_args, **_kwargs):
    return None


def fake_random() -> float:
    return 0.25


def smoke_forced_binding_maps_every_field() -> None:
    binding = ForcedRogueAiTurnBinding(
        try_finish_forced_rogue_ai_move=fake_async,
        roll_random=fake_random,
        dice_pass_chance=0.3,
        mirror_chance=0.4,
        gtp_to_coord=fake_sync,
        coord_to_gtp=fake_sync,
        mirror_coord=fake_sync,
        prepare_player_turn_modifiers=fake_sync,
        finalize_forced_pass=fake_async,
        finalize_forced_stone=fake_async,
        apply_puppet_move=fake_async,
        finish_ai_move=fake_async,
    )

    deps = build_forced_rogue_ai_turn_deps(binding)

    assert deps.try_finish_forced_rogue_ai_move is fake_async
    assert deps.roll_random is fake_random
    assert deps.dice_pass_chance == 0.3
    assert deps.mirror_chance == 0.4
    assert deps.gtp_to_coord is fake_sync
    assert deps.coord_to_gtp is fake_sync
    assert deps.mirror_coord is fake_sync
    assert deps.prepare_player_turn_modifiers is fake_sync
    assert deps.finalize_forced_pass is fake_async
    assert deps.finalize_forced_stone is fake_async
    assert deps.apply_puppet_move is fake_async
    assert deps.finish_ai_move is fake_async


def smoke_restriction_binding_maps_every_field() -> None:
    binding = RestrictionRogueAiTurnBinding(
        try_finish_rogue_restriction_ai_move=fake_async,
        choose_tengen_target=fake_sync,
        tengen_followup_points=fake_sync,
        gravity_allowed_points=fake_sync,
        lowline_allowed_points=fake_sync,
        sansan_opening_restriction=fake_sync,
        coord_to_gtp=fake_sync,
        finalize_forced_stone=fake_async,
        prepare_player_turn_modifiers=fake_sync,
        choose_allowed_move=fake_async,
        choose_avoid_move=fake_async,
        finish_ai_move=fake_async,
        finish_allowed_restriction_move=fake_async,
        finish_sansan_restriction_move=fake_async,
    )

    deps = build_restriction_rogue_ai_turn_deps(binding)

    assert deps.try_finish_rogue_restriction_ai_move is fake_async
    assert deps.choose_tengen_target is fake_sync
    assert deps.tengen_followup_points is fake_sync
    assert deps.gravity_allowed_points is fake_sync
    assert deps.lowline_allowed_points is fake_sync
    assert deps.sansan_opening_restriction is fake_sync
    assert deps.coord_to_gtp is fake_sync
    assert deps.finalize_forced_stone is fake_async
    assert deps.prepare_player_turn_modifiers is fake_sync
    assert deps.choose_allowed_move is fake_async
    assert deps.choose_avoid_move is fake_async
    assert deps.finish_ai_move is fake_async
    assert deps.finish_allowed_restriction_move is fake_async
    assert deps.finish_sansan_restriction_move is fake_async


def smoke_shadow_and_suboptimal_bindings_map_every_field() -> None:
    shadow_binding = ShadowRogueAiTurnBinding(
        try_finish_shadow_restriction_move=fake_async,
        roll_random=fake_random,
        choose_restriction=fake_sync,
        choose_allowed_move=fake_async,
        finish_ai_move=fake_async,
    )
    suboptimal_binding = SuboptimalRogueAiTurnBinding(
        try_finish_suboptimal_rogue_move=fake_async,
        roll_random=fake_random,
        choose_suboptimal_move=fake_async,
        finish_ai_move=fake_async,
    )

    shadow_deps = build_shadow_rogue_ai_turn_deps(shadow_binding)
    suboptimal_deps = build_suboptimal_rogue_ai_turn_deps(suboptimal_binding)

    assert shadow_deps.try_finish_shadow_restriction_move is fake_async
    assert shadow_deps.roll_random is fake_random
    assert shadow_deps.choose_restriction is fake_sync
    assert shadow_deps.choose_allowed_move is fake_async
    assert shadow_deps.finish_ai_move is fake_async
    assert suboptimal_deps.try_finish_suboptimal_rogue_move is fake_async
    assert suboptimal_deps.roll_random is fake_random
    assert suboptimal_deps.choose_suboptimal_move is fake_async
    assert suboptimal_deps.finish_ai_move is fake_async


async def smoke_adapters_delegate_to_underlying_flow() -> None:
    game = object()
    turn = SimpleNamespace(color="W", card="dice", rogue_cards={"dice"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=120, time_limit=1.5)
    calls = []

    async def send(_payload):
        calls.append(("send",))

    async def run_engine(command: str):
        calls.append(("engine", command))
        return "= ok"

    async def forced(game_arg, send_fn, **kwargs):
        calls.append(("forced", game_arg is game, send_fn is send, kwargs["run_engine_command"] is run_engine))
        return True

    async def restriction(game_arg, send_fn, **kwargs):
        calls.append(("restriction", game_arg is game, send_fn is send, kwargs["visits"], kwargs["time_limit"]))
        return True

    async def shadow(game_arg, send_fn, **kwargs):
        calls.append(("shadow", game_arg is game, send_fn is send, kwargs["ai_move_count"]))
        return True

    async def suboptimal(game_arg, send_fn, **kwargs):
        calls.append(("suboptimal", game_arg is game, send_fn is send, kwargs["card"]))
        return True

    assert await try_finish_forced_rogue_ai_turn(
        game,
        send,
        turn,
        run_engine,
        ForcedRogueAiTurnBinding(
            try_finish_forced_rogue_ai_move=forced,
            roll_random=fake_random,
            dice_pass_chance=0.3,
            mirror_chance=0.4,
            gtp_to_coord=fake_sync,
            coord_to_gtp=fake_sync,
            mirror_coord=fake_sync,
            prepare_player_turn_modifiers=fake_sync,
            finalize_forced_pass=fake_async,
            finalize_forced_stone=fake_async,
            apply_puppet_move=fake_async,
            finish_ai_move=fake_async,
        ),
    ) is True
    assert await try_finish_restriction_rogue_ai_turn(
        game,
        send,
        turn,
        ai_plan,
        run_engine,
        RestrictionRogueAiTurnBinding(
            try_finish_rogue_restriction_ai_move=restriction,
            choose_tengen_target=fake_sync,
            tengen_followup_points=fake_sync,
            gravity_allowed_points=fake_sync,
            lowline_allowed_points=fake_sync,
            sansan_opening_restriction=fake_sync,
            coord_to_gtp=fake_sync,
            finalize_forced_stone=fake_async,
            prepare_player_turn_modifiers=fake_sync,
            choose_allowed_move=fake_async,
            choose_avoid_move=fake_async,
            finish_ai_move=fake_async,
            finish_allowed_restriction_move=fake_async,
            finish_sansan_restriction_move=fake_async,
        ),
    ) is True
    assert await try_finish_shadow_rogue_ai_turn(
        game,
        send,
        turn,
        ai_plan,
        ShadowRogueAiTurnBinding(
            try_finish_shadow_restriction_move=shadow,
            roll_random=fake_random,
            choose_restriction=fake_sync,
            choose_allowed_move=fake_async,
            finish_ai_move=fake_async,
        ),
    ) is True
    assert await try_finish_suboptimal_rogue_ai_turn(
        game,
        send,
        turn,
        ai_plan,
        SuboptimalRogueAiTurnBinding(
            try_finish_suboptimal_rogue_move=suboptimal,
            roll_random=fake_random,
            choose_suboptimal_move=fake_async,
            finish_ai_move=fake_async,
        ),
    ) is True

    assert calls == [
        ("forced", True, True, True),
        ("restriction", True, True, 120, 1.5),
        ("shadow", True, True, 2),
        ("suboptimal", True, True, "dice"),
    ]


def smoke_server_bindings_resolve_current_runtime() -> None:
    original_random = s.random.random
    original_forced = s.try_finish_forced_rogue_ai_move
    original_restriction = s.try_finish_rogue_restriction_ai_move
    original_shadow = s.try_finish_shadow_restriction_move
    original_suboptimal = s.try_finish_suboptimal_rogue_move
    original_choose_suboptimal = s._ai_move_suboptimal
    original_finish = s._finish_ai_move
    original_shadow_followup = s.shadow_followup_points
    original_gtp_to_coord = s.gtp_to_coord
    game = object()
    calls = []

    def fake_gtp_to_coord(move: str, size: int):
        calls.append(("gtp", move, size))
        return (1, 2)

    def fake_shadow_followup(game_arg, color, ai_count, **kwargs):
        calls.append((
            "shadow_followup",
            game_arg is game,
            color,
            ai_count,
            kwargs["gtp_to_coord"] is fake_gtp_to_coord,
        ))
        kwargs["gtp_to_coord"]("D4", 9)
        return SimpleNamespace(points=[(2, 2)], message="shadow")

    try:
        s.random.random = fake_random
        s.try_finish_forced_rogue_ai_move = fake_async
        s.try_finish_rogue_restriction_ai_move = fake_async
        s.try_finish_shadow_restriction_move = fake_async
        s.try_finish_suboptimal_rogue_move = fake_async
        s._ai_move_suboptimal = fake_async
        s._finish_ai_move = fake_async
        s.shadow_followup_points = fake_shadow_followup
        s.gtp_to_coord = fake_gtp_to_coord

        forced = s._forced_rogue_ai_turn_binding()
        restriction = s._restriction_rogue_ai_turn_binding()
        shadow = s._shadow_rogue_ai_turn_binding()
        suboptimal = s._suboptimal_rogue_ai_turn_binding()

        assert forced.try_finish_forced_rogue_ai_move is fake_async
        assert forced.roll_random is fake_random
        assert forced.finish_ai_move is fake_async
        assert restriction.try_finish_rogue_restriction_ai_move is fake_async
        assert restriction.choose_avoid_move is s._ai_move_avoid_points
        assert restriction.finish_ai_move is fake_async
        assert shadow.try_finish_shadow_restriction_move is fake_async
        assert shadow.roll_random is fake_random
        assert shadow.finish_ai_move is fake_async
        assert shadow.choose_restriction(game, "W", 3).message == "shadow"
        assert calls == [
            ("shadow_followup", True, "W", 3, True),
            ("gtp", "D4", 9),
        ]
        assert suboptimal.try_finish_suboptimal_rogue_move is fake_async
        assert suboptimal.choose_suboptimal_move is fake_async
        assert suboptimal.finish_ai_move is fake_async
    finally:
        s.random.random = original_random
        s.try_finish_forced_rogue_ai_move = original_forced
        s.try_finish_rogue_restriction_ai_move = original_restriction
        s.try_finish_shadow_restriction_move = original_shadow
        s.try_finish_suboptimal_rogue_move = original_suboptimal
        s._ai_move_suboptimal = original_choose_suboptimal
        s._finish_ai_move = original_finish
        s.shadow_followup_points = original_shadow_followup
        s.gtp_to_coord = original_gtp_to_coord


def main() -> None:
    smoke_forced_binding_maps_every_field()
    smoke_restriction_binding_maps_every_field()
    smoke_shadow_and_suboptimal_bindings_map_every_field()
    asyncio.run(smoke_adapters_delegate_to_underlying_flow())
    smoke_server_bindings_resolve_current_runtime()
    print("rogue ai turn adapters smoke test: OK")


if __name__ == "__main__":
    main()
