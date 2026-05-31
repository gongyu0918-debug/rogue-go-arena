from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import SendFn
from app.runtime.ultimate_effect_adapters import UltimateEffectBinding


@dataclass(frozen=True)
class UltimateEffectFns:
    apply_effect: Callable[..., Awaitable[bool]]
    apply_foolish_wisdom_wave: Callable[..., Any]


@dataclass(frozen=True)
class UltimateEffectRuntimeFns:
    coord_to_gtp: Callable[[int, int, int], str | None]
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None]
    trigger_five_in_row: Callable[[Any, SendFn, str], Awaitable[bool]]
    trigger_last_stand: Callable[[Any, SendFn, str], Awaitable[bool]]
    make_rng: Callable[[], Any]
    sleep: Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class UltimateEffectTuning:
    foolish_chain_delay: float


@dataclass(frozen=True)
class UltimateEffectDependencies:
    effects: UltimateEffectFns
    runtime: UltimateEffectRuntimeFns
    tuning: UltimateEffectTuning


def build_ultimate_effect_binding(
    dependencies: UltimateEffectDependencies,
) -> UltimateEffectBinding:
    return UltimateEffectBinding(
        apply_effect=dependencies.effects.apply_effect,
        coord_to_gtp=dependencies.runtime.coord_to_gtp,
        gtp_to_coord=dependencies.runtime.gtp_to_coord,
        trigger_five_in_row=dependencies.runtime.trigger_five_in_row,
        trigger_last_stand=dependencies.runtime.trigger_last_stand,
        apply_foolish_wisdom_wave=dependencies.effects.apply_foolish_wisdom_wave,
        make_rng=dependencies.runtime.make_rng,
        sleep=dependencies.runtime.sleep,
        foolish_chain_delay=dependencies.tuning.foolish_chain_delay,
    )
