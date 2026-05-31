from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.callback_types import EngineCommandFn, SendFn
from app.runtime.ai_turn_adapters import AiTurnBinding


@dataclass(frozen=True)
class AiTurnRuntimeFns:
    engine_ready: Callable[[], bool]
    sync_board_to_katago: Callable[[Any], Awaitable[None]]
    snapshot_ai_turn: Callable[[Any, Callable[[], list[str]]], Any]
    rogue_card_ids: Callable[[], list[str]]
    run_engine_command: EngineCommandFn


@dataclass(frozen=True)
class AiTurnStepFns:
    try_finish_forced: Callable[[Any, SendFn, Any, EngineCommandFn], Awaitable[bool]]
    plan_search: Callable[[Any, Any], Any]
    refresh_fog_restriction: Callable[[Any, SendFn, Any, Any], Awaitable[None]]
    try_finish_restriction: Callable[[Any, SendFn, Any, Any, EngineCommandFn], Awaitable[bool]]
    try_finish_shadow: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]
    try_finish_suboptimal: Callable[[Any, SendFn, Any, Any], Awaitable[bool]]
    try_finish_generated: Callable[[Any, SendFn, Any, Any, EngineCommandFn], Awaitable[bool]]


@dataclass(frozen=True)
class AiTurnDependencies:
    runtime: AiTurnRuntimeFns
    steps: AiTurnStepFns


def build_ai_turn_binding(dependencies: AiTurnDependencies) -> AiTurnBinding:
    return AiTurnBinding(
        engine_ready=dependencies.runtime.engine_ready,
        sync_board_to_katago=dependencies.runtime.sync_board_to_katago,
        snapshot_turn=lambda game: dependencies.runtime.snapshot_ai_turn(
            game,
            dependencies.runtime.rogue_card_ids,
        ),
        try_finish_forced=lambda game, send_fn, turn: dependencies.steps.try_finish_forced(
            game,
            send_fn,
            turn,
            dependencies.runtime.run_engine_command,
        ),
        plan_search=dependencies.steps.plan_search,
        refresh_fog_restriction=dependencies.steps.refresh_fog_restriction,
        try_finish_restriction=lambda game, send_fn, turn, plan: dependencies.steps.try_finish_restriction(
            game,
            send_fn,
            turn,
            plan,
            dependencies.runtime.run_engine_command,
        ),
        try_finish_shadow=dependencies.steps.try_finish_shadow,
        try_finish_suboptimal=dependencies.steps.try_finish_suboptimal,
        try_finish_generated=lambda game, send_fn, turn, plan: dependencies.steps.try_finish_generated(
            game,
            send_fn,
            turn,
            plan,
            dependencies.runtime.run_engine_command,
        ),
    )
