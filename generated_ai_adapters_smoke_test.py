from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.generated_ai_adapters import (
    GeneratedAiTurnBinding,
    GeneratedMoveCandidateBinding,
    GeneratedMoveFinishBinding,
    GeneratedMovePreparationBinding,
    build_generated_ai_turn_deps,
    build_generated_move_candidate_deps,
    build_generated_move_finish_deps,
    build_generated_move_preparation_deps,
    try_finish_generated_ai_turn,
)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def fake_gtp_to_coord(_move: str, _size: int):
    return (1, 2)


def fake_coord_to_gtp(x: int, y: int, _size: int) -> str:
    return f"{x},{y}"


def smoke_candidate_binding_maps_every_field() -> None:
    binding = GeneratedMoveCandidateBinding(
        choose_candidate=fake_sync,
        choose_avoid_move=fake_async,
        analyze_position=fake_async,
        choose_style_move=fake_async,
        generate_move=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        log_error=fake_sync,
    )

    deps = build_generated_move_candidate_deps(binding)

    assert deps.choose_candidate is fake_sync
    assert deps.choose_avoid_move is fake_async
    assert deps.analyze_position is fake_async
    assert deps.choose_style_move is fake_async
    assert deps.generate_move is fake_async
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.log_error is fake_sync


def smoke_preparation_binding_maps_every_field() -> None:
    binding = GeneratedMovePreparationBinding(
        prepare_move=fake_async,
        apply_suspicious_pass_fallback_fn=fake_async,
        is_suspicious_pass=fake_sync,
        pick_nonpass_fallback_move=fake_async,
        log_event=fake_sync,
        resolve_resign_move=fake_async,
        no_resign_move=fake_async,
        apply_slip_move=fake_sync,
        roll_random=fake_sync,
        choose_point=fake_sync,
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        adjacent_points=fake_sync,
        retry_ko_move=fake_async,
        retry_avoiding_ko=fake_async,
    )

    deps = build_generated_move_preparation_deps(binding)

    assert deps.prepare_move is fake_async
    assert deps.apply_suspicious_pass_fallback_fn is fake_async
    assert deps.is_suspicious_pass is fake_sync
    assert deps.pick_nonpass_fallback_move is fake_async
    assert deps.log_event is fake_sync
    assert deps.resolve_resign_move is fake_async
    assert deps.no_resign_move is fake_async
    assert deps.apply_slip_move is fake_sync
    assert deps.roll_random is fake_sync
    assert deps.choose_point is fake_sync
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.coord_to_gtp is fake_coord_to_gtp
    assert deps.adjacent_points is fake_sync
    assert deps.retry_ko_move is fake_async
    assert deps.retry_avoiding_ko is fake_async


def smoke_finish_binding_maps_every_field() -> None:
    async def run_erosion(command: str) -> str:
        return f"erosion:{command}"

    async def run_double_pass(command: str) -> str:
        return f"double:{command}"

    binding = GeneratedMoveFinishBinding(
        finish_move=fake_async,
        apply_placement_effects=fake_async,
        finish_turn_response=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        sync_board_to_engine=fake_async,
        engine_is_ready=fake_sync,
        apply_move_to_board=fake_sync,
        apply_sansan_trap_counter=fake_async,
        try_no_regret_bonus=fake_async,
        trap_stones=3,
        get_sansan_points=fake_sync,
        adjacent_points=fake_sync,
        shuffle_points=fake_sync,
        spawn_bonus_points=fake_sync,
        coord_to_gtp=fake_coord_to_gtp,
        apply_trap_bonus=fake_async,
        no_regret_chance=0.4,
        roll_random=fake_sync,
        has_rogue_card=fake_sync,
        pick_best_point=fake_async,
        prepare_player_turn_modifiers=fake_sync,
        apply_erosion_counter=fake_async,
        erosion_shift=1.5,
        run_erosion_command=run_erosion,
        erosion_message=lambda capture_count, komi: f"{capture_count}:{komi}",
        finalize_double_pass=fake_async,
        run_double_pass_command=run_double_pass,
        send_ai_move_response=fake_async,
        run_coach_turn_if_needed=fake_async,
    )

    deps = build_generated_move_finish_deps(binding)

    assert deps.finish_move is fake_async
    assert deps.apply_placement_effects is fake_async
    assert deps.finish_turn_response is fake_async
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.sync_board_to_engine is fake_async
    assert deps.engine_is_ready is fake_sync
    assert deps.apply_move_to_board is fake_sync
    assert deps.apply_sansan_trap_counter is fake_async
    assert deps.try_no_regret_bonus is fake_async
    assert deps.trap_stones == 3
    assert deps.get_sansan_points is fake_sync
    assert deps.adjacent_points is fake_sync
    assert deps.shuffle_points is fake_sync
    assert deps.spawn_bonus_points is fake_sync
    assert deps.coord_to_gtp is fake_coord_to_gtp
    assert deps.apply_trap_bonus is fake_async
    assert deps.no_regret_chance == 0.4
    assert deps.roll_random is fake_sync
    assert deps.has_rogue_card is fake_sync
    assert deps.pick_best_point is fake_async
    assert deps.prepare_player_turn_modifiers is fake_sync
    assert deps.apply_erosion_counter is fake_async
    assert deps.erosion_shift == 1.5
    assert deps.run_erosion_command is run_erosion
    assert deps.erosion_message(2, 6.5) == "2:6.5"
    assert deps.finalize_double_pass is fake_async
    assert deps.run_double_pass_command is run_double_pass
    assert deps.send_ai_move_response is fake_async
    assert deps.run_coach_turn_if_needed is fake_async


async def smoke_generated_turn_binding_delegates_with_factories() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="W", card="fog", rogue_cards={"fog"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=123, time_limit=1.5)
    candidate_deps = object()
    preparation_deps = object()
    finish_deps = object()

    async def send(payload):
        sent.append(payload)

    async def run_engine(command: str) -> str:
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
        return [(2, 2)]

    def candidate_factory():
        calls.append(("candidate",))
        return candidate_deps

    def preparation_factory():
        calls.append(("preparation",))
        return preparation_deps

    def finish_factory(engine_command):
        calls.append(("finish", engine_command is run_engine))
        return finish_deps

    async def finish_move(game_arg, send_fn, **kwargs):
        calls.append((
            "finish_move",
            game_arg is game,
            send_fn is send,
            kwargs["forbidden"],
            kwargs["candidate_deps"] is candidate_deps,
            kwargs["preparation_deps"] is preparation_deps,
            kwargs["finish_deps"] is finish_deps,
        ))
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    binding = GeneratedAiTurnBinding(
        rogue_forbidden_points=rogue_forbidden_points,
        challenge_zone_points=challenge_zone_points,
        try_finish_generated_ai_move=finish_move,
        candidate_deps=candidate_factory,
        preparation_deps=preparation_factory,
        finish_deps=finish_factory,
    )

    deps = build_generated_ai_turn_deps(binding)
    assert deps.rogue_forbidden_points is rogue_forbidden_points
    assert deps.challenge_zone_points is challenge_zone_points
    assert deps.try_finish_generated_ai_move is finish_move
    assert deps.candidate_deps is candidate_factory
    assert deps.preparation_deps is preparation_factory
    assert deps.finish_deps is finish_factory

    result = await try_finish_generated_ai_turn(
        game,
        send,
        turn,
        ai_plan,
        run_engine,
        binding,
    )

    assert result is True
    assert calls == [
        ("forbidden", True, {"fog"}, 2, True),
        ("zone", True, ((1, 1),)),
        ("candidate",),
        ("preparation",),
        ("finish", True),
        ("finish_move", True, True, [(2, 2)], True, True, True),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


def smoke_server_generated_bindings_resolve_current_runtime() -> None:
    original_choose_candidate = s.choose_ai_move_candidate
    original_generate_move = s._ai_generate_move
    original_gtp_to_coord = s.gtp_to_coord
    original_ready = s.engine.ready
    try:
        s.choose_ai_move_candidate = fake_sync
        s._ai_generate_move = fake_async
        s.gtp_to_coord = fake_gtp_to_coord
        s.engine.ready = True

        candidate = s._generated_ai_move_candidate_binding()
        candidate_deps = s._generated_ai_move_candidate_deps()
        finish = s._generated_ai_move_finish_binding(fake_async)
        finish_deps = s._generated_ai_move_finish_deps(fake_async)
        turn = s._generated_ai_turn_binding()

        assert candidate.choose_candidate is fake_sync
        assert candidate.generate_move is fake_async
        assert candidate.gtp_to_coord is fake_gtp_to_coord
        assert candidate_deps.choose_candidate is fake_sync
        assert candidate_deps.generate_move is fake_async
        assert finish.engine_is_ready() is True
        assert finish.gtp_to_coord is fake_gtp_to_coord
        assert finish.run_double_pass_command is fake_async
        assert finish_deps.run_double_pass_command is fake_async
        assert turn.rogue_forbidden_points is s.rogue_forbidden_points
        assert turn.challenge_zone_points is s._challenge_zone_points
        assert turn.candidate_deps is s._generated_ai_move_candidate_deps
        assert turn.finish_deps is s._generated_ai_move_finish_deps
    finally:
        s.choose_ai_move_candidate = original_choose_candidate
        s._ai_generate_move = original_generate_move
        s.gtp_to_coord = original_gtp_to_coord
        s.engine.ready = original_ready


def main() -> None:
    smoke_candidate_binding_maps_every_field()
    smoke_preparation_binding_maps_every_field()
    smoke_finish_binding_maps_every_field()
    asyncio.run(smoke_generated_turn_binding_delegates_with_factories())
    smoke_server_generated_bindings_resolve_current_runtime()
    print("generated ai adapters smoke test: OK")


if __name__ == "__main__":
    main()
