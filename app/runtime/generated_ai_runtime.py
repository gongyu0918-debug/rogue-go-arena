from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn
from app.runtime.generated_ai_adapters import (
    GeneratedAiTurnBinding,
    GeneratedMoveCandidateBinding,
    GeneratedMoveFinishBinding,
    GeneratedMovePreparationBinding,
)


@dataclass(frozen=True)
class GeneratedMoveCandidateFns:
    choose_candidate: Callable[..., Any]
    choose_avoid_move: Callable[..., Awaitable[Any]]
    analyze_position: Callable[..., Awaitable[Any]]
    choose_style_move: Callable[..., Awaitable[Any]]
    generate_move: Callable[..., Awaitable[str]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    log_error: Callable[[str], None]


@dataclass(frozen=True)
class GeneratedMovePreparationFns:
    prepare_move: Callable[..., Awaitable[Any]]
    apply_suspicious_pass_fallback_fn: Callable[..., Awaitable[str]]
    is_suspicious_pass: Callable[..., bool]
    pick_nonpass_fallback_move: Callable[..., Awaitable[str | None]]
    undo_engine_move: Callable[[], None] | None
    run_engine_command: EngineCommandFn | None
    log_event: Callable[[str], None]
    resolve_resign_move: Callable[..., Awaitable[Any]]
    no_resign_move: Callable[..., Awaitable[str]]
    apply_slip_move: Callable[..., Any]
    roll_random: Callable[[], float]
    choose_point: Callable[[Any], Any]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    coord_to_gtp: Callable[[int, int, int], str]
    adjacent_points: Callable[..., list[tuple[int, int]]]
    retry_ko_move: Callable[..., Awaitable[Any]]
    retry_avoiding_ko: Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class GeneratedMoveFinishFns:
    finish_move: Callable[..., Awaitable[Any]]
    apply_placement_effects: Callable[..., Awaitable[Any]]
    finish_turn_response: Callable[..., Awaitable[Any]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    sync_board_to_engine: Callable[[Any], Awaitable[None]]
    engine_is_ready: Callable[[], bool]
    apply_move_to_board: Callable[..., Any]
    apply_sansan_trap_counter: Callable[..., Awaitable[Any]]
    try_no_regret_bonus: Callable[..., Awaitable[Any]]
    get_sansan_points: Callable[..., list[tuple[int, int]]]
    adjacent_points: Callable[..., list[tuple[int, int]]]
    shuffle_points: Callable[[list[Any]], None]
    spawn_bonus_points: Callable[..., Any]
    coord_to_gtp: Callable[[int, int, int], str]
    apply_trap_bonus: Callable[..., Awaitable[None]]
    roll_random: Callable[[], float]
    has_rogue_card: Callable[[Any, str], bool]
    pick_best_point: Callable[..., Awaitable[tuple[int, int] | None]]
    check_capture_foul: Callable[..., Awaitable[None]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    apply_erosion_counter: Callable[..., Awaitable[Any]]
    run_erosion_command: EngineCommandFn
    erosion_message: Callable[[int, float], str]
    finalize_double_pass: Callable[..., Awaitable[Any]]
    send_ai_move_response: Callable[..., Awaitable[Any]]
    run_coach_turn_if_needed: Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class GeneratedMoveFinishTuning:
    trap_stones: int
    no_regret_chance: float
    erosion_shift: float


@dataclass(frozen=True)
class GeneratedAiTurnFns:
    rogue_forbidden_points: Callable[..., list[tuple[int, int]]]
    challenge_zone_points: Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
    try_finish_generated_ai_move: Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class GeneratedAiRuntimeDependencies:
    candidate: GeneratedMoveCandidateFns
    preparation: GeneratedMovePreparationFns
    finish: GeneratedMoveFinishFns
    finish_tuning: GeneratedMoveFinishTuning
    turn: GeneratedAiTurnFns


def build_generated_move_candidate_binding(
    dependencies: GeneratedAiRuntimeDependencies,
) -> GeneratedMoveCandidateBinding:
    return GeneratedMoveCandidateBinding(
        choose_candidate=dependencies.candidate.choose_candidate,
        choose_avoid_move=dependencies.candidate.choose_avoid_move,
        analyze_position=dependencies.candidate.analyze_position,
        choose_style_move=dependencies.candidate.choose_style_move,
        generate_move=dependencies.candidate.generate_move,
        gtp_to_coord=dependencies.candidate.gtp_to_coord,
        log_error=dependencies.candidate.log_error,
    )


def build_generated_move_preparation_binding(
    dependencies: GeneratedAiRuntimeDependencies,
) -> GeneratedMovePreparationBinding:
    return GeneratedMovePreparationBinding(
        prepare_move=dependencies.preparation.prepare_move,
        apply_suspicious_pass_fallback_fn=dependencies.preparation.apply_suspicious_pass_fallback_fn,
        is_suspicious_pass=dependencies.preparation.is_suspicious_pass,
        pick_nonpass_fallback_move=dependencies.preparation.pick_nonpass_fallback_move,
        undo_engine_move=dependencies.preparation.undo_engine_move,
        run_engine_command=dependencies.preparation.run_engine_command,
        log_event=dependencies.preparation.log_event,
        resolve_resign_move=dependencies.preparation.resolve_resign_move,
        no_resign_move=dependencies.preparation.no_resign_move,
        apply_slip_move=dependencies.preparation.apply_slip_move,
        roll_random=dependencies.preparation.roll_random,
        choose_point=dependencies.preparation.choose_point,
        gtp_to_coord=dependencies.preparation.gtp_to_coord,
        coord_to_gtp=dependencies.preparation.coord_to_gtp,
        adjacent_points=dependencies.preparation.adjacent_points,
        retry_ko_move=dependencies.preparation.retry_ko_move,
        retry_avoiding_ko=dependencies.preparation.retry_avoiding_ko,
    )


def build_generated_move_finish_binding(
    dependencies: GeneratedAiRuntimeDependencies,
    run_double_pass_command: EngineCommandFn,
) -> GeneratedMoveFinishBinding:
    return GeneratedMoveFinishBinding(
        finish_move=dependencies.finish.finish_move,
        apply_placement_effects=dependencies.finish.apply_placement_effects,
        finish_turn_response=dependencies.finish.finish_turn_response,
        gtp_to_coord=dependencies.finish.gtp_to_coord,
        sync_board_to_engine=dependencies.finish.sync_board_to_engine,
        engine_is_ready=dependencies.finish.engine_is_ready,
        apply_move_to_board=dependencies.finish.apply_move_to_board,
        apply_sansan_trap_counter=dependencies.finish.apply_sansan_trap_counter,
        try_no_regret_bonus=dependencies.finish.try_no_regret_bonus,
        trap_stones=dependencies.finish_tuning.trap_stones,
        get_sansan_points=dependencies.finish.get_sansan_points,
        adjacent_points=dependencies.finish.adjacent_points,
        shuffle_points=dependencies.finish.shuffle_points,
        spawn_bonus_points=dependencies.finish.spawn_bonus_points,
        coord_to_gtp=dependencies.finish.coord_to_gtp,
        apply_trap_bonus=dependencies.finish.apply_trap_bonus,
        no_regret_chance=dependencies.finish_tuning.no_regret_chance,
        roll_random=dependencies.finish.roll_random,
        has_rogue_card=dependencies.finish.has_rogue_card,
        pick_best_point=dependencies.finish.pick_best_point,
        check_capture_foul=dependencies.finish.check_capture_foul,
        prepare_player_turn_modifiers=dependencies.finish.prepare_player_turn_modifiers,
        apply_erosion_counter=dependencies.finish.apply_erosion_counter,
        erosion_shift=dependencies.finish_tuning.erosion_shift,
        run_erosion_command=dependencies.finish.run_erosion_command,
        erosion_message=dependencies.finish.erosion_message,
        finalize_double_pass=dependencies.finish.finalize_double_pass,
        run_double_pass_command=run_double_pass_command,
        send_ai_move_response=dependencies.finish.send_ai_move_response,
        run_coach_turn_if_needed=dependencies.finish.run_coach_turn_if_needed,
    )


def build_generated_ai_turn_binding(
    dependencies: GeneratedAiRuntimeDependencies,
    *,
    candidate_binding: Callable[[], GeneratedMoveCandidateBinding],
    preparation_binding: Callable[[], GeneratedMovePreparationBinding],
    finish_binding: Callable[[EngineCommandFn], GeneratedMoveFinishBinding],
) -> GeneratedAiTurnBinding:
    return GeneratedAiTurnBinding(
        rogue_forbidden_points=dependencies.turn.rogue_forbidden_points,
        challenge_zone_points=dependencies.turn.challenge_zone_points,
        try_finish_generated_ai_move=dependencies.turn.try_finish_generated_ai_move,
        candidate_binding=candidate_binding,
        preparation_binding=preparation_binding,
        finish_binding=finish_binding,
    )
