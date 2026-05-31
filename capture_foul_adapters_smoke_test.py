from __future__ import annotations

import asyncio
from dataclasses import dataclass

import app.config.gameplay as gameplay_config
import server as s
from app.domain.game_state import GoGame
from app.runtime.capture_foul_adapters import (
    CaptureFoulBinding,
    check_capture_foul_violation,
)
from app.runtime.capture_foul_runtime import (
    CaptureFoulDependencies,
    CaptureFoulRuntimeFns,
    build_capture_foul_binding,
)


@dataclass(frozen=True)
class FakeCaptureResult:
    triggered: bool
    message: str | None = None


def make_game() -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k")
    game.ai_color = "W"
    return game


def smoke_runtime_builder_maps_sync_komi() -> None:
    async def sync_komi(_game):
        return None

    binding = build_capture_foul_binding(
        CaptureFoulDependencies(
            runtime=CaptureFoulRuntimeFns(
                sync_komi=sync_komi,
            ),
        )
    )

    assert binding.sync_komi is sync_komi


async def smoke_adapter_skips_when_not_triggered() -> None:
    game = make_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game))

    def check(game_arg, offender, captured, *, ultimate):
        calls.append(("check", game_arg is game, offender, captured, ultimate))
        return FakeCaptureResult(False)

    await check_capture_foul_violation(
        game,
        send,
        "W",
        0,
        ultimate=False,
        binding=CaptureFoulBinding(
            sync_komi=sync_komi,
            check_capture_foul=check,
        ),
    )

    assert calls == [("check", True, "W", 0, False)]
    assert sent == []


async def smoke_adapter_sends_event_then_syncs_komi() -> None:
    game = make_game()
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game))

    def check(game_arg, offender, captured, *, ultimate):
        calls.append(("check", game_arg is game, offender, captured, ultimate))
        return FakeCaptureResult(True, "capture foul triggered")

    await check_capture_foul_violation(
        game,
        send,
        "B",
        3,
        ultimate=True,
        binding=CaptureFoulBinding(
            sync_komi=sync_komi,
            check_capture_foul=check,
        ),
    )

    assert calls == [
        ("check", True, "B", 3, True),
        ("send", {"type": "rogue_event", "msg": "capture foul triggered"}),
        ("sync", True),
    ]


async def smoke_server_wrapper_resolves_current_sync_binding() -> None:
    game = make_game()
    game.rogue_card = "capture_foul"
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game, game_arg.komi))

    original_sync = s._sync_engine_komi
    try:
        s._sync_engine_komi = sync_komi
        binding = s._capture_foul_binding()

        assert binding.sync_komi is sync_komi

        await s._check_capture_foul(
            game,
            send,
            "W",
            gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
            ultimate=False,
        )
    finally:
        s._sync_engine_komi = original_sync

    assert game.rogue_capture_foul_progress["W"] == 0
    assert game.komi == 7.5 - gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY
    assert sent == [
        {
            "type": "rogue_event",
            "msg": f"🧺 提子犯规！白棋 被罚 {gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY:.1f} 目",
        }
    ]
    assert calls == [("sync", True, game.komi)]


async def main() -> None:
    smoke_runtime_builder_maps_sync_komi()
    await smoke_adapter_skips_when_not_triggered()
    await smoke_adapter_sends_event_then_syncs_komi()
    await smoke_server_wrapper_resolves_current_sync_binding()
    print("capture foul adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
