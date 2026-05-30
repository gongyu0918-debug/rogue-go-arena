from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ai_finish_move_flow import AiFinishMoveDeps, finish_ai_move_event
from app.gameplay.coach_mode import (
    CoachMoveChoiceDeps,
    CoachTurnDeps,
    choose_coach_ai_move as choose_coach_ai_move_event,
    run_coach_turn_if_needed as run_coach_turn_if_needed_event,
)


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
EngineCommandFn = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class AiFinishMoveBinding:
    finalize_ai_move: Callable[..., Awaitable[None]]
    gtp_to_coord: Callable[..., Any]
    no_resign_move: Callable[[Any, str], Awaitable[str]]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    check_capture_foul: Callable[..., Awaitable[None]]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    run_engine_command: EngineCommandFn
    run_coach_turn_if_needed: Callable[[Any, SendFn], Awaitable[None]]


@dataclass(frozen=True)
class CoachMoveChoiceBinding:
    get_game_visits: Callable[..., int]
    generate_ai_style_move: Callable[[Any, str, int, float], Awaitable[str]]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    retry_avoiding_ko: Callable[[Any, str], Awaitable[str]]
    coach_visits: int
    max_move_time: float


@dataclass(frozen=True)
class CoachTurnBinding:
    engine_ready: Callable[[], bool]
    choose_coach_ai_move: Callable[[Any, str], Awaitable[tuple[str, tuple[int, int] | None]]]
    place_auxiliary_move: Callable[[Any, str, str, tuple[int, int] | None], Any]
    check_capture_foul: Callable[..., Awaitable[None]]
    apply_player_rogue_move_effects: Callable[[Any, SendFn, int, int, str, int], Awaitable[None]]
    apply_ai_rogue_response_effects: Callable[[Any, SendFn, int, int, str], Awaitable[None]]
    estimate_side_winrate: Callable[[Any, str], Awaitable[float]]
    ai_move: Callable[[Any, SendFn], Awaitable[None]]
    bonus_threshold: float
    bonus_turns: int


def build_ai_finish_move_deps(binding: AiFinishMoveBinding) -> AiFinishMoveDeps:
    return AiFinishMoveDeps(
        finalize_ai_move=binding.finalize_ai_move,
        gtp_to_coord=binding.gtp_to_coord,
        no_resign_move=binding.no_resign_move,
        retry_avoiding_ko=binding.retry_avoiding_ko,
        check_capture_foul=binding.check_capture_foul,
        prepare_player_turn_modifiers=binding.prepare_player_turn_modifiers,
        run_engine_command=binding.run_engine_command,
        run_coach_turn_if_needed=binding.run_coach_turn_if_needed,
    )


def build_coach_move_choice_deps(binding: CoachMoveChoiceBinding) -> CoachMoveChoiceDeps:
    return CoachMoveChoiceDeps(
        get_game_visits=binding.get_game_visits,
        generate_ai_style_move=binding.generate_ai_style_move,
        gtp_to_coord=binding.gtp_to_coord,
        retry_avoiding_ko=binding.retry_avoiding_ko,
        coach_visits=binding.coach_visits,
        max_move_time=binding.max_move_time,
    )


def build_coach_turn_deps(binding: CoachTurnBinding) -> CoachTurnDeps:
    return CoachTurnDeps(
        engine_ready=binding.engine_ready,
        choose_coach_ai_move=binding.choose_coach_ai_move,
        place_auxiliary_move=binding.place_auxiliary_move,
        check_capture_foul=binding.check_capture_foul,
        apply_player_rogue_move_effects=binding.apply_player_rogue_move_effects,
        apply_ai_rogue_response_effects=binding.apply_ai_rogue_response_effects,
        estimate_side_winrate=binding.estimate_side_winrate,
        ai_move=binding.ai_move,
        bonus_threshold=binding.bonus_threshold,
        bonus_turns=binding.bonus_turns,
    )


async def finish_ai_move(
    game: Any,
    send_fn: SendFn,
    *,
    color: str,
    card: str | None,
    gtp_move: str,
    rogue_msg: str | None = None,
    binding: AiFinishMoveBinding,
) -> None:
    await finish_ai_move_event(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=gtp_move,
        rogue_msg=rogue_msg,
        deps=build_ai_finish_move_deps(binding),
    )


async def choose_coach_ai_move(
    game: Any,
    color: str,
    binding: CoachMoveChoiceBinding,
) -> tuple[str, tuple[int, int] | None]:
    return await choose_coach_ai_move_event(
        game,
        color,
        build_coach_move_choice_deps(binding),
    )


async def run_coach_turn_if_needed(
    game: Any,
    send_fn: SendFn,
    binding: CoachTurnBinding,
) -> None:
    await run_coach_turn_if_needed_event(
        game,
        send_fn,
        build_coach_turn_deps(binding),
    )
