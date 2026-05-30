from __future__ import annotations

import asyncio

from app.domain.game_state import GoGame
from app.gameplay.challenge_flow import (
    ChallengeFlowDeps,
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
    await smoke_trap_bonus_event()
    await smoke_level_decay_syncs_visits_when_engine_ready()
    await smoke_level_decay_skips_visits_when_engine_not_ready()
    await smoke_set_bonus_status_event()
    print("challenge flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
