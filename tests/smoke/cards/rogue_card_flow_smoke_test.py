from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

from app.gameplay.rogue_card_flow import (
    AiRogueCardActivationFlowDeps,
    RogueCardActivationFlowDeps,
    activate_ai_rogue_card_event,
    activate_rogue_card_event,
)


class DummyGame:
    def __init__(self) -> None:
        self.komi = 7.5
        self.state_marker = "ready"

    def to_state(self) -> dict:
        return {"state_marker": self.state_marker, "komi": self.komi}


def card(card_id: str) -> dict:
    return {"id": card_id, "name": f"name-{card_id}", "icon": "icon"}


async def smoke_player_activation_flow_sends_events_syncs_and_selects() -> None:
    game = DummyGame()
    calls = []
    sent = []
    rng = object()

    async def send(payload):
        sent.append(payload)

    def get_card(card_id):
        calls.append(("get_card", card_id))
        return card(card_id)

    def coord_to_gtp(x, y, size):
        calls.append(("coord", x, y, size))
        return "D4"

    def choose_corner():
        calls.append(("corner",))
        return 1

    def make_rng():
        calls.append(("rng",))
        return rng

    def blackhole(size):
        calls.append(("blackhole", size))
        return [(0, 0)]

    def golden(size, corner, span):
        calls.append(("golden", size, corner, span))
        return [(1, 1)]

    def joseki(size, count):
        calls.append(("joseki", size, count))
        return [(2, 2)]

    def hidden(size, radius, rng_value):
        calls.append(("hidden", size, radius, rng_value is rng))
        return (3, 3)

    def diamond(x, y, radius, size):
        calls.append(("diamond", x, y, radius, size))
        return [(x, y)]

    def apply_activation(game_arg, card_id, card_def, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            card_id,
            card_def["name"],
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["choose_corner"] is choose_corner,
            kwargs["make_rng"] is make_rng,
            kwargs["get_blackhole_points_fn"] is blackhole,
            kwargs["get_golden_corner_points_fn"] is golden,
            kwargs["pick_joseki_targets_fn"] is joseki,
            kwargs["random_hidden_center_fn"] is hidden,
            kwargs["diamond_points_fn"] is diamond,
        ))
        kwargs["coord_to_gtp"](1, 2, 9)
        kwargs["choose_corner"]()
        rng_value = kwargs["make_rng"]()
        kwargs["get_blackhole_points_fn"](9)
        kwargs["get_golden_corner_points_fn"](9, 1, 6)
        kwargs["pick_joseki_targets_fn"](9, 5)
        center = kwargs["random_hidden_center_fn"](9, 2, rng_value)
        kwargs["diamond_points_fn"](center[0], center[1], 4, 9)
        game_arg.komi = 0.5
        return SimpleNamespace(messages=["activated"], sync_komi=True)

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game, game_arg.komi))

    deps = RogueCardActivationFlowDeps(
        get_card=get_card,
        apply_activation=apply_activation,
        coord_to_gtp=coord_to_gtp,
        choose_corner=choose_corner,
        make_rng=make_rng,
        get_blackhole_points=blackhole,
        get_golden_corner_points=golden,
        pick_joseki_targets=joseki,
        random_hidden_center=hidden,
        diamond_points=diamond,
        sync_engine_komi=sync_komi,
    )

    result = await activate_rogue_card_event(game, send, "seal", deps)

    assert result.messages == ["activated"]
    assert calls == [
        ("get_card", "seal"),
        (
            "apply",
            True,
            "seal",
            "name-seal",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
        ("coord", 1, 2, 9),
        ("corner",),
        ("rng",),
        ("blackhole", 9),
        ("golden", 9, 1, 6),
        ("joseki", 9, 5),
        ("hidden", 9, 2, True),
        ("diamond", 3, 3, 4, 9),
        ("sync", True, 0.5),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "activated"},
        {
            "type": "rogue_card_selected",
            "card_id": "seal",
            "name": "name-seal",
            "icon": "icon",
            "waiting_seal": True,
            "state_marker": "ready",
            "komi": 0.5,
        },
    ]


async def smoke_ai_activation_flow_sends_selection() -> None:
    game = DummyGame()
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    def get_card(card_id):
        calls.append(("get_card", card_id))
        return card(card_id)

    def choose_corner():
        calls.append(("corner",))
        return 2

    def blackhole(size):
        calls.append(("blackhole", size))
        return [(0, 0)]

    def golden(size, corner, span):
        calls.append(("golden", size, corner, span))
        return [(1, 1)]

    def refresh(game_arg):
        calls.append(("refresh", game_arg is game))

    def apply_activation(game_arg, card_id, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            card_id,
            kwargs["choose_corner"] is choose_corner,
            kwargs["get_blackhole_points_fn"] is blackhole,
            kwargs["get_golden_corner_points_fn"] is golden,
            kwargs["refresh_ai_rogue_player_turn_fn"] is refresh,
            kwargs["golden_corner_span"],
        ))
        kwargs["choose_corner"]()
        kwargs["get_blackhole_points_fn"](9)
        kwargs["get_golden_corner_points_fn"](9, 2, kwargs["golden_corner_span"])
        kwargs["refresh_ai_rogue_player_turn_fn"](game_arg)

    deps = AiRogueCardActivationFlowDeps(
        get_card=get_card,
        apply_activation=apply_activation,
        choose_corner=choose_corner,
        get_blackhole_points=blackhole,
        get_golden_corner_points=golden,
        refresh_ai_rogue_player_turn=refresh,
        golden_corner_span=6,
    )

    await activate_ai_rogue_card_event(game, send, "golden_corner", deps)

    assert calls == [
        ("get_card", "golden_corner"),
        ("apply", True, "golden_corner", True, True, True, True, 6),
        ("corner",),
        ("blackhole", 9),
        ("golden", 9, 2, 6),
        ("refresh", True),
    ]
    assert sent == [
        {
            "type": "rogue_ai_selected",
            "card_id": "golden_corner",
            "name": "name-golden_corner",
            "icon": "icon",
            "state_marker": "ready",
            "komi": 7.5,
        }
    ]


async def main() -> None:
    await smoke_player_activation_flow_sends_events_syncs_and_selects()
    await smoke_ai_activation_flow_sends_selection()
    print("rogue card flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
