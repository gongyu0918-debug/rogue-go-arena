from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.gameplay.ai_turn_flow import AiTurnFlowDeps, run_ai_turn as run_ai_turn_event


SendFn = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class AiTurnBinding:
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    snapshot_turn: Callable[[Any], Any]
    try_finish_forced: Callable[[Any, SendFn, Any], Awaitable[bool]]
    plan_search: Callable[[Any, Any], Any]
    refresh_fog_restriction: Callable[[Any, SendFn, Any, Any], Awaitable[None]]
    try_finish_restriction: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]
    try_finish_shadow: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]
    try_finish_suboptimal: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]
    try_finish_generated: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]


def build_ai_turn_flow_deps(binding: AiTurnBinding) -> AiTurnFlowDeps:
    return AiTurnFlowDeps(
        engine_ready=binding.engine_ready,
        sync_board_to_katago=binding.sync_board_to_katago,
        snapshot_turn=binding.snapshot_turn,
        try_finish_forced=binding.try_finish_forced,
        plan_search=binding.plan_search,
        refresh_fog_restriction=binding.refresh_fog_restriction,
        try_finish_restriction=binding.try_finish_restriction,
        try_finish_shadow=binding.try_finish_shadow,
        try_finish_suboptimal=binding.try_finish_suboptimal,
        try_finish_generated=binding.try_finish_generated,
    )


async def run_ai_turn(
    game: Any,
    send_fn: SendFn,
    binding: AiTurnBinding,
) -> None:
    await run_ai_turn_event(game, send_fn, build_ai_turn_flow_deps(binding))
