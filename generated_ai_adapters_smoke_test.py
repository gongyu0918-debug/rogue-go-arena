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
from app.runtime.generated_ai_runtime import (
    GeneratedAiRuntimeDependencies,
    GeneratedAiTurnFns,
    GeneratedMoveCandidateFns,
    GeneratedMoveFinishFns,
    GeneratedMoveFinishTuning,
    GeneratedMovePreparationFns,
    build_generated_ai_turn_binding,
    build_generated_move_candidate_binding,
    build_generated_move_finish_binding,
    build_generated_move_preparation_binding,
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


def smoke_generated_ai_runtime_builders_group_dependencies() -> None:
    async def run_erosion(command: str) -> str:
        return f"erosion:{command}"

    async def run_double_pass(command: str) -> str:
        return f"double:{command}"

    candidate_fns = GeneratedMoveCandidateFns(
        choose_candidate=lambda *_args, **_kwargs: "candidate",
        choose_avoid_move=fake_async,
        analyze_position=fake_async,
        choose_style_move=fake_async,
        generate_move=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        log_error=fake_sync,
    )
    preparation_fns = GeneratedMovePreparationFns(
        prepare_move=fake_async,
        apply_suspicious_pass_fallback_fn=fake_async,
        is_suspicious_pass=lambda *_args, **_kwargs: False,
        pick_nonpass_fallback_move=fake_async,
        log_event=fake_sync,
        resolve_resign_move=fake_async,
        no_resign_move=fake_async,
        apply_slip_move=fake_sync,
        roll_random=lambda: 0.3,
        choose_point=lambda points: points[0],
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        adjacent_points=fake_sync,
        retry_ko_move=fake_async,
        retry_avoiding_ko=fake_async,
    )
    finish_fns = GeneratedMoveFinishFns(
        finish_move=fake_async,
        apply_placement_effects=fake_async,
        finish_turn_response=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        sync_board_to_engine=fake_async,
        engine_is_ready=lambda: True,
        apply_move_to_board=fake_sync,
        apply_sansan_trap_counter=fake_async,
        try_no_regret_bonus=fake_async,
        get_sansan_points=fake_sync,
        adjacent_points=fake_sync,
        shuffle_points=fake_sync,
        spawn_bonus_points=fake_sync,
        coord_to_gtp=fake_coord_to_gtp,
        apply_trap_bonus=fake_async,
        roll_random=lambda: 0.4,
        has_rogue_card=fake_sync,
        pick_best_point=fake_async,
        prepare_player_turn_modifiers=fake_sync,
        apply_erosion_counter=fake_async,
        run_erosion_command=run_erosion,
        erosion_message=lambda capture_count, komi: f"{capture_count}:{komi}",
        finalize_double_pass=fake_async,
        send_ai_move_response=fake_async,
        run_coach_turn_if_needed=fake_async,
    )
    turn_fns = GeneratedAiTurnFns(
        rogue_forbidden_points=fake_sync,
        challenge_zone_points=lambda _game, points: list(points),
        try_finish_generated_ai_move=fake_async,
    )
    dependencies = GeneratedAiRuntimeDependencies(
        candidate=candidate_fns,
        preparation=preparation_fns,
        finish=finish_fns,
        finish_tuning=GeneratedMoveFinishTuning(
            trap_stones=4,
            no_regret_chance=0.25,
            erosion_shift=0.75,
        ),
        turn=turn_fns,
    )

    candidate = build_generated_move_candidate_binding(dependencies)
    preparation = build_generated_move_preparation_binding(dependencies)
    finish = build_generated_move_finish_binding(dependencies, run_double_pass)
    turn = build_generated_ai_turn_binding(
        dependencies,
        candidate_binding=lambda: candidate,
        preparation_binding=lambda: preparation,
        finish_binding=lambda engine_command: build_generated_move_finish_binding(
            dependencies,
            engine_command,
        ),
    )

    assert candidate.choose_candidate is candidate_fns.choose_candidate
    assert candidate.choose_avoid_move is fake_async
    assert candidate.gtp_to_coord is fake_gtp_to_coord
    assert candidate.log_error is fake_sync
    assert preparation.prepare_move is fake_async
    assert preparation.roll_random() == 0.3
    assert preparation.gtp_to_coord is fake_gtp_to_coord
    assert preparation.coord_to_gtp is fake_coord_to_gtp
    assert finish.finish_move is fake_async
    assert finish.trap_stones == 4
    assert finish.no_regret_chance == 0.25
    assert finish.erosion_shift == 0.75
    assert finish.run_erosion_command is run_erosion
    assert finish.run_double_pass_command is run_double_pass
    assert turn.rogue_forbidden_points is fake_sync
    assert turn.challenge_zone_points is turn_fns.challenge_zone_points
    assert turn.try_finish_generated_ai_move is fake_async
    assert turn.candidate_binding() is candidate
    assert turn.preparation_binding() is preparation
    assert turn.finish_binding(run_double_pass).run_double_pass_command is run_double_pass


async def smoke_generated_turn_binding_delegates_with_factories() -> None:
    game = object()
    sent = []
    calls = []
    turn = SimpleNamespace(color="W", card="fog", rogue_cards={"fog"}, ai_move_count=2)
    ai_plan = SimpleNamespace(visits=123, time_limit=1.5)

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

    def candidate_binding():
        calls.append(("candidate_binding",))
        return GeneratedMoveCandidateBinding(
            choose_candidate=fake_sync,
            choose_avoid_move=fake_async,
            analyze_position=fake_async,
            choose_style_move=fake_async,
            generate_move=fake_async,
            gtp_to_coord=fake_gtp_to_coord,
            log_error=fake_sync,
        )

    def preparation_binding():
        calls.append(("preparation_binding",))
        return GeneratedMovePreparationBinding(
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

    def finish_binding(engine_command):
        calls.append(("finish_binding", engine_command is run_engine))
        return GeneratedMoveFinishBinding(
            finish_move=fake_async,
            apply_placement_effects=fake_async,
            finish_turn_response=fake_async,
            gtp_to_coord=fake_gtp_to_coord,
            sync_board_to_engine=fake_async,
            engine_is_ready=lambda: True,
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
            run_erosion_command=engine_command,
            erosion_message=lambda capture_count, komi: f"{capture_count}:{komi}",
            finalize_double_pass=fake_async,
            run_double_pass_command=engine_command,
            send_ai_move_response=fake_async,
            run_coach_turn_if_needed=fake_async,
        )

    async def finish_move(game_arg, send_fn, **kwargs):
        calls.append((
            "finish_move",
            game_arg is game,
            send_fn is send,
            kwargs["forbidden"],
            kwargs["candidate_deps"].choose_candidate is fake_sync,
            kwargs["preparation_deps"].prepare_move is fake_async,
            kwargs["finish_deps"].run_double_pass_command is run_engine,
        ))
        await send_fn({"type": "ai_move", "gtp": "D4"})
        return True

    binding = GeneratedAiTurnBinding(
        rogue_forbidden_points=rogue_forbidden_points,
        challenge_zone_points=challenge_zone_points,
        try_finish_generated_ai_move=finish_move,
        candidate_binding=candidate_binding,
        preparation_binding=preparation_binding,
        finish_binding=finish_binding,
    )

    deps = build_generated_ai_turn_deps(binding)
    assert deps.rogue_forbidden_points is rogue_forbidden_points
    assert deps.challenge_zone_points is challenge_zone_points
    assert deps.try_finish_generated_ai_move is finish_move
    assert callable(deps.candidate_deps)
    assert callable(deps.preparation_deps)
    assert callable(deps.finish_deps)

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
        ("candidate_binding",),
        ("preparation_binding",),
        ("finish_binding", True),
        ("finish_move", True, True, [(2, 2)], True, True, True),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


def smoke_server_generated_bindings_resolve_current_runtime() -> None:
    async def choose_avoid(*_args, **_kwargs):
        return "avoid"

    async def analyze(*_args, **_kwargs):
        return {"top_moves": []}

    async def choose_style(*_args, **_kwargs):
        return "style"

    async def generate(*_args, **_kwargs):
        return "= D4"

    async def prepare(*_args, **_kwargs):
        return "prepared"

    async def suspicious_fallback(*_args, **_kwargs):
        return "fallback"

    async def nonpass(*_args, **_kwargs):
        return "D4"

    async def resolve_resign(*_args, **_kwargs):
        return "resign"

    async def no_resign(*_args, **_kwargs):
        return "pass"

    async def retry_ko(*_args, **_kwargs):
        return "retry"

    async def retry_avoiding(*_args, **_kwargs):
        return "retry-avoiding"

    async def finish_move(*_args, **_kwargs):
        return "finished"

    async def placement(*_args, **_kwargs):
        return None

    async def response(*_args, **_kwargs):
        return None

    async def sansan(*_args, **_kwargs):
        return None

    async def no_regret(*_args, **_kwargs):
        return None

    async def trap_bonus(*_args, **_kwargs):
        return None

    async def pick_best(*_args, **_kwargs):
        return (1, 2)

    async def erosion_counter(*_args, **_kwargs):
        return None

    async def erosion_command(command: str) -> str:
        return f"erosion:{command}"

    async def double_pass(command: str) -> str:
        return f"double:{command}"

    async def finalize_double(*_args, **_kwargs):
        return None

    async def send_response(*_args, **_kwargs):
        return None

    async def coach(*_args, **_kwargs):
        return None

    choose_candidate = lambda *_args, **_kwargs: "candidate"
    is_suspicious = lambda *_args, **_kwargs: False
    log_event = lambda _message: None
    slip = lambda *_args, **_kwargs: "slip"
    choose_point = lambda points: points[0]
    adjacent = lambda *_args, **_kwargs: [(1, 1)]
    move_to_board = lambda *_args, **_kwargs: None
    sansan_points = lambda *_args, **_kwargs: [(2, 2)]
    adjacent8 = lambda *_args, **_kwargs: [(3, 3)]
    shuffle = lambda _points: None
    spawn_bonus = lambda *_args, **_kwargs: None
    has_rogue = lambda *_args, **_kwargs: True
    prepare_modifiers = lambda _game: None
    rogue_forbidden = lambda *_args, **_kwargs: [(4, 4)]
    challenge_zone = lambda _game, points: list(points)
    try_finish = lambda *_args, **_kwargs: True

    originals = {
        "choose_ai_move_candidate": s.choose_ai_move_candidate,
        "_ai_move_avoid_points": s._ai_move_avoid_points,
        "_analyze_current_position": s._analyze_current_position,
        "choose_ai_style_move": s.choose_ai_style_move,
        "_ai_generate_move": s._ai_generate_move,
        "gtp_to_coord": s.gtp_to_coord,
        "coord_to_gtp": s.coord_to_gtp,
        "prepare_generated_ai_move": s.prepare_generated_ai_move,
        "apply_suspicious_pass_fallback": s.apply_suspicious_pass_fallback,
        "_is_suspicious_ai_pass": s._is_suspicious_ai_pass,
        "_pick_nonpass_fallback_move": s._pick_nonpass_fallback_move,
        "_engine_log": s._engine_log,
        "resolve_ai_resign_move": s.resolve_ai_resign_move,
        "_ai_move_no_resign": s._ai_move_no_resign,
        "apply_slip_ai_move": s.apply_slip_ai_move,
        "random_random": s.random.random,
        "random_choice": s.random.choice,
        "_adjacent_points": s._adjacent_points,
        "retry_ai_move_avoiding_ko": s.retry_ai_move_avoiding_ko,
        "_ai_retry_avoiding_ko": s._ai_retry_avoiding_ko,
        "finish_prepared_ai_move": s.finish_prepared_ai_move,
        "apply_ai_move_placement_effects": s.apply_ai_move_placement_effects,
        "finish_ai_turn_response": s.finish_ai_turn_response,
        "_sync_board_to_katago": s._sync_board_to_katago,
        "engine_ready": s.engine.ready,
        "apply_ai_move_to_board": s.apply_ai_move_to_board,
        "try_apply_sansan_trap_counter": s.try_apply_sansan_trap_counter,
        "try_apply_no_regret_bonus": s.try_apply_no_regret_bonus,
        "ROGUE_SANSAN_TRAP_STONES": s.ROGUE_SANSAN_TRAP_STONES,
        "_get_sansan_points": s._get_sansan_points,
        "_adjacent8_points": s._adjacent8_points,
        "random_shuffle": s.random.shuffle,
        "_spawn_bonus_points": s._spawn_bonus_points,
        "_challenge_apply_trap_bonus": s._challenge_apply_trap_bonus,
        "ROGUE_NO_REGRET_CHANCE": s.ROGUE_NO_REGRET_CHANCE,
        "_rogue_has": s._rogue_has,
        "_pick_best_point": s._pick_best_point,
        "_prepare_player_turn_modifiers": s._prepare_player_turn_modifiers,
        "apply_erosion_komi_counter": s.apply_erosion_komi_counter,
        "ROGUE_EROSION_SHIFT": s.ROGUE_EROSION_SHIFT,
        "_send_engine_command": s._send_engine_command,
        "try_finalize_double_pass": s.try_finalize_double_pass,
        "send_ai_move_and_run_coach": s.send_ai_move_and_run_coach,
        "_run_coach_turn_if_needed": s._run_coach_turn_if_needed,
        "rogue_forbidden_points": s.rogue_forbidden_points,
        "_challenge_zone_points": s._challenge_zone_points,
        "try_finish_generated_ai_move": s.try_finish_generated_ai_move,
    }
    try:
        s.choose_ai_move_candidate = choose_candidate
        s._ai_move_avoid_points = choose_avoid
        s._analyze_current_position = analyze
        s.choose_ai_style_move = choose_style
        s._ai_generate_move = generate
        s.gtp_to_coord = fake_gtp_to_coord
        s.coord_to_gtp = fake_coord_to_gtp
        s.prepare_generated_ai_move = prepare
        s.apply_suspicious_pass_fallback = suspicious_fallback
        s._is_suspicious_ai_pass = is_suspicious
        s._pick_nonpass_fallback_move = nonpass
        s._engine_log = log_event
        s.resolve_ai_resign_move = resolve_resign
        s._ai_move_no_resign = no_resign
        s.apply_slip_ai_move = slip
        s.random.random = lambda: 0.6
        s.random.choice = choose_point
        s._adjacent_points = adjacent
        s.retry_ai_move_avoiding_ko = retry_ko
        s._ai_retry_avoiding_ko = retry_avoiding
        s.finish_prepared_ai_move = finish_move
        s.apply_ai_move_placement_effects = placement
        s.finish_ai_turn_response = response
        s._sync_board_to_katago = fake_async
        s.engine.ready = True
        s.apply_ai_move_to_board = move_to_board
        s.try_apply_sansan_trap_counter = sansan
        s.try_apply_no_regret_bonus = no_regret
        s.ROGUE_SANSAN_TRAP_STONES = 7
        s._get_sansan_points = sansan_points
        s._adjacent8_points = adjacent8
        s.random.shuffle = shuffle
        s._spawn_bonus_points = spawn_bonus
        s._challenge_apply_trap_bonus = trap_bonus
        s.ROGUE_NO_REGRET_CHANCE = 0.8
        s._rogue_has = has_rogue
        s._pick_best_point = pick_best
        s._prepare_player_turn_modifiers = prepare_modifiers
        s.apply_erosion_komi_counter = erosion_counter
        s.ROGUE_EROSION_SHIFT = 0.9
        s._send_engine_command = erosion_command
        s.try_finalize_double_pass = finalize_double
        s.send_ai_move_and_run_coach = send_response
        s._run_coach_turn_if_needed = coach
        s.rogue_forbidden_points = rogue_forbidden
        s._challenge_zone_points = challenge_zone
        s.try_finish_generated_ai_move = try_finish

        candidate = s._generated_ai_move_candidate_binding()
        candidate_deps = build_generated_move_candidate_deps(candidate)
        preparation = s._generated_ai_move_preparation_binding()
        preparation_deps = build_generated_move_preparation_deps(preparation)
        finish = s._generated_ai_move_finish_binding(double_pass)
        finish_deps = build_generated_move_finish_deps(finish)
        turn = s._generated_ai_turn_binding()

        assert candidate.choose_candidate is choose_candidate
        assert candidate.choose_avoid_move is choose_avoid
        assert candidate.analyze_position is analyze
        assert candidate.choose_style_move is choose_style
        assert candidate.generate_move is generate
        assert candidate.gtp_to_coord is fake_gtp_to_coord
        assert candidate.log_error is print
        assert candidate_deps.choose_candidate is choose_candidate
        assert candidate_deps.choose_avoid_move is choose_avoid
        assert candidate_deps.analyze_position is analyze
        assert candidate_deps.choose_style_move is choose_style
        assert candidate_deps.generate_move is generate
        assert candidate_deps.log_error is print

        assert preparation.prepare_move is prepare
        assert preparation.apply_suspicious_pass_fallback_fn is suspicious_fallback
        assert preparation.is_suspicious_pass is is_suspicious
        assert preparation.pick_nonpass_fallback_move is nonpass
        assert preparation.log_event is log_event
        assert preparation.resolve_resign_move is resolve_resign
        assert preparation.no_resign_move is no_resign
        assert preparation.apply_slip_move is slip
        assert preparation.roll_random() == 0.6
        assert preparation.choose_point is choose_point
        assert preparation.gtp_to_coord is fake_gtp_to_coord
        assert preparation.coord_to_gtp is fake_coord_to_gtp
        assert preparation.adjacent_points is adjacent
        assert preparation.retry_ko_move is retry_ko
        assert preparation.retry_avoiding_ko is retry_avoiding
        assert preparation_deps.prepare_move is prepare
        assert preparation_deps.coord_to_gtp is fake_coord_to_gtp

        assert finish.finish_move is finish_move
        assert finish.apply_placement_effects is placement
        assert finish.finish_turn_response is response
        assert finish.engine_is_ready() is True
        assert finish.gtp_to_coord is fake_gtp_to_coord
        assert finish.sync_board_to_engine is fake_async
        assert finish.apply_move_to_board is move_to_board
        assert finish.apply_sansan_trap_counter is sansan
        assert finish.try_no_regret_bonus is no_regret
        assert finish.trap_stones == 7
        assert finish.get_sansan_points is sansan_points
        assert finish.adjacent_points is adjacent8
        assert finish.shuffle_points is shuffle
        assert finish.spawn_bonus_points is spawn_bonus
        assert finish.coord_to_gtp is fake_coord_to_gtp
        assert finish.apply_trap_bonus is trap_bonus
        assert finish.no_regret_chance == 0.8
        assert finish.roll_random() == 0.6
        assert finish.has_rogue_card is has_rogue
        assert finish.pick_best_point is pick_best
        assert finish.prepare_player_turn_modifiers is prepare_modifiers
        assert finish.apply_erosion_counter is erosion_counter
        assert finish.erosion_shift == 0.9
        assert finish.run_erosion_command is erosion_command
        assert finish.erosion_message(2, 6.5) == "蚕食反制：AI 提掉了 2 子，当前贴目变为 6.5"
        assert finish.finalize_double_pass is finalize_double
        assert finish.run_double_pass_command is double_pass
        assert finish.send_ai_move_response is send_response
        assert finish.run_coach_turn_if_needed is coach
        assert finish_deps.run_double_pass_command is double_pass
        assert finish_deps.coord_to_gtp is fake_coord_to_gtp

        assert turn.rogue_forbidden_points is rogue_forbidden
        assert turn.challenge_zone_points is challenge_zone
        assert turn.try_finish_generated_ai_move is try_finish
        assert turn.candidate_binding is s._generated_ai_move_candidate_binding
        assert turn.preparation_binding is s._generated_ai_move_preparation_binding
        assert turn.finish_binding is s._generated_ai_move_finish_binding
    finally:
        for name, value in originals.items():
            if name == "random_random":
                s.random.random = value
            elif name == "random_choice":
                s.random.choice = value
            elif name == "random_shuffle":
                s.random.shuffle = value
            elif name == "engine_ready":
                s.engine.ready = value
            else:
                setattr(s, name, value)


def main() -> None:
    smoke_candidate_binding_maps_every_field()
    smoke_preparation_binding_maps_every_field()
    smoke_finish_binding_maps_every_field()
    smoke_generated_ai_runtime_builders_group_dependencies()
    asyncio.run(smoke_generated_turn_binding_delegates_with_factories())
    smoke_server_generated_bindings_resolve_current_runtime()
    print("generated ai adapters smoke test: OK")


if __name__ == "__main__":
    main()
