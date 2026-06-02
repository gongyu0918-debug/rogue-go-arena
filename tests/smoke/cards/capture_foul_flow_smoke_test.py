from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from app.gameplay.capture_foul_flow import check_capture_foul_event


@dataclass(frozen=True)
class FakeCaptureResult:
    triggered: bool
    message: str | None = None
    beneficiary: str | None = None
    sync_komi: bool = False


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
        return FakeCaptureResult(True, "capture foul triggered", sync_komi=True)

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
    await smoke_rogue_trigger_gifts_recommended_point_and_syncs_board()
    print("capture foul flow smoke test: OK")


async def smoke_rogue_trigger_gifts_recommended_point_and_syncs_board() -> None:
    game = SimpleNamespace(size=9, board=[[0] * 9 for _ in range(9)])
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sync_komi(_game):
        calls.append(("sync_komi",))

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def pick_best(game_arg, color):
        calls.append(("pick", game_arg is game, color))
        return (4, 4)

    def spawn(game_arg, points, color):
        calls.append(("spawn", game_arg is game, points, color))
        game_arg.board[4][4] = 1
        return [(4, 4)]

    def coord(x, y, size):
        return "E5" if (x, y, size) == (4, 4, 9) else "?"

    def check_capture_foul_fn(game_arg, offender, captured, *, ultimate):
        assert game_arg is game
        assert (offender, captured, ultimate) == ("W", 4, False)
        return FakeCaptureResult(True, "capture foul triggered", beneficiary="B")

    await check_capture_foul_event(
        game,
        send,
        "W",
        4,
        ultimate=False,
        sync_komi=sync_komi,
        sync_board=sync_board,
        pick_best_point=pick_best,
        spawn_bonus_points=spawn,
        coord_to_gtp=coord,
        check_capture_foul_fn=check_capture_foul_fn,
    )

    assert calls == [
        ("pick", True, "B"),
        ("spawn", True, [(4, 4)], "B"),
        ("send", {"type": "rogue_event", "msg": "capture foul triggered，在我方推荐点 E5 赠送 1 颗己棋"}),
        ("sync_board", True),
    ]


if __name__ == "__main__":
    asyncio.run(main())
