from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

from app.gameplay.line_trigger_flow import (
    RogueFiveInRowDeps,
    RogueLastStandDeps,
    UltimateFiveInRowDeps,
    UltimateLastStandDeps,
    trigger_rogue_five_in_row,
    trigger_rogue_last_stand,
    trigger_ultimate_five_in_row,
    trigger_ultimate_last_stand,
)


def result(modified: bool, messages: list[str]):
    return SimpleNamespace(modified=modified, messages=messages)


async def smoke_rogue_five_syncs_before_events() -> None:
    game = SimpleNamespace()
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def apply_five(game_arg, color, *, shuffle_points, should_bonus_derivative_fn, support_stones):
        assert game_arg is game
        assert color == "B"
        assert support_stones == 2
        assert should_bonus_derivative_fn(game) is True
        sample = [2, 1]
        shuffle_points(sample)
        assert sample == [1, 2]
        return result(True, ["five"])

    await trigger_rogue_five_in_row(
        game,
        send,
        "B",
        RogueFiveInRowDeps(
            apply_five_in_row=apply_five,
            shuffle_points=lambda values: values.sort(),
            should_bonus_derivative=lambda _game: True,
            support_stones=2,
            engine_ready=lambda: True,
            sync_board=sync_board,
        ),
    )

    assert calls == [
        ("sync", True),
        ("send", {"type": "rogue_event", "msg": "five"}),
    ]


async def smoke_rogue_last_stand_high_winrate_guard() -> None:
    game = SimpleNamespace(rogue_last_stand_done={"B": False})
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def estimate(game_arg, color):
        calls.append(("estimate", game_arg is game, color))
        return 0.8

    def apply_last(*_args, **_kwargs):
        raise AssertionError("last stand should be guarded")

    await trigger_rogue_last_stand(
        game,
        send,
        "B",
        (4, 4),
        RogueLastStandDeps(
            apply_last_stand=apply_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: object(),
            get_forbidden_points=lambda _game, _color: set(),
            clear_count=2,
            spawn_count=3,
            threshold=0.5,
            engine_ready=lambda: True,
            sync_board=lambda _game: asyncio.sleep(0),
        ),
    )

    assert calls == [("estimate", True, "B")]


async def smoke_already_done_guards_skip_last_stand() -> None:
    rogue_game = SimpleNamespace(rogue_last_stand_done={"B": True})
    ultimate_game = SimpleNamespace(ultimate_last_stand_done={"W": True})
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def estimate(*_args):
        calls.append(("estimate",))
        return 0.0

    def apply_last(*_args, **_kwargs):
        calls.append(("apply",))
        return result(True, ["unexpected"])

    await trigger_rogue_last_stand(
        rogue_game,
        send,
        "B",
        (4, 4),
        RogueLastStandDeps(
            apply_last_stand=apply_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: object(),
            get_forbidden_points=lambda _game, _color: set(),
            clear_count=2,
            spawn_count=3,
            threshold=0.5,
            engine_ready=lambda: True,
            sync_board=lambda _game: asyncio.sleep(0),
        ),
    )
    ultimate_modified = await trigger_ultimate_last_stand(
        ultimate_game,
        send,
        "W",
        UltimateLastStandDeps(
            apply_last_stand=apply_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: object(),
            threshold=0.5,
        ),
    )

    assert calls == []
    assert ultimate_modified is False


async def smoke_rogue_five_engine_not_ready_skips_sync() -> None:
    game = SimpleNamespace()
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sync_board(_game):
        calls.append(("sync",))

    def apply_five(*_args, **_kwargs):
        return result(True, ["five"])

    await trigger_rogue_five_in_row(
        game,
        send,
        "B",
        RogueFiveInRowDeps(
            apply_five_in_row=apply_five,
            shuffle_points=lambda _values: None,
            should_bonus_derivative=lambda _game: False,
            support_stones=2,
            engine_ready=lambda: False,
            sync_board=sync_board,
        ),
    )

    assert calls == [("send", {"type": "rogue_event", "msg": "five"})]


async def smoke_rogue_last_stand_applies_and_sends() -> None:
    game = SimpleNamespace(rogue_last_stand_done={"B": False})
    calls = []
    expected_rng = object()

    async def send(payload):
        calls.append(("send", payload))

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    async def estimate(_game, _color):
        return 0.2

    def apply_last(game_arg, color, center, *, rng, forbidden_points, clear_count, spawn_count):
        assert game_arg is game
        assert (color, center, forbidden_points, clear_count, spawn_count) == ("B", (4, 4), {(1, 1)}, 2, 3)
        assert rng is expected_rng
        return result(True, ["last"])

    await trigger_rogue_last_stand(
        game,
        send,
        "B",
        (4, 4),
        RogueLastStandDeps(
            apply_last_stand=apply_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: expected_rng,
            get_forbidden_points=lambda _game, _color: {(1, 1)},
            clear_count=2,
            spawn_count=3,
            threshold=0.5,
            engine_ready=lambda: True,
            sync_board=sync_board,
        ),
    )

    assert calls == [
        ("sync", True),
        ("send", {"type": "rogue_event", "msg": "last"}),
    ]


async def smoke_ultimate_triggers_return_modified() -> None:
    game = SimpleNamespace(ultimate_last_stand_done={"W": False})
    sent = []
    expected_rng = object()

    async def send(payload):
        sent.append(payload)

    async def estimate(_game, _color):
        return 0.1

    def apply_last(game_arg, color, *, rng):
        assert game_arg is game
        assert color == "W"
        assert rng is expected_rng
        return result(True, ["ultimate-last"])

    modified = await trigger_ultimate_last_stand(
        game,
        send,
        "W",
        UltimateLastStandDeps(
            apply_last_stand=apply_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: expected_rng,
            threshold=0.5,
        ),
    )
    assert modified is True
    assert sent == [{"type": "rogue_event", "msg": "ultimate-last"}]

    sent.clear()

    def apply_five(game_arg, color, *, rng):
        assert game_arg is game
        assert color == "B"
        assert rng is expected_rng
        return result(False, ["ultimate-five"])

    modified = await trigger_ultimate_five_in_row(
        game,
        send,
        "B",
        UltimateFiveInRowDeps(
            apply_five_in_row=apply_five,
            make_rng=lambda: expected_rng,
        ),
    )
    assert modified is False
    assert sent == [{"type": "rogue_event", "msg": "ultimate-five"}]


async def main() -> None:
    await smoke_rogue_five_syncs_before_events()
    await smoke_rogue_last_stand_high_winrate_guard()
    await smoke_already_done_guards_skip_last_stand()
    await smoke_rogue_five_engine_not_ready_skips_sync()
    await smoke_rogue_last_stand_applies_and_sends()
    await smoke_ultimate_triggers_return_modified()
    print("line trigger flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
