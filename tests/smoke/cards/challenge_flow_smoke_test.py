from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

from app.domain.game_state import GoGame
from app.gameplay.challenge_flow import (
    ChallengeFlowDeps,
    ChallengeLoadoutFlowDeps,
    apply_challenge_rogue_loadout_event,
    apply_challenge_trap_bonus_event,
    emit_challenge_set_bonus_status,
    maybe_reduce_challenge_ai_level,
)


def challenge_game(cards: list[str]) -> GoGame:
    game = GoGame(size=9, player_color="B", level="5k")
    game.challenge_beta = True
    game.challenge_cards = cards
    return game


def deps(*, engine_ready: bool = True, calls: list | None = None) -> ChallengeFlowDeps:
    if calls is None:
        calls = []

    async def run_in_executor(func, *args):
        calls.append(("executor", args))
        return func(*args)

    def set_visits(visits):
        calls.append(("set_visits", visits))

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 321

    def weaken_rank(level):
        return "6k" if level == "5k" else level

    return ChallengeFlowDeps(
        roll_random=lambda: 0.0,
        trap_extra_turn_chance=0.5,
        restriction_decay_chance=0.5,
        weaken_rank_one_step=weaken_rank,
        rank_labels={"6k": "6级"},
        challenge_set_min_count=2,
        engine_ready=lambda: engine_ready,
        get_game_visits=get_visits,
        run_in_executor=run_in_executor,
        set_engine_visits=set_visits,
    )


def loadout_deps(calls: list) -> ChallengeLoadoutFlowDeps:
    def card_ids(card_ids):
        calls.append(("card_ids", tuple(card_ids)))
        return list(card_ids)

    def get_card(card_id):
        calls.append(("get_card", card_id))
        return {"id": card_id}

    def active_bonus(_game, card_id):
        calls.append(("active_bonus", card_id))
        return 0

    def zone_points(_game, points):
        calls.append(("zone_points", tuple(points)))
        return list(points)

    def choose_corner():
        calls.append(("corner",))
        return 2

    def make_rng():
        calls.append(("rng",))
        return object()

    def blackhole_points(size):
        calls.append(("blackhole", size))
        return [(0, 0)]

    def golden_corner_points(size, corner, span):
        calls.append(("golden_corner", size, corner, span))
        return [(1, 1)]

    def joseki_targets(size, count):
        calls.append(("joseki", size, count))
        return [(2, 2)]

    def hidden_center(size, radius, rng):
        calls.append(("hidden", size, radius, rng is not None))
        return (3, 3)

    def diamond_points(x, y, radius, size):
        calls.append(("diamond", x, y, radius, size))
        return [(x, y)]

    def apply_loadout(game, **kwargs):
        calls.append((
            "loadout",
            kwargs["card_ids_fn"] is card_ids,
            kwargs["get_rogue_card_fn"] is get_card,
            kwargs["active_use_bonus_fn"] is active_bonus,
            kwargs["challenge_zone_points_fn"] is zone_points,
            kwargs["choose_corner"] is choose_corner,
            kwargs["make_rng"] is make_rng,
            kwargs["get_blackhole_points_fn"] is blackhole_points,
            kwargs["get_golden_corner_points_fn"] is golden_corner_points,
            kwargs["pick_joseki_targets_fn"] is joseki_targets,
            kwargs["random_hidden_center_fn"] is hidden_center,
            kwargs["diamond_points_fn"] is diamond_points,
            kwargs["golden_corner_span"],
            kwargs["joseki_target_count"],
            kwargs["godhand_radius"],
        ))
        game.komi = 3.5
        return {"cards": ["komi_relief"]}

    async def sync_komi(game):
        calls.append(("sync", game.komi))

    async def emit_status(game, send_fn):
        calls.append(("status", game.komi))
        await send_fn({"type": "rogue_event", "msg": "status"})

    return ChallengeLoadoutFlowDeps(
        apply_loadout=apply_loadout,
        card_ids_fn=card_ids,
        get_rogue_card_fn=get_card,
        active_use_bonus_fn=active_bonus,
        challenge_zone_points_fn=zone_points,
        choose_corner=choose_corner,
        make_rng=make_rng,
        get_blackhole_points_fn=blackhole_points,
        get_golden_corner_points_fn=golden_corner_points,
        pick_joseki_targets_fn=joseki_targets,
        random_hidden_center_fn=hidden_center,
        diamond_points_fn=diamond_points,
        golden_corner_span=6,
        joseki_target_count=5,
        godhand_radius=4,
        sync_engine_komi=sync_komi,
        emit_set_bonus_status=emit_status,
    )


async def smoke_loadout_flow_injects_deps_and_syncs_status() -> None:
    game = challenge_game(["komi_relief"])
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    result = await apply_challenge_rogue_loadout_event(
        game,
        send,
        loadout_deps(calls),
    )

    assert result == {"cards": ["komi_relief"]}
    assert calls == [
        (
            "loadout",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            6,
            5,
            4,
        ),
        ("sync", 3.5),
        ("status", 3.5),
    ]
    assert sent == [{"type": "rogue_event", "msg": "status"}]


async def smoke_trap_bonus_event() -> None:
    game = challenge_game(["god_hand", "sansan_trap"])
    sent = []

    async def send(payload):
        sent.append(payload)

    await apply_challenge_trap_bonus_event(game, send, "神之一手", deps())

    assert game.rogue_skip_ai is True
    assert sent == [{"type": "rogue_event", "msg": "陷阱套装触发：神之一手 额外夺得一次落子权"}]


async def smoke_level_decay_syncs_visits_when_engine_ready() -> None:
    game = challenge_game(["dice", "nerf"])
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    await maybe_reduce_challenge_ai_level(game, send, deps(engine_ready=True, calls=calls))

    assert game.level == "6k"
    assert sent == [{"type": "rogue_event", "msg": "限制套装触发：AI 临时下调至 6级"}]
    assert calls == [
        ("visits", "6k", 0, "rogue"),
        ("executor", (321,)),
        ("set_visits", 321),
    ]


async def smoke_level_decay_skips_visits_when_engine_not_ready() -> None:
    game = challenge_game(["dice", "nerf"])
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    await maybe_reduce_challenge_ai_level(game, send, deps(engine_ready=False, calls=calls))

    assert game.level == "6k"
    assert sent == [{"type": "rogue_event", "msg": "限制套装触发：AI 临时下调至 6级"}]
    assert calls == []


async def smoke_set_bonus_status_event() -> None:
    game = challenge_game(["twin", "exchange", "fog", "blackhole"])
    sent = []

    async def send(payload):
        sent.append(payload)

    await emit_challenge_set_bonus_status(game, send, deps())

    assert sent == [{"type": "rogue_event", "msg": "闯关套装已激活：限位 / 主动"}]


async def main() -> None:
    await smoke_loadout_flow_injects_deps_and_syncs_status()
    await smoke_trap_bonus_event()
    await smoke_level_decay_syncs_visits_when_engine_ready()
    await smoke_level_decay_skips_visits_when_engine_not_ready()
    await smoke_set_bonus_status_event()
    print("challenge flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
