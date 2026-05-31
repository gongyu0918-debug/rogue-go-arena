from __future__ import annotations

import asyncio

import server as s
from app.runtime.ultimate_effect_adapters import (
    UltimateEffectBinding,
    apply_ultimate_effect,
    build_ultimate_effect_flow_deps,
)
from app.runtime.ultimate_effect_runtime import (
    UltimateEffectDependencies,
    UltimateEffectFns,
    UltimateEffectRuntimeFns,
    UltimateEffectTuning,
    build_ultimate_effect_binding,
)


async def fake_async(*_args, **_kwargs):
    return True


async def fake_trigger_five(*_args, **_kwargs):
    return True


async def fake_trigger_last(*_args, **_kwargs):
    return False


def fake_sync(*_args, **_kwargs):
    return None


def fake_coord_to_gtp(x: int, y: int, size: int) -> str:
    return f"{x}:{y}:{size}"


def fake_gtp_to_coord(_move: str, _size: int):
    return (1, 2)


def smoke_binding_maps_every_field() -> None:
    binding = UltimateEffectBinding(
        apply_effect=fake_async,
        coord_to_gtp=fake_coord_to_gtp,
        gtp_to_coord=fake_gtp_to_coord,
        trigger_five_in_row=fake_async,
        trigger_last_stand=fake_async,
        apply_foolish_wisdom_wave=fake_sync,
        make_rng=fake_sync,
        sleep=fake_async,
        foolish_chain_delay=0.25,
    )

    deps = build_ultimate_effect_flow_deps(binding)

    assert deps.apply_effect is fake_async
    assert deps.coord_to_gtp is fake_coord_to_gtp
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.trigger_five_in_row is fake_async
    assert deps.trigger_last_stand is fake_async
    assert deps.apply_foolish_wisdom_wave is fake_sync
    assert deps.make_rng is fake_sync
    assert deps.sleep is fake_async
    assert deps.foolish_chain_delay == 0.25


def smoke_ultimate_effect_runtime_builder_groups_dependencies() -> None:
    async def trigger_five(_game, _send, _color):
        return True

    async def trigger_last(_game, _send, _color):
        return False

    dependencies = UltimateEffectDependencies(
        effects=UltimateEffectFns(
            apply_effect=fake_async,
            apply_foolish_wisdom_wave=fake_sync,
        ),
        runtime=UltimateEffectRuntimeFns(
            coord_to_gtp=fake_coord_to_gtp,
            gtp_to_coord=fake_gtp_to_coord,
            trigger_five_in_row=trigger_five,
            trigger_last_stand=trigger_last,
            make_rng=lambda: "rng",
            sleep=fake_async,
        ),
        tuning=UltimateEffectTuning(
            foolish_chain_delay=0.35,
        ),
    )

    binding = build_ultimate_effect_binding(dependencies)
    deps = build_ultimate_effect_flow_deps(binding)

    assert binding.apply_effect is fake_async
    assert binding.coord_to_gtp is fake_coord_to_gtp
    assert binding.gtp_to_coord is fake_gtp_to_coord
    assert binding.trigger_five_in_row is trigger_five
    assert binding.trigger_last_stand is trigger_last
    assert binding.apply_foolish_wisdom_wave is fake_sync
    assert binding.make_rng() == "rng"
    assert binding.sleep is fake_async
    assert binding.foolish_chain_delay == 0.35
    assert deps.apply_effect is fake_async
    assert deps.coord_to_gtp is fake_coord_to_gtp
    assert deps.gtp_to_coord is fake_gtp_to_coord
    assert deps.trigger_five_in_row is trigger_five
    assert deps.trigger_last_stand is trigger_last
    assert deps.apply_foolish_wisdom_wave is fake_sync
    assert deps.make_rng() == "rng"
    assert deps.sleep is fake_async
    assert deps.foolish_chain_delay == 0.35


async def smoke_adapter_delegates_to_effect_flow() -> None:
    game = object()
    sent = []
    calls = []
    rng = object()

    async def send(payload):
        sent.append(payload)

    def make_rng():
        calls.append(("rng",))
        return rng

    async def trigger_five(game_arg, send_fn, color):
        calls.append(("five", game_arg is game, send_fn is send, color))
        return True

    async def trigger_last(game_arg, send_fn, color):
        calls.append(("last", game_arg is game, send_fn is send, color))
        return False

    def wave(game_arg, color, **kwargs):
        calls.append(("wave", game_arg is game, color, kwargs["rng"] is rng))

    async def apply_effect(game_arg, send_fn, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            send_fn is send,
            kwargs["x"],
            kwargs["y"],
            kwargs["color"],
            kwargs["card"],
            kwargs["coord_to_gtp"] is fake_coord_to_gtp,
            kwargs["gtp_to_coord"] is fake_gtp_to_coord,
            kwargs["trigger_five_in_row_fn"] is trigger_five,
            kwargs["trigger_last_stand_fn"] is trigger_last,
            kwargs["apply_foolish_wisdom_wave_fn"] is wave,
            kwargs["make_rng"] is make_rng,
            kwargs["sleep_fn"] is fake_async,
            kwargs["foolish_chain_delay"],
        ))
        rng_value = kwargs["make_rng"]()
        kwargs["apply_foolish_wisdom_wave_fn"](game_arg, kwargs["color"], rng=rng_value)
        await kwargs["trigger_five_in_row_fn"](game_arg, send_fn, kwargs["color"])
        await kwargs["trigger_last_stand_fn"](game_arg, send_fn, kwargs["color"])
        await send_fn({"type": "rogue_event", "msg": "ok"})
        return True

    result = await apply_ultimate_effect(
        game,
        send,
        x=2,
        y=3,
        color="B",
        card="foolish_wisdom",
        binding=UltimateEffectBinding(
            apply_effect=apply_effect,
            coord_to_gtp=fake_coord_to_gtp,
            gtp_to_coord=fake_gtp_to_coord,
            trigger_five_in_row=trigger_five,
            trigger_last_stand=trigger_last,
            apply_foolish_wisdom_wave=wave,
            make_rng=make_rng,
            sleep=fake_async,
            foolish_chain_delay=0.4,
        ),
    )

    assert result is True
    assert calls == [
        (
            "apply",
            True,
            True,
            2,
            3,
            "B",
            "foolish_wisdom",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            0.4,
        ),
        ("rng",),
        ("wave", True, "B", True),
        ("five", True, True, "B"),
        ("last", True, True, "B"),
    ]
    assert sent == [{"type": "rogue_event", "msg": "ok"}]


def smoke_server_binding_resolves_current_runtime() -> None:
    originals = {
        "apply_ultimate_card_effect_state": s.apply_ultimate_card_effect_state,
        "coord_to_gtp": s.coord_to_gtp,
        "gtp_to_coord": s.gtp_to_coord,
        "_trigger_ultimate_five_in_row": s._trigger_ultimate_five_in_row,
        "_trigger_ultimate_last_stand": s._trigger_ultimate_last_stand,
        "apply_ultimate_foolish_wisdom_wave": s.apply_ultimate_foolish_wisdom_wave,
        "ULTIMATE_FOOLISH_CHAIN_DELAY": s.ULTIMATE_FOOLISH_CHAIN_DELAY,
        "random_random_class": s.random.Random,
        "time_time_ns": s.time.time_ns,
    }

    class FakeRandom:
        def __init__(self, seed):
            self.seed = seed

    try:
        s.apply_ultimate_card_effect_state = fake_async
        s.coord_to_gtp = fake_coord_to_gtp
        s.gtp_to_coord = fake_gtp_to_coord
        s._trigger_ultimate_five_in_row = fake_trigger_five
        s._trigger_ultimate_last_stand = fake_trigger_last
        s.apply_ultimate_foolish_wisdom_wave = fake_sync
        s.ULTIMATE_FOOLISH_CHAIN_DELAY = 0.7
        s.random.Random = FakeRandom
        s.time.time_ns = lambda: 12345

        binding = s._ultimate_effect_binding()
        deps = build_ultimate_effect_flow_deps(binding)

        assert binding.apply_effect is fake_async
        assert binding.coord_to_gtp is fake_coord_to_gtp
        assert binding.gtp_to_coord is fake_gtp_to_coord
        assert binding.trigger_five_in_row is fake_trigger_five
        assert binding.trigger_last_stand is fake_trigger_last
        assert binding.apply_foolish_wisdom_wave is fake_sync
        assert binding.make_rng().seed == 12345
        assert binding.sleep is s.asyncio.sleep
        assert binding.foolish_chain_delay == 0.7
        assert deps.apply_effect is fake_async
        assert deps.coord_to_gtp is fake_coord_to_gtp
        assert deps.gtp_to_coord is fake_gtp_to_coord
        assert deps.trigger_five_in_row is fake_trigger_five
        assert deps.trigger_last_stand is fake_trigger_last
        assert deps.apply_foolish_wisdom_wave is fake_sync
        assert deps.make_rng().seed == 12345
        assert deps.sleep is s.asyncio.sleep
        assert deps.foolish_chain_delay == 0.7
    finally:
        for name, value in originals.items():
            if name == "random_random_class":
                s.random.Random = value
            elif name == "time_time_ns":
                s.time.time_ns = value
            else:
                setattr(s, name, value)


def main() -> None:
    smoke_binding_maps_every_field()
    smoke_ultimate_effect_runtime_builder_groups_dependencies()
    asyncio.run(smoke_adapter_delegates_to_effect_flow())
    smoke_server_binding_resolves_current_runtime()
    print("ultimate effect adapters smoke test: OK")


if __name__ == "__main__":
    main()
