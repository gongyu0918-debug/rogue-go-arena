from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn, SendFn
from app.runtime.coach_adapters import (
    AiFinishMoveBinding,
    CoachMoveChoiceBinding,
    CoachTurnBinding,
)


@dataclass(frozen=True)
class AiFinishMoveRuntimeFns:
    finalize_ai_move: Callable[..., Awaitable[None]]
    gtp_to_coord: Callable[..., Any]
    no_resign_move: Callable[[Any, str], Awaitable[str]]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    check_capture_foul: Callable[..., Awaitable[None]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    run_engine_command: EngineCommandFn
    run_coach_turn_if_needed: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class CoachMoveChoiceRuntimeFns:
    get_game_visits: Callable[..., int]
    generate_ai_style_move: Callable[[Any, str, int, float], Awaitable[str]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]


@dataclass(frozen=True)
class CoachTurnRuntimeFns:
    engine_ready: Callable[[], bool]
    choose_coach_ai_move: Callable[[Any, str], Awaitable[tuple[str, tuple[int, int] | None]]]
    place_auxiliary_move: Callable[[Any, str, str, tuple[int, int] | None], Any]
    check_capture_foul: Callable[..., Awaitable[None]]
    apply_player_rogue_move_effects: Callable[[Any, SendFn, int, int, str, int], Awaitable[None]]
    apply_ai_rogue_response_effects: Callable[[Any, SendFn, int, int, str], Awaitable[None]]
    estimate_side_winrate: Callable[[Any, str], Awaitable[float]]
    ai_move: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class CoachTuning:
    coach_visits: int
    max_move_time: float
    bonus_threshold: float
    bonus_turns: int


@dataclass(frozen=True)
class CoachDependencies:
    finish: AiFinishMoveRuntimeFns
    choice: CoachMoveChoiceRuntimeFns
    turn: CoachTurnRuntimeFns
    tuning: CoachTuning


def build_ai_finish_move_binding(
    dependencies: CoachDependencies,
) -> AiFinishMoveBinding:
    return AiFinishMoveBinding(
        finalize_ai_move=dependencies.finish.finalize_ai_move,
        gtp_to_coord=dependencies.finish.gtp_to_coord,
        no_resign_move=dependencies.finish.no_resign_move,
        retry_avoiding_ko=dependencies.finish.retry_avoiding_ko,
        check_capture_foul=dependencies.finish.check_capture_foul,
        prepare_player_turn_modifiers=dependencies.finish.prepare_player_turn_modifiers,
        run_engine_command=dependencies.finish.run_engine_command,
        run_coach_turn_if_needed=dependencies.finish.run_coach_turn_if_needed,
    )


def build_coach_move_choice_binding(
    dependencies: CoachDependencies,
) -> CoachMoveChoiceBinding:
    return CoachMoveChoiceBinding(
        get_game_visits=dependencies.choice.get_game_visits,
        generate_ai_style_move=dependencies.choice.generate_ai_style_move,
        gtp_to_coord=dependencies.choice.gtp_to_coord,
        retry_avoiding_ko=dependencies.choice.retry_avoiding_ko,
        coach_visits=dependencies.tuning.coach_visits,
        max_move_time=dependencies.tuning.max_move_time,
    )


def build_coach_turn_binding(
    dependencies: CoachDependencies,
) -> CoachTurnBinding:
    return CoachTurnBinding(
        engine_ready=dependencies.turn.engine_ready,
        choose_coach_ai_move=dependencies.turn.choose_coach_ai_move,
        place_auxiliary_move=dependencies.turn.place_auxiliary_move,
        check_capture_foul=dependencies.turn.check_capture_foul,
        apply_player_rogue_move_effects=dependencies.turn.apply_player_rogue_move_effects,
        apply_ai_rogue_response_effects=dependencies.turn.apply_ai_rogue_response_effects,
        estimate_side_winrate=dependencies.turn.estimate_side_winrate,
        ai_move=dependencies.turn.ai_move,
        bonus_threshold=dependencies.tuning.bonus_threshold,
        bonus_turns=dependencies.tuning.bonus_turns,
    )
