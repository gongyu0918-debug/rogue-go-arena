from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.domain.coordinates import gtp_to_coord
from app.gameplay.coach_mode import (
    CoachMoveChoiceDeps,
    CoachTurnDeps,
    choose_coach_ai_move,
    run_coach_turn_if_needed,
)


class FakeGame:
    def __init__(self) -> None:
        self.size = 9
        self.level = "5k"
        self.moves = []
        self.game_over = False
        self.two_player = False
        self.current_player = "B"
        self.player_color = "B"
        self.ai_color = "W"
        self.rogue_card = "coach_mode"
        self.rogue_coach_moves_left = 2
        self.rogue_coach_bonus_checked = False
        self.history_pushes = 0
        self.ko_points: set[tuple[int, int]] = set()

    def is_ko(self, x: int, y: int, _color: str) -> bool:
        return (x, y) in self.ko_points

    def push_history(self) -> None:
        self.history_pushes += 1

    def to_state(self) -> dict:
        return {
            "current_player": self.current_player,
            "coach_left": self.rogue_coach_moves_left,
            "history_pushes": self.history_pushes,
        }


async def smoke_choose_resign_becomes_pass() -> None:
    game = FakeGame()
    calls = []

    def get_game_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 120

    async def generate_move(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "RESIGN"

    async def retry(_game, _color):
        raise AssertionError("retry should not be used")

    gtp_move, coord = await choose_coach_ai_move(
        game,
        "B",
        CoachMoveChoiceDeps(
            get_game_visits=get_game_visits,
            generate_ai_style_move=generate_move,
            gtp_to_coord=gtp_to_coord,
            retry_avoiding_ko=retry,
            coach_visits=200,
            max_move_time=12.0,
        ),
    )

    assert (gtp_move, coord) == ("pass", None)
    assert calls == [
        ("visits", "5k", 0, "rogue"),
        ("generate", True, "B", 200, 8.0),
    ]


async def smoke_choose_ko_retries() -> None:
    game = FakeGame()
    game.ko_points.add((3, 5))

    async def generate_move(*_args):
        return "D4"

    async def retry(game_arg, color):
        assert game_arg is game
        assert color == "B"
        return "E5"

    gtp_move, coord = await choose_coach_ai_move(
        game,
        "B",
        CoachMoveChoiceDeps(
            get_game_visits=lambda _level, _move_count, mode=None: 500,
            generate_ai_style_move=generate_move,
            gtp_to_coord=gtp_to_coord,
            retry_avoiding_ko=retry,
            coach_visits=200,
            max_move_time=5.0,
        ),
    )

    assert (gtp_move, coord) == ("E5", (4, 4))


async def smoke_guard_skips_ineligible_turn() -> None:
    game = FakeGame()
    game.two_player = True
    calls = []

    async def choose(*_args):
        calls.append("choose")
        return "D4", (3, 5)

    await run_coach_turn_if_needed(
        game,
        lambda _payload: asyncio.sleep(0),
        CoachTurnDeps(
            engine_ready=lambda: True,
            choose_coach_ai_move=choose,
            place_auxiliary_move=lambda *_args: SimpleNamespace(coord=None, captured=0),
            check_capture_foul=lambda *_args, **_kwargs: asyncio.sleep(0),
            apply_player_rogue_move_effects=lambda *_args: asyncio.sleep(0),
            apply_ai_rogue_response_effects=lambda *_args: asyncio.sleep(0),
            estimate_side_winrate=lambda *_args: asyncio.sleep(0, result=0.5),
            ai_move=lambda *_args: asyncio.sleep(0),
            bonus_threshold=0.5,
            bonus_turns=3,
        ),
    )

    assert calls == []
    assert game.history_pushes == 0


async def smoke_run_coach_turn_full_flow() -> None:
    game = FakeGame()
    calls = []
    sent = []

    async def send_fn(payload):
        sent.append(payload)

    async def choose(game_arg, color):
        calls.append(("choose", game_arg is game, color))
        return "D4", (3, 5)

    def place(game_arg, color, gtp_move, coord):
        calls.append(("place", game_arg is game, color, gtp_move, coord))
        game_arg.moves.append((color, gtp_move))
        return SimpleNamespace(coord=coord, captured=1)

    async def check_capture_foul(game_arg, send_arg, offender, captured, *, ultimate):
        calls.append(("capture", game_arg is game, send_arg is send_fn, offender, captured, ultimate))

    async def player_effects(game_arg, send_arg, x, y, color, captured):
        calls.append(("player_effects", game_arg is game, send_arg is send_fn, x, y, color, captured))

    async def ai_response_effects(game_arg, send_arg, x, y, color):
        calls.append(("ai_effects", game_arg is game, send_arg is send_fn, x, y, color))

    async def estimate_winrate(*_args):
        raise AssertionError("bonus check should not run while one coach move remains")

    async def ai_move(game_arg, send_arg):
        calls.append(("ai_move", game_arg is game, send_arg is send_fn))

    await run_coach_turn_if_needed(
        game,
        send_fn,
        CoachTurnDeps(
            engine_ready=lambda: True,
            choose_coach_ai_move=choose,
            place_auxiliary_move=place,
            check_capture_foul=check_capture_foul,
            apply_player_rogue_move_effects=player_effects,
            apply_ai_rogue_response_effects=ai_response_effects,
            estimate_side_winrate=estimate_winrate,
            ai_move=ai_move,
            bonus_threshold=0.5,
            bonus_turns=3,
        ),
    )

    assert game.current_player == "W"
    assert game.rogue_coach_moves_left == 1
    assert game.history_pushes == 1
    assert sent == [
        {"type": "ai_move", "gtp": "D4", "color": "B", "x": 3, "y": 5},
        {"type": "rogue_event", "msg": "🎓 代练上号：强化 AI 接管了一手，剩余 1 手"},
        {
            "type": "game_state",
            "current_player": "W",
            "coach_left": 1,
            "history_pushes": 1,
        },
    ]
    assert calls == [
        ("choose", True, "B"),
        ("place", True, "B", "D4", (3, 5)),
        ("capture", True, True, "B", 1, False),
        ("player_effects", True, True, 3, 5, "B", 1),
        ("ai_effects", True, True, 3, 5, "B"),
        ("ai_move", True, True),
    ]


async def smoke_bonus_turns_trigger_when_still_losing() -> None:
    game = FakeGame()
    game.rogue_coach_moves_left = 1
    sent = []
    ai_move_called = False

    async def send_fn(payload):
        sent.append(payload)

    async def choose(_game, _color):
        return "PASS", None

    def place(_game, _color, _gtp_move, coord):
        return SimpleNamespace(coord=coord, captured=0)

    async def estimate_winrate(game_arg, color):
        assert game_arg is game
        assert color == "B"
        return 0.42

    async def ai_move(_game, _send):
        nonlocal ai_move_called
        ai_move_called = True

    await run_coach_turn_if_needed(
        game,
        send_fn,
        CoachTurnDeps(
            engine_ready=lambda: True,
            choose_coach_ai_move=choose,
            place_auxiliary_move=place,
            check_capture_foul=lambda *_args, **_kwargs: asyncio.sleep(0),
            apply_player_rogue_move_effects=lambda *_args: asyncio.sleep(0),
            apply_ai_rogue_response_effects=lambda *_args: asyncio.sleep(0),
            estimate_side_winrate=estimate_winrate,
            ai_move=ai_move,
            bonus_threshold=0.5,
            bonus_turns=3,
        ),
    )

    assert game.rogue_coach_bonus_checked is True
    assert game.rogue_coach_moves_left == 3
    assert ai_move_called is True
    assert sent[-1] == {
        "type": "rogue_event",
        "msg": "🎓 代练上号追加触发：胜率仍低于 50%，额外再代打 3 手",
    }


async def main() -> None:
    await smoke_choose_resign_becomes_pass()
    await smoke_choose_ko_retries()
    await smoke_guard_skips_ineligible_turn()
    await smoke_run_coach_turn_full_flow()
    await smoke_bonus_turns_trigger_when_still_losing()
    print("coach mode smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
