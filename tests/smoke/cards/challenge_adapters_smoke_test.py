from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
from app.runtime.challenge_adapters import (
    ChallengeFlowBinding,
    ChallengeLoadoutBinding,
    apply_challenge_loadout,
    build_challenge_flow_deps,
    build_challenge_loadout_flow_deps,
)
from app.runtime.challenge_runtime import (
    ChallengeFlowRuntimeFns,
    ChallengeFlowTuning,
    ChallengeLoadoutRuntimeFns,
    ChallengeLoadoutTuning,
    ChallengeRuntimeDependencies,
    build_challenge_flow_binding,
    build_challenge_loadout_binding,
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


def smoke_challenge_runtime_builders_group_dependencies() -> None:
    async def sync_komi(_game):
        return None

    async def emit_status(_game, _send):
        return None

    flow_runtime = ChallengeFlowRuntimeFns(
        roll_random=fake_random,
        weaken_rank_one_step=fake_weaken,
        engine_ready=lambda: False,
        get_game_visits=fake_visits,
        run_in_executor=fake_executor,
        set_engine_visits=fake_set_visits,
    )
    flow_tuning = ChallengeFlowTuning(
        trap_extra_turn_chance=0.22,
        restriction_decay_chance=0.33,
        rank_labels={"2k": "2k"},
        challenge_set_min_count=5,
    )
    loadout_runtime = ChallengeLoadoutRuntimeFns(
        apply_loadout=lambda *_args, **_kwargs: "loadout",
        card_ids_fn=lambda *_args, **_kwargs: ["card"],
        get_rogue_card_fn=lambda *_args, **_kwargs: {"id": "card"},
        active_use_bonus_fn=lambda *_args, **_kwargs: 1,
        challenge_zone_points_fn=lambda *_args, **_kwargs: [(1, 1)],
        choose_corner=lambda: 3,
        make_rng=lambda: "rng",
        get_blackhole_points_fn=lambda *_args, **_kwargs: [(2, 2)],
        get_golden_corner_points_fn=lambda *_args, **_kwargs: [(3, 3)],
        pick_joseki_targets_fn=lambda *_args, **_kwargs: [(4, 4)],
        random_hidden_center_fn=lambda *_args, **_kwargs: (5, 5),
        diamond_points_fn=lambda *_args, **_kwargs: [(6, 6)],
        sync_engine_komi=sync_komi,
        emit_set_bonus_status=emit_status,
    )
    loadout_tuning = ChallengeLoadoutTuning(
        golden_corner_span=8,
        joseki_target_count=7,
        godhand_radius=6,
    )
    dependencies = ChallengeRuntimeDependencies(
        flow_runtime=flow_runtime,
        flow_tuning=flow_tuning,
        loadout_runtime=loadout_runtime,
        loadout_tuning=loadout_tuning,
    )

    flow_binding = build_challenge_flow_binding(dependencies)
    loadout_binding = build_challenge_loadout_binding(dependencies)

    assert flow_binding.roll_random is flow_runtime.roll_random
    assert flow_binding.trap_extra_turn_chance == 0.22
    assert flow_binding.restriction_decay_chance == 0.33
    assert flow_binding.weaken_rank_one_step is flow_runtime.weaken_rank_one_step
    assert flow_binding.rank_labels == {"2k": "2k"}
    assert flow_binding.challenge_set_min_count == 5
    assert flow_binding.engine_ready is flow_runtime.engine_ready
    assert flow_binding.get_game_visits is flow_runtime.get_game_visits
    assert flow_binding.run_in_executor is flow_runtime.run_in_executor
    assert flow_binding.set_engine_visits is flow_runtime.set_engine_visits

    assert loadout_binding.apply_loadout is loadout_runtime.apply_loadout
    assert loadout_binding.card_ids_fn is loadout_runtime.card_ids_fn
    assert loadout_binding.get_rogue_card_fn is loadout_runtime.get_rogue_card_fn
    assert loadout_binding.active_use_bonus_fn is loadout_runtime.active_use_bonus_fn
    assert loadout_binding.challenge_zone_points_fn is loadout_runtime.challenge_zone_points_fn
    assert loadout_binding.choose_corner is loadout_runtime.choose_corner
    assert loadout_binding.make_rng is loadout_runtime.make_rng
    assert loadout_binding.get_blackhole_points_fn is loadout_runtime.get_blackhole_points_fn
    assert loadout_binding.get_golden_corner_points_fn is loadout_runtime.get_golden_corner_points_fn
    assert loadout_binding.pick_joseki_targets_fn is loadout_runtime.pick_joseki_targets_fn
    assert loadout_binding.random_hidden_center_fn is loadout_runtime.random_hidden_center_fn
    assert loadout_binding.diamond_points_fn is loadout_runtime.diamond_points_fn
    assert loadout_binding.golden_corner_span == 8
    assert loadout_binding.joseki_target_count == 7
    assert loadout_binding.godhand_radius == 6
    assert loadout_binding.sync_engine_komi is sync_komi
    assert loadout_binding.emit_set_bonus_status is emit_status


def smoke_server_challenge_flow_binding_resolves_current_runtime() -> None:
    original_random = s.random.random
    original_ready = s.engine.ready
    original_set_visits = s.engine.set_visits
    original_run_executor = s.run_in_executor
    original_get_visits = s.get_game_visits
    original_weaken = s.weaken_rank_one_step
    original_trap_chance = s.CHALLENGE_TRAP_EXTRA_TURN_CHANCE
    original_decay_chance = s.CHALLENGE_RESTRICTION_DECAY_CHANCE
    original_rank_labels = s.RANK_LABELS
    original_set_min_count = s.CHALLENGE_SET_MIN_COUNT
    try:
        s.random.random = fake_random
        s.engine.ready = True
        s.engine.set_visits = fake_set_visits
        s.run_in_executor = fake_executor
        s.get_game_visits = fake_visits
        s.weaken_rank_one_step = fake_weaken
        s.CHALLENGE_TRAP_EXTRA_TURN_CHANCE = 0.41
        s.CHALLENGE_RESTRICTION_DECAY_CHANCE = 0.52
        s.RANK_LABELS = {"3k": "3k"}
        s.CHALLENGE_SET_MIN_COUNT = 6

        binding = s._challenge_flow_binding()
        deps = build_challenge_flow_deps(binding)

        assert binding.roll_random is fake_random
        assert binding.trap_extra_turn_chance == 0.41
        assert binding.restriction_decay_chance == 0.52
        assert binding.weaken_rank_one_step is fake_weaken
        assert binding.rank_labels == {"3k": "3k"}
        assert binding.challenge_set_min_count == 6
        assert binding.engine_ready() is True
        assert binding.set_engine_visits is fake_set_visits
        assert binding.run_in_executor is fake_executor
        assert binding.get_game_visits is fake_visits
        assert deps.roll_random is fake_random
        assert deps.trap_extra_turn_chance == 0.41
        assert deps.restriction_decay_chance == 0.52
        assert deps.weaken_rank_one_step is fake_weaken
        assert deps.rank_labels == {"3k": "3k"}
        assert deps.challenge_set_min_count == 6
        assert deps.engine_ready() is True
        assert deps.set_engine_visits is fake_set_visits
        assert deps.run_in_executor is fake_executor
        assert deps.get_game_visits is fake_visits
    finally:
        s.random.random = original_random
        s.engine.ready = original_ready
        s.engine.set_visits = original_set_visits
        s.run_in_executor = original_run_executor
        s.get_game_visits = original_get_visits
        s.weaken_rank_one_step = original_weaken
        s.CHALLENGE_TRAP_EXTRA_TURN_CHANCE = original_trap_chance
        s.CHALLENGE_RESTRICTION_DECAY_CHANCE = original_decay_chance
        s.RANK_LABELS = original_rank_labels
        s.CHALLENGE_SET_MIN_COUNT = original_set_min_count


def smoke_server_challenge_loadout_binding_resolves_current_runtime() -> None:
    fake_loadout = lambda *_args, **_kwargs: None
    fake_card_ids = lambda *_args, **_kwargs: []
    fake_get_card = lambda *_args, **_kwargs: {"id": "fake"}
    fake_active_bonus = lambda *_args, **_kwargs: 2
    fake_zone_points = lambda *_args, **_kwargs: [(1, 1)]
    fake_blackhole_points = lambda *_args, **_kwargs: [(2, 2)]
    fake_golden_points = lambda *_args, **_kwargs: [(3, 3)]
    fake_joseki_targets = lambda *_args, **_kwargs: [(4, 4)]
    fake_hidden_center = lambda *_args, **_kwargs: (5, 5)
    fake_diamond_points = lambda *_args, **_kwargs: [(6, 6)]

    async def fake_sync_komi(_game):
        return None

    async def fake_emit_status(_game, _send):
        return None

    class FakeRandom:
        def __init__(self, seed):
            self.seed = seed

    original_loadout = s.apply_challenge_rogue_loadout_state
    original_card_ids = s.rogue_card_ids
    original_get_card = s.get_rogue_card
    original_active_bonus = s._challenge_active_use_bonus
    original_zone_points = s._challenge_zone_points
    original_randint = s.random.randint
    original_random_class = s.random.Random
    original_time_ns = s.time.time_ns
    original_blackhole_points = s._get_blackhole_points
    original_golden_points = s._get_golden_corner_points
    original_joseki_targets = s._pick_joseki_targets
    original_hidden_center = s._random_hidden_center
    original_diamond_points = s._diamond_points
    original_sync_komi = s._sync_engine_komi
    original_emit_status = s._challenge_emit_set_bonus_status
    original_span = s.ROGUE_GOLDEN_CORNER_SPAN
    original_joseki_count = s.ROGUE_JOSEKI_TARGET_COUNT
    original_godhand_radius = s.ROGUE_GODHAND_RADIUS
    try:
        s.apply_challenge_rogue_loadout_state = fake_loadout
        s.rogue_card_ids = fake_card_ids
        s.get_rogue_card = fake_get_card
        s._challenge_active_use_bonus = fake_active_bonus
        s._challenge_zone_points = fake_zone_points
        s.random.randint = lambda _low, _high: 1
        s.random.Random = FakeRandom
        s.time.time_ns = lambda: 98765
        s._get_blackhole_points = fake_blackhole_points
        s._get_golden_corner_points = fake_golden_points
        s._pick_joseki_targets = fake_joseki_targets
        s._random_hidden_center = fake_hidden_center
        s._diamond_points = fake_diamond_points
        s._sync_engine_komi = fake_sync_komi
        s._challenge_emit_set_bonus_status = fake_emit_status
        s.ROGUE_GOLDEN_CORNER_SPAN = 8
        s.ROGUE_JOSEKI_TARGET_COUNT = 7
        s.ROGUE_GODHAND_RADIUS = 6

        binding = s._challenge_loadout_binding()
        deps = build_challenge_loadout_flow_deps(binding)

        assert binding.apply_loadout is fake_loadout
        assert binding.card_ids_fn is fake_card_ids
        assert binding.get_rogue_card_fn is fake_get_card
        assert binding.active_use_bonus_fn is fake_active_bonus
        assert binding.challenge_zone_points_fn is fake_zone_points
        assert binding.choose_corner() == 1
        assert binding.make_rng().seed == 98765
        assert binding.get_blackhole_points_fn is fake_blackhole_points
        assert binding.get_golden_corner_points_fn is fake_golden_points
        assert binding.pick_joseki_targets_fn is fake_joseki_targets
        assert binding.random_hidden_center_fn is fake_hidden_center
        assert binding.diamond_points_fn is fake_diamond_points
        assert binding.golden_corner_span == 8
        assert binding.joseki_target_count == 7
        assert binding.godhand_radius == 6
        assert binding.sync_engine_komi is fake_sync_komi
        assert binding.emit_set_bonus_status is fake_emit_status
        assert deps.apply_loadout is fake_loadout
        assert deps.card_ids_fn is fake_card_ids
        assert deps.get_rogue_card_fn is fake_get_card
        assert deps.active_use_bonus_fn is fake_active_bonus
        assert deps.challenge_zone_points_fn is fake_zone_points
        assert deps.choose_corner() == 1
        assert deps.make_rng().seed == 98765
        assert deps.get_blackhole_points_fn is fake_blackhole_points
        assert deps.get_golden_corner_points_fn is fake_golden_points
        assert deps.pick_joseki_targets_fn is fake_joseki_targets
        assert deps.random_hidden_center_fn is fake_hidden_center
        assert deps.diamond_points_fn is fake_diamond_points
        assert deps.golden_corner_span == 8
        assert deps.joseki_target_count == 7
        assert deps.godhand_radius == 6
        assert deps.sync_engine_komi is fake_sync_komi
        assert deps.emit_set_bonus_status is fake_emit_status
    finally:
        s.apply_challenge_rogue_loadout_state = original_loadout
        s.rogue_card_ids = original_card_ids
        s.get_rogue_card = original_get_card
        s._challenge_active_use_bonus = original_active_bonus
        s._challenge_zone_points = original_zone_points
        s.random.randint = original_randint
        s.random.Random = original_random_class
        s.time.time_ns = original_time_ns
        s._get_blackhole_points = original_blackhole_points
        s._get_golden_corner_points = original_golden_points
        s._pick_joseki_targets = original_joseki_targets
        s._random_hidden_center = original_hidden_center
        s._diamond_points = original_diamond_points
        s._sync_engine_komi = original_sync_komi
        s._challenge_emit_set_bonus_status = original_emit_status
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
    smoke_challenge_runtime_builders_group_dependencies()
    smoke_server_challenge_flow_binding_resolves_current_runtime()
    smoke_server_challenge_loadout_binding_resolves_current_runtime()
    asyncio.run(smoke_challenge_loadout_adapter_returns_result_after_sync_and_status())
    print("challenge adapters smoke test: OK")


if __name__ == "__main__":
    main()
