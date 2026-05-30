from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
UltimateEffectFn = Callable[..., Awaitable[bool]]
UltimateTriggerFn = Callable[[Any, SendFn, str], Awaitable[bool]]
CoordToGtpFn = Callable[[int, int, int], str | None]
GtpToCoordFn = Callable[[str, int], tuple[int, int] | None]
RngFactoryFn = Callable[[], Any]
SleepFn = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class UltimateEffectFlowDeps:
    apply_effect: UltimateEffectFn
    coord_to_gtp: CoordToGtpFn
    gtp_to_coord: GtpToCoordFn
    trigger_five_in_row: UltimateTriggerFn
    trigger_last_stand: UltimateTriggerFn
    apply_foolish_wisdom_wave: Callable[..., Any]
    make_rng: RngFactoryFn
    sleep: SleepFn
    foolish_chain_delay: float


async def apply_ultimate_effect_event(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    card: str,
    deps: UltimateEffectFlowDeps,
) -> bool:
    return await deps.apply_effect(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        card=card,
        coord_to_gtp=deps.coord_to_gtp,
        gtp_to_coord=deps.gtp_to_coord,
        trigger_five_in_row_fn=deps.trigger_five_in_row,
        trigger_last_stand_fn=deps.trigger_last_stand,
        apply_foolish_wisdom_wave_fn=deps.apply_foolish_wisdom_wave,
        make_rng=deps.make_rng,
        sleep_fn=deps.sleep,
        foolish_chain_delay=deps.foolish_chain_delay,
    )
