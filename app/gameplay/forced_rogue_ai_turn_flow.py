from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
EngineCommandFn = Callable[[str], Awaitable[str]]
TryFinishForcedFn = Callable[..., Awaitable[bool]]


@dataclass(frozen=True)
class ForcedRogueAiTurnDeps:
    try_finish_forced_rogue_ai_move: TryFinishForcedFn
    roll_random: Callable[[], float]
    dice_pass_chance: float
    mirror_chance: float
    gtp_to_coord: Callable[..., Any]
    coord_to_gtp: Callable[..., Any]
    mirror_coord: Callable[..., Any]
    prepare_player_turn_modifiers: Callable[[Any], Any]
    finalize_forced_pass: Callable[..., Awaitable[None]]
    finalize_forced_stone: Callable[..., Awaitable[bool]]
    apply_puppet_move: Callable[..., Awaitable[bool]]
    finish_ai_move: Callable[..., Awaitable[None]]


async def try_finish_forced_rogue_ai_turn_event(
    game: Any,
    send_fn: SendFn,
    turn: Any,
    run_engine_command: EngineCommandFn,
    deps: ForcedRogueAiTurnDeps,
) -> bool:
    return await deps.try_finish_forced_rogue_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        roll_random=deps.roll_random,
        dice_pass_chance=deps.dice_pass_chance,
        mirror_chance=deps.mirror_chance,
        gtp_to_coord=deps.gtp_to_coord,
        coord_to_gtp=deps.coord_to_gtp,
        mirror_coord=deps.mirror_coord,
        prepare_player_turn_modifiers=deps.prepare_player_turn_modifiers,
        run_engine_command=run_engine_command,
        finalize_forced_pass=deps.finalize_forced_pass,
        finalize_forced_stone=deps.finalize_forced_stone,
        apply_puppet_move=deps.apply_puppet_move,
        finish_ai_move=deps.finish_ai_move,
    )
