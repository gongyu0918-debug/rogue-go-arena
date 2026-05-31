from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn
from app.runtime.ultimate_ai_adapters import (
    UltimateAiBonusTurnBinding,
    UltimateAiMoveSelectionBinding,
    UltimateAiTurnFinishBinding,
)


@dataclass(frozen=True)
class UltimateAiSelectionRuntimeFns:
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    plan_search: Callable[[Any], Any]
    engine: Any
    run_in_executor: Callable[..., Awaitable[Any]]
    get_game_visits: Callable[..., int]
    log_fn: Callable[[str], None]


@dataclass(frozen=True)
class UltimateAiSelectionMoveFns:
    no_resign_move: Callable[[Any, str], Awaitable[str]]
    pick_ranked_legal_move: Callable[..., Awaitable[str | None]]
    pick_nonpass_fallback_move: Callable[..., Awaitable[str | None]]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    is_suspicious_ai_pass: Callable[[Any, str, str], bool]
    resolve_occupied_ai_move: Callable[..., tuple[str, tuple[int, int] | None]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    coord_to_gtp: Callable[[int, int, int], str]


@dataclass(frozen=True)
class UltimateAiFinishFns:
    apply_ai_move_result: Callable[..., int]
    record_ultimate_turn: Callable[[Any], None]
    check_capture_foul: Callable[..., Awaitable[None]]
    post_move_effects: Callable[..., Awaitable[bool]]
    count_stones: Callable[[Any, int], int]
    apply_ultimate_effect: Callable[..., Awaitable[bool]]
    resolve_pending_ultimate_shadow_links: Callable[[Any, SendFn], Awaitable[bool]]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    choose_bonus_turn: Callable[..., Any]
    run_bonus_turn: Callable[[Any, SendFn, str, Any], Awaitable[bool]]
    finish_normal_turn: Callable[..., None]
    prepare_player_turn_modifiers: Callable[[Any], None]
    force_score: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class UltimateAiBonusFns:
    start_bonus_turn: Callable[[Any, str], None]
    run_next_ai_move: Callable[[Any, SendFn, bool], Awaitable[None]]


@dataclass(frozen=True)
class UltimateAiTuning:
    chain_chance: float
    chain_random: Callable[[], float]


@dataclass(frozen=True)
class UltimateAiDependencies:
    selection_runtime: UltimateAiSelectionRuntimeFns
    selection_moves: UltimateAiSelectionMoveFns
    finish: UltimateAiFinishFns
    bonus: UltimateAiBonusFns
    tuning: UltimateAiTuning


def build_ultimate_ai_move_selection_binding(
    dependencies: UltimateAiDependencies,
) -> UltimateAiMoveSelectionBinding:
    return UltimateAiMoveSelectionBinding(
        engine_ready=dependencies.selection_runtime.engine_ready,
        sync_board_to_katago=dependencies.selection_runtime.sync_board_to_katago,
        plan_search=dependencies.selection_runtime.plan_search,
        engine=dependencies.selection_runtime.engine,
        run_in_executor=dependencies.selection_runtime.run_in_executor,
        get_game_visits=dependencies.selection_runtime.get_game_visits,
        no_resign_move=dependencies.selection_moves.no_resign_move,
        pick_ranked_legal_move=dependencies.selection_moves.pick_ranked_legal_move,
        pick_nonpass_fallback_move=dependencies.selection_moves.pick_nonpass_fallback_move,
        retry_avoiding_ko=dependencies.selection_moves.retry_avoiding_ko,
        is_suspicious_ai_pass=dependencies.selection_moves.is_suspicious_ai_pass,
        resolve_occupied_ai_move=dependencies.selection_moves.resolve_occupied_ai_move,
        gtp_to_coord=dependencies.selection_moves.gtp_to_coord,
        coord_to_gtp=dependencies.selection_moves.coord_to_gtp,
        log_fn=dependencies.selection_runtime.log_fn,
    )


def build_ultimate_ai_turn_finish_binding(
    dependencies: UltimateAiDependencies,
) -> UltimateAiTurnFinishBinding:
    return UltimateAiTurnFinishBinding(
        chain_chance=dependencies.tuning.chain_chance,
        chain_random=dependencies.tuning.chain_random,
        apply_ai_move_result=dependencies.finish.apply_ai_move_result,
        record_ultimate_turn=dependencies.finish.record_ultimate_turn,
        check_capture_foul=dependencies.finish.check_capture_foul,
        post_move_effects=dependencies.finish.post_move_effects,
        count_stones=dependencies.finish.count_stones,
        apply_ultimate_effect=dependencies.finish.apply_ultimate_effect,
        resolve_pending_ultimate_shadow_links=dependencies.finish.resolve_pending_ultimate_shadow_links,
        sync_board_to_katago=dependencies.finish.sync_board_to_katago,
        choose_bonus_turn=dependencies.finish.choose_bonus_turn,
        run_bonus_turn=dependencies.finish.run_bonus_turn,
        finish_normal_turn=dependencies.finish.finish_normal_turn,
        prepare_player_turn_modifiers=dependencies.finish.prepare_player_turn_modifiers,
        force_score=dependencies.finish.force_score,
    )


def build_ultimate_ai_bonus_turn_binding(
    dependencies: UltimateAiDependencies,
) -> UltimateAiBonusTurnBinding:
    return UltimateAiBonusTurnBinding(
        start_bonus_turn=dependencies.bonus.start_bonus_turn,
        run_next_ai_move=dependencies.bonus.run_next_ai_move,
    )
