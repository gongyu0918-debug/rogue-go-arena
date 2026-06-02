from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

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
from app.runtime.rogue_ai_turn_runtime import (
    ForcedRogueAiTurnFns,
    RestrictionRogueAiTurnFns,
    RogueAiTurnDependencies,
    RogueAiTurnSharedFns,
    RogueAiTurnTuning,
    ShadowRogueAiTurnFns,
    SuboptimalRogueAiTurnFns,
    build_forced_rogue_ai_turn_binding,
    build_restriction_rogue_ai_turn_binding,
    build_shadow_rogue_ai_turn_binding,
    build_suboptimal_rogue_ai_turn_binding,
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
        check_capture_foul=fake_async,
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
    assert deps.check_capture_foul is fake_async
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
        check_capture_foul=fake_async,
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
    assert deps.check_capture_foul is fake_async
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


def smoke_rogue_ai_turn_runtime_builders_group_dependencies() -> None:
    async def forced_move(*_args, **_kwargs):
        return True

    async def finalize_pass(*_args, **_kwargs):
        return None

    async def finalize_stone(*_args, **_kwargs):
        return True

    async def apply_puppet(*_args, **_kwargs):
        return True

    async def restriction_move(*_args, **_kwargs):
        return True

    async def choose_allowed(*_args, **_kwargs):
        return "D4"

    async def choose_avoid(*_args, **_kwargs):
        return "Q16"

    async def finish_allowed(*_args, **_kwargs):
        return True

    async def finish_sansan(*_args, **_kwargs):
        return True

    async def shadow_move(*_args, **_kwargs):
        return True

    async def shadow_choose_allowed(*_args, **_kwargs):
        return "C3"

    async def suboptimal_move(*_args, **_kwargs):
        return True

    async def choose_suboptimal(*_args, **_kwargs):
        return "pass"

    async def finish_ai(*_args, **_kwargs):
        return None

    def roll_random() -> float:
        return 0.42

    def gtp_to_coord(_move: str, _size: int):
        return (3, 3)

    def coord_to_gtp(x: int, y: int, _size: int) -> str:
        return f"{x}:{y}"

    def mirror_coord(_coord, _size: int):
        return (4, 4)

    def prepare_modifiers(_game):
        return SimpleNamespace(prepared=True)

    def choose_tengen(*_args, **_kwargs):
        return (4, 4)

    def tengen_followup(*_args, **_kwargs):
        return [(4, 5)]

    def gravity_points(*_args, **_kwargs):
        return [(0, 0)]

    def lowline_points(*_args, **_kwargs):
        return [(2, 0)]

    def sansan_restriction(*_args, **_kwargs):
        return [(2, 2)]

    def choose_shadow_restriction(_game, color: str, ai_count: int):
        return SimpleNamespace(color=color, ai_count=ai_count)

    dependencies = RogueAiTurnDependencies(
        shared=RogueAiTurnSharedFns(
            roll_random=roll_random,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
            prepare_player_turn_modifiers=prepare_modifiers,
            check_capture_foul=fake_async,
            finish_ai_move=finish_ai,
        ),
        forced=ForcedRogueAiTurnFns(
            try_finish_forced_rogue_ai_move=forced_move,
            mirror_coord=mirror_coord,
            finalize_forced_pass=finalize_pass,
            finalize_forced_stone=finalize_stone,
            apply_puppet_move=apply_puppet,
        ),
        restriction=RestrictionRogueAiTurnFns(
            try_finish_rogue_restriction_ai_move=restriction_move,
            choose_tengen_target=choose_tengen,
            tengen_followup_points=tengen_followup,
            gravity_allowed_points=gravity_points,
            lowline_allowed_points=lowline_points,
            sansan_opening_restriction=sansan_restriction,
            choose_allowed_move=choose_allowed,
            choose_avoid_move=choose_avoid,
            finish_allowed_restriction_move=finish_allowed,
            finish_sansan_restriction_move=finish_sansan,
        ),
        shadow=ShadowRogueAiTurnFns(
            try_finish_shadow_restriction_move=shadow_move,
            choose_restriction=choose_shadow_restriction,
            choose_allowed_move=shadow_choose_allowed,
        ),
        suboptimal=SuboptimalRogueAiTurnFns(
            try_finish_suboptimal_rogue_move=suboptimal_move,
            choose_suboptimal_move=choose_suboptimal,
        ),
        tuning=RogueAiTurnTuning(
            dice_pass_chance=0.31,
            mirror_chance=0.63,
        ),
    )

    forced = build_forced_rogue_ai_turn_binding(dependencies)
    restriction = build_restriction_rogue_ai_turn_binding(dependencies)
    shadow = build_shadow_rogue_ai_turn_binding(dependencies)
    suboptimal = build_suboptimal_rogue_ai_turn_binding(dependencies)

    assert forced.try_finish_forced_rogue_ai_move is forced_move
    assert forced.roll_random is roll_random
    assert forced.dice_pass_chance == 0.31
    assert forced.mirror_chance == 0.63
    assert forced.gtp_to_coord is gtp_to_coord
    assert forced.coord_to_gtp is coord_to_gtp
    assert forced.mirror_coord is mirror_coord
    assert forced.prepare_player_turn_modifiers is prepare_modifiers
    assert forced.finalize_forced_pass is finalize_pass
    assert forced.finalize_forced_stone is finalize_stone
    assert forced.check_capture_foul is fake_async
    assert forced.apply_puppet_move is apply_puppet
    assert forced.finish_ai_move is finish_ai
    assert restriction.try_finish_rogue_restriction_ai_move is restriction_move
    assert restriction.choose_tengen_target is choose_tengen
    assert restriction.tengen_followup_points is tengen_followup
    assert restriction.gravity_allowed_points is gravity_points
    assert restriction.lowline_allowed_points is lowline_points
    assert restriction.sansan_opening_restriction is sansan_restriction
    assert restriction.coord_to_gtp is coord_to_gtp
    assert restriction.finalize_forced_stone is finalize_stone
    assert restriction.prepare_player_turn_modifiers is prepare_modifiers
    assert restriction.check_capture_foul is fake_async
    assert restriction.choose_allowed_move is choose_allowed
    assert restriction.choose_avoid_move is choose_avoid
    assert restriction.finish_ai_move is finish_ai
    assert restriction.finish_allowed_restriction_move is finish_allowed
    assert restriction.finish_sansan_restriction_move is finish_sansan
    assert shadow.try_finish_shadow_restriction_move is shadow_move
    assert shadow.roll_random is roll_random
    assert shadow.choose_restriction is choose_shadow_restriction
    assert shadow.choose_allowed_move is shadow_choose_allowed
    assert shadow.finish_ai_move is finish_ai
    assert suboptimal.try_finish_suboptimal_rogue_move is suboptimal_move
    assert suboptimal.roll_random is roll_random
    assert suboptimal.choose_suboptimal_move is choose_suboptimal
    assert suboptimal.finish_ai_move is finish_ai


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
            check_capture_foul=fake_async,
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
            check_capture_foul=fake_async,
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
    original_finalize_pass = s.finalize_forced_ai_pass
    original_finalize_stone = s.try_finalize_forced_ai_stone
    original_apply_puppet = s.try_apply_puppet_ai_move
    original_restriction = s.try_finish_rogue_restriction_ai_move
    original_choose_tengen = s.choose_tengen_target
    original_tengen_followup = s.tengen_followup_points
    original_gravity_points = s.gravity_allowed_points
    original_lowline_points = s.lowline_allowed_points
    original_sansan_restriction = s.sansan_opening_restriction
    original_choose_allowed = s._ai_move_avoid_points_allow_only
    original_choose_avoid = s._ai_move_avoid_points
    original_finish_allowed = s.try_finish_allowed_restriction_move
    original_finish_sansan = s.try_finish_sansan_restriction_move
    original_shadow = s.try_finish_shadow_restriction_move
    original_suboptimal = s.try_finish_suboptimal_rogue_move
    original_choose_suboptimal = s._ai_move_suboptimal
    original_finish = s._finish_ai_move
    original_shadow_followup = s.shadow_followup_points
    original_gtp_to_coord = s.gtp_to_coord
    original_coord_to_gtp = s.coord_to_gtp
    original_mirror_coord = s._mirror_coord
    original_prepare_modifiers = s._prepare_player_turn_modifiers
    game = object()
    calls = []

    async def forced_move(*_args, **_kwargs):
        return True

    async def finalize_pass(*_args, **_kwargs):
        return None

    async def finalize_stone(*_args, **_kwargs):
        return True

    async def apply_puppet(*_args, **_kwargs):
        return True

    async def restriction_move(*_args, **_kwargs):
        return True

    async def choose_allowed(*_args, **_kwargs):
        return "D4"

    async def choose_avoid(*_args, **_kwargs):
        return "Q16"

    async def finish_allowed(*_args, **_kwargs):
        return True

    async def finish_sansan(*_args, **_kwargs):
        return True

    async def shadow_move(*_args, **_kwargs):
        return True

    async def suboptimal_move(*_args, **_kwargs):
        return True

    async def choose_suboptimal(*_args, **_kwargs):
        return "pass"

    async def finish_ai(*_args, **_kwargs):
        return None

    def fake_gtp_to_coord(move: str, size: int):
        calls.append(("gtp", move, size))
        return (1, 2)

    def fake_coord_to_gtp(x: int, y: int, _size: int) -> str:
        return f"{x}:{y}"

    def fake_mirror_coord(_coord, _size: int):
        return (7, 7)

    def fake_prepare_modifiers(_game):
        return SimpleNamespace(prepared=True)

    def choose_tengen(*_args, **_kwargs):
        return (4, 4)

    def tengen_followup(*_args, **_kwargs):
        return [(4, 5)]

    def gravity_points(*_args, **_kwargs):
        return [(0, 0)]

    def lowline_points(*_args, **_kwargs):
        return [(2, 0)]

    def sansan_restriction(*_args, **_kwargs):
        return [(2, 2)]

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
        s.try_finish_forced_rogue_ai_move = forced_move
        s.finalize_forced_ai_pass = finalize_pass
        s.try_finalize_forced_ai_stone = finalize_stone
        s.try_apply_puppet_ai_move = apply_puppet
        s.try_finish_rogue_restriction_ai_move = restriction_move
        s.choose_tengen_target = choose_tengen
        s.tengen_followup_points = tengen_followup
        s.gravity_allowed_points = gravity_points
        s.lowline_allowed_points = lowline_points
        s.sansan_opening_restriction = sansan_restriction
        s._ai_move_avoid_points_allow_only = choose_allowed
        s._ai_move_avoid_points = choose_avoid
        s.try_finish_allowed_restriction_move = finish_allowed
        s.try_finish_sansan_restriction_move = finish_sansan
        s.try_finish_shadow_restriction_move = shadow_move
        s.try_finish_suboptimal_rogue_move = suboptimal_move
        s._ai_move_suboptimal = choose_suboptimal
        s._finish_ai_move = finish_ai
        s.shadow_followup_points = fake_shadow_followup
        s.gtp_to_coord = fake_gtp_to_coord
        s.coord_to_gtp = fake_coord_to_gtp
        s._mirror_coord = fake_mirror_coord
        s._prepare_player_turn_modifiers = fake_prepare_modifiers

        forced = s._forced_rogue_ai_turn_binding()
        restriction = s._restriction_rogue_ai_turn_binding()
        shadow = s._shadow_rogue_ai_turn_binding()
        suboptimal = s._suboptimal_rogue_ai_turn_binding()

        assert forced.try_finish_forced_rogue_ai_move is forced_move
        assert forced.roll_random is fake_random
        assert forced.dice_pass_chance == s.ROGUE_DICE_PASS_CHANCE
        assert forced.mirror_chance == s.ROGUE_MIRROR_CHANCE
        assert forced.gtp_to_coord is fake_gtp_to_coord
        assert forced.coord_to_gtp is fake_coord_to_gtp
        assert forced.mirror_coord is fake_mirror_coord
        assert forced.prepare_player_turn_modifiers is fake_prepare_modifiers
        assert forced.finalize_forced_pass is finalize_pass
        assert forced.finalize_forced_stone is finalize_stone
        assert forced.check_capture_foul is s._check_capture_foul
        assert forced.apply_puppet_move is apply_puppet
        assert forced.finish_ai_move is finish_ai
        assert restriction.try_finish_rogue_restriction_ai_move is restriction_move
        assert restriction.choose_tengen_target is choose_tengen
        assert restriction.tengen_followup_points is tengen_followup
        assert restriction.gravity_allowed_points is gravity_points
        assert restriction.lowline_allowed_points is lowline_points
        assert restriction.sansan_opening_restriction is sansan_restriction
        assert restriction.coord_to_gtp is fake_coord_to_gtp
        assert restriction.finalize_forced_stone is finalize_stone
        assert restriction.prepare_player_turn_modifiers is fake_prepare_modifiers
        assert restriction.check_capture_foul is s._check_capture_foul
        assert restriction.choose_allowed_move is choose_allowed
        assert restriction.choose_avoid_move is choose_avoid
        assert restriction.finish_ai_move is finish_ai
        assert restriction.finish_allowed_restriction_move is finish_allowed
        assert restriction.finish_sansan_restriction_move is finish_sansan
        assert shadow.try_finish_shadow_restriction_move is shadow_move
        assert shadow.roll_random is fake_random
        assert shadow.choose_allowed_move is choose_allowed
        assert shadow.finish_ai_move is finish_ai
        assert shadow.choose_restriction(game, "W", 3).message == "shadow"
        assert calls == [
            ("shadow_followup", True, "W", 3, True),
            ("gtp", "D4", 9),
        ]
        assert suboptimal.try_finish_suboptimal_rogue_move is suboptimal_move
        assert suboptimal.choose_suboptimal_move is choose_suboptimal
        assert suboptimal.finish_ai_move is finish_ai
    finally:
        s.random.random = original_random
        s.try_finish_forced_rogue_ai_move = original_forced
        s.finalize_forced_ai_pass = original_finalize_pass
        s.try_finalize_forced_ai_stone = original_finalize_stone
        s.try_apply_puppet_ai_move = original_apply_puppet
        s.try_finish_rogue_restriction_ai_move = original_restriction
        s.choose_tengen_target = original_choose_tengen
        s.tengen_followup_points = original_tengen_followup
        s.gravity_allowed_points = original_gravity_points
        s.lowline_allowed_points = original_lowline_points
        s.sansan_opening_restriction = original_sansan_restriction
        s._ai_move_avoid_points_allow_only = original_choose_allowed
        s._ai_move_avoid_points = original_choose_avoid
        s.try_finish_allowed_restriction_move = original_finish_allowed
        s.try_finish_sansan_restriction_move = original_finish_sansan
        s.try_finish_shadow_restriction_move = original_shadow
        s.try_finish_suboptimal_rogue_move = original_suboptimal
        s._ai_move_suboptimal = original_choose_suboptimal
        s._finish_ai_move = original_finish
        s.shadow_followup_points = original_shadow_followup
        s.gtp_to_coord = original_gtp_to_coord
        s.coord_to_gtp = original_coord_to_gtp
        s._mirror_coord = original_mirror_coord
        s._prepare_player_turn_modifiers = original_prepare_modifiers


def main() -> None:
    smoke_forced_binding_maps_every_field()
    smoke_restriction_binding_maps_every_field()
    smoke_shadow_and_suboptimal_bindings_map_every_field()
    smoke_rogue_ai_turn_runtime_builders_group_dependencies()
    asyncio.run(smoke_adapters_delegate_to_underlying_flow())
    smoke_server_bindings_resolve_current_runtime()
    print("rogue ai turn adapters smoke test: OK")


if __name__ == "__main__":
    main()
