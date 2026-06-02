from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

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
    beneficiary: str | None = None
    sync_komi: bool = False


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
        return FakeCaptureResult(True, "capture foul triggered", sync_komi=True)

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

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def pick_best(game_arg, color):
        calls.append(("pick", game_arg is game, color))
        return (4, 4)

    original_pick_best = s._pick_best_point
    original_sync_board = s._sync_board_to_katago
    try:
        s._pick_best_point = pick_best
        s._sync_board_to_katago = sync_board
        binding = s._capture_foul_binding()

        assert binding.pick_best_point is pick_best
        assert binding.sync_board is sync_board

        await s._check_capture_foul(
            game,
            send,
            "W",
            gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
            ultimate=False,
        )
    finally:
        s._pick_best_point = original_pick_best
        s._sync_board_to_katago = original_sync_board

    assert game.rogue_capture_foul_progress["W"] == 0
    assert game.komi == 7.5
    assert game.board[4][4] == 1
    assert sent == [
        {
            "type": "rogue_event",
            "msg": f"🧺 提子犯规触发！白棋 提子达到 {gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD} 颗，在我方推荐点 E5 赠送 1 颗己棋",
        }
    ]
    assert calls == [("pick", True, "B"), ("sync_board", True)]


async def main() -> None:
    smoke_runtime_builder_maps_sync_komi()
    await smoke_adapter_skips_when_not_triggered()
    await smoke_adapter_sends_event_then_syncs_komi()
    await smoke_server_wrapper_resolves_current_sync_binding()
    print("capture foul adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
