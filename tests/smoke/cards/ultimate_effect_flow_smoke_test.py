from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

from app.gameplay.ultimate_effect_flow import (
    UltimateEffectFlowDeps,
    apply_ultimate_effect_event,
)


async def smoke_effect_flow_injects_runtime_hooks() -> None:
    game = object()
    calls = []
    sent = []
    rng = object()

    async def send(payload):
        sent.append(payload)

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return f"{x}:{y}:{size}"

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (1, 2)

    async def trigger_five(effect_game, effect_send, color):
        calls.append(("five", effect_game is game, effect_send is send, color))
        return True

    async def trigger_last(effect_game, effect_send, color):
        calls.append(("last", effect_game is game, effect_send is send, color))
        return False

    def wave(effect_game, color, **kwargs):
        calls.append(("wave", effect_game is game, color, kwargs["rng"] is rng))
        return None

    def make_rng():
        calls.append(("rng",))
        return rng

    async def sleep(delay):
        calls.append(("sleep", delay))

    async def apply_effect(effect_game, effect_send, **kwargs):
        calls.append((
            "apply",
            effect_game is game,
            effect_send is send,
            kwargs["x"],
            kwargs["y"],
            kwargs["color"],
            kwargs["card"],
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["trigger_five_in_row_fn"] is trigger_five,
            kwargs["trigger_last_stand_fn"] is trigger_last,
            kwargs["apply_foolish_wisdom_wave_fn"] is wave,
            kwargs["make_rng"] is make_rng,
            kwargs["sleep_fn"] is sleep,
            kwargs["foolish_chain_delay"],
        ))
        kwargs["coord_to_gtp"](2, 3, 9)
        kwargs["gtp_to_coord"]("D4", 9)
        rng_value = kwargs["make_rng"]()
        kwargs["apply_foolish_wisdom_wave_fn"](effect_game, kwargs["color"], rng=rng_value)
        await kwargs["sleep_fn"](kwargs["foolish_chain_delay"])
        await kwargs["trigger_five_in_row_fn"](effect_game, effect_send, kwargs["color"])
        await kwargs["trigger_last_stand_fn"](effect_game, effect_send, kwargs["color"])
        await effect_send({"type": "rogue_event", "msg": "ok"})
        return True

    deps = UltimateEffectFlowDeps(
        apply_effect=apply_effect,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
        trigger_five_in_row=trigger_five,
        trigger_last_stand=trigger_last,
        apply_foolish_wisdom_wave=wave,
        make_rng=make_rng,
        sleep=sleep,
        foolish_chain_delay=0.25,
    )

    result = await apply_ultimate_effect_event(
        game,
        send,
        x=2,
        y=3,
        color="B",
        card="foolish_wisdom",
        deps=deps,
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
            0.25,
        ),
        ("coord", 2, 3, 9),
        ("gtp", "D4", 9),
        ("rng",),
        ("wave", True, "B", True),
        ("sleep", 0.25),
        ("five", True, True, "B"),
        ("last", True, True, "B"),
    ]
    assert sent == [{"type": "rogue_event", "msg": "ok"}]


async def main() -> None:
    await smoke_effect_flow_injects_runtime_hooks()
    print("ultimate effect flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
