from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.coach_adapters import (
    AiFinishMoveBinding,
    CoachMoveChoiceBinding,
    CoachTurnBinding,
    build_ai_finish_move_deps,
    build_coach_move_choice_deps,
    build_coach_turn_deps,
    choose_coach_ai_move,
    finish_ai_move,
    run_coach_turn_if_needed,
)
from app.runtime.coach_runtime import (
    AiFinishMoveRuntimeFns,
    CoachDependencies,
    CoachMoveChoiceRuntimeFns,
    CoachTuning,
    CoachTurnRuntimeFns,
    build_ai_finish_move_binding,
    build_coach_move_choice_binding,
    build_coach_turn_binding,
)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def fake_gtp_to_coord(_move: str, _size: int):
    return (1, 2)


def smoke_finish_binding_maps_every_field() -> None:
    binding = AiFinishMoveBinding(
        finalize_ai_move=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        no_resign_move=fake_async,
        retry_avoiding_ko=fake_async,
        check_capture_foul=fake_async,
        prepare_player_turn_modifiers=fake_sync,
        run_engine_command=fake_async,
        run_coach_turn_if_needed=fake_async,
    )

    deps = build_ai_finish_move_deps(binding)

    assert deps.finalize_ai_move is fake_async
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.no_resign_move is fake_async
    assert deps.retry_avoiding_ko is fake_async
    assert deps.check_capture_foul is fake_async
    assert deps.prepare_player_turn_modifiers is fake_sync
    assert deps.run_engine_command is fake_async
    assert deps.run_coach_turn_if_needed is fake_async


def smoke_coach_bindings_map_every_field() -> None:
    choice_binding = CoachMoveChoiceBinding(
        get_game_visits=lambda *_args, **_kwargs: 100,
        generate_ai_style_move=fake_async,
        gtp_to_coord=fake_gtp_to_coord,
        retry_avoiding_ko=fake_async,
        coach_visits=200,
        max_move_time=8.0,
    )
    turn_binding = CoachTurnBinding(
        engine_ready=lambda: True,
        choose_coach_ai_move=fake_async,
        place_auxiliary_move=fake_sync,
        check_capture_foul=fake_async,
        apply_player_rogue_move_effects=fake_async,
        apply_ai_rogue_response_effects=fake_async,
        estimate_side_winrate=fake_async,
        ai_move=fake_async,
        bonus_threshold=0.5,
        bonus_turns=3,
    )

    choice_deps = build_coach_move_choice_deps(choice_binding)
    turn_deps = build_coach_turn_deps(turn_binding)

    assert choice_deps.get_game_visits is choice_binding.get_game_visits
    assert choice_deps.generate_ai_style_move is fake_async
    assert choice_deps.gtp_to_coord is fake_gtp_to_coord
    assert choice_deps.retry_avoiding_ko is fake_async
    assert choice_deps.coach_visits == 200
    assert choice_deps.max_move_time == 8.0
    assert turn_deps.engine_ready() is True
    assert turn_deps.choose_coach_ai_move is fake_async
    assert turn_deps.place_auxiliary_move is fake_sync
    assert turn_deps.check_capture_foul is fake_async
    assert turn_deps.apply_player_rogue_move_effects is fake_async
    assert turn_deps.apply_ai_rogue_response_effects is fake_async
    assert turn_deps.estimate_side_winrate is fake_async
    assert turn_deps.ai_move is fake_async
    assert turn_deps.bonus_threshold == 0.5
    assert turn_deps.bonus_turns == 3


def smoke_coach_runtime_builders_group_dependencies() -> None:
    async def finalize_move(*_args, **_kwargs):
        return None

    def finish_gtp_to_coord(_move: str, _size: int):
        return (2, 3)

    async def no_resign(*_args, **_kwargs):
        return "D4"

    async def retry_ko(*_args, **_kwargs):
        return "Q16"

    async def finish_check_capture(*_args, **_kwargs):
        return None

    async def turn_check_capture(*_args, **_kwargs):
        return None

    def prepare_modifiers(_game):
        return SimpleNamespace(prepared=True)

    async def run_engine(*_args, **_kwargs):
        return "= ok"

    async def run_coach(*_args, **_kwargs):
        return None

    def get_visits(*_args, **_kwargs):
        return 111

    async def generate_style(*_args, **_kwargs):
        return "C3"

    def choice_gtp_to_coord(_move: str, _size: int):
        return (4, 5)

    async def choice_retry_ko(*_args, **_kwargs):
        return "R4"

    async def choose_coach(*_args, **_kwargs):
        return ("F6", (5, 5))

    def place_auxiliary(*_args, **_kwargs):
        return SimpleNamespace(coord=(6, 6))

    async def player_effects(*_args, **_kwargs):
        return None

    async def ai_effects(*_args, **_kwargs):
        return None

    async def estimate_winrate(*_args, **_kwargs):
        return 0.7

    async def ai_move(*_args, **_kwargs):
        return None

    dependencies = CoachDependencies(
        finish=AiFinishMoveRuntimeFns(
            finalize_ai_move=finalize_move,
            gtp_to_coord=finish_gtp_to_coord,
            no_resign_move=no_resign,
            retry_avoiding_ko=retry_ko,
            check_capture_foul=finish_check_capture,
            prepare_player_turn_modifiers=prepare_modifiers,
            run_engine_command=run_engine,
            run_coach_turn_if_needed=run_coach,
        ),
        choice=CoachMoveChoiceRuntimeFns(
            get_game_visits=get_visits,
            generate_ai_style_move=generate_style,
            gtp_to_coord=choice_gtp_to_coord,
            retry_avoiding_ko=choice_retry_ko,
        ),
        turn=CoachTurnRuntimeFns(
            engine_ready=lambda: True,
            choose_coach_ai_move=choose_coach,
            place_auxiliary_move=place_auxiliary,
            check_capture_foul=turn_check_capture,
            apply_player_rogue_move_effects=player_effects,
            apply_ai_rogue_response_effects=ai_effects,
            estimate_side_winrate=estimate_winrate,
            ai_move=ai_move,
        ),
        tuning=CoachTuning(
            coach_visits=222,
            max_move_time=7.5,
            bonus_threshold=0.45,
            bonus_turns=4,
        ),
    )

    finish = build_ai_finish_move_binding(dependencies)
    choice = build_coach_move_choice_binding(dependencies)
    turn = build_coach_turn_binding(dependencies)

    assert finish.finalize_ai_move is finalize_move
    assert finish.gtp_to_coord is finish_gtp_to_coord
    assert finish.no_resign_move is no_resign
    assert finish.retry_avoiding_ko is retry_ko
    assert finish.check_capture_foul is finish_check_capture
    assert finish.prepare_player_turn_modifiers is prepare_modifiers
    assert finish.run_engine_command is run_engine
    assert finish.run_coach_turn_if_needed is run_coach
    assert choice.get_game_visits is get_visits
    assert choice.generate_ai_style_move is generate_style
    assert choice.gtp_to_coord is choice_gtp_to_coord
    assert choice.retry_avoiding_ko is choice_retry_ko
    assert choice.coach_visits == 222
    assert choice.max_move_time == 7.5
    assert turn.engine_ready() is True
    assert turn.choose_coach_ai_move is choose_coach
    assert turn.place_auxiliary_move is place_auxiliary
    assert turn.check_capture_foul is turn_check_capture
    assert turn.apply_player_rogue_move_effects is player_effects
    assert turn.apply_ai_rogue_response_effects is ai_effects
    assert turn.estimate_side_winrate is estimate_winrate
    assert turn.ai_move is ai_move
    assert turn.bonus_threshold == 0.45
    assert turn.bonus_turns == 4


async def smoke_finish_adapter_delegates_to_flow() -> None:
    game = object()
    calls = []

    async def send(_payload):
        calls.append(("send",))

    async def finalize(game_arg, send_fn, **kwargs):
        calls.append((
            "finalize",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is fake_gtp_to_coord,
            kwargs["run_coach_turn_if_needed"] is fake_async,
        ))

    await finish_ai_move(
        game,
        send,
        color="W",
        card="dice",
        gtp_move="D4",
        rogue_msg="forced",
        binding=AiFinishMoveBinding(
            finalize_ai_move=finalize,
            gtp_to_coord=fake_gtp_to_coord,
            no_resign_move=fake_async,
            retry_avoiding_ko=fake_async,
            check_capture_foul=fake_async,
            prepare_player_turn_modifiers=fake_sync,
            run_engine_command=fake_async,
            run_coach_turn_if_needed=fake_async,
        ),
    )

    assert calls == [("finalize", True, True, "W", "dice", "D4", "forced", True, True)]


async def smoke_coach_adapters_delegate_to_flow() -> None:
    game = SimpleNamespace(
        size=9,
        level="5k",
        moves=[],
        game_over=True,
        two_player=False,
        current_player="B",
        player_color="B",
        ai_color="W",
        rogue_card="coach_mode",
        rogue_coach_moves_left=1,
        rogue_coach_bonus_checked=False,
        is_ko=lambda *_args: False,
    )
    calls = []

    async def generate(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "D4"

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 120

    move, coord = await choose_coach_ai_move(
        game,
        "B",
        CoachMoveChoiceBinding(
            get_game_visits=get_visits,
            generate_ai_style_move=generate,
            gtp_to_coord=fake_gtp_to_coord,
            retry_avoiding_ko=fake_async,
            coach_visits=200,
            max_move_time=10.0,
        ),
    )
    await run_coach_turn_if_needed(
        game,
        lambda _payload: asyncio.sleep(0),
        CoachTurnBinding(
            engine_ready=lambda: True,
            choose_coach_ai_move=fake_async,
            place_auxiliary_move=fake_sync,
            check_capture_foul=fake_async,
            apply_player_rogue_move_effects=fake_async,
            apply_ai_rogue_response_effects=fake_async,
            estimate_side_winrate=fake_async,
            ai_move=fake_async,
            bonus_threshold=0.5,
            bonus_turns=3,
        ),
    )

    assert (move, coord) == ("D4", (1, 2))
    assert calls == [
        ("visits", "5k", 0, "rogue"),
        ("generate", True, "B", 200, 8.0),
    ]


def smoke_server_bindings_resolve_current_runtime() -> None:
    async def finalize_move(*_args, **_kwargs):
        return None

    def server_gtp_to_coord(_move: str, _size: int):
        return (3, 4)

    async def no_resign(*_args, **_kwargs):
        return "D4"

    async def retry_ko(*_args, **_kwargs):
        return "Q16"

    async def check_capture(*_args, **_kwargs):
        return None

    def prepare_modifiers(_game):
        return SimpleNamespace(prepared=True)

    async def run_engine(*_args, **_kwargs):
        return "= ok"

    async def run_coach(*_args, **_kwargs):
        return None

    def get_visits(*_args, **_kwargs):
        return 123

    async def generate_style(*_args, **_kwargs):
        return "C3"

    async def choose_coach(*_args, **_kwargs):
        return ("E5", (4, 4))

    def place_auxiliary(*_args, **_kwargs):
        return SimpleNamespace(coord=(5, 5))

    async def player_effects(*_args, **_kwargs):
        return None

    async def ai_effects(*_args, **_kwargs):
        return None

    async def estimate_winrate(*_args, **_kwargs):
        return 0.6

    async def ai_move(*_args, **_kwargs):
        return None

    originals = {
        "finalize_ai_move": s.finalize_ai_move,
        "gtp_to_coord": s.gtp_to_coord,
        "_ai_move_no_resign": s._ai_move_no_resign,
        "_ai_retry_avoiding_ko": s._ai_retry_avoiding_ko,
        "_check_capture_foul": s._check_capture_foul,
        "_prepare_player_turn_modifiers": s._prepare_player_turn_modifiers,
        "_send_engine_command": s._send_engine_command,
        "_run_coach_turn_if_needed": s._run_coach_turn_if_needed,
        "get_game_visits": s.get_game_visits,
        "_generate_ai_style_move": s._generate_ai_style_move,
        "_choose_coach_ai_move": s._choose_coach_ai_move,
        "_place_auxiliary_ai_move_on_board": s._place_auxiliary_ai_move_on_board,
        "_apply_player_rogue_move_effects": s._apply_player_rogue_move_effects,
        "_apply_ai_rogue_response_effects": s._apply_ai_rogue_response_effects,
        "_estimate_side_winrate": s._estimate_side_winrate,
        "_ai_move": s._ai_move,
        "ROGUE_COACH_VISITS": s.ROGUE_COACH_VISITS,
        "MAX_MOVE_TIME": s.MAX_MOVE_TIME,
        "ROGUE_COACH_BONUS_THRESHOLD": s.ROGUE_COACH_BONUS_THRESHOLD,
        "ROGUE_COACH_BONUS_TURNS": s.ROGUE_COACH_BONUS_TURNS,
        "engine_ready": s.engine.ready,
    }
    try:
        s.finalize_ai_move = finalize_move
        s.gtp_to_coord = server_gtp_to_coord
        s._ai_move_no_resign = no_resign
        s._ai_retry_avoiding_ko = retry_ko
        s._check_capture_foul = check_capture
        s._prepare_player_turn_modifiers = prepare_modifiers
        s._send_engine_command = run_engine
        s._run_coach_turn_if_needed = run_coach
        s.get_game_visits = get_visits
        s._generate_ai_style_move = generate_style
        s._choose_coach_ai_move = choose_coach
        s._place_auxiliary_ai_move_on_board = place_auxiliary
        s._apply_player_rogue_move_effects = player_effects
        s._apply_ai_rogue_response_effects = ai_effects
        s._estimate_side_winrate = estimate_winrate
        s._ai_move = ai_move
        s.ROGUE_COACH_VISITS = 345
        s.MAX_MOVE_TIME = 6.5
        s.ROGUE_COACH_BONUS_THRESHOLD = 0.4
        s.ROGUE_COACH_BONUS_TURNS = 2
        s.engine.ready = True

        finish = s._ai_finish_move_binding()
        choice = s._coach_move_choice_binding()
        turn = s._coach_turn_binding()

        assert finish.finalize_ai_move is finalize_move
        assert finish.gtp_to_coord is server_gtp_to_coord
        assert finish.no_resign_move is no_resign
        assert finish.retry_avoiding_ko is retry_ko
        assert finish.check_capture_foul is check_capture
        assert finish.prepare_player_turn_modifiers is prepare_modifiers
        assert finish.run_engine_command is run_engine
        assert finish.run_coach_turn_if_needed is run_coach
        assert choice.get_game_visits is get_visits
        assert choice.generate_ai_style_move is generate_style
        assert choice.gtp_to_coord is server_gtp_to_coord
        assert choice.retry_avoiding_ko is retry_ko
        assert choice.coach_visits == 345
        assert choice.max_move_time == 6.5
        assert turn.engine_ready() is True
        assert turn.choose_coach_ai_move is choose_coach
        assert turn.place_auxiliary_move is place_auxiliary
        assert turn.check_capture_foul is check_capture
        assert turn.apply_player_rogue_move_effects is player_effects
        assert turn.apply_ai_rogue_response_effects is ai_effects
        assert turn.estimate_side_winrate is estimate_winrate
        assert turn.ai_move is ai_move
        assert turn.bonus_threshold == 0.4
        assert turn.bonus_turns == 2
    finally:
        for name, value in originals.items():
            if name == "engine_ready":
                s.engine.ready = value
            else:
                setattr(s, name, value)


def main() -> None:
    smoke_finish_binding_maps_every_field()
    smoke_coach_bindings_map_every_field()
    smoke_coach_runtime_builders_group_dependencies()
    asyncio.run(smoke_finish_adapter_delegates_to_flow())
    asyncio.run(smoke_coach_adapters_delegate_to_flow())
    smoke_server_bindings_resolve_current_runtime()
    print("coach adapters smoke test: OK")


if __name__ == "__main__":
    main()
