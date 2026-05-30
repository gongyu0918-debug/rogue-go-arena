from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from app.gameplay.capture_foul_flow import check_capture_foul_event


@dataclass(frozen=True)
class FakeCaptureResult:
    triggered: bool
    message: str | None = None


async def smoke_no_trigger_sends_nothing() -> None:
    game = SimpleNamespace()
    sent = []
    synced = []

    async def send(payload):
        sent.append(payload)

    async def sync_komi(game_arg):
        synced.append(game_arg is game)

    def check_capture_foul_fn(game_arg, offender, captured, *, ultimate):
        assert game_arg is game
        assert (offender, captured, ultimate) == ("W", 0, False)
        return FakeCaptureResult(False)

    await check_capture_foul_event(
        game,
        send,
        "W",
        0,
        ultimate=False,
        sync_komi=sync_komi,
        check_capture_foul_fn=check_capture_foul_fn,
    )

    assert sent == []
    assert synced == []


async def smoke_trigger_sends_event_then_syncs_komi() -> None:
    game = SimpleNamespace()
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game))

    def check_capture_foul_fn(game_arg, offender, captured, *, ultimate):
        assert game_arg is game
        assert (offender, captured, ultimate) == ("B", 3, True)
        return FakeCaptureResult(True, "capture foul triggered")

    await check_capture_foul_event(
        game,
        send,
        "B",
        3,
        ultimate=True,
        sync_komi=sync_komi,
        check_capture_foul_fn=check_capture_foul_fn,
    )

    assert calls == [
        ("send", {"type": "rogue_event", "msg": "capture foul triggered"}),
        ("sync", True),
    ]


async def main() -> None:
    await smoke_no_trigger_sends_nothing()
    await smoke_trigger_sends_event_then_syncs_komi()
    print("capture foul flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
