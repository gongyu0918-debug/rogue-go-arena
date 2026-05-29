from __future__ import annotations

import asyncio
import copy

import server as s
from app.domain.game_state import GoGame
from app.gameplay.challenge_effects import (
    apply_challenge_level_decay,
    apply_challenge_trap_bonus,
    challenge_set_bonus_status_message,
)


def _challenge_game(cards: list[str]) -> GoGame:
    game = GoGame(size=9, player_color="B", level="5k")
    game.challenge_beta = True
    game.challenge_cards = cards
    return game


def test_apply_challenge_trap_bonus_sets_skip_and_message() -> None:
    game = _challenge_game(["god_hand", "sansan_trap"])

    skipped = apply_challenge_trap_bonus(
        game,
        "神之一手",
        roll_random=lambda: 1.0,
        chance=0.5,
    )
    assert skipped is None
    assert game.rogue_skip_ai is False

    message = apply_challenge_trap_bonus(
        game,
        "神之一手",
        roll_random=lambda: 0.0,
        chance=0.5,
    )

    assert game.rogue_skip_ai is True
    assert message == "陷阱套装触发：神之一手 额外夺得一次落子权"

    game = _challenge_game(["god_hand", "sansan_trap"])
    boundary_message = apply_challenge_trap_bonus(
        game,
        "神之一手",
        roll_random=lambda: 0.5,
        chance=0.5,
    )
    assert boundary_message == "陷阱套装触发：神之一手 额外夺得一次落子权"
    assert game.rogue_skip_ai is True


def test_apply_challenge_trap_bonus_ignores_missing_set() -> None:
    game = _challenge_game(["god_hand"])

    message = apply_challenge_trap_bonus(
        game,
        "神之一手",
        roll_random=lambda: 0.0,
        chance=1.0,
    )

    assert message is None
    assert game.rogue_skip_ai is False


def test_apply_challenge_level_decay_mutates_once() -> None:
    game = _challenge_game(["dice", "nerf"])

    missed = apply_challenge_level_decay(
        game,
        roll_random=lambda: 1.0,
        weaken_rank_one_step=s.weaken_rank_one_step,
        rank_labels=s.RANK_LABELS,
        chance=0.5,
    )
    assert missed is None
    assert game.level == "5k"

    result = apply_challenge_level_decay(
        game,
        roll_random=lambda: 0.0,
        weaken_rank_one_step=s.weaken_rank_one_step,
        rank_labels=s.RANK_LABELS,
        chance=0.5,
    )

    assert result is not None
    assert result.new_level == "6k"
    assert game.level == "6k"
    assert result.message == "限制套装触发：AI 临时下调至 6级"

    boundary_game = _challenge_game(["dice", "nerf"])
    boundary = apply_challenge_level_decay(
        boundary_game,
        roll_random=lambda: 0.5,
        weaken_rank_one_step=s.weaken_rank_one_step,
        rank_labels=s.RANK_LABELS,
        chance=0.5,
    )
    assert boundary is None
    assert boundary_game.level == "5k"


def test_apply_challenge_level_decay_ignores_unchanged_level() -> None:
    game = _challenge_game(["dice", "nerf"])
    game.level = "18k"

    result = apply_challenge_level_decay(
        game,
        roll_random=lambda: 0.0,
        weaken_rank_one_step=s.weaken_rank_one_step,
        rank_labels=s.RANK_LABELS,
        chance=0.5,
    )

    assert result is None
    assert game.level == "18k"


def test_challenge_set_bonus_status_message() -> None:
    assert challenge_set_bonus_status_message(GoGame(size=9)) is None

    game = _challenge_game(["twin", "exchange"])
    assert challenge_set_bonus_status_message(game) == "闯关套装已激活：主动"


async def _server_challenge_wrappers_keep_patchable_boundaries() -> None:
    game = _challenge_game(["dice", "nerf"])
    sent = []
    calls = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    async def run_executor(func, *args):
        calls.append(("executor", args))
        return func(*args)

    def set_visits(visits):
        calls.append(("set_visits", visits))

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 321

    original_random = s.random.random
    original_ready = s.engine.ready
    original_set_visits = s.engine.set_visits
    original_run_executor = s.run_in_executor
    original_get_visits = s.get_game_visits
    s.random.random = lambda: 0.0
    s.engine.ready = True
    s.engine.set_visits = set_visits
    s.run_in_executor = run_executor
    s.get_game_visits = get_visits
    try:
        await s._challenge_maybe_reduce_ai_level(game, send)
    finally:
        s.random.random = original_random
        s.engine.ready = original_ready
        s.engine.set_visits = original_set_visits
        s.run_in_executor = original_run_executor
        s.get_game_visits = original_get_visits

    assert game.level == "6k"
    assert sent == [{"type": "rogue_event", "msg": "限制套装触发：AI 临时下调至 6级"}]
    assert calls == [
        ("visits", "6k", 0, "rogue"),
        ("executor", (321,)),
        ("set_visits", 321),
    ]

    game = _challenge_game(["god_hand", "sansan_trap"])
    sent = []
    original_random = s.random.random
    s.random.random = lambda: 0.0
    try:
        await s._challenge_apply_trap_bonus(game, send, "神之一手")
    finally:
        s.random.random = original_random

    assert game.rogue_skip_ai is True
    assert sent == [{"type": "rogue_event", "msg": "陷阱套装触发：神之一手 额外夺得一次落子权"}]

    game = _challenge_game(["dice", "nerf"])
    sent = []
    calls = []
    original_random = s.random.random
    original_ready = s.engine.ready
    original_set_visits = s.engine.set_visits
    original_run_executor = s.run_in_executor
    original_get_visits = s.get_game_visits
    s.random.random = lambda: 0.0
    s.engine.ready = False
    s.engine.set_visits = set_visits
    s.run_in_executor = run_executor
    s.get_game_visits = get_visits
    try:
        await s._challenge_maybe_reduce_ai_level(game, send)
    finally:
        s.random.random = original_random
        s.engine.ready = original_ready
        s.engine.set_visits = original_set_visits
        s.run_in_executor = original_run_executor
        s.get_game_visits = original_get_visits

    assert game.level == "6k"
    assert sent == [{"type": "rogue_event", "msg": "限制套装触发：AI 临时下调至 6级"}]
    assert calls == []


async def _server_challenge_set_bonus_status_wrapper_sends_message() -> None:
    game = _challenge_game(["twin", "exchange", "fog", "blackhole"])
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    await s._challenge_emit_set_bonus_status(game, send)

    assert sent == [{"type": "rogue_event", "msg": "闯关套装已激活：限位 / 主动"}]


def test_server_challenge_wrappers_keep_patchable_boundaries() -> None:
    asyncio.run(_server_challenge_wrappers_keep_patchable_boundaries())


def test_server_challenge_set_bonus_status_wrapper_sends_message() -> None:
    asyncio.run(_server_challenge_set_bonus_status_wrapper_sends_message())


if __name__ == "__main__":
    test_apply_challenge_trap_bonus_sets_skip_and_message()
    test_apply_challenge_trap_bonus_ignores_missing_set()
    test_apply_challenge_level_decay_mutates_once()
    test_apply_challenge_level_decay_ignores_unchanged_level()
    test_challenge_set_bonus_status_message()
    test_server_challenge_wrappers_keep_patchable_boundaries()
    test_server_challenge_set_bonus_status_wrapper_sends_message()
    print("challenge_effects_smoke_test passed")
