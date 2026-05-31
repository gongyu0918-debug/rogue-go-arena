from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ultimate_ai_flow import (
    UltimateAiMoveChoice,
    choose_ultimate_ai_move,
    finish_ultimate_ai_turn,
    run_ultimate_ai_bonus_turn,
)
from app.callback_types import SendFn


@dataclass(frozen=True)
class UltimateAiMoveSelection:
    search_plan: Any
    choice: UltimateAiMoveChoice


@dataclass(frozen=True)
class UltimateAiMoveSelectionBinding:
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    plan_search: Callable[[Any], Any]
    engine: Any
    run_in_executor: Callable[..., Awaitable[Any]]
    get_game_visits: Callable[..., int]
    no_resign_move: Callable[[Any, str], Awaitable[str]]
    pick_ranked_legal_move: Callable[..., Awaitable[str | None]]
    pick_nonpass_fallback_move: Callable[..., Awaitable[str | None]]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    is_suspicious_ai_pass: Callable[[Any, str, str], bool]
    resolve_occupied_ai_move: Callable[..., tuple[str, tuple[int, int] | None]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    coord_to_gtp: Callable[[int, int, int], str]
    log_fn: Callable[[str], None]


@dataclass(frozen=True)
class UltimateAiTurnFinishBinding:
    chain_chance: float
    chain_random: Callable[[], float]
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
class UltimateAiBonusTurnBinding:
    start_bonus_turn: Callable[[Any, str], None]
    run_next_ai_move: Callable[[Any, SendFn, bool], Awaitable[None]]


async def select_ultimate_ai_move(
    game: Any,
    binding: UltimateAiMoveSelectionBinding,
) -> UltimateAiMoveSelection | None:
    if game.game_over or not binding.engine_ready():
        return None

    game.ultimate_extra_turn = False
    await binding.sync_board_to_katago(game)

    search_plan = binding.plan_search(game)
    color = search_plan.color
    visits = search_plan.visits

    def generate_locked() -> str:
        with binding.engine.command_lock:
            binding.engine._send_command_locked(f"kata-set-param maxVisits {visits}")
            resp = binding.engine._send_command_locked(f"genmove {color}", timeout=30)
            reset_visits = binding.get_game_visits(game.level, 0, mode="ultimate")
            binding.engine._send_command_locked(f"kata-set-param maxVisits {reset_visits}")
            return resp.replace("=", "").strip()

    def undo_engine_move() -> None:
        with binding.engine.command_lock:
            binding.engine._send_command_locked("undo")

    async def restore_engine_pass() -> str:
        return await binding.run_in_executor(binding.engine.send_command, f"play {color} pass")

    async def play_engine_move(gtp_move: str) -> str:
        return await binding.run_in_executor(binding.engine.send_command, f"play {color} {gtp_move}")

    choice = await choose_ultimate_ai_move(
        game,
        color=color,
        visits=visits,
        forbidden=search_plan.forbidden,
        generate_move=lambda: binding.run_in_executor(generate_locked),
        no_resign_move=binding.no_resign_move,
        undo_engine_move=undo_engine_move,
        restore_engine_pass=restore_engine_pass,
        play_engine_move=play_engine_move,
        pick_ranked_legal_move=binding.pick_ranked_legal_move,
        pick_nonpass_fallback_move=binding.pick_nonpass_fallback_move,
        retry_avoiding_ko=binding.retry_avoiding_ko,
        is_suspicious_ai_pass=binding.is_suspicious_ai_pass,
        resolve_occupied_ai_move=binding.resolve_occupied_ai_move,
        gtp_to_coord=binding.gtp_to_coord,
        coord_to_gtp=binding.coord_to_gtp,
        log_fn=binding.log_fn,
    )
    return UltimateAiMoveSelection(search_plan=search_plan, choice=choice)


async def finish_selected_ultimate_ai_move(
    game: Any,
    send_fn: SendFn,
    selection: UltimateAiMoveSelection,
    *,
    allow_double_bonus: bool,
    binding: UltimateAiTurnFinishBinding,
) -> bool:
    if selection.choice.error_message:
        await send_fn({"type": "error", "message": selection.choice.error_message})
        return True

    return await finish_ultimate_ai_turn(
        game,
        send_fn,
        color=selection.search_plan.color,
        ai_card=selection.search_plan.ai_card,
        gtp_move=selection.choice.gtp_move,
        coord=selection.choice.coord,
        allow_double_bonus=allow_double_bonus,
        chain_chance=binding.chain_chance,
        chain_random=binding.chain_random,
        apply_ai_move_result=binding.apply_ai_move_result,
        record_ultimate_turn=binding.record_ultimate_turn,
        check_capture_foul=binding.check_capture_foul,
        post_move_effects=binding.post_move_effects,
        count_stones=binding.count_stones,
        apply_ultimate_effect=binding.apply_ultimate_effect,
        resolve_pending_ultimate_shadow_links=binding.resolve_pending_ultimate_shadow_links,
        sync_board_to_katago=binding.sync_board_to_katago,
        choose_bonus_turn=binding.choose_bonus_turn,
        run_bonus_turn=binding.run_bonus_turn,
        finish_normal_turn=binding.finish_normal_turn,
        prepare_player_turn_modifiers=binding.prepare_player_turn_modifiers,
        force_score=binding.force_score,
    )


async def run_ultimate_ai_bonus_turn_adapter(
    game: Any,
    send_fn: SendFn,
    color: str,
    bonus_turn: Any,
    binding: UltimateAiBonusTurnBinding,
) -> bool:
    return await run_ultimate_ai_bonus_turn(
        game,
        send_fn,
        color,
        bonus_turn,
        start_bonus_turn=binding.start_bonus_turn,
        run_next_ai_move=binding.run_next_ai_move,
    )
