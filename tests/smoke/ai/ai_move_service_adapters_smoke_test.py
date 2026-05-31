from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
from app.runtime.ai_move_service_adapters import (
    AiMoveServiceRuntime,
    allow_only_points,
    avoid_points,
    bind_ai_move_service,
    generate_move,
    no_resign_move,
    pick_nonpass_fallback_move,
    pick_ranked_legal_move,
    retry_avoiding_ko,
    suboptimal_move,
)
from app.runtime.service_bindings import AiMoveServiceBinding


async def fake_executor(*_args, **_kwargs):
    return None


class FakeAiMoveService:
    def __init__(self) -> None:
        self.events = []

    def bind_runtime(self, **kwargs) -> None:
        self.events.append(("bind", kwargs["engine"], kwargs["run_in_executor"]))

    async def pick_nonpass_fallback_move(self, game, color, visits, forbidden):
        self.events.append(("nonpass", game, color, visits, forbidden))
        return "D4"

    async def pick_ranked_legal_move(self, game, color, visits, forbidden, *, time_limit):
        self.events.append(("ranked", game, color, visits, forbidden, time_limit))
        return "Q16"

    async def avoid_points(self, game, color, visits, time_limit, forbidden):
        self.events.append(("avoid", game, color, visits, time_limit, forbidden))
        return "C3"

    async def allow_only_points(self, game, color, visits, time_limit, allowed):
        self.events.append(("allow", game, color, visits, time_limit, allowed))
        return "E5"

    async def suboptimal_move(self, game, color, visits, time_limit, *, start_idx, end_idx):
        self.events.append(("suboptimal", game, color, visits, time_limit, start_idx, end_idx))
        return "K10"

    async def no_resign_move(self, game, color):
        self.events.append(("no_resign", game, color))
        return "pass"

    async def retry_avoiding_ko(self, game, color):
        self.events.append(("retry", game, color))
        return "R4"

    async def generate_move(self, color, visits, time_limit):
        self.events.append(("generate", color, visits, time_limit))
        return "= D16"


def make_runtime(service: FakeAiMoveService, engine: object) -> AiMoveServiceRuntime:
    return AiMoveServiceRuntime(
        service=service,
        binding=AiMoveServiceBinding(engine=engine, run_in_executor=fake_executor),
    )


async def smoke_adapters_bind_before_service_calls() -> None:
    service = FakeAiMoveService()
    engine = object()
    runtime = make_runtime(service, engine)
    game = object()
    forbidden = {(1, 2)}
    allowed = [(3, 4)]

    bind_ai_move_service(runtime)
    assert await pick_nonpass_fallback_move(runtime, game, "B", 100, forbidden) == "D4"
    assert await pick_ranked_legal_move(runtime, game, "W", 200, forbidden, time_limit=2.5) == "Q16"
    assert await avoid_points(runtime, game, "B", 300, 1.5, forbidden) == "C3"
    assert await allow_only_points(runtime, game, "W", 400, 2.0, allowed) == "E5"
    assert await suboptimal_move(runtime, game, "B", 500, 2.2, start_idx=3, end_idx=6) == "K10"
    assert await no_resign_move(runtime, game, "W") == "pass"
    assert await retry_avoiding_ko(runtime, game, "B") == "R4"
    assert await generate_move(runtime, "W", 600, 3.3) == "= D16"

    bind = ("bind", engine, fake_executor)
    assert service.events == [
        bind,
        bind,
        ("nonpass", game, "B", 100, forbidden),
        bind,
        ("ranked", game, "W", 200, forbidden, 2.5),
        bind,
        ("avoid", game, "B", 300, 1.5, forbidden),
        bind,
        ("allow", game, "W", 400, 2.0, allowed),
        bind,
        ("suboptimal", game, "B", 500, 2.2, 3, 6),
        bind,
        ("no_resign", game, "W"),
        bind,
        ("retry", game, "B"),
        bind,
        ("generate", "W", 600, 3.3),
    ]


async def smoke_server_wrappers_resolve_current_runtime() -> None:
    service = FakeAiMoveService()
    engine = object()
    game = object()
    forbidden = {(2, 3)}
    allowed = [(4, 5)]

    originals = {
        "ai_move_service": s.ai_move_service,
        "engine": s.engine,
        "run_in_executor": s.run_in_executor,
    }
    try:
        s.ai_move_service = service
        s.engine = engine
        s.run_in_executor = fake_executor

        runtime = s._ai_move_service_runtime()
        assert runtime.service is service
        assert runtime.binding.engine is engine
        assert runtime.binding.run_in_executor is fake_executor

        s._bind_ai_move_service_runtime()
        assert await s._pick_nonpass_fallback_move(game, "B", 101, forbidden) == "D4"
        assert await s._pick_ranked_legal_move(game, "W", 202, forbidden, time_limit=2.7) == "Q16"
        assert await s._ai_move_avoid_points(game, "B", 303, 1.6, forbidden) == "C3"
        assert await s._ai_move_avoid_points_allow_only(game, "W", 404, 2.1, allowed) == "E5"
        assert await s._ai_move_suboptimal(game, "B", 505, 2.3, start_idx=4, end_idx=7) == "K10"
        assert await s._ai_move_no_resign(game, "W") == "pass"
        assert await s._ai_retry_avoiding_ko(game, "B") == "R4"
        assert await s._ai_generate_move("W", 606, 3.4) == "= D16"
    finally:
        s.ai_move_service = originals["ai_move_service"]
        s.engine = originals["engine"]
        s.run_in_executor = originals["run_in_executor"]

    bind = ("bind", engine, fake_executor)
    assert service.events == [
        bind,
        bind,
        ("nonpass", game, "B", 101, forbidden),
        bind,
        ("ranked", game, "W", 202, forbidden, 2.7),
        bind,
        ("avoid", game, "B", 303, 1.6, forbidden),
        bind,
        ("allow", game, "W", 404, 2.1, allowed),
        bind,
        ("suboptimal", game, "B", 505, 2.3, 4, 7),
        bind,
        ("no_resign", game, "W"),
        bind,
        ("retry", game, "B"),
        bind,
        ("generate", "W", 606, 3.4),
    ]


async def main() -> None:
    await smoke_adapters_bind_before_service_calls()
    await smoke_server_wrappers_resolve_current_runtime()
    print("ai move service adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
