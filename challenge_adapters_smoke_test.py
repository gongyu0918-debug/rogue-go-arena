from __future__ import annotations

import asyncio

import server as s
from app.runtime.challenge_adapters import (
    ChallengeFlowBinding,
    ChallengeLoadoutBinding,
    apply_challenge_loadout,
    build_challenge_flow_deps,
    build_challenge_loadout_flow_deps,
)


async def fake_executor(func, *args):
    return func(*args)


def fake_random() -> float:
    return 0.25


def fake_weaken(level: str) -> str:
    return f"weakened-{level}"


def fake_visits(*_args, **_kwargs) -> int:
    return 123


def fake_set_visits(_visits: int) -> None:
    return None


def smoke_challenge_flow_binding_maps_every_field() -> None:
    binding = ChallengeFlowBinding(
        roll_random=fake_random,
        trap_extra_turn_chance=0.2,
        restriction_decay_chance=0.3,
        weaken_rank_one_step=fake_weaken,
        rank_labels={"1k": "1k"},
        challenge_set_min_count=4,
        engine_ready=lambda: True,
        get_game_visits=fake_visits,
        run_in_executor=fake_executor,
        set_engine_visits=fake_set_visits,
    )

    deps = build_challenge_flow_deps(binding)

    assert deps.roll_random is fake_random
    assert deps.trap_extra_turn_chance == 0.2
    assert deps.restriction_decay_chance == 0.3
    assert deps.weaken_rank_one_step is fake_weaken
    assert deps.rank_labels == {"1k": "1k"}
    assert deps.challenge_set_min_count == 4
    assert deps.engine_ready() is True
    assert deps.get_game_visits is fake_visits
    assert deps.run_in_executor is fake_executor
    assert deps.set_engine_visits is fake_set_visits


def smoke_challenge_loadout_binding_maps_every_field() -> None:
    async def sync_komi(_game):
        return None

    async def emit_status(_game, _send):
        return None

    functions = {
        "apply_loadout": lambda *_args, **_kwargs: None,
        "card_ids_fn": lambda *_args, **_kwargs: [],
        "get_rogue_card_fn": lambda *_args, **_kwargs: {},
        "active_use_bonus_fn": lambda *_args, **_kwargs: 0,
        "challenge_zone_points_fn": lambda *_args, **_kwargs: [],
        "choose_corner": lambda: 2,
        "make_rng": lambda: object(),
        "get_blackhole_points_fn": lambda *_args, **_kwargs: [],
        "get_golden_corner_points_fn": lambda *_args, **_kwargs: [],
        "pick_joseki_targets_fn": lambda *_args, **_kwargs: [],
        "random_hidden_center_fn": lambda *_args, **_kwargs: (0, 0),
        "diamond_points_fn": lambda *_args, **_kwargs: [],
    }
    binding = ChallengeLoadoutBinding(
        **functions,
        golden_corner_span=6,
        joseki_target_count=5,
        godhand_radius=4,
        sync_engine_komi=sync_komi,
        emit_set_bonus_status=emit_status,
    )

    deps = build_challenge_loadout_flow_deps(binding)

    for name, expected in functions.items():
        assert getattr(deps, name) is expected, name
    assert deps.golden_corner_span == 6
    assert deps.joseki_target_count == 5
    assert deps.godhand_radius == 4
    assert deps.sync_engine_komi is sync_komi
    assert deps.emit_set_bonus_status is emit_status


def smoke_server_challenge_flow_binding_resolves_current_runtime() -> None:
    original_random = s.random.random
    original_ready = s.engine.ready
    original_set_visits = s.engine.set_visits
    original_run_executor = s.run_in_executor
    original_get_visits = s.get_game_visits
    try:
        s.random.random = fake_random
        s.engine.ready = True
        s.engine.set_visits = fake_set_visits
        s.run_in_executor = fake_executor
        s.get_game_visits = fake_visits

        binding = s._challenge_flow_binding()
        deps = s._challenge_flow_deps()

        assert binding.roll_random is fake_random
        assert binding.engine_ready() is True
        assert binding.set_engine_visits is fake_set_visits
        assert binding.run_in_executor is fake_executor
        assert binding.get_game_visits is fake_visits
        assert deps.roll_random is fake_random
        assert deps.run_in_executor is fake_executor
    finally:
        s.random.random = original_random
        s.engine.ready = original_ready
        s.engine.set_visits = original_set_visits
        s.run_in_executor = original_run_executor
        s.get_game_visits = original_get_visits


def smoke_server_challenge_loadout_binding_resolves_current_runtime() -> None:
    fake_loadout = lambda *_args, **_kwargs: None
    fake_card_ids = lambda *_args, **_kwargs: []
    original_loadout = s.apply_challenge_rogue_loadout_state
    original_card_ids = s.rogue_card_ids
    original_randint = s.random.randint
    original_span = s.ROGUE_GOLDEN_CORNER_SPAN
    original_joseki_count = s.ROGUE_JOSEKI_TARGET_COUNT
    original_godhand_radius = s.ROGUE_GODHAND_RADIUS
    try:
        s.apply_challenge_rogue_loadout_state = fake_loadout
        s.rogue_card_ids = fake_card_ids
        s.random.randint = lambda _low, _high: 1
        s.ROGUE_GOLDEN_CORNER_SPAN = 8
        s.ROGUE_JOSEKI_TARGET_COUNT = 7
        s.ROGUE_GODHAND_RADIUS = 6

        binding = s._challenge_loadout_binding()
        deps = s._challenge_loadout_flow_deps()

        assert binding.apply_loadout is fake_loadout
        assert binding.card_ids_fn is fake_card_ids
        assert binding.choose_corner() == 1
        assert binding.golden_corner_span == 8
        assert binding.joseki_target_count == 7
        assert binding.godhand_radius == 6
        assert binding.emit_set_bonus_status is s._challenge_emit_set_bonus_status
        assert deps.apply_loadout is fake_loadout
        assert deps.card_ids_fn is fake_card_ids
        assert deps.golden_corner_span == 8
    finally:
        s.apply_challenge_rogue_loadout_state = original_loadout
        s.rogue_card_ids = original_card_ids
        s.random.randint = original_randint
        s.ROGUE_GOLDEN_CORNER_SPAN = original_span
        s.ROGUE_JOSEKI_TARGET_COUNT = original_joseki_count
        s.ROGUE_GODHAND_RADIUS = original_godhand_radius


async def smoke_challenge_loadout_adapter_returns_result_after_sync_and_status() -> None:
    calls = []
    game = object()
    sent = []

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game))

    async def emit_status(game_arg, send_fn):
        calls.append(("status", game_arg is game, send_fn is send))
        await send_fn({"type": "rogue_event", "msg": "status"})

    async def send(payload):
        sent.append(payload)

    def apply_loadout(game_arg, **kwargs):
        calls.append(("loadout", game_arg is game))
        return {"ok": True}

    binding = ChallengeLoadoutBinding(
        apply_loadout=apply_loadout,
        card_ids_fn=lambda *_args, **_kwargs: [],
        get_rogue_card_fn=lambda *_args, **_kwargs: {},
        active_use_bonus_fn=lambda *_args, **_kwargs: 0,
        challenge_zone_points_fn=lambda *_args, **_kwargs: [],
        choose_corner=lambda: 0,
        make_rng=lambda: object(),
        get_blackhole_points_fn=lambda *_args, **_kwargs: [],
        get_golden_corner_points_fn=lambda *_args, **_kwargs: [],
        pick_joseki_targets_fn=lambda *_args, **_kwargs: [],
        random_hidden_center_fn=lambda *_args, **_kwargs: (0, 0),
        diamond_points_fn=lambda *_args, **_kwargs: [],
        golden_corner_span=6,
        joseki_target_count=5,
        godhand_radius=4,
        sync_engine_komi=sync_komi,
        emit_set_bonus_status=emit_status,
    )

    result = await apply_challenge_loadout(game, send, binding)

    assert result == {"ok": True}
    assert calls == [
        ("loadout", True),
        ("sync", True),
        ("status", True, True),
    ]
    assert sent == [{"type": "rogue_event", "msg": "status"}]


def main() -> None:
    smoke_challenge_flow_binding_maps_every_field()
    smoke_challenge_loadout_binding_maps_every_field()
    smoke_server_challenge_flow_binding_resolves_current_runtime()
    smoke_server_challenge_loadout_binding_resolves_current_runtime()
    asyncio.run(smoke_challenge_loadout_adapter_returns_result_after_sync_and_status())
    print("challenge adapters smoke test: OK")


if __name__ == "__main__":
    main()
