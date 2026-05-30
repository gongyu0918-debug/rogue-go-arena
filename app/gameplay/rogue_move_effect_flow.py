from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn

HasRogueFn = Callable[[Any, str], bool]
SyncGameFn = Callable[[Any], Awaitable[None]]
BoardEffectFn = Callable[..., Any]
ChallengeTrapBonusFn = Callable[[Any, SendFn, str], Awaitable[None]]
ChallengeReduceFn = Callable[[Any, SendFn], Awaitable[None]]
TriggerFiveInRowFn = Callable[[Any, SendFn, str], Awaitable[Any]]
TriggerLastStandFn = Callable[[Any, SendFn, str, tuple[int, int]], Awaitable[Any]]


@dataclass(frozen=True)
class PlayerRogueMoveEffectDeps:
    has_rogue: HasRogueFn
    erosion_shift: float
    sync_engine_komi: SyncGameFn
    apply_board_effects: BoardEffectFn
    coord_to_gtp: Callable[..., Any]
    gtp_to_coord: Callable[..., Any]
    engine_ready: Callable[[], bool]
    sync_board_to_katago: SyncGameFn
    challenge_apply_trap_bonus: ChallengeTrapBonusFn
    trigger_five_in_row: TriggerFiveInRowFn
    trigger_last_stand: TriggerLastStandFn
    challenge_maybe_reduce_ai_level: ChallengeReduceFn


@dataclass(frozen=True)
class AiRogueResponseEffectDeps:
    apply_board_effects: BoardEffectFn
    coord_to_gtp: Callable[..., Any]
    shuffle_points: Callable[..., Any]
    engine_ready: Callable[[], bool]
    sync_board_to_katago: SyncGameFn


async def apply_player_rogue_move_effects_event(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    captured: int,
    deps: PlayerRogueMoveEffectDeps,
) -> None:
    if deps.has_rogue(game, "erosion") and captured > 0:
        shift = deps.erosion_shift * captured
        owner_color = color if game.two_player else game.player_color
        if owner_color == "B":
            game.komi -= shift
        else:
            game.komi += shift
        await deps.sync_engine_komi(game)
        await send_fn({
            "type": "rogue_event",
            "msg": f"蚕食触发：提掉 {captured} 子，当前贴目变为 {game.komi}",
        })

    board_effect = deps.apply_board_effects(
        game,
        x=x,
        y=y,
        color=color,
        captured=captured,
        coord_to_gtp=deps.coord_to_gtp,
        gtp_to_coord=deps.gtp_to_coord,
    )
    if board_effect.modified and deps.engine_ready():
        await deps.sync_board_to_katago(game)
    for message in board_effect.messages:
        await send_fn({"type": "rogue_event", "msg": message})
    for source_name in board_effect.trap_bonus_sources:
        await deps.challenge_apply_trap_bonus(game, send_fn, source_name)

    if deps.has_rogue(game, "five_in_row"):
        await deps.trigger_five_in_row(game, send_fn, color)

    if deps.has_rogue(game, "last_stand"):
        await deps.trigger_last_stand(game, send_fn, color, (x, y))

    await deps.challenge_maybe_reduce_ai_level(game, send_fn)


async def apply_ai_rogue_response_effects_event(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    deps: AiRogueResponseEffectDeps,
) -> None:
    board_effect = deps.apply_board_effects(
        game,
        x=x,
        y=y,
        coord_to_gtp=deps.coord_to_gtp,
        shuffle_points=deps.shuffle_points,
    )
    if board_effect.modified and deps.engine_ready():
        await deps.sync_board_to_katago(game)
    for message in board_effect.messages:
        await send_fn({"type": "rogue_event", "msg": message})
