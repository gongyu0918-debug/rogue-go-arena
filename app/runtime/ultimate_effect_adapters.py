from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ultimate_effect_flow import (
    UltimateEffectFlowDeps,
    apply_ultimate_effect_event,
)
from app.callback_types import SendFn


@dataclass(frozen=True)
class UltimateEffectBinding:
    apply_effect: Callable[..., Awaitable[bool]]
    coord_to_gtp: Callable[[int, int, int], str | None]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    trigger_five_in_row: Callable[[Any, SendFn, str], Awaitable[bool]]
    trigger_last_stand: Callable[[Any, SendFn, str], Awaitable[bool]]
    apply_foolish_wisdom_wave: Callable[..., Any]
    make_rng: Callable[[], Any]
    sleep: Callable[[float], Awaitable[None]]
    foolish_chain_delay: float


def build_ultimate_effect_flow_deps(binding: UltimateEffectBinding) -> UltimateEffectFlowDeps:
    return UltimateEffectFlowDeps(
        apply_effect=binding.apply_effect,
        coord_to_gtp=binding.coord_to_gtp,
        gtp_to_coord=binding.gtp_to_coord,
        trigger_five_in_row=binding.trigger_five_in_row,
        trigger_last_stand=binding.trigger_last_stand,
        apply_foolish_wisdom_wave=binding.apply_foolish_wisdom_wave,
        make_rng=binding.make_rng,
        sleep=binding.sleep,
        foolish_chain_delay=binding.foolish_chain_delay,
    )


async def apply_ultimate_effect(
    game: Any,
    send_fn: SendFn,
    *,
    x: int,
    y: int,
    color: str,
    card: str,
    binding: UltimateEffectBinding,
) -> bool:
    return await apply_ultimate_effect_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        card=card,
        deps=build_ultimate_effect_flow_deps(binding),
    )
