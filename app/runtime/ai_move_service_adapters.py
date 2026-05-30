from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.service_bindings import AiMoveServiceBinding, bind_ai_move_service_runtime


@dataclass(frozen=True)
class AiMoveServiceRuntime:
    service: Any
    binding: AiMoveServiceBinding


def bind_ai_move_service(runtime: AiMoveServiceRuntime) -> None:
    bind_ai_move_service_runtime(runtime.service, runtime.binding)


async def pick_nonpass_fallback_move(
    runtime: AiMoveServiceRuntime,
    game: Any,
    color: str,
    visits: int,
    forbidden: set[tuple[int, int]] | None = None,
) -> str | None:
    bind_ai_move_service(runtime)
    return await runtime.service.pick_nonpass_fallback_move(game, color, visits, forbidden)


async def pick_ranked_legal_move(
    runtime: AiMoveServiceRuntime,
    game: Any,
    color: str,
    visits: int,
    forbidden: set[tuple[int, int]] | None = None,
    *,
    time_limit: float = 1.5,
) -> str | None:
    bind_ai_move_service(runtime)
    return await runtime.service.pick_ranked_legal_move(
        game,
        color,
        visits,
        forbidden,
        time_limit=time_limit,
    )


async def avoid_points(
    runtime: AiMoveServiceRuntime,
    game: Any,
    color: str,
    visits: int,
    time_limit: float,
    forbidden: list[tuple[int, int]] | set[tuple[int, int]],
) -> str:
    bind_ai_move_service(runtime)
    return await runtime.service.avoid_points(game, color, visits, time_limit, forbidden)


async def allow_only_points(
    runtime: AiMoveServiceRuntime,
    game: Any,
    color: str,
    visits: int,
    time_limit: float,
    allowed: list[tuple[int, int]],
) -> str:
    bind_ai_move_service(runtime)
    return await runtime.service.allow_only_points(game, color, visits, time_limit, allowed)


async def suboptimal_move(
    runtime: AiMoveServiceRuntime,
    game: Any,
    color: str,
    visits: int,
    time_limit: float,
    *,
    start_idx: int = 2,
    end_idx: int = 5,
) -> str | None:
    bind_ai_move_service(runtime)
    return await runtime.service.suboptimal_move(
        game,
        color,
        visits,
        time_limit,
        start_idx=start_idx,
        end_idx=end_idx,
    )


async def no_resign_move(runtime: AiMoveServiceRuntime, game: Any, color: str) -> str:
    bind_ai_move_service(runtime)
    return await runtime.service.no_resign_move(game, color)


async def retry_avoiding_ko(runtime: AiMoveServiceRuntime, game: Any, color: str) -> str:
    bind_ai_move_service(runtime)
    return await runtime.service.retry_avoiding_ko(game, color)


async def generate_move(
    runtime: AiMoveServiceRuntime,
    color: str,
    visits: int,
    time_limit: float,
) -> str:
    bind_ai_move_service(runtime)
    return await runtime.service.generate_move(color, visits, time_limit)
