from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

from app.config import gameplay as gameplay_config
from app.domain.game_state import GoGame
from app.gameplay import quickthink_timer as qt
from app.runtime.ws_actions import WS_ACTION_HANDLERS
from app.runtime import ws_play_actions
from ws_play_actions_smoke_test import FakeContext


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def make_game(stage: int = 1) -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k")
    game.rogue_card = "quickthink"
    game.rogue_quickthink_stage = stage
    game.current_player = "B"
    return game


FIRST = float(gameplay_config.ROGUE_QUICKTHINK_FIRST_SECONDS)
SECOND = float(gameplay_config.ROGUE_QUICKTHINK_SECOND_SECONDS)
GRACE = gameplay_config.ROGUE_QUICKTHINK_GRACE_SECONDS


def smoke_shipped_config_gives_two_seconds() -> None:
    """The card promises 2 seconds; the shipped tuning value used to say 1."""
    from app.data import cards as card_data

    assert card_data.get_gameplay_tuning_values()["ROGUE_QUICKTHINK_FIRST_SECONDS"] == 2
    assert FIRST == 2.0


def smoke_deadline_counts_from_visible_prompt_with_grace() -> None:
    clock = FakeClock()
    game = make_game()
    key = qt.quickthink_key(game)
    clock.now += 5.0  # however long the prompt took to reach and paint on the client
    assert not qt.quickthink_expired(game, clock=clock), "nothing counts before the prompt is shown"
    assert qt.arm_quickthink(game, key, clock=clock) == FIRST
    shown_at = clock.now
    clock.now = shown_at + FIRST + GRACE - 0.001
    assert not qt.quickthink_expired(game, clock=clock), "a move inside the grace window is accepted"
    clock.now = shown_at + FIRST + GRACE + 0.001
    assert qt.quickthink_expired(game, clock=clock), "a move after the grace window is late"


def smoke_rearming_cannot_extend_time() -> None:
    clock = FakeClock()
    game = make_game()
    key = qt.quickthink_key(game)
    qt.arm_quickthink(game, key, clock=clock)
    deadline = game.rogue_quickthink_deadline
    clock.now += 1.5
    assert qt.arm_quickthink(game, key, clock=clock) is None
    assert game.rogue_quickthink_deadline == deadline


def smoke_stale_or_foreign_keys_are_ignored() -> None:
    clock = FakeClock()
    game = make_game()
    assert qt.arm_quickthink(game, "rq:99:1", clock=clock) is None
    game.current_player = "W"
    assert qt.arm_quickthink(game, qt.quickthink_key(game), clock=clock) is None
    # An old prompt's deadline does not apply to the next prompt.
    game = make_game()
    qt.arm_quickthink(game, qt.quickthink_key(game), clock=clock)
    game.moves.append(("B", "E5"))
    game.rogue_quickthink_stage = 2
    clock.now += 60
    assert not qt.quickthink_expired(game, clock=clock)
    assert qt.arm_quickthink(game, qt.quickthink_key(game), clock=clock) == SECOND


def smoke_monotonic_clock_is_the_default() -> None:
    import inspect
    import time

    assert inspect.signature(qt.arm_quickthink).parameters["clock"].default is time.monotonic
    assert inspect.signature(qt.quickthink_expired).parameters["clock"].default is time.monotonic


async def smoke_late_move_becomes_timeout_pass() -> None:
    game = make_game()
    ctx = FakeContext(game)
    assert WS_ACTION_HANDLERS["quickthink_shown"] is ws_play_actions.handle_quickthink_shown
    await ws_play_actions.handle_quickthink_shown(ctx, {"key": qt.quickthink_key(game)})
    assert ctx.sent[-1] == {"type": "quickthink_armed", "key": "rq:0:1", "seconds": FIRST}
    game.rogue_quickthink_deadline -= FIRST + GRACE + 0.1  # the deadline has passed

    await ws_play_actions.handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)

    assert game.board[4][4] == 0, "the late move is not placed"
    assert game.moves == [("B", "pass")]
    assert game.rogue_quickthink_stage == 0
    assert any(p.get("msg") == "⚡ 快速思考超时，自动虚手" for p in ctx.sent)
    assert ctx.ai_moves == [game]


async def smoke_move_in_time_opens_combo_window() -> None:
    game = make_game()
    ctx = FakeContext(game)
    await ws_play_actions.handle_quickthink_shown(ctx, {"key": qt.quickthink_key(game)})
    await ws_play_actions.handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)
    assert game.board[4][4] == 1 and game.rogue_quickthink_stage == 2
    assert not qt.quickthink_expired(game), "the combo prompt needs its own visible report"


def main() -> None:
    smoke_shipped_config_gives_two_seconds()
    smoke_deadline_counts_from_visible_prompt_with_grace()
    smoke_rearming_cannot_extend_time()
    smoke_stale_or_foreign_keys_are_ignored()
    smoke_monotonic_clock_is_the_default()
    asyncio.run(smoke_late_move_becomes_timeout_pass())
    asyncio.run(smoke_move_in_time_opens_combo_window())
    print("quickthink timer smoke ok")


if __name__ == "__main__":
    main()
