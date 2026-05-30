from __future__ import annotations

import asyncio
from types import SimpleNamespace

import server as s
from app.runtime.rogue_activation_adapters import (
    AiRogueCardActivationBinding,
    RogueCardActivationBinding,
    activate_ai_rogue_card,
    activate_rogue_card,
    build_ai_rogue_card_activation_deps,
    build_rogue_card_activation_deps,
)


async def fake_async(*_args, **_kwargs):
    return None


def fake_sync(*_args, **_kwargs):
    return None


def fake_get_card(card_id: str) -> dict:
    return {"id": card_id, "name": card_id, "icon": "icon.png"}


def smoke_player_binding_maps_every_field() -> None:
    binding = RogueCardActivationBinding(
        get_card=fake_get_card,
        apply_activation=fake_sync,
        coord_to_gtp=fake_sync,
        choose_corner=lambda: 1,
        make_rng=fake_sync,
        get_blackhole_points=fake_sync,
        get_golden_corner_points=fake_sync,
        pick_joseki_targets=fake_sync,
        random_hidden_center=fake_sync,
        diamond_points=fake_sync,
        sync_engine_komi=fake_async,
    )

    deps = build_rogue_card_activation_deps(binding)

    assert deps.get_card is fake_get_card
    assert deps.apply_activation is fake_sync
    assert deps.coord_to_gtp is fake_sync
    assert deps.choose_corner() == 1
    assert deps.make_rng is fake_sync
    assert deps.get_blackhole_points is fake_sync
    assert deps.get_golden_corner_points is fake_sync
    assert deps.pick_joseki_targets is fake_sync
    assert deps.random_hidden_center is fake_sync
    assert deps.diamond_points is fake_sync
    assert deps.sync_engine_komi is fake_async


def smoke_ai_binding_maps_every_field() -> None:
    binding = AiRogueCardActivationBinding(
        get_card=fake_get_card,
        apply_activation=fake_sync,
        choose_corner=lambda: 2,
        get_blackhole_points=fake_sync,
        get_golden_corner_points=fake_sync,
        refresh_ai_rogue_player_turn=fake_sync,
        golden_corner_span=7,
    )

    deps = build_ai_rogue_card_activation_deps(binding)

    assert deps.get_card is fake_get_card
    assert deps.apply_activation is fake_sync
    assert deps.choose_corner() == 2
    assert deps.get_blackhole_points is fake_sync
    assert deps.get_golden_corner_points is fake_sync
    assert deps.refresh_ai_rogue_player_turn is fake_sync
    assert deps.golden_corner_span == 7


async def smoke_player_activation_adapter_returns_result_and_sends() -> None:
    game = SimpleNamespace(to_state=lambda: {"state": "ok"})
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def apply_activation(game_arg, card_id, card_def, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            card_id,
            card_def["name"],
            kwargs["coord_to_gtp"] is fake_sync,
            kwargs["choose_corner"]() == 1,
        ))
        return SimpleNamespace(messages=["activated"], sync_komi=True)

    async def sync_komi(game_arg):
        calls.append(("sync", game_arg is game))

    result = await activate_rogue_card(
        game,
        send,
        "seal",
        RogueCardActivationBinding(
            get_card=fake_get_card,
            apply_activation=apply_activation,
            coord_to_gtp=fake_sync,
            choose_corner=lambda: 1,
            make_rng=fake_sync,
            get_blackhole_points=fake_sync,
            get_golden_corner_points=fake_sync,
            pick_joseki_targets=fake_sync,
            random_hidden_center=fake_sync,
            diamond_points=fake_sync,
            sync_engine_komi=sync_komi,
        ),
    )

    assert result.messages == ["activated"]
    assert calls == [
        ("apply", True, "seal", "seal", True, True),
        ("sync", True),
    ]
    assert sent == [
        {"type": "rogue_event", "msg": "activated"},
        {
            "type": "rogue_card_selected",
            "card_id": "seal",
            "name": "seal",
            "icon": "icon.png",
            "waiting_seal": True,
            "state": "ok",
        },
    ]


async def smoke_ai_activation_adapter_sends_selection() -> None:
    game = SimpleNamespace(to_state=lambda: {"state": "ai"})
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def apply_activation(game_arg, card_id, **kwargs):
        calls.append((
            "apply_ai",
            game_arg is game,
            card_id,
            kwargs["choose_corner"]() == 3,
            kwargs["golden_corner_span"],
            kwargs["refresh_ai_rogue_player_turn_fn"] is fake_sync,
        ))

    await activate_ai_rogue_card(
        game,
        send,
        "golden_corner",
        AiRogueCardActivationBinding(
            get_card=fake_get_card,
            apply_activation=apply_activation,
            choose_corner=lambda: 3,
            get_blackhole_points=fake_sync,
            get_golden_corner_points=fake_sync,
            refresh_ai_rogue_player_turn=fake_sync,
            golden_corner_span=8,
        ),
    )

    assert calls == [("apply_ai", True, "golden_corner", True, 8, True)]
    assert sent == [
        {
            "type": "rogue_ai_selected",
            "card_id": "golden_corner",
            "name": "golden_corner",
            "icon": "icon.png",
            "state": "ai",
        }
    ]


def smoke_server_bindings_resolve_current_runtime() -> None:
    originals = {
        "get_rogue_card": s.get_rogue_card,
        "apply_rogue_card_activation": s.apply_rogue_card_activation,
        "apply_ai_rogue_card_activation": s.apply_ai_rogue_card_activation,
        "coord_to_gtp": s.coord_to_gtp,
        "_sync_engine_komi": s._sync_engine_komi,
        "_refresh_ai_rogue_player_turn": s._refresh_ai_rogue_player_turn,
        "ROGUE_GOLDEN_CORNER_SPAN": s.ROGUE_GOLDEN_CORNER_SPAN,
        "random_randint": s.random.randint,
        "random_random_class": s.random.Random,
        "time_time_ns": s.time.time_ns,
    }

    class FakeRandom:
        def __init__(self, seed):
            self.seed = seed

    try:
        s.get_rogue_card = fake_get_card
        s.apply_rogue_card_activation = fake_sync
        s.apply_ai_rogue_card_activation = fake_sync
        s.coord_to_gtp = fake_sync
        s._sync_engine_komi = fake_async
        s._refresh_ai_rogue_player_turn = fake_sync
        s.ROGUE_GOLDEN_CORNER_SPAN = 9
        s.random.randint = lambda _low, _high: 2
        s.random.Random = FakeRandom
        s.time.time_ns = lambda: 456

        player = s._rogue_card_activation_binding()
        player_deps = build_rogue_card_activation_deps(player)
        ai = s._ai_rogue_card_activation_binding()
        ai_deps = build_ai_rogue_card_activation_deps(ai)

        assert player.get_card is fake_get_card
        assert player.apply_activation is fake_sync
        assert player.coord_to_gtp is fake_sync
        assert player.choose_corner() == 2
        assert player.make_rng().seed == 456
        assert player.sync_engine_komi is fake_async
        assert player_deps.get_card is fake_get_card
        assert player_deps.apply_activation is fake_sync
        assert ai.get_card is fake_get_card
        assert ai.apply_activation is fake_sync
        assert ai.choose_corner() == 2
        assert ai.refresh_ai_rogue_player_turn is fake_sync
        assert ai.golden_corner_span == 9
        assert ai_deps.get_card is fake_get_card
        assert ai_deps.golden_corner_span == 9
    finally:
        for name, value in originals.items():
            if name == "random_randint":
                s.random.randint = value
            elif name == "random_random_class":
                s.random.Random = value
            elif name == "time_time_ns":
                s.time.time_ns = value
            else:
                setattr(s, name, value)


def main() -> None:
    smoke_player_binding_maps_every_field()
    smoke_ai_binding_maps_every_field()
    asyncio.run(smoke_player_activation_adapter_returns_result_and_sends())
    asyncio.run(smoke_ai_activation_adapter_sends_selection())
    smoke_server_bindings_resolve_current_runtime()
    print("rogue activation adapters smoke test: OK")


if __name__ == "__main__":
    main()
