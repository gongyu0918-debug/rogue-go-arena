from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.line_trigger_adapters import (
    RogueFiveInRowBinding,
    RogueLastStandBinding,
    UltimateFiveInRowBinding,
    UltimateLastStandBinding,
    build_rogue_five_in_row_deps,
    build_rogue_last_stand_deps,
    build_ultimate_five_in_row_deps,
    build_ultimate_last_stand_deps,
    trigger_rogue_five_in_row,
    trigger_rogue_last_stand,
    trigger_ultimate_five_in_row,
    trigger_ultimate_last_stand,
)
from app.runtime.line_trigger_runtime import (
    LineTriggerDependencies,
    LineTriggerEffectFns,
    LineTriggerRuntimeFns,
    LineTriggerTuning,
    build_rogue_five_in_row_binding,
    build_rogue_last_stand_binding,
    build_ultimate_five_in_row_binding,
    build_ultimate_last_stand_binding,
)


def result(modified: bool, messages: list[str]):
    return SimpleNamespace(modified=modified, messages=messages)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def smoke_bindings_map_every_field() -> None:
    rogue_five = RogueFiveInRowBinding(
        apply_five_in_row=fake_sync,
        shuffle_points=fake_sync,
        should_bonus_derivative=lambda _game: True,
        support_stones=4,
        engine_ready=lambda: False,
        sync_board=fake_async,
    )
    rogue_five_deps = build_rogue_five_in_row_deps(rogue_five)
    assert rogue_five_deps.apply_five_in_row is fake_sync
    assert rogue_five_deps.shuffle_points is fake_sync
    assert rogue_five_deps.should_bonus_derivative(None) is True
    assert rogue_five_deps.support_stones == 4
    assert rogue_five_deps.engine_ready() is False
    assert rogue_five_deps.sync_board is fake_async

    rogue_last = RogueLastStandBinding(
        apply_last_stand=fake_sync,
        estimate_side_winrate=fake_async,
        make_rng=lambda: "rng",
        get_forbidden_points=lambda _game, _color: {(1, 2)},
        clear_count=2,
        spawn_count=3,
        threshold=0.4,
        engine_ready=lambda: True,
        sync_board=fake_async,
    )
    rogue_last_deps = build_rogue_last_stand_deps(rogue_last)
    assert rogue_last_deps.apply_last_stand is fake_sync
    assert rogue_last_deps.estimate_side_winrate is fake_async
    assert rogue_last_deps.make_rng() == "rng"
    assert rogue_last_deps.get_forbidden_points(None, "B") == {(1, 2)}
    assert rogue_last_deps.clear_count == 2
    assert rogue_last_deps.spawn_count == 3
    assert rogue_last_deps.threshold == 0.4
    assert rogue_last_deps.engine_ready() is True
    assert rogue_last_deps.sync_board is fake_async

    ultimate_last = UltimateLastStandBinding(
        apply_last_stand=fake_sync,
        estimate_side_winrate=fake_async,
        make_rng=lambda: "ultimate-rng",
        threshold=0.25,
    )
    ultimate_last_deps = build_ultimate_last_stand_deps(ultimate_last)
    assert ultimate_last_deps.apply_last_stand is fake_sync
    assert ultimate_last_deps.estimate_side_winrate is fake_async
    assert ultimate_last_deps.make_rng() == "ultimate-rng"
    assert ultimate_last_deps.threshold == 0.25

    ultimate_five = UltimateFiveInRowBinding(
        apply_five_in_row=fake_sync,
        make_rng=lambda: "five-rng",
    )
    ultimate_five_deps = build_ultimate_five_in_row_deps(ultimate_five)
    assert ultimate_five_deps.apply_five_in_row is fake_sync
    assert ultimate_five_deps.make_rng() == "five-rng"


def smoke_line_trigger_runtime_builders_group_dependencies() -> None:
    async def estimate(_game, _color):
        return 0.2

    async def sync_board(_game):
        return None

    runtime = LineTriggerRuntimeFns(
        shuffle_points=fake_sync,
        should_bonus_derivative=lambda _game: True,
        engine_ready=lambda: False,
        sync_board=sync_board,
        estimate_side_winrate=estimate,
        make_rng=lambda: "runtime-rng",
        get_forbidden_points=lambda _game, _color: {(3, 3)},
    )
    effects = LineTriggerEffectFns(
        apply_rogue_five_in_row=fake_sync,
        apply_rogue_last_stand=lambda *_args, **_kwargs: None,
        apply_ultimate_last_stand=lambda *_args, **_kwargs: None,
        apply_ultimate_five_in_row=lambda *_args, **_kwargs: None,
    )
    tuning = LineTriggerTuning(
        rogue_five_in_row_support_stones=6,
        rogue_last_stand_clear_count=7,
        rogue_last_stand_spawn_count=8,
        rogue_last_stand_threshold=0.35,
        ultimate_last_stand_threshold=0.45,
    )
    deps = LineTriggerDependencies(effects=effects, runtime=runtime, tuning=tuning)

    rogue_five = build_rogue_five_in_row_binding(deps)
    rogue_last = build_rogue_last_stand_binding(deps)
    ultimate_last = build_ultimate_last_stand_binding(deps)
    ultimate_five = build_ultimate_five_in_row_binding(deps)

    assert rogue_five.apply_five_in_row is effects.apply_rogue_five_in_row
    assert rogue_five.shuffle_points is runtime.shuffle_points
    assert rogue_five.should_bonus_derivative is runtime.should_bonus_derivative
    assert rogue_five.support_stones == 6
    assert rogue_five.engine_ready is runtime.engine_ready
    assert rogue_five.sync_board is runtime.sync_board

    assert rogue_last.apply_last_stand is effects.apply_rogue_last_stand
    assert rogue_last.estimate_side_winrate is runtime.estimate_side_winrate
    assert rogue_last.make_rng is runtime.make_rng
    assert rogue_last.get_forbidden_points is runtime.get_forbidden_points
    assert rogue_last.clear_count == 7
    assert rogue_last.spawn_count == 8
    assert rogue_last.threshold == 0.35
    assert rogue_last.engine_ready is runtime.engine_ready
    assert rogue_last.sync_board is runtime.sync_board

    assert ultimate_last.apply_last_stand is effects.apply_ultimate_last_stand
    assert ultimate_last.estimate_side_winrate is runtime.estimate_side_winrate
    assert ultimate_last.make_rng is runtime.make_rng
    assert ultimate_last.threshold == 0.45

    assert ultimate_five.apply_five_in_row is effects.apply_ultimate_five_in_row
    assert ultimate_five.make_rng is runtime.make_rng


async def smoke_adapters_delegate_and_return() -> None:
    game = SimpleNamespace(
        rogue_last_stand_done={"B": False},
        ultimate_last_stand_done={"W": False},
    )
    sent = []
    calls = []
    rng = object()

    async def send(payload):
        sent.append(payload)

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    async def estimate(game_arg, color):
        calls.append(("estimate", game_arg is game, color))
        return 0.1

    def apply_rogue_five(game_arg, color, **kwargs):
        calls.append((
            "rogue_five",
            game_arg is game,
            color,
            kwargs["shuffle_points"] is fake_sync,
            kwargs["should_bonus_derivative_fn"](game),
            kwargs["support_stones"],
        ))
        return result(True, ["rogue five"])

    def apply_rogue_last(game_arg, color, center, **kwargs):
        calls.append((
            "rogue_last",
            game_arg is game,
            color,
            center,
            kwargs["rng"] is rng,
            kwargs["forbidden_points"],
            kwargs["clear_count"],
            kwargs["spawn_count"],
        ))
        return result(True, ["rogue last"])

    def apply_ultimate_last(game_arg, color, **kwargs):
        calls.append(("ultimate_last", game_arg is game, color, kwargs["rng"] is rng))
        return result(True, ["ultimate last"])

    def apply_ultimate_five(game_arg, color, **kwargs):
        calls.append(("ultimate_five", game_arg is game, color, kwargs["rng"] is rng))
        return result(False, ["ultimate five"])

    await trigger_rogue_five_in_row(
        game,
        send,
        "B",
        RogueFiveInRowBinding(
            apply_five_in_row=apply_rogue_five,
            shuffle_points=fake_sync,
            should_bonus_derivative=lambda _game: True,
            support_stones=5,
            engine_ready=lambda: True,
            sync_board=sync_board,
        ),
    )
    await trigger_rogue_last_stand(
        game,
        send,
        "B",
        (4, 4),
        RogueLastStandBinding(
            apply_last_stand=apply_rogue_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: rng,
            get_forbidden_points=lambda _game, _color: {(1, 1)},
            clear_count=2,
            spawn_count=3,
            threshold=0.5,
            engine_ready=lambda: True,
            sync_board=sync_board,
        ),
    )
    ultimate_last_modified = await trigger_ultimate_last_stand(
        game,
        send,
        "W",
        UltimateLastStandBinding(
            apply_last_stand=apply_ultimate_last,
            estimate_side_winrate=estimate,
            make_rng=lambda: rng,
            threshold=0.5,
        ),
    )
    ultimate_five_modified = await trigger_ultimate_five_in_row(
        game,
        send,
        "B",
        UltimateFiveInRowBinding(
            apply_five_in_row=apply_ultimate_five,
            make_rng=lambda: rng,
        ),
    )

    assert ultimate_last_modified is True
    assert ultimate_five_modified is False
    assert calls == [
        ("rogue_five", True, "B", True, True, 5),
        ("sync_board", True),
        ("estimate", True, "B"),
        ("rogue_last", True, "B", (4, 4), True, {(1, 1)}, 2, 3),
        ("sync_board", True),
        ("estimate", True, "W"),
        ("ultimate_last", True, "W", True),
        ("ultimate_five", True, "B", True),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "rogue five"},
        {"type": "rogue_event", "msg": "rogue last"},
        {"type": "rogue_event", "msg": "ultimate last"},
        {"type": "rogue_event", "msg": "ultimate five"},
    ]


async def smoke_server_bindings_resolve_current_runtime() -> None:
    game = SimpleNamespace(
        rogue_last_stand_done={"B": False},
        ultimate_last_stand_done={"W": False},
    )
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    class FakeRandom:
        def __init__(self, seed):
            self.seed = seed

    def shuffle(points):
        calls.append(("shuffle", points))

    def should_bonus(game_arg):
        calls.append(("bonus", game_arg is game))
        return True

    async def estimate(game_arg, color):
        calls.append(("estimate", game_arg is game, color))
        return 0.1

    async def sync_board(game_arg):
        calls.append(("sync_board", game_arg is game))

    def forbidden(game_arg, color):
        calls.append(("forbidden", game_arg is game, color))
        return {(2, 2)}

    def rogue_five(game_arg, color, **kwargs):
        calls.append((
            "rogue_five",
            game_arg is game,
            color,
            kwargs["shuffle_points"] is shuffle,
            kwargs["should_bonus_derivative_fn"] is should_bonus,
            kwargs["support_stones"],
        ))
        kwargs["should_bonus_derivative_fn"](game)
        return result(True, ["server rogue five"])

    def rogue_last(game_arg, color, center, **kwargs):
        calls.append((
            "rogue_last",
            game_arg is game,
            color,
            center,
            kwargs["rng"].seed,
            kwargs["forbidden_points"],
            kwargs["clear_count"],
            kwargs["spawn_count"],
        ))
        return result(True, ["server rogue last"])

    def ultimate_last(game_arg, color, **kwargs):
        calls.append(("ultimate_last", game_arg is game, color, kwargs["rng"].seed))
        return result(True, ["server ultimate last"])

    def ultimate_five(game_arg, color, **kwargs):
        calls.append(("ultimate_five", game_arg is game, color, kwargs["rng"].seed))
        return result(True, ["server ultimate five"])

    originals = {
        "apply_rogue_five_in_row": s.apply_rogue_five_in_row,
        "apply_rogue_last_stand": s.apply_rogue_last_stand,
        "apply_ultimate_last_stand": s.apply_ultimate_last_stand,
        "apply_ultimate_five_in_row": s.apply_ultimate_five_in_row,
        "_challenge_should_bonus_derivative": s._challenge_should_bonus_derivative,
        "ROGUE_FIVE_IN_ROW_SUPPORT_STONES": s.ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
        "ROGUE_LAST_STAND_CLEAR_COUNT": s.ROGUE_LAST_STAND_CLEAR_COUNT,
        "ROGUE_LAST_STAND_SPAWN_COUNT": s.ROGUE_LAST_STAND_SPAWN_COUNT,
        "ROGUE_LAST_STAND_THRESHOLD": s.ROGUE_LAST_STAND_THRESHOLD,
        "ULTIMATE_LAST_STAND_THRESHOLD": s.ULTIMATE_LAST_STAND_THRESHOLD,
        "_estimate_side_winrate": s._estimate_side_winrate,
        "_get_player_bonus_forbidden_points": s._get_player_bonus_forbidden_points,
        "_sync_board_to_katago": s._sync_board_to_katago,
        "engine_ready": s.engine.ready,
        "random_shuffle": s.random.shuffle,
        "random_class": s.random.Random,
        "time_time_ns": s.time.time_ns,
    }

    try:
        s.apply_rogue_five_in_row = rogue_five
        s.apply_rogue_last_stand = rogue_last
        s.apply_ultimate_last_stand = ultimate_last
        s.apply_ultimate_five_in_row = ultimate_five
        s._challenge_should_bonus_derivative = should_bonus
        s.ROGUE_FIVE_IN_ROW_SUPPORT_STONES = 9
        s.ROGUE_LAST_STAND_CLEAR_COUNT = 4
        s.ROGUE_LAST_STAND_SPAWN_COUNT = 5
        s.ROGUE_LAST_STAND_THRESHOLD = 0.6
        s.ULTIMATE_LAST_STAND_THRESHOLD = 0.7
        s._estimate_side_winrate = estimate
        s._get_player_bonus_forbidden_points = forbidden
        s._sync_board_to_katago = sync_board
        s.engine.ready = True
        s.random.shuffle = shuffle
        s.random.Random = FakeRandom
        s.time.time_ns = lambda: 12345

        rogue_five_binding = s._rogue_five_in_row_binding()
        rogue_five_deps = build_rogue_five_in_row_deps(rogue_five_binding)
        rogue_last_binding = s._rogue_last_stand_binding()
        rogue_last_deps = build_rogue_last_stand_deps(rogue_last_binding)
        ultimate_last_binding = s._ultimate_last_stand_binding()
        ultimate_last_deps = build_ultimate_last_stand_deps(ultimate_last_binding)
        ultimate_five_binding = s._ultimate_five_in_row_binding()
        ultimate_five_deps = build_ultimate_five_in_row_deps(ultimate_five_binding)

        assert rogue_five_binding.apply_five_in_row is rogue_five
        assert rogue_five_deps.shuffle_points is shuffle
        assert rogue_five_deps.should_bonus_derivative is should_bonus
        assert rogue_five_deps.support_stones == 9
        assert rogue_five_deps.engine_ready() is True
        assert rogue_five_deps.sync_board is sync_board
        assert rogue_last_binding.apply_last_stand is rogue_last
        assert rogue_last_deps.estimate_side_winrate is estimate
        assert rogue_last_deps.make_rng().seed == 12345
        assert rogue_last_deps.get_forbidden_points is forbidden
        assert rogue_last_deps.clear_count == 4
        assert rogue_last_deps.spawn_count == 5
        assert rogue_last_deps.threshold == 0.6
        assert rogue_last_deps.engine_ready() is True
        assert rogue_last_deps.sync_board is sync_board
        assert ultimate_last_binding.apply_last_stand is ultimate_last
        assert ultimate_last_deps.estimate_side_winrate is estimate
        assert ultimate_last_deps.make_rng().seed == 12345
        assert ultimate_last_deps.threshold == 0.7
        assert ultimate_five_binding.apply_five_in_row is ultimate_five
        assert ultimate_five_deps.make_rng().seed == 12345

        await s._trigger_rogue_five_in_row(game, send, "B")
        await s._trigger_rogue_last_stand(game, send, "B", (4, 4))
        ultimate_last_modified = await s._trigger_ultimate_last_stand(game, send, "W")
        ultimate_five_modified = await s._trigger_ultimate_five_in_row(game, send, "B")
    finally:
        s.apply_rogue_five_in_row = originals["apply_rogue_five_in_row"]
        s.apply_rogue_last_stand = originals["apply_rogue_last_stand"]
        s.apply_ultimate_last_stand = originals["apply_ultimate_last_stand"]
        s.apply_ultimate_five_in_row = originals["apply_ultimate_five_in_row"]
        s._challenge_should_bonus_derivative = originals["_challenge_should_bonus_derivative"]
        s.ROGUE_FIVE_IN_ROW_SUPPORT_STONES = originals["ROGUE_FIVE_IN_ROW_SUPPORT_STONES"]
        s.ROGUE_LAST_STAND_CLEAR_COUNT = originals["ROGUE_LAST_STAND_CLEAR_COUNT"]
        s.ROGUE_LAST_STAND_SPAWN_COUNT = originals["ROGUE_LAST_STAND_SPAWN_COUNT"]
        s.ROGUE_LAST_STAND_THRESHOLD = originals["ROGUE_LAST_STAND_THRESHOLD"]
        s.ULTIMATE_LAST_STAND_THRESHOLD = originals["ULTIMATE_LAST_STAND_THRESHOLD"]
        s._estimate_side_winrate = originals["_estimate_side_winrate"]
        s._get_player_bonus_forbidden_points = originals["_get_player_bonus_forbidden_points"]
        s._sync_board_to_katago = originals["_sync_board_to_katago"]
        s.engine.ready = originals["engine_ready"]
        s.random.shuffle = originals["random_shuffle"]
        s.random.Random = originals["random_class"]
        s.time.time_ns = originals["time_time_ns"]

    assert ultimate_last_modified is True
    assert ultimate_five_modified is True
    assert calls == [
        ("rogue_five", True, "B", True, True, 9),
        ("bonus", True),
        ("sync_board", True),
        ("estimate", True, "B"),
        ("forbidden", True, "B"),
        ("rogue_last", True, "B", (4, 4), 12345, {(2, 2)}, 4, 5),
        ("sync_board", True),
        ("estimate", True, "W"),
        ("ultimate_last", True, "W", 12345),
        ("ultimate_five", True, "B", 12345),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "server rogue five"},
        {"type": "rogue_event", "msg": "server rogue last"},
        {"type": "rogue_event", "msg": "server ultimate last"},
        {"type": "rogue_event", "msg": "server ultimate five"},
    ]


async def main() -> None:
    smoke_bindings_map_every_field()
    smoke_line_trigger_runtime_builders_group_dependencies()
    await smoke_adapters_delegate_and_return()
    await smoke_server_bindings_resolve_current_runtime()
    print("line trigger adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
