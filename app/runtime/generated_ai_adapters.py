from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ai_move_flow import (
    GeneratedMoveCandidateDeps,
    GeneratedMoveFinishDeps,
    GeneratedMovePreparationDeps,
)
from app.gameplay.generated_ai_turn_flow import (
    GeneratedAiTurnDeps,
    try_finish_generated_ai_turn_event,
)
from app.callback_types import EngineCommandFn, SendFn


@dataclass(frozen=True)
class GeneratedMoveCandidateBinding:
    choose_candidate: Callable[..., Any]
    choose_avoid_move: Callable[..., Awaitable[Any]]
    analyze_position: Callable[..., Awaitable[Any]]
    choose_style_move: Callable[..., Awaitable[Any]]
    generate_move: Callable[..., Awaitable[str]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    log_error: Callable[[str], None]


@dataclass(frozen=True)
class GeneratedMovePreparationBinding:
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
class GeneratedMoveFinishBinding:
    finish_move: Callable[..., Awaitable[Any]]
    apply_placement_effects: Callable[..., Awaitable[Any]]
    finish_turn_response: Callable[..., Awaitable[Any]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    sync_board_to_engine: Callable[[Any], Awaitable[None]]
    engine_is_ready: Callable[[], bool]
    apply_move_to_board: Callable[..., Any]
    apply_sansan_trap_counter: Callable[..., Awaitable[Any]]
    try_no_regret_bonus: Callable[..., Awaitable[Any]]
    trap_stones: int
    get_sansan_points: Callable[..., list[tuple[int, int]]]
    adjacent_points: Callable[..., list[tuple[int, int]]]
    shuffle_points: Callable[[list[Any]], None]
    spawn_bonus_points: Callable[..., Any]
    coord_to_gtp: Callable[[int, int, int], str]
    apply_trap_bonus: Callable[..., Awaitable[None]]
    no_regret_chance: float
    roll_random: Callable[[], float]
    has_rogue_card: Callable[[Any, str], bool]
    pick_best_point: Callable[..., Awaitable[tuple[int, int] | None]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    apply_erosion_counter: Callable[..., Awaitable[Any]]
    erosion_shift: float
    run_erosion_command: EngineCommandFn
    erosion_message: Callable[[int, float], str]
    finalize_double_pass: Callable[..., Awaitable[Any]]
    run_double_pass_command: EngineCommandFn
    send_ai_move_response: Callable[..., Awaitable[Any]]
    run_coach_turn_if_needed: Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class GeneratedAiTurnBinding:
    rogue_forbidden_points: Callable[..., list[tuple[int, int]]]
    challenge_zone_points: Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
    try_finish_generated_ai_move: Callable[..., Awaitable[bool]]
    candidate_binding: Callable[[], GeneratedMoveCandidateBinding]
    preparation_binding: Callable[[], GeneratedMovePreparationBinding]
    finish_binding: Callable[[EngineCommandFn], GeneratedMoveFinishBinding]


def build_generated_move_candidate_deps(binding: GeneratedMoveCandidateBinding) -> GeneratedMoveCandidateDeps:
    return GeneratedMoveCandidateDeps(
        choose_candidate=binding.choose_candidate,
        choose_avoid_move=binding.choose_avoid_move,
        analyze_position=binding.analyze_position,
        choose_style_move=binding.choose_style_move,
        generate_move=binding.generate_move,
        gtp_to_coord=binding.gtp_to_coord,
        log_error=binding.log_error,
    )


def build_generated_move_preparation_deps(binding: GeneratedMovePreparationBinding) -> GeneratedMovePreparationDeps:
    return GeneratedMovePreparationDeps(
        prepare_move=binding.prepare_move,
        apply_suspicious_pass_fallback_fn=binding.apply_suspicious_pass_fallback_fn,
        is_suspicious_pass=binding.is_suspicious_pass,
        pick_nonpass_fallback_move=binding.pick_nonpass_fallback_move,
        undo_engine_move=binding.undo_engine_move,
        run_engine_command=binding.run_engine_command,
        log_event=binding.log_event,
        resolve_resign_move=binding.resolve_resign_move,
        no_resign_move=binding.no_resign_move,
        apply_slip_move=binding.apply_slip_move,
        roll_random=binding.roll_random,
        choose_point=binding.choose_point,
        gtp_to_coord=binding.gtp_to_coord,
        coord_to_gtp=binding.coord_to_gtp,
        adjacent_points=binding.adjacent_points,
        retry_ko_move=binding.retry_ko_move,
        retry_avoiding_ko=binding.retry_avoiding_ko,
    )


def build_generated_move_finish_deps(binding: GeneratedMoveFinishBinding) -> GeneratedMoveFinishDeps:
    return GeneratedMoveFinishDeps(
        finish_move=binding.finish_move,
        apply_placement_effects=binding.apply_placement_effects,
        finish_turn_response=binding.finish_turn_response,
        gtp_to_coord=binding.gtp_to_coord,
        sync_board_to_engine=binding.sync_board_to_engine,
        engine_is_ready=binding.engine_is_ready,
        apply_move_to_board=binding.apply_move_to_board,
        apply_sansan_trap_counter=binding.apply_sansan_trap_counter,
        try_no_regret_bonus=binding.try_no_regret_bonus,
        trap_stones=binding.trap_stones,
        get_sansan_points=binding.get_sansan_points,
        adjacent_points=binding.adjacent_points,
        shuffle_points=binding.shuffle_points,
        spawn_bonus_points=binding.spawn_bonus_points,
        coord_to_gtp=binding.coord_to_gtp,
        apply_trap_bonus=binding.apply_trap_bonus,
        no_regret_chance=binding.no_regret_chance,
        roll_random=binding.roll_random,
        has_rogue_card=binding.has_rogue_card,
        pick_best_point=binding.pick_best_point,
        prepare_player_turn_modifiers=binding.prepare_player_turn_modifiers,
        apply_erosion_counter=binding.apply_erosion_counter,
        erosion_shift=binding.erosion_shift,
        run_erosion_command=binding.run_erosion_command,
        erosion_message=binding.erosion_message,
        finalize_double_pass=binding.finalize_double_pass,
        run_double_pass_command=binding.run_double_pass_command,
        send_ai_move_response=binding.send_ai_move_response,
        run_coach_turn_if_needed=binding.run_coach_turn_if_needed,
    )


def build_generated_ai_turn_deps(binding: GeneratedAiTurnBinding) -> GeneratedAiTurnDeps:
    return GeneratedAiTurnDeps(
        rogue_forbidden_points=binding.rogue_forbidden_points,
        challenge_zone_points=binding.challenge_zone_points,
        try_finish_generated_ai_move=binding.try_finish_generated_ai_move,
        candidate_deps=lambda: build_generated_move_candidate_deps(binding.candidate_binding()),
        preparation_deps=lambda: build_generated_move_preparation_deps(binding.preparation_binding()),
        finish_deps=lambda run_engine_command: build_generated_move_finish_deps(
            binding.finish_binding(run_engine_command),
        ),
    )


async def try_finish_generated_ai_turn(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    ai_plan: Any,
    run_engine_command: EngineCommandFn,
    binding: GeneratedAiTurnBinding,
) -> bool:
    return await try_finish_generated_ai_turn_event(
        game,
        send_fn,
        turn,
        ai_plan,
        run_engine_command,
        build_generated_ai_turn_deps(binding),
    )
