from __future__ import annotations

import asyncio

import app.config.gameplay as gameplay_config
import app.gameplay.ai_move_flow as ai_move_flow
import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import (
    AiMoveAdjustment,
    AiMoveCandidate,
    AiMovePlacement,
    AiMoveResolution,
    apply_ai_move_to_board,
    apply_ai_move_placement_effects,
    apply_erosion_komi_counter,
    apply_slip_ai_move,
    apply_suspicious_pass_fallback,
    choose_ai_move_candidate,
    choose_or_generate_ai_style_move,
    finalize_ai_move,
    finalize_forced_ai_pass,
    resolve_ai_resign_move,
    retry_ai_move_avoiding_ko,
    send_ai_move_and_run_coach,
    try_apply_no_regret_bonus,
    try_apply_puppet_ai_move,
    try_apply_sansan_trap_counter,
    try_choose_ai_style_move,
    try_finalize_double_pass,
    try_finalize_forced_ai_stone,
    try_finish_suboptimal_rogue_move,
)


async def _unused_no_resign(_game, _color):
    raise AssertionError("no_resign_move should not be called")


async def _unused_retry_ko(_game, _color):
    raise AssertionError("retry_avoiding_ko should not be called")


def test_apply_ai_move_to_board_places_stone() -> None:
    game = GoGame(size=5, player_color="B")

    result = apply_ai_move_to_board(
        game,
        color="W",
        gtp_move="C3",
        gtp_to_coord=gtp_to_coord,
    )

    assert result == AiMovePlacement(coord=(2, 2), captured=0)
    assert game.moves == [("W", "C3")]
    assert game.board[2][2] == 2
    assert game.passed["W"] is False


def test_apply_ai_move_to_board_records_pass() -> None:
    game = GoGame(size=5, player_color="B")

    result = apply_ai_move_to_board(
        game,
        color="W",
        gtp_move="pass",
        gtp_to_coord=gtp_to_coord,
    )

    assert result == AiMovePlacement(coord=None, captured=0)
    assert game.moves == [("W", "pass")]
    assert game.passed["W"] is True
    assert all(cell == 0 for row in game.board for cell in row)


def test_apply_ai_move_to_board_preserves_invalid_non_pass_as_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return None

    result = apply_ai_move_to_board(
        game,
        color="W",
        gtp_move="not-a-gtp",
        gtp_to_coord=parse_coord,
    )

    assert result == AiMovePlacement(coord=None, captured=0)
    assert game.moves == [("W", "not-a-gtp")]
    assert game.passed["W"] is False
    assert calls == [("parse", "not-a-gtp", 5)]


def test_apply_ai_move_to_board_returns_capture_count() -> None:
    game = GoGame(size=3, player_color="B")
    game.board = [
        [0, 2, 0],
        [2, 1, 2],
        [0, 0, 0],
    ]

    result = apply_ai_move_to_board(
        game,
        color="W",
        gtp_move="B1",
        gtp_to_coord=gtp_to_coord,
    )

    assert result == AiMovePlacement(coord=(1, 2), captured=1)
    assert game.moves == [("W", "B1")]
    assert game.board[1][1] == 0
    assert game.captures["W"] == 1
    assert game.passed["W"] is False


def test_apply_ai_move_to_board_appends_before_parse_and_place() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", list(game.moves), gtp, size))
        return (2, 2)

    def place_stone(x, y, color):
        calls.append(("place", list(game.moves), x, y, color))
        return 1

    game.place_stone = place_stone

    result = apply_ai_move_to_board(
        game,
        color="W",
        gtp_move="C3",
        gtp_to_coord=parse_coord,
    )

    assert result == AiMovePlacement(coord=(2, 2), captured=1)
    assert calls == [
        ("parse", [("W", "C3")], "C3", 5),
        ("place", [("W", "C3")], 2, 2, "W"),
    ]
    assert game.moves == [("W", "C3")]
    assert game.passed["W"] is False


async def _apply_ai_move_placement_effects_syncs_between_counters() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def apply_move(game_arg, **kwargs):
        calls.append(("apply", game_arg is game, kwargs["gtp_move"]))
        return apply_ai_move_to_board(game_arg, **kwargs)

    async def sansan_counter(game_arg, send_fn, **kwargs):
        assert game.board[2][2] == 2
        calls.append(("sansan", game_arg is game, send_fn is send, kwargs["coord"]))
        return True

    async def no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append(("no_regret", game_arg is game, send_fn is send))
        return True

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    result = await apply_ai_move_placement_effects(
        game,
        send,
        color="W",
        card="sansan_trap",
        gtp_move="C3",
        needs_sync=False,
        gtp_to_coord=gtp_to_coord,
        sync_board_to_engine=sync,
        engine_is_ready=lambda: True,
        apply_move_to_board=apply_move,
        apply_sansan_trap_counter=sansan_counter,
        try_no_regret_bonus=no_regret_bonus,
        trap_stones=2,
        get_sansan_points=lambda _size: [(2, 2)],
        adjacent_points=lambda _x, _y, _size: [],
        shuffle_points=lambda _points: None,
        spawn_bonus_points=lambda _game, _points, _color: [],
        coord_to_gtp=lambda _x, _y, _size: "C3",
        apply_trap_bonus=lambda _game, _send, _label: None,
        no_regret_chance=1.0,
        roll_random=lambda: 0.0,
        has_rogue_card=lambda _game, _card: True,
        pick_best_point=lambda _game, _color: None,
    )

    assert result == AiMovePlacement(coord=(2, 2), captured=0)
    assert calls == [
        ("apply", True, "C3"),
        ("sansan", True, True, (2, 2)),
        ("sync", True),
        ("no_regret", True, True),
        ("sync", True),
    ]


def test_apply_ai_move_placement_effects_syncs_between_counters() -> None:
    asyncio.run(_apply_ai_move_placement_effects_syncs_between_counters())


async def _apply_ai_move_placement_effects_keeps_pending_sync_when_engine_not_ready() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def sansan_counter(_game, _send, **_kwargs):
        calls.append(("sansan",))
        return False

    async def no_regret_bonus(_game, _send, **_kwargs):
        calls.append(("no_regret",))
        return False

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    def engine_ready():
        calls.append(("ready",))
        return False

    result = await apply_ai_move_placement_effects(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        needs_sync=True,
        gtp_to_coord=gtp_to_coord,
        sync_board_to_engine=sync,
        engine_is_ready=engine_ready,
        apply_move_to_board=apply_ai_move_to_board,
        apply_sansan_trap_counter=sansan_counter,
        try_no_regret_bonus=no_regret_bonus,
        trap_stones=2,
        get_sansan_points=lambda _size: [],
        adjacent_points=lambda _x, _y, _size: [],
        shuffle_points=lambda _points: None,
        spawn_bonus_points=lambda _game, _points, _color: [],
        coord_to_gtp=lambda _x, _y, _size: "C3",
        apply_trap_bonus=lambda _game, _send, _label: None,
        no_regret_chance=0.0,
        roll_random=lambda: 1.0,
        has_rogue_card=lambda _game, _card: False,
        pick_best_point=lambda _game, _color: None,
    )

    assert result == AiMovePlacement(coord=(2, 2), captured=0)
    assert calls == [
        ("sansan",),
        ("ready",),
        ("no_regret",),
        ("sync", True),
    ]


def test_apply_ai_move_placement_effects_keeps_pending_sync_when_engine_not_ready() -> None:
    asyncio.run(_apply_ai_move_placement_effects_keeps_pending_sync_when_engine_not_ready())


async def _try_apply_sansan_trap_counter_skips_without_card_or_target() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def get_sansan_points(size):
        calls.append(("sansan", size))
        return [(2, 2)]

    def adjacent_points(*_args):
        calls.append(("adjacent",))
        return []

    def shuffle_points(_points):
        calls.append(("shuffle",))

    def spawn_bonus_points(*_args):
        calls.append(("spawn",))
        return []

    async def apply_trap_bonus(*_args):
        calls.append(("trap_bonus",))

    skipped_card = await try_apply_sansan_trap_counter(
        game,
        send,
        card=None,
        coord=(2, 2),
        stones=2,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )
    skipped_coord = await try_apply_sansan_trap_counter(
        game,
        send,
        card="sansan_trap",
        coord=None,
        stones=2,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )

    assert skipped_card is False
    assert skipped_coord is False
    assert calls == []


def test_try_apply_sansan_trap_counter_skips_without_card_or_target() -> None:
    asyncio.run(_try_apply_sansan_trap_counter_skips_without_card_or_target())


async def _try_apply_sansan_trap_counter_skips_non_sansan_point() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def get_sansan_points(size):
        calls.append(("sansan", size))
        return [(1, 1)]

    def adjacent_points(*_args):
        calls.append(("adjacent",))
        return []

    def shuffle_points(_points):
        calls.append(("shuffle",))

    def spawn_bonus_points(*_args):
        calls.append(("spawn",))
        return []

    async def apply_trap_bonus(*_args):
        calls.append(("trap_bonus",))

    changed = await try_apply_sansan_trap_counter(
        game,
        send,
        card="sansan_trap",
        coord=(2, 2),
        stones=2,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )

    assert changed is False
    assert calls == [("sansan", 5)]


def test_try_apply_sansan_trap_counter_skips_non_sansan_point() -> None:
    asyncio.run(_try_apply_sansan_trap_counter_skips_non_sansan_point())


async def _try_apply_sansan_trap_counter_applies_bonus_and_trap_bonus() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[1][1] = 2
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    def get_sansan_points(size):
        calls.append(("sansan", size))
        return [(2, 2)]

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(1, 1), (2, 1), (3, 1)]

    def shuffle_points(points):
        calls.append(("shuffle", list(points)))
        points.reverse()

    def spawn_bonus_points(game_arg, points, color):
        calls.append(("spawn", game_arg is game, list(points), color))
        return points[:1]

    async def apply_trap_bonus(game_arg, send_fn, source_name):
        calls.append(("trap_bonus", game_arg is game, send_fn is send, source_name))

    changed = await try_apply_sansan_trap_counter(
        game,
        send,
        card="sansan_trap",
        coord=(2, 2),
        stones=2,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )

    assert changed is True
    assert calls == [
        ("sansan", 5),
        ("adjacent", 2, 2, 5),
        ("shuffle", [(2, 1), (3, 1)]),
        ("spawn", True, [(3, 1), (2, 1)], "B"),
        ("send", "rogue_event", "△ 三三陷阱发动，在 C3 相邻点反打 1 子"),
        ("trap_bonus", True, True, "三三陷阱"),
    ]


def test_try_apply_sansan_trap_counter_applies_bonus_and_trap_bonus() -> None:
    asyncio.run(_try_apply_sansan_trap_counter_applies_bonus_and_trap_bonus())


async def _try_apply_sansan_trap_counter_keeps_state_without_bonus_points() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def get_sansan_points(_size):
        calls.append(("sansan",))
        return [(2, 2)]

    def adjacent_points(_x, _y, _size):
        calls.append(("adjacent",))
        return [(1, 1)]

    def shuffle_points(points):
        calls.append(("shuffle", list(points)))

    def spawn_bonus_points(_game, points, color):
        calls.append(("spawn", list(points), color))
        return []

    async def apply_trap_bonus(*_args):
        calls.append(("trap_bonus",))

    changed = await try_apply_sansan_trap_counter(
        game,
        send,
        card="sansan_trap",
        coord=(2, 2),
        stones=2,
        get_sansan_points=get_sansan_points,
        adjacent_points=adjacent_points,
        shuffle_points=shuffle_points,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
        apply_trap_bonus=apply_trap_bonus,
    )

    assert changed is False
    assert calls == [
        ("sansan",),
        ("adjacent",),
        ("shuffle", [(1, 1)]),
        ("spawn", [(1, 1)], "B"),
    ]


def test_try_apply_sansan_trap_counter_keeps_state_without_bonus_points() -> None:
    asyncio.run(_try_apply_sansan_trap_counter_keeps_state_without_bonus_points())


async def _try_apply_no_regret_bonus_skips_without_card() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def has_rogue_card(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return False

    def roll_random():
        calls.append(("random",))
        return 0.0

    async def pick_best_point(*_args):
        calls.append(("pick",))
        return (2, 2)

    def spawn_bonus_points(*_args):
        calls.append(("spawn",))
        return [(2, 2)]

    changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
    )

    assert changed is False
    assert calls == [("has", True, "no_regret")]


def test_try_apply_no_regret_bonus_skips_without_card() -> None:
    asyncio.run(_try_apply_no_regret_bonus_skips_without_card())


async def _try_apply_no_regret_bonus_skips_on_chance_miss() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def has_rogue_card(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return True

    def roll_random():
        calls.append(("random",))
        return 0.5

    async def pick_best_point(*_args):
        calls.append(("pick",))
        return (2, 2)

    def spawn_bonus_points(*_args):
        calls.append(("spawn",))
        return [(2, 2)]

    changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
    )

    assert changed is False
    assert calls == [
        ("has", True, "no_regret"),
        ("random",),
    ]


def test_try_apply_no_regret_bonus_skips_on_chance_miss() -> None:
    asyncio.run(_try_apply_no_regret_bonus_skips_on_chance_miss())


async def _try_apply_no_regret_bonus_keeps_legacy_random_before_game_over_check() -> None:
    game = GoGame(size=5, player_color="B")
    game.game_over = True
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def has_rogue_card(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return True

    def roll_random():
        calls.append(("random",))
        return 0.0

    async def pick_best_point(*_args):
        calls.append(("pick",))
        return (2, 2)

    def spawn_bonus_points(*_args):
        calls.append(("spawn",))
        return [(2, 2)]

    changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
    )

    assert changed is False
    assert calls == [
        ("has", True, "no_regret"),
        ("random",),
    ]


def test_try_apply_no_regret_bonus_keeps_legacy_random_before_game_over_check() -> None:
    asyncio.run(_try_apply_no_regret_bonus_keeps_legacy_random_before_game_over_check())


async def _try_apply_no_regret_bonus_applies_bonus_and_sends_event() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    def has_rogue_card(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return True

    def roll_random():
        calls.append(("random",))
        return 0.0

    async def pick_best_point(game_arg, color):
        calls.append(("pick", game_arg is game, color))
        return (2, 1)

    def spawn_bonus_points(game_arg, points, color):
        calls.append(("spawn", game_arg is game, list(points), color))
        return points[:]

    changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_best_point,
        spawn_bonus_points=spawn_bonus_points,
        coord_to_gtp=s.coord_to_gtp,
    )

    assert changed is True
    assert calls == [
        ("has", True, "no_regret"),
        ("random",),
        ("pick", True, "B"),
        ("spawn", True, [(2, 1)], "B"),
        ("send", "rogue_event", "🚫 永不悔棋发动，AI 落子后在 C4 赠送一子"),
    ]


def test_try_apply_no_regret_bonus_applies_bonus_and_sends_event() -> None:
    asyncio.run(_try_apply_no_regret_bonus_applies_bonus_and_sends_event())


async def _try_apply_no_regret_bonus_keeps_state_without_point_or_change() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def has_rogue_card(game_arg, card_id):
        calls.append(("has", game_arg is game, card_id))
        return True

    def roll_random():
        calls.append(("random",))
        return 0.0

    async def pick_no_point(game_arg, color):
        calls.append(("pick_none", game_arg is game, color))
        return None

    async def pick_point(game_arg, color):
        calls.append(("pick_point", game_arg is game, color))
        return (2, 2)

    def spawn_no_change(game_arg, points, color):
        calls.append(("spawn", game_arg is game, list(points), color))
        return []

    no_point_changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_no_point,
        spawn_bonus_points=spawn_no_change,
        coord_to_gtp=s.coord_to_gtp,
    )
    no_change_changed = await try_apply_no_regret_bonus(
        game,
        send,
        chance=0.5,
        roll_random=roll_random,
        has_rogue_card=has_rogue_card,
        pick_best_point=pick_point,
        spawn_bonus_points=spawn_no_change,
        coord_to_gtp=s.coord_to_gtp,
    )

    assert no_point_changed is False
    assert no_change_changed is False
    assert calls == [
        ("has", True, "no_regret"),
        ("random",),
        ("pick_none", True, "B"),
        ("has", True, "no_regret"),
        ("random",),
        ("pick_point", True, "B"),
        ("spawn", True, [(2, 2)], "B"),
    ]


def test_try_apply_no_regret_bonus_keeps_state_without_point_or_change() -> None:
    asyncio.run(_try_apply_no_regret_bonus_keeps_state_without_point_or_change())


async def _apply_erosion_komi_counter_skips_without_card_or_capture() -> None:
    game = GoGame(size=5, komi=7.5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= ok"

    def message(_captured, _komi):
        calls.append(("message",))
        return "erosion"

    skipped_card = await apply_erosion_komi_counter(
        game,
        send,
        card=None,
        captured=2,
        shift_per_capture=0.5,
        run_engine_command=run_engine_command,
        message=message,
    )
    skipped_capture = await apply_erosion_komi_counter(
        game,
        send,
        card="erosion",
        captured=0,
        shift_per_capture=0.5,
        run_engine_command=run_engine_command,
        message=message,
    )

    assert skipped_card is False
    assert skipped_capture is False
    assert game.komi == 7.5
    assert calls == []


def test_apply_erosion_komi_counter_skips_without_card_or_capture() -> None:
    asyncio.run(_apply_erosion_komi_counter_skips_without_card_or_capture())


async def _apply_erosion_komi_counter_increases_komi_for_white_ai() -> None:
    game = GoGame(size=5, komi=0.0, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= ok"

    def message(captured, komi):
        calls.append(("message", captured, komi))
        return f"erosion {captured} {komi}"

    changed = await apply_erosion_komi_counter(
        game,
        send,
        card="erosion",
        captured=2,
        shift_per_capture=0.5,
        run_engine_command=run_engine_command,
        message=message,
    )

    assert changed is True
    assert game.komi == 1.0
    assert calls == [
        ("engine", "komi 1.0"),
        ("message", 2, 1.0),
        ("send", "rogue_event", "erosion 2 1.0"),
    ]


def test_apply_erosion_komi_counter_increases_komi_for_white_ai() -> None:
    asyncio.run(_apply_erosion_komi_counter_increases_komi_for_white_ai())


async def _apply_erosion_komi_counter_decreases_komi_for_black_ai() -> None:
    game = GoGame(size=5, komi=7.5, player_color="W")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= ok"

    changed = await apply_erosion_komi_counter(
        game,
        send,
        card="erosion",
        captured=1,
        shift_per_capture=0.5,
        run_engine_command=run_engine_command,
        message=lambda captured, komi: f"erosion {captured} {komi}",
    )

    assert changed is True
    assert game.komi == 7.0
    assert calls == [
        ("engine", "komi 7.0"),
        ("send", "rogue_event", "erosion 1 7.0"),
    ]


def test_apply_erosion_komi_counter_decreases_komi_for_black_ai() -> None:
    asyncio.run(_apply_erosion_komi_counter_decreases_komi_for_black_ai())


async def _try_finalize_double_pass_skips_without_both_passes() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    handled = await try_finalize_double_pass(
        game,
        send,
        color="W",
        gtp_move="pass",
        run_engine_command=run_engine_command,
        rogue_msg="slip msg",
    )

    assert handled is False
    assert game.game_over is False
    assert calls == []


def test_try_finalize_double_pass_skips_without_both_passes() -> None:
    asyncio.run(_try_finalize_double_pass_skips_without_both_passes())


async def _try_finalize_double_pass_scores_and_sends_legacy_payloads() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    game.passed["W"] = True
    calls = []

    async def send(payload):
        calls.append((
            "send",
            payload["type"],
            payload.get("gtp"),
            payload.get("color"),
            payload.get("x"),
            payload.get("y"),
            payload.get("winner"),
            payload.get("score"),
            payload.get("reason"),
            payload.get("msg"),
        ))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    handled = await try_finalize_double_pass(
        game,
        send,
        color="W",
        gtp_move="pass",
        run_engine_command=run_engine_command,
        rogue_msg="slip msg",
    )

    assert handled is True
    assert game.game_over is True
    assert game.winner == "B"
    assert calls == [
        ("engine", "final_score"),
        ("send", "ai_move", "pass", "W", None, None, None, None, None, None),
        ("send", "rogue_event", None, None, None, None, None, None, None, "slip msg"),
        ("send", "game_over", None, None, None, None, "B", "B+0.5", "double_pass", None),
    ]


def test_try_finalize_double_pass_scores_and_sends_legacy_payloads() -> None:
    asyncio.run(_try_finalize_double_pass_scores_and_sends_legacy_payloads())


async def _try_finalize_double_pass_keeps_legacy_non_b_score_winner() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    game.passed["W"] = True
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("winner"), payload.get("score"), payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= W+0.5"

    handled = await try_finalize_double_pass(
        game,
        send,
        color="W",
        gtp_move="pass",
        run_engine_command=run_engine_command,
    )

    assert handled is True
    assert game.winner == "W"
    assert calls == [
        ("engine", "final_score"),
        ("send", "ai_move", None, None, None),
        ("send", "game_over", "W", "W+0.5", None),
    ]


def test_try_finalize_double_pass_keeps_legacy_non_b_score_winner() -> None:
    asyncio.run(_try_finalize_double_pass_keeps_legacy_non_b_score_winner())


async def _send_ai_move_and_run_coach_sends_coord_and_coach() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("color"), payload.get("x"), payload.get("y"), payload.get("msg")))

    async def run_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    await send_ai_move_and_run_coach(
        game,
        send,
        color="W",
        gtp_move="C3",
        coord=(2, 2),
        run_coach_turn_if_needed=run_coach,
    )

    assert calls == [
        ("send", "ai_move", "C3", "W", 2, 2, None),
        ("coach", True, True),
    ]


def test_send_ai_move_and_run_coach_sends_coord_and_coach() -> None:
    asyncio.run(_send_ai_move_and_run_coach_sends_coord_and_coach())


async def _send_ai_move_and_run_coach_sends_pass_and_rogue_msg_before_coach() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("color"), payload.get("x"), payload.get("y"), payload.get("msg")))

    async def run_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    await send_ai_move_and_run_coach(
        game,
        send,
        color="W",
        gtp_move="pass",
        coord=None,
        rogue_msg="slip msg",
        run_coach_turn_if_needed=run_coach,
    )

    assert calls == [
        ("send", "ai_move", "pass", "W", None, None, None),
        ("send", "rogue_event", None, None, None, None, "slip msg"),
        ("coach", True, True),
    ]


def test_send_ai_move_and_run_coach_sends_pass_and_rogue_msg_before_coach() -> None:
    asyncio.run(_send_ai_move_and_run_coach_sends_pass_and_rogue_msg_before_coach())


async def _choose_or_generate_ai_style_move_plays_style_choice() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    coord_parser = gtp_to_coord

    async def analyze(game_arg, color):
        calls.append(("analyze", game_arg is game, color))
        return {"top_moves": [{"move": "D4"}]}

    def choose(game_arg, color, top_moves, style, *, gtp_to_coord):
        calls.append(("choose", game_arg is game, color, top_moves, style, gtp_to_coord is coord_parser))
        return "D4"

    async def generate(_color, _visits, _time_limit):
        raise AssertionError("generate_move should not be called")

    async def play(command):
        calls.append(("play", command))
        return "="

    gtp_move = await choose_or_generate_ai_style_move(
        game,
        color="W",
        visits=99,
        time_limit=1.5,
        style="territory",
        analyze_position=analyze,
        choose_style_move=choose,
        generate_move=generate,
        gtp_to_coord=coord_parser,
        play_chosen_move=play,
    )

    assert gtp_move == "D4"
    assert calls == [
        ("analyze", True, "W"),
        ("choose", True, "W", [{"move": "D4"}], "territory", True),
        ("play", "play W D4"),
    ]


def test_choose_or_generate_ai_style_move_plays_style_choice() -> None:
    asyncio.run(_choose_or_generate_ai_style_move_plays_style_choice())


async def _choose_or_generate_ai_style_move_balanced_falls_back_to_genmove() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def analyze(_game, _color):
        raise AssertionError("balanced style should skip analysis")

    def choose(*_args, **_kwargs):
        raise AssertionError("balanced style should skip style choice")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "= C3"

    async def play(_command):
        raise AssertionError("play_chosen_move should not be called")

    gtp_move = await choose_or_generate_ai_style_move(
        game,
        color="B",
        visits=77,
        time_limit=2.0,
        style="balanced",
        analyze_position=analyze,
        choose_style_move=choose,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        play_chosen_move=play,
    )

    assert gtp_move == "C3"
    assert calls == [("generate", "B", 77, 2.0)]


def test_choose_or_generate_ai_style_move_balanced_falls_back_to_genmove() -> None:
    asyncio.run(_choose_or_generate_ai_style_move_balanced_falls_back_to_genmove())


async def _choose_or_generate_ai_style_move_analysis_error_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def analyze(_game, color):
        calls.append(("analyze", color))
        raise RuntimeError("analysis unavailable")

    def choose(*_args, **_kwargs):
        raise AssertionError("style choice should not run after analysis failure")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "= pass"

    async def play(_command):
        raise AssertionError("play_chosen_move should not be called")

    gtp_move = await choose_or_generate_ai_style_move(
        game,
        color="W",
        visits=88,
        time_limit=3.0,
        style="influence",
        analyze_position=analyze,
        choose_style_move=choose,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        play_chosen_move=play,
    )

    assert gtp_move == "pass"
    assert calls == [("analyze", "W"), ("generate", "W", 88, 3.0)]


def test_choose_or_generate_ai_style_move_analysis_error_falls_back() -> None:
    asyncio.run(_choose_or_generate_ai_style_move_analysis_error_falls_back())


async def _choose_or_generate_ai_style_move_choice_error_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    coord_parser = gtp_to_coord

    async def analyze(_game, color):
        calls.append(("analyze", color))
        return {"top_moves": [{"move": "Q16"}]}

    def choose(_game, color, top_moves, style, *, gtp_to_coord):
        calls.append(("choose", color, top_moves, style, gtp_to_coord is coord_parser))
        raise RuntimeError("style choice unavailable")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "= E2"

    async def play(_command):
        raise AssertionError("play_chosen_move should not be called")

    gtp_move = await choose_or_generate_ai_style_move(
        game,
        color="B",
        visits=66,
        time_limit=4.0,
        style="territory",
        analyze_position=analyze,
        choose_style_move=choose,
        generate_move=generate,
        gtp_to_coord=coord_parser,
        play_chosen_move=play,
    )

    assert gtp_move == "E2"
    assert calls == [
        ("analyze", "B"),
        ("choose", "B", [{"move": "Q16"}], "territory", True),
        ("generate", "B", 66, 4.0),
    ]


def test_choose_or_generate_ai_style_move_choice_error_falls_back() -> None:
    asyncio.run(_choose_or_generate_ai_style_move_choice_error_falls_back())


async def _try_choose_ai_style_move_returns_none_for_balanced() -> None:
    game = GoGame(size=5, player_color="B")

    async def analyze(_game, _color):
        raise AssertionError("balanced style should skip analysis")

    def choose(*_args, **_kwargs):
        raise AssertionError("balanced style should skip style choice")

    chosen = await try_choose_ai_style_move(
        game,
        color="W",
        style="balanced",
        analyze_position=analyze,
        choose_style_move=choose,
        gtp_to_coord=gtp_to_coord,
    )

    assert chosen is None


def test_try_choose_ai_style_move_returns_none_for_balanced() -> None:
    asyncio.run(_try_choose_ai_style_move_returns_none_for_balanced())


async def _try_choose_ai_style_move_swallows_choice_errors() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def analyze(_game, color):
        calls.append(("analyze", color))
        return {"top_moves": [{"move": "C3"}]}

    def choose(_game, color, top_moves, style, *, gtp_to_coord):
        calls.append(("choose", color, top_moves, style))
        raise RuntimeError("style chooser failed")

    chosen = await try_choose_ai_style_move(
        game,
        color="W",
        style="territory",
        analyze_position=analyze,
        choose_style_move=choose,
        gtp_to_coord=gtp_to_coord,
    )

    assert chosen is None
    assert calls == [
        ("analyze", "W"),
        ("choose", "W", [{"move": "C3"}], "territory"),
    ]


def test_try_choose_ai_style_move_swallows_choice_errors() -> None:
    asyncio.run(_try_choose_ai_style_move_swallows_choice_errors())


async def _choose_ai_move_candidate_uses_forbidden_avoid_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    forbidden = [(0, 0), (1, 1)]

    async def avoid(game_arg, color, visits, time_limit, forbidden_arg):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, forbidden_arg))
        return "D4"

    async def analyze(*_args):
        raise AssertionError("forbidden move choice should skip style analysis")

    def choose_style(*_args, **_kwargs):
        raise AssertionError("forbidden move choice should skip style choice")

    async def generate(*_args):
        raise AssertionError("forbidden move choice should skip genmove")

    def log_error(_message):
        raise AssertionError("forbidden move choice should not log errors")

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=44,
        time_limit=1.0,
        rogue_cards=set(),
        forbidden=forbidden,
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate("D4")
    assert calls == [("avoid", True, "W", 44, 1.0, forbidden)]


def test_choose_ai_move_candidate_uses_forbidden_avoid_move() -> None:
    asyncio.run(_choose_ai_move_candidate_uses_forbidden_avoid_move())


async def _choose_ai_move_candidate_forbidden_none_does_not_genmove() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def avoid(game_arg, color, visits, time_limit, forbidden_arg):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, forbidden_arg))
        return None

    async def analyze(*_args):
        raise AssertionError("forbidden move choice should skip style analysis")

    def choose_style(*_args, **_kwargs):
        raise AssertionError("forbidden move choice should skip style choice")

    async def generate(*_args):
        raise AssertionError("forbidden move choice should not fall back to genmove")

    def log_error(_message):
        raise AssertionError("forbidden move choice should not log errors")

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=45,
        time_limit=1.5,
        rogue_cards=set(),
        forbidden=[(0, 0)],
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate(None)
    assert calls == [("avoid", True, "W", 45, 1.5, [(0, 0)])]


def test_choose_ai_move_candidate_forbidden_none_does_not_genmove() -> None:
    asyncio.run(_choose_ai_move_candidate_forbidden_none_does_not_genmove())


async def _choose_ai_move_candidate_uses_non_rogue_style_choice() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    calls = []

    async def avoid(*_args):
        raise AssertionError("empty forbidden set should skip avoid move")

    async def analyze(game_arg, color):
        calls.append(("analyze", game_arg is game, color))
        return {"top_moves": [{"move": "C3"}]}

    def choose_style(game_arg, color, top_moves, style, *, gtp_to_coord):
        calls.append(("style", game_arg is game, color, top_moves, style))
        return "C3"

    async def generate(*_args):
        raise AssertionError("style move should skip genmove")

    def log_error(_message):
        raise AssertionError("style move should not log errors")

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=44,
        time_limit=1.0,
        rogue_cards=set(),
        forbidden=[],
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate("C3")
    assert calls == [
        ("analyze", True, "W"),
        ("style", True, "W", [{"move": "C3"}], "territory"),
    ]


def test_choose_ai_move_candidate_uses_non_rogue_style_choice() -> None:
    asyncio.run(_choose_ai_move_candidate_uses_non_rogue_style_choice())


async def _choose_ai_move_candidate_rogue_cards_skip_style_choice() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    calls = []

    async def avoid(*_args):
        raise AssertionError("empty forbidden set should skip avoid move")

    async def analyze(*_args):
        raise AssertionError("rogue cards should skip style analysis")

    def choose_style(*_args, **_kwargs):
        raise AssertionError("rogue cards should skip style choice")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "= E2"

    def log_error(_message):
        raise AssertionError("successful genmove should not log errors")

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=55,
        time_limit=2.0,
        rogue_cards={"slip"},
        forbidden=[],
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate("E2")
    assert calls == [("generate", "W", 55, 2.0)]


def test_choose_ai_move_candidate_rogue_cards_skip_style_choice() -> None:
    asyncio.run(_choose_ai_move_candidate_rogue_cards_skip_style_choice())


async def _choose_ai_move_candidate_genmove_game_over_completes() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "balanced"
    calls = []

    async def avoid(*_args):
        raise AssertionError("empty forbidden set should skip avoid move")

    async def analyze(*_args):
        raise AssertionError("balanced style should skip analysis")

    def choose_style(*_args, **_kwargs):
        raise AssertionError("balanced style should skip style choice")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        game.game_over = True
        return "= C3"

    def log_error(_message):
        raise AssertionError("game_over after genmove should not log errors")

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=66,
        time_limit=3.0,
        rogue_cards=set(),
        forbidden=[],
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate(None, completed=True)
    assert calls == [("generate", "W", 66, 3.0)]


def test_choose_ai_move_candidate_genmove_game_over_completes() -> None:
    asyncio.run(_choose_ai_move_candidate_genmove_game_over_completes())


async def _choose_ai_move_candidate_genmove_error_completes_and_logs() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "balanced"
    calls = []

    async def avoid(*_args):
        raise AssertionError("empty forbidden set should skip avoid move")

    async def analyze(*_args):
        raise AssertionError("balanced style should skip analysis")

    def choose_style(*_args, **_kwargs):
        raise AssertionError("balanced style should skip style choice")

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "? illegal move"

    def log_error(message):
        calls.append(("log", message))

    result = await choose_ai_move_candidate(
        game,
        color="W",
        visits=77,
        time_limit=4.0,
        rogue_cards=set(),
        forbidden=[],
        choose_avoid_move=avoid,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        log_error=log_error,
    )

    assert result == AiMoveCandidate(None, completed=True)
    assert calls == [
        ("generate", "W", 77, 4.0),
        ("log", "[AI] genmove returned error: ? illegal move"),
    ]


def test_choose_ai_move_candidate_genmove_error_completes_and_logs() -> None:
    asyncio.run(_choose_ai_move_candidate_genmove_error_completes_and_logs())


async def _finalize_ai_move_places_stone_and_sends_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("x"), payload.get("y")))

    async def check_capture_foul(_game, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate, send_fn is send))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, send_fn):
        calls.append(("coach", send_fn is send))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        rogue_msg="forced move",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.board[2][2] == 2
    assert game.moves[-1] == ("W", "C3")
    assert game.passed["W"] is False
    assert game.current_player == "B"
    assert calls == [
        ("capture_foul", "W", 0, False, True),
        ("prepare", "B"),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "C3", 2, 2),
        ("send", "rogue_event", None, None, None),
        ("coach", True),
    ]


def test_finalize_ai_move_places_stone_and_sends_message() -> None:
    asyncio.run(_finalize_ai_move_places_stone_and_sends_message())


async def _finalize_ai_move_resign_without_card_ends_game() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign_move(*_args):
        calls.append(("no_resign",))
        return "C3"

    async def retry_ko(*_args):
        calls.append(("retry_ko",))
        return "D3"

    async def check_capture_foul(*_args, **_kwargs):
        calls.append(("capture_foul",))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(*_args):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="resign",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=no_resign_move,
        retry_avoiding_ko=retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is True
    assert game.winner == "B"
    assert game.moves == []
    assert calls == [
        ("send", {
            "type": "game_over",
            "winner": "B",
            "score": None,
            "reason": "ai_resign",
        }),
    ]


def test_finalize_ai_move_resign_without_card_ends_game() -> None:
    asyncio.run(_finalize_ai_move_resign_without_card_ends_game())


async def _finalize_ai_move_resign_with_card_uses_no_resign_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def no_resign_move(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "C3"

    async def check_capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card="suboptimal",
        gtp_move="RESIGN",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=no_resign_move,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is False
    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("no_resign", True, "W"),
        ("capture_foul", "W", 0, False),
        ("prepare",),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach",),
    ]


def test_finalize_ai_move_resign_with_card_uses_no_resign_move() -> None:
    asyncio.run(_finalize_ai_move_resign_with_card_uses_no_resign_move())


async def _finalize_ai_move_retries_ko_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("x"), payload.get("y")))

    async def retry_ko(game_arg, color):
        calls.append(("retry_ko", game_arg is game, color))
        return "D3"

    async def check_capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("retry_ko", True, "W"),
        ("capture_foul", "W", 0, False),
        ("prepare",),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "D3", 3, 2),
        ("coach",),
    ]


def test_finalize_ai_move_retries_ko_move() -> None:
    asyncio.run(_finalize_ai_move_retries_ko_move())


async def _finalize_ai_move_delegates_non_terminal_finish_response() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def check_capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(game_arg, send_fn):
        calls.append(("coach_fn", game_arg is game, send_fn is send))

    async def fake_finish_response(game_arg, send_fn, **kwargs):
        calls.append((
            "finish_response",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["rogue_msg"],
            kwargs["run_coach_turn_if_needed"] is run_coach_turn,
        ))

    original_finish_response = ai_move_flow.send_ai_move_and_run_coach
    ai_move_flow.send_ai_move_and_run_coach = fake_finish_response
    try:
        await finalize_ai_move(
            game,
            send,
            color="W",
            card=None,
            gtp_move="C3",
            rogue_msg="message",
            gtp_to_coord=gtp_to_coord,
            no_resign_move=_unused_no_resign,
            retry_avoiding_ko=_unused_retry_ko,
            check_capture_foul=check_capture_foul,
            prepare_player_turn_modifiers=prepare_player_turn,
            run_engine_command=run_engine_command,
            run_coach_turn_if_needed=run_coach_turn,
        )
    finally:
        ai_move_flow.send_ai_move_and_run_coach = original_finish_response

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("capture_foul", "W", 0, False),
        ("prepare", "B"),
        ("send", {"type": "game_state", **game.to_state()}),
        ("finish_response", True, True, "W", "C3", (2, 2), "message", True),
    ]


def test_finalize_ai_move_delegates_non_terminal_finish_response() -> None:
    asyncio.run(_finalize_ai_move_delegates_non_terminal_finish_response())


async def _finalize_ai_move_double_pass_scores_without_coach_turn() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("score")))

    async def check_capture_foul(*_args, **_kwargs):
        calls.append(("capture_foul",))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= W+0.5"

    async def run_coach_turn(*_args):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="pass",
        rogue_msg="should not send in double pass",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.game_over is True
    assert game.winner == "W"
    assert game.moves[-1] == ("W", "pass")
    assert calls == [
        ("capture_foul",),
        ("prepare",),
        ("send", "game_state", None, None),
        ("engine", "final_score"),
        ("send", "ai_move", "pass", None),
        ("send", "game_over", None, "W+0.5"),
    ]


def test_finalize_ai_move_double_pass_scores_without_coach_turn() -> None:
    asyncio.run(_finalize_ai_move_double_pass_scores_without_coach_turn())


async def _finalize_ai_move_erosion_updates_komi_after_capture() -> None:
    game = GoGame(size=3, komi=0.0, player_color="B")
    game.board = [
        [0, 2, 0],
        [2, 1, 2],
        [0, 0, 0],
    ]
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def check_capture_foul(_game, _send_fn, _offender, captured, *, ultimate):
        calls.append(("capture_foul", captured, ultimate))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "= B+0.5"

    async def run_coach_turn(_game, _send_fn):
        calls.append(("coach",))

    await finalize_ai_move(
        game,
        send,
        color="W",
        card="erosion",
        gtp_move="B1",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        run_coach_turn_if_needed=run_coach_turn,
    )

    assert game.board[1][1] == 0
    assert game.captures["W"] == 1
    assert game.komi == gameplay_config.ROGUE_EROSION_SHIFT
    assert ("engine", f"komi {gameplay_config.ROGUE_EROSION_SHIFT}") in calls
    assert calls[:5] == [
        ("capture_foul", 1, False),
        ("prepare",),
        ("engine", f"komi {gameplay_config.ROGUE_EROSION_SHIFT}"),
        ("send", "rogue_event", f"🐛 蚕食！AI 提 1 子，贴目变为 {gameplay_config.ROGUE_EROSION_SHIFT}"),
        ("send", "game_state", None),
    ]


def test_finalize_ai_move_erosion_updates_komi_after_capture() -> None:
    asyncio.run(_finalize_ai_move_erosion_updates_komi_after_capture())


async def _finalize_forced_ai_pass_sends_legacy_payloads() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append((
            "send",
            payload["type"],
            payload.get("gtp"),
            payload.get("color"),
            payload.get("msg"),
        ))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    await finalize_forced_ai_pass(
        game,
        send,
        color="W",
        message="forced pass",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert game.moves[-1] == ("W", "pass")
    assert game.passed["W"] is True
    assert game.game_over is False
    assert game.current_player == "B"
    assert calls == [
        ("engine", "play W pass"),
        ("prepare", "B"),
        ("send", "game_state", None, None, None),
        ("send", "ai_move", "pass", "W", None),
        ("send", "rogue_event", None, None, "forced pass"),
    ]


def test_finalize_forced_ai_pass_sends_legacy_payloads() -> None:
    asyncio.run(_finalize_forced_ai_pass_sends_legacy_payloads())


async def _try_finalize_forced_ai_stone_sends_legacy_payloads() -> None:
    game = GoGame(size=5, player_color="B")
    history_len = len(game._history)
    calls = []

    async def send(payload):
        calls.append((
            "send",
            payload["type"],
            payload.get("gtp"),
            payload.get("color"),
            payload.get("x"),
            payload.get("y"),
            payload.get("msg"),
        ))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    succeeded = await try_finalize_forced_ai_stone(
        game,
        send,
        color="W",
        gtp_move="D3",
        coord=(3, 2),
        message="forced stone",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert succeeded is True
    assert game.board[2][3] == 2
    assert game.moves[-1] == ("W", "D3")
    assert game.passed["W"] is False
    assert game.current_player == "B"
    assert len(game._history) == history_len + 1
    assert calls == [
        ("engine", "play W D3"),
        ("prepare", "B"),
        ("send", "game_state", None, None, None, None, None),
        ("send", "ai_move", "D3", "W", 3, 2, None),
        ("send", "rogue_event", None, None, None, None, "forced stone"),
    ]


def test_try_finalize_forced_ai_stone_sends_legacy_payloads() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_sends_legacy_payloads())


async def _try_finalize_forced_ai_stone_can_skip_history_push() -> None:
    game = GoGame(size=5, player_color="B")
    history_len = len(game._history)
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    def prepare_player_turn(_game):
        calls.append(("prepare", game.current_player))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    succeeded = await try_finalize_forced_ai_stone(
        game,
        send,
        color="W",
        gtp_move="D3",
        coord=(3, 2),
        message="forced stone",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
        push_history=False,
    )

    assert succeeded is True
    assert game.board[2][3] == 2
    assert game.moves[-1] == ("W", "D3")
    assert len(game._history) == history_len
    assert calls == [
        ("engine", "play W D3"),
        ("prepare", "B"),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("send", "rogue_event", None),
    ]


def test_try_finalize_forced_ai_stone_can_skip_history_push() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_can_skip_history_push())


async def _try_finalize_forced_ai_stone_skips_state_on_engine_error() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def prepare_player_turn(_game):
        calls.append(("prepare",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "? illegal move"

    succeeded = await try_finalize_forced_ai_stone(
        game,
        send,
        color="W",
        gtp_move="D3",
        coord=(3, 2),
        message="forced stone",
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=run_engine_command,
    )

    assert succeeded is False
    assert game.board[2][3] == 0
    assert game.moves == []
    assert calls == [("engine", "play W D3")]


def test_try_finalize_forced_ai_stone_skips_state_on_engine_error() -> None:
    asyncio.run(_try_finalize_forced_ai_stone_skips_state_on_engine_error())


async def _server_ai_move_dice_delegates_to_forced_pass() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "dice"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["message"],
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_pass = s.finalize_forced_ai_pass
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.finalize_forced_ai_pass = fake_forced_pass
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.finalize_forced_ai_pass = original_forced_pass

    assert calls == [
        ("sync", True),
        (
            "forced_pass",
            True,
            True,
            "W",
            "掷骰触发，AI 这手选择虚手",
            True,
            True,
        ),
    ]


def test_server_ai_move_dice_delegates_to_forced_pass() -> None:
    asyncio.run(_server_ai_move_dice_delegates_to_forced_pass())


async def _server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "exchange"
    game.rogue_skip_ai = True
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["message"],
            game.rogue_skip_ai,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_forced_pass = s.finalize_forced_ai_pass
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.finalize_forced_ai_pass = fake_forced_pass
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.finalize_forced_ai_pass = original_forced_pass

    assert calls == [
        ("sync", True),
        (
            "forced_pass",
            True,
            True,
            "W",
            "乾坤挪移生效，AI 本回合虚手并把回合交还给你",
            False,
            True,
            True,
        ),
    ]


def test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass() -> None:
    asyncio.run(_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass())


async def _server_ai_move_mirror_delegates_to_forced_stone() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "mirror"
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs.get("push_history", True),
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_stone = s.try_finalize_forced_ai_stone
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.try_finalize_forced_ai_stone = fake_forced_stone
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.try_finalize_forced_ai_stone = original_forced_stone

    assert calls == [
        ("sync", True),
        (
            "forced_stone",
            True,
            True,
            "W",
            "D4",
            (3, 1),
            "镜像触发，AI 在对称点 D4 落子",
            True,
            True,
            True,
        ),
    ]


def test_server_ai_move_mirror_delegates_to_forced_stone() -> None:
    asyncio.run(_server_ai_move_mirror_delegates_to_forced_stone())


async def _server_ai_move_mirror_helper_false_falls_back_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "mirror"
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["gtp_move"],
        ))
        return False

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_random = s.random.random
    original_forced_stone = s.try_finalize_forced_ai_stone
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = lambda: 0.0
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.try_finalize_forced_ai_stone = original_forced_stone
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("forced_stone", True, True, "D4"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_mirror_helper_false_falls_back_to_normal_move() -> None:
    asyncio.run(_server_ai_move_mirror_helper_false_falls_back_to_normal_move())


async def _server_ai_move_tengen_delegates_to_forced_stone_without_history() -> None:
    class TargetPlan:
        coord = (2, 2)
        message = "天元压迫触发"

    game = GoGame(size=5, player_color="B")
    game.rogue_card = "tengen"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_choose_tengen_target(game_arg, ai_move_count):
        calls.append(("target", game_arg is game, ai_move_count))
        return TargetPlan()

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs["push_history"],
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            callable(kwargs["run_engine_command"]),
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_choose_tengen_target = s.choose_tengen_target
    original_forced_stone = s.try_finalize_forced_ai_stone
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_tengen_target = fake_choose_tengen_target
    s.try_finalize_forced_ai_stone = fake_forced_stone
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_tengen_target = original_choose_tengen_target
        s.try_finalize_forced_ai_stone = original_forced_stone

    assert calls == [
        ("sync", True),
        ("target", True, 0),
        (
            "forced_stone",
            True,
            True,
            "W",
            "C3",
            (2, 2),
            "天元压迫触发",
            False,
            True,
            True,
        ),
    ]


def test_server_ai_move_tengen_delegates_to_forced_stone_without_history() -> None:
    asyncio.run(_server_ai_move_tengen_delegates_to_forced_stone_without_history())


async def _server_ai_move_tengen_helper_false_falls_back_to_followup() -> None:
    class TargetPlan:
        coord = (2, 2)
        message = "天元压迫触发"

    class Restriction:
        points = [(0, 0)]
        message = "天元后续限制"

    game = GoGame(size=5, player_color="B")
    game.rogue_card = "tengen"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_choose_tengen_target(game_arg, ai_move_count):
        calls.append(("target", game_arg is game, ai_move_count))
        return TargetPlan()

    async def fake_forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["gtp_move"],
            kwargs["push_history"],
        ))
        return False

    def fake_tengen_followup_points(game_arg, ai_move_count):
        calls.append(("followup", game_arg is game, ai_move_count))
        return Restriction()

    async def fake_allow_only(game_arg, color, visits, time_limit, points):
        calls.append(("allow_only", game_arg is game, color, points))
        return "C3"

    async def fake_finish(game_arg, send_fn, color, card, gtp_move, rogue_msg=None):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            color,
            card,
            gtp_move,
            rogue_msg,
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_choose_tengen_target = s.choose_tengen_target
    original_forced_stone = s.try_finalize_forced_ai_stone
    original_tengen_followup_points = s.tengen_followup_points
    original_allow_only = s._ai_move_avoid_points_allow_only
    original_finish = s._finish_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_tengen_target = fake_choose_tengen_target
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s.tengen_followup_points = fake_tengen_followup_points
    s._ai_move_avoid_points_allow_only = fake_allow_only
    s._finish_ai_move = fake_finish
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_tengen_target = original_choose_tengen_target
        s.try_finalize_forced_ai_stone = original_forced_stone
        s.tengen_followup_points = original_tengen_followup_points
        s._ai_move_avoid_points_allow_only = original_allow_only
        s._finish_ai_move = original_finish

    assert calls == [
        ("sync", True),
        ("target", True, 0),
        ("forced_stone", True, True, "C3", False),
        ("followup", True, 0),
        ("allow_only", True, "W", [(0, 0)]),
        ("finish", True, True, "W", "tengen", "C3", "天元后续限制"),
    ]


def test_server_ai_move_tengen_helper_false_falls_back_to_followup() -> None:
    asyncio.run(_server_ai_move_tengen_helper_false_falls_back_to_followup())


async def _try_apply_puppet_ai_move_success_finishes_and_updates_uses() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.rogue_uses["puppet"] = 2
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("uses")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            color,
            card,
            gtp_move,
            rogue_msg,
            game.rogue_uses["puppet"],
        ))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert game.rogue_puppet_target is None
    assert game.rogue_uses["puppet"] == 1
    assert calls == [
        ("engine", "play W C3"),
        (
            "finish",
            True,
            True,
            "W",
            "puppet",
            "C3",
            "🎭 傀儡术生效，AI 被迫落子于 C3",
            1,
        ),
        ("send", "rogue_uses_update", {"puppet": 1}),
    ]


def test_try_apply_puppet_ai_move_success_finishes_and_updates_uses() -> None:
    asyncio.run(_try_apply_puppet_ai_move_success_finishes_and_updates_uses())


async def _try_apply_puppet_ai_move_occupied_target_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.board[2][2] = 1
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert calls == [
        ("send", "rogue_event", "🎭 傀儡术目标 C3 已被占用，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_occupied_target_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_occupied_target_falls_back())


async def _try_apply_puppet_ai_move_illegal_target_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert calls == [
        ("send", "rogue_event", "🎭 傀儡术目标 C3 当前不合法，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_illegal_target_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_illegal_target_falls_back())


async def _try_apply_puppet_ai_move_engine_error_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    game.rogue_uses["puppet"] = 1
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "? illegal move"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_apply_puppet_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        target=game.rogue_puppet_target,
        coord_to_gtp=s.coord_to_gtp,
        run_engine_command=run_engine_command,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert game.rogue_puppet_target is None
    assert game.rogue_uses["puppet"] == 1
    assert calls == [
        ("engine", "play W C3"),
        ("send", "rogue_event", "🎭 傀儡术目标 C3 执行失败，AI 改为正常应手"),
    ]


def test_try_apply_puppet_ai_move_engine_error_falls_back() -> None:
    asyncio.run(_try_apply_puppet_ai_move_engine_error_falls_back())


async def _server_ai_move_puppet_delegates_to_puppet_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = (2, 2)
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "puppet",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["target"],
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            callable(kwargs["run_engine_command"]),
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow

    assert calls == [
        ("sync", True),
        (
            "puppet",
            True,
            True,
            "W",
            "puppet",
            (2, 2),
            True,
            True,
            True,
        ),
    ]


def test_server_ai_move_puppet_delegates_to_puppet_flow() -> None:
    asyncio.run(_server_ai_move_puppet_delegates_to_puppet_flow())


async def _server_ai_move_puppet_helper_false_falls_back_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = (2, 2)
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "puppet",
            game_arg is game,
            send_fn is send,
            kwargs["target"],
        ))
        game.rogue_puppet_target = None
        return False

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("puppet", True, True, (2, 2)),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_puppet_helper_false_falls_back_to_normal_move() -> None:
    asyncio.run(_server_ai_move_puppet_helper_false_falls_back_to_normal_move())


async def _server_ai_move_puppet_without_target_skips_puppet_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "puppet"
    game.rogue_puppet_target = None
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_puppet_flow(*_args, **_kwargs):
        calls.append(("puppet",))
        return True

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_puppet_flow = s.try_apply_puppet_ai_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_apply_puppet_ai_move = fake_puppet_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_apply_puppet_ai_move = original_puppet_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_puppet_without_target_skips_puppet_flow() -> None:
    asyncio.run(_server_ai_move_puppet_without_target_skips_puppet_flow())


def test_apply_slip_ai_move_skips_without_card_or_playable_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result_no_card = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards=set(),
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )
    result_pass = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="pass",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result_no_card == AiMoveAdjustment("C3")
    assert result_pass == AiMoveAdjustment("pass")
    assert calls == []


def test_apply_slip_ai_move_skips_resign_without_random() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="RESIGN",
        roll_random=roll_random,
        choose_point=lambda points: points[0],
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result == AiMoveAdjustment("RESIGN")
    assert calls == []


def test_apply_slip_ai_move_skips_on_chance_miss() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return gameplay_config.ROGUE_SLIP_CHANCE

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=lambda points: points[0],
        gtp_to_coord=parse_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=s._adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [("random",)]


def test_apply_slip_ai_move_keeps_move_when_coord_parse_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return None

    def adjacent_points(*_args):
        calls.append(("adjacent",))
        return [(1, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def format_coord(*_args):
        calls.append(("format",))
        return "B2"

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=parse_coord,
        coord_to_gtp=format_coord,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("parse", "C3", 5),
    ]


def test_apply_slip_ai_move_slips_to_legal_neighbor() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[2][1] = 1
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(1, 2), (3, 2), (2, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    game.is_legal_move = lambda x, y, color: (x, y, color) != (3, 2, "W")

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment(
        "C4",
        needs_sync=True,
        message="手滑了触发，AI 原本想下 C3，结果滑到 C4",
    )
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
        ("choice", [(2, 1)]),
    ]


def test_apply_slip_ai_move_keeps_move_when_format_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(2, 1)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    def format_coord(x, y, size):
        calls.append(("format", x, y, size))
        return None

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=format_coord,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
        ("choice", [(2, 1)]),
        ("format", 2, 1, 5),
    ]


def test_apply_slip_ai_move_keeps_move_without_legal_neighbor() -> None:
    game = GoGame(size=5, player_color="B")
    game.board[2][1] = 1
    game.board[2][3] = 1
    calls = []

    def roll_random():
        calls.append(("random",))
        return 0.0

    def adjacent_points(x, y, size):
        calls.append(("adjacent", x, y, size))
        return [(1, 2), (3, 2)]

    def choose_point(points):
        calls.append(("choice", points))
        return points[0]

    result = apply_slip_ai_move(
        game,
        color="W",
        rogue_cards={"slip"},
        gtp_move="C3",
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        adjacent_points=adjacent_points,
    )

    assert result == AiMoveAdjustment("C3")
    assert calls == [
        ("random",),
        ("adjacent", 2, 2, 5),
    ]


async def _apply_suspicious_pass_fallback_skips_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def is_suspicious_pass(game_arg, gtp_move, color):
        calls.append(("suspicious", game_arg is game, gtp_move, color))
        return False

    async def pick_fallback_move(*_args):
        calls.append(("fallback",))
        return "D3"

    def log_event(message):
        calls.append(("log", message))

    result = await apply_suspicious_pass_fallback(
        game,
        color="W",
        gtp_move="C3",
        visits=24,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_fallback_move,
        log_event=log_event,
        log_prefix="Suspicious early PASS in rogue/normal mode",
    )

    assert result == "C3"
    assert calls == [("suspicious", True, "C3", "W")]


def test_apply_suspicious_pass_fallback_skips_normal_move() -> None:
    asyncio.run(_apply_suspicious_pass_fallback_skips_normal_move())


async def _apply_suspicious_pass_fallback_uses_fallback_and_logs() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def is_suspicious_pass(game_arg, gtp_move, color):
        calls.append(("suspicious", game_arg is game, gtp_move, color))
        return True

    async def pick_fallback_move(game_arg, color, visits):
        calls.append(("fallback", game_arg is game, color, visits))
        return "D3"

    def log_event(message):
        calls.append(("log", message))

    result = await apply_suspicious_pass_fallback(
        game,
        color="W",
        gtp_move="pass",
        visits=48,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_fallback_move,
        log_event=log_event,
        log_prefix="Suspicious early PASS in rogue/normal mode",
    )

    assert result == "D3"
    assert calls == [
        ("suspicious", True, "pass", "W"),
        ("fallback", True, "W", 48),
        ("log", "Suspicious early PASS in rogue/normal mode, replaced with D3"),
    ]


def test_apply_suspicious_pass_fallback_uses_fallback_and_logs() -> None:
    asyncio.run(_apply_suspicious_pass_fallback_uses_fallback_and_logs())


async def _apply_suspicious_pass_fallback_keeps_pass_without_fallback() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def is_suspicious_pass(game_arg, gtp_move, color):
        calls.append(("suspicious", game_arg is game, gtp_move, color))
        return True

    async def pick_fallback_move(game_arg, color, visits):
        calls.append(("fallback", game_arg is game, color, visits))
        return None

    def log_event(message):
        calls.append(("log", message))

    result = await apply_suspicious_pass_fallback(
        game,
        color="W",
        gtp_move="pass",
        visits=12,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_fallback_move,
        log_event=log_event,
        log_prefix="Suspicious early PASS in rogue/normal mode",
    )

    assert result == "pass"
    assert calls == [
        ("suspicious", True, "pass", "W"),
        ("fallback", True, "W", 12),
    ]


def test_apply_suspicious_pass_fallback_keeps_pass_without_fallback() -> None:
    asyncio.run(_apply_suspicious_pass_fallback_keeps_pass_without_fallback())


async def _server_ai_move_suspicious_pass_fallback_runs_before_resign_and_slip() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= pass"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append((
            "suspicious_fallback",
            game_arg is game,
            kwargs["color"],
            kwargs["gtp_move"],
            isinstance(kwargs["visits"], int),
            kwargs["is_suspicious_pass"] is s._is_suspicious_ai_pass,
            kwargs["pick_fallback_move"] is s._pick_nonpass_fallback_move,
            kwargs["log_event"] is s._engine_log,
            kwargs["log_prefix"],
        ))
        return "C3"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        (
            "suspicious_fallback",
            True,
            "W",
            "pass",
            True,
            True,
            True,
            True,
            "Suspicious early PASS in rogue/normal mode",
        ),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_suspicious_pass_fallback_runs_before_resign_and_slip() -> None:
    asyncio.run(_server_ai_move_suspicious_pass_fallback_runs_before_resign_and_slip())


async def _server_ai_move_style_choice_runs_suspicious_pass_fallback() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_analysis(game_arg, color):
        calls.append(("analysis", game_arg is game))
        assert color == "W"
        return {"top_moves": [{"move": "pass"}]}

    def fake_choose_style(game_arg, color, top_moves, style, *, gtp_to_coord):
        calls.append(("style", game_arg is game, color, top_moves, style, gtp_to_coord is s.gtp_to_coord))
        return "pass"

    async def fake_generate(*_args):
        raise AssertionError("genmove should not be called after style move selection")

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return "C3"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_analysis = s._analyze_current_position
    original_choose_style = s.choose_ai_style_move
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._analyze_current_position = fake_analysis
    s.choose_ai_style_move = fake_choose_style
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._analyze_current_position = original_analysis
        s.choose_ai_style_move = original_choose_style
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("analysis", True),
        ("style", True, "W", [{"move": "pass"}], "territory", True),
        ("suspicious_fallback", True, "pass"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_style_choice_runs_suspicious_pass_fallback() -> None:
    asyncio.run(_server_ai_move_style_choice_runs_suspicious_pass_fallback())


async def _server_ai_move_delegates_to_candidate_helper() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_candidate(game_arg, **kwargs):
        calls.append((
            "candidate",
            game_arg is game,
            kwargs["color"],
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["rogue_cards"],
            kwargs["forbidden"],
            kwargs["choose_avoid_move"] is s._ai_move_avoid_points,
            kwargs["analyze_position"] is s._analyze_current_position,
            kwargs["choose_style_move"] is s.choose_ai_style_move,
            kwargs["generate_move"] is s._ai_generate_move,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["log_error"] is s.print,
        ))
        return AiMoveCandidate("C3")

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return kwargs["gtp_move"]

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_candidate = s.choose_ai_move_candidate
    had_print = hasattr(s, "print")
    original_print = getattr(s, "print", None)
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_ai_move_candidate = fake_candidate
    s.print = print
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_ai_move_candidate = original_candidate
        if had_print:
            s.print = original_print
        else:
            delattr(s, "print")
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("candidate", True, "W", True, True, set(), [], True, True, True, True, True, True),
        ("suspicious_fallback", True, "C3"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_delegates_to_candidate_helper() -> None:
    asyncio.run(_server_ai_move_delegates_to_candidate_helper())


async def _server_ai_move_balanced_style_skips_style_helper() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "balanced"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return kwargs["gtp_move"]

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("suspicious_fallback", True, "C3"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_balanced_style_skips_style_helper() -> None:
    asyncio.run(_server_ai_move_balanced_style_skips_style_helper())


async def _server_ai_move_rogue_cards_skip_style_helper() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    game.rogue_card = "slip"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return kwargs["gtp_move"]

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"], "slip" in kwargs["rogue_cards"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("suspicious_fallback", True, "C3"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_rogue_cards_skip_style_helper() -> None:
    asyncio.run(_server_ai_move_rogue_cards_skip_style_helper())


async def _server_ai_move_style_without_playable_choice_falls_back_to_genmove() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_style = "territory"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_analysis(game_arg, color):
        calls.append(("analysis", game_arg is game, color))
        return {"top_moves": [{"move": "pass"}]}

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= pass"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return "C3"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_analysis = s._analyze_current_position
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._analyze_current_position = fake_analysis
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._analyze_current_position = original_analysis
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("analysis", True, "W"),
        ("generate", "W", True, True),
        ("suspicious_fallback", True, "pass"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_style_without_playable_choice_falls_back_to_genmove() -> None:
    asyncio.run(_server_ai_move_style_without_playable_choice_falls_back_to_genmove())


async def _server_ai_move_genmove_game_over_returns_before_finalizing() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        game.game_over = True
        return "= C3"

    async def fail_suspicious_fallback(*_args, **_kwargs):
        raise AssertionError("game_over after genmove should return before suspicious pass fallback")

    async def fail_resign(*_args, **_kwargs):
        raise AssertionError("game_over after genmove should return before resign handling")

    def fail_slip(*_args, **_kwargs):
        raise AssertionError("game_over after genmove should return before slip handling")

    def fail_prepare(*_args, **_kwargs):
        raise AssertionError("game_over after genmove should return before turn preparation")

    async def fail_coach(*_args, **_kwargs):
        raise AssertionError("game_over after genmove should return before coach turn")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fail_suspicious_fallback
    s.resolve_ai_resign_move = fail_resign
    s.apply_slip_ai_move = fail_slip
    s._prepare_player_turn_modifiers = fail_prepare
    s._run_coach_turn_if_needed = fail_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves == []
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
    ]


def test_server_ai_move_genmove_game_over_returns_before_finalizing() -> None:
    asyncio.run(_server_ai_move_genmove_game_over_returns_before_finalizing())


async def _server_ai_move_genmove_error_returns_before_finalizing() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "? illegal move"

    def fake_print(message):
        calls.append(("print", message))

    async def fail_suspicious_fallback(*_args, **_kwargs):
        raise AssertionError("genmove error should return before suspicious pass fallback")

    async def fail_resign(*_args, **_kwargs):
        raise AssertionError("genmove error should return before resign handling")

    def fail_slip(*_args, **_kwargs):
        raise AssertionError("genmove error should return before slip handling")

    def fail_prepare(*_args, **_kwargs):
        raise AssertionError("genmove error should return before turn preparation")

    async def fail_coach(*_args, **_kwargs):
        raise AssertionError("genmove error should return before coach turn")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    had_print = hasattr(s, "print")
    original_print = getattr(s, "print", None)
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.print = fake_print
    s.apply_suspicious_pass_fallback = fail_suspicious_fallback
    s.resolve_ai_resign_move = fail_resign
    s.apply_slip_ai_move = fail_slip
    s._prepare_player_turn_modifiers = fail_prepare
    s._run_coach_turn_if_needed = fail_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        if had_print:
            s.print = original_print
        else:
            delattr(s, "print")
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves == []
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("print", "[AI] genmove returned error: ? illegal move"),
    ]


def test_server_ai_move_genmove_error_returns_before_finalizing() -> None:
    asyncio.run(_server_ai_move_genmove_error_returns_before_finalizing())


async def _server_ai_move_forbidden_choice_runs_suspicious_pass_fallback() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "seal"
    game.rogue_seal_points = [(0, 0)]
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_avoid_points(game_arg, color, visits, time_limit, forbidden):
        calls.append((
            "avoid_points",
            game_arg is game,
            color,
            isinstance(visits, int),
            isinstance(time_limit, float),
            sorted(forbidden),
        ))
        return "pass"

    async def fake_generate(*_args):
        raise AssertionError("genmove should not be called after forbidden move selection")

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return "C3"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"], "seal" in kwargs["rogue_cards"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"], "seal" in kwargs["rogue_cards"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_avoid_points = s._ai_move_avoid_points
    original_generate = s._ai_generate_move
    original_suspicious_fallback = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_move_avoid_points = fake_avoid_points
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_move_avoid_points = original_avoid_points
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious_fallback
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert calls == [
        ("sync", True),
        ("avoid_points", True, "W", True, True, [(0, 0)]),
        ("suspicious_fallback", True, "pass"),
        ("resign", True, True, "C3", True),
        ("slip", True, "C3", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_forbidden_choice_runs_suspicious_pass_fallback() -> None:
    asyncio.run(_server_ai_move_forbidden_choice_runs_suspicious_pass_fallback())


async def _server_ai_move_suspicious_pass_without_fallback_keeps_pass() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= pass"

    def fake_is_suspicious(game_arg, gtp_move, color):
        calls.append(("is_suspicious", game_arg is game, gtp_move, color))
        return True

    async def fake_pick_fallback(game_arg, color, visits):
        calls.append(("pick_fallback", game_arg is game, color, isinstance(visits, int)))
        return None

    def fake_engine_log(message):
        calls.append(("engine_log", message))

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_is_suspicious = s._is_suspicious_ai_pass
    original_pick_fallback = s._pick_nonpass_fallback_move
    original_engine_log = s._engine_log
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s._is_suspicious_ai_pass = fake_is_suspicious
    s._pick_nonpass_fallback_move = fake_pick_fallback
    s._engine_log = fake_engine_log
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s._is_suspicious_ai_pass = original_is_suspicious
        s._pick_nonpass_fallback_move = original_pick_fallback
        s._engine_log = original_engine_log
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "pass")
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("is_suspicious", True, "pass", "W"),
        ("pick_fallback", True, "W", True),
        ("resign", True, True, "pass"),
        ("slip", True, "pass"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "pass"),
        ("coach", True, True),
    ]


def test_server_ai_move_suspicious_pass_without_fallback_keeps_pass() -> None:
    asyncio.run(_server_ai_move_suspicious_pass_without_fallback_keeps_pass())


async def _server_ai_move_slip_delegates_to_slip_adjustment() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "slip"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append((
            "slip",
            game_arg is game,
            kwargs["color"],
            "slip" in kwargs["rogue_cards"],
            kwargs["gtp_move"],
            kwargs["roll_random"] is s.random.random,
            kwargs["choose_point"] is s.random.choice,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["adjacent_points"] is s._adjacent_points,
        ))
        return AiMoveAdjustment("D3", needs_sync=True, message="slip msg")

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s._ai_retry_avoiding_ko
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s._ai_retry_avoiding_ko = lambda *_args: (_ for _ in ()).throw(AssertionError("retry should not be called"))
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s._ai_retry_avoiding_ko = original_retry
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "W", True, "C3", True, True, True, True, True),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None, None),
        ("send", "ai_move", "D3", None),
        ("send", "rogue_event", None, "slip msg"),
        ("coach", True, True),
    ]


def test_server_ai_move_slip_delegates_to_slip_adjustment() -> None:
    asyncio.run(_server_ai_move_slip_delegates_to_slip_adjustment())


async def _retry_ai_move_avoiding_ko_skips_pass_and_resign() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    pass_result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="pass",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )
    resign_result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="RESIGN",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert pass_result == AiMoveAdjustment("pass", message="slip msg")
    assert resign_result == AiMoveAdjustment("RESIGN", message="slip msg")
    assert calls == []


def test_retry_ai_move_avoiding_ko_skips_pass_and_resign() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_skips_pass_and_resign())


async def _retry_ai_move_avoiding_ko_preserves_non_ko_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: False

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="C3",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("C3", message="slip msg")
    assert calls == [("parse", "C3", 5)]


def test_retry_ai_move_avoiding_ko_preserves_non_ko_message() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_preserves_non_ko_message())


async def _retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return None

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="bad-move",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("bad-move", message="slip msg")
    assert calls == [("parse", "bad-move", 5)]


def test_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails())


async def _retry_ai_move_avoiding_ko_retries_and_clears_message() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")

    def parse_coord(gtp, size):
        calls.append(("parse", gtp, size))
        return (2, 2)

    async def retry_ko(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "D3"

    result = await retry_ai_move_avoiding_ko(
        game,
        color="W",
        gtp_move="C3",
        rogue_msg="slip msg",
        gtp_to_coord=parse_coord,
        retry_avoiding_ko=retry_ko,
    )

    assert result == AiMoveAdjustment("D3", message=None)
    assert calls == [
        ("parse", "C3", 5),
        ("retry", True, "W"),
    ]


def test_retry_ai_move_avoiding_ko_retries_and_clears_message() -> None:
    asyncio.run(_retry_ai_move_avoiding_ko_retries_and_clears_message())


async def _server_ai_move_ko_guard_runs_after_slip_and_clears_message() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "slip"
    game.is_ko = lambda x, y, color: (x, y, color) == (2, 2, "W")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= E5"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment("C3", needs_sync=True, message="slip msg")

    async def fake_retry(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "D3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s._ai_retry_avoiding_ko
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s._ai_retry_avoiding_ko = fake_retry
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s._ai_retry_avoiding_ko = original_retry
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "E5"),
        ("retry", True, "W"),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None, None),
        ("send", "ai_move", "D3", None),
        ("coach", True, True),
    ]


def test_server_ai_move_ko_guard_runs_after_slip_and_clears_message() -> None:
    asyncio.run(_server_ai_move_ko_guard_runs_after_slip_and_clears_message())


async def _server_ai_move_applies_final_move_through_board_helper() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment("D3")

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"], kwargs["retry_avoiding_ko"] is s._ai_retry_avoiding_ko))
        return AiMoveAdjustment("E3", message=kwargs["rogue_msg"])

    def fake_apply(game_arg, **kwargs):
        calls.append((
            "apply",
            game_arg is game,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
        ))
        return original_apply(game_arg, **kwargs)

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_apply = s.apply_ai_move_to_board
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.apply_ai_move_to_board = fake_apply
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.apply_ai_move_to_board = original_apply
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "E3")
    assert game.board[2][4] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "C3"),
        ("retry", True, "D3", True),
        ("apply", True, "W", "E3", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "E3"),
        ("coach", True, True),
    ]


def test_server_ai_move_applies_final_move_through_board_helper() -> None:
    asyncio.run(_server_ai_move_applies_final_move_through_board_helper())


async def _server_ai_move_delegates_sansan_trap_counter_and_syncs() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "sansan_trap"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        assert game.board[2][2] == 2
        calls.append((
            "sansan_counter",
            game_arg is game,
            send_fn is send,
            kwargs["card"],
            kwargs["coord"],
            kwargs["stones"] == s.ROGUE_SANSAN_TRAP_STONES,
            kwargs["get_sansan_points"] is s._get_sansan_points,
            kwargs["adjacent_points"] is s._adjacent8_points,
            kwargs["shuffle_points"] is s.random.shuffle,
            kwargs["spawn_bonus_points"] is s._spawn_bonus_points,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["apply_trap_bonus"] is s._challenge_apply_trap_bonus,
        ))
        return True

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "C3"),
        ("retry", True, "C3"),
        (
            "sansan_counter",
            True,
            True,
            "sansan_trap",
            (2, 2),
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_delegates_sansan_trap_counter_and_syncs() -> None:
    asyncio.run(_server_ai_move_delegates_sansan_trap_counter_and_syncs())


async def _server_ai_move_delegates_no_regret_bonus_and_syncs() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "no_regret"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        calls.append(("sansan_counter", game_arg is game, send_fn is send, kwargs["card"]))
        return False

    async def fake_no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append((
            "no_regret",
            game_arg is game,
            send_fn is send,
            kwargs["chance"] == s.ROGUE_NO_REGRET_CHANCE,
            kwargs["roll_random"] is s.random.random,
            kwargs["has_rogue_card"] is s._rogue_has,
            kwargs["pick_best_point"] is s._pick_best_point,
            kwargs["spawn_bonus_points"] is s._spawn_bonus_points,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
        ))
        return True

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_no_regret = s.try_apply_no_regret_bonus
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s.try_apply_no_regret_bonus = fake_no_regret_bonus
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s.try_apply_no_regret_bonus = original_no_regret
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "C3"),
        ("retry", True, "C3"),
        ("sansan_counter", True, True, "no_regret"),
        ("no_regret", True, True, True, True, True, True, True, True),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_delegates_no_regret_bonus_and_syncs() -> None:
    asyncio.run(_server_ai_move_delegates_no_regret_bonus_and_syncs())


async def _server_ai_move_syncs_between_sansan_and_no_regret_effects() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "sansan_trap"
    game.challenge_cards = ["no_regret"]
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        calls.append(("sansan_counter", game_arg is game, send_fn is send, kwargs["card"]))
        return True

    async def fake_no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append(("no_regret", game_arg is game, send_fn is send))
        return True

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_no_regret = s.try_apply_no_regret_bonus
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s.try_apply_no_regret_bonus = fake_no_regret_bonus
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s.try_apply_no_regret_bonus = original_no_regret
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "C3"),
        ("retry", True, "C3"),
        ("sansan_counter", True, True, "sansan_trap"),
        ("sync", True),
        ("no_regret", True, True),
        ("sync", True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_syncs_between_sansan_and_no_regret_effects() -> None:
    asyncio.run(_server_ai_move_syncs_between_sansan_and_no_regret_effects())


async def _server_ai_move_delegates_erosion_after_prepare() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "erosion"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    def fake_apply(game_arg, **kwargs):
        calls.append(("apply", game_arg is game, kwargs["gtp_move"]))
        game.moves.append((kwargs["color"], kwargs["gtp_move"]))
        game.board[2][2] = 2
        game.passed[kwargs["color"]] = False
        return AiMovePlacement(coord=(2, 2), captured=2)

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        calls.append(("sansan_counter", game_arg is game, send_fn is send, kwargs["card"]))
        return False

    async def fake_no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append(("no_regret", game_arg is game, send_fn is send))
        return False

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_erosion(game_arg, send_fn, **kwargs):
        calls.append((
            "erosion",
            game_arg is game,
            send_fn is send,
            kwargs["card"],
            kwargs["captured"],
            kwargs["shift_per_capture"] == s.ROGUE_EROSION_SHIFT,
            callable(kwargs["run_engine_command"]),
            kwargs["message"](2, 7.5),
        ))
        return True

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_apply = s.apply_ai_move_to_board
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_no_regret = s.try_apply_no_regret_bonus
    original_prepare = s._prepare_player_turn_modifiers
    original_erosion = s.apply_erosion_komi_counter
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.apply_ai_move_to_board = fake_apply
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s.try_apply_no_regret_bonus = fake_no_regret_bonus
    s._prepare_player_turn_modifiers = fake_prepare
    s.apply_erosion_komi_counter = fake_erosion
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.apply_ai_move_to_board = original_apply
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s.try_apply_no_regret_bonus = original_no_regret
        s._prepare_player_turn_modifiers = original_prepare
        s.apply_erosion_komi_counter = original_erosion
        s._run_coach_turn_if_needed = original_coach

    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("slip", True, "C3"),
        ("retry", True, "C3"),
        ("apply", True, "C3"),
        ("sansan_counter", True, True, "erosion"),
        ("no_regret", True, True),
        ("prepare", True),
        (
            "erosion",
            True,
            True,
            "erosion",
            2,
            True,
            True,
            "蚕食反制：AI 提掉了 2 子，当前贴目变为 7.5",
        ),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_delegates_erosion_after_prepare() -> None:
    asyncio.run(_server_ai_move_delegates_erosion_after_prepare())


async def _server_ai_move_delegates_double_pass_after_game_state() -> None:
    game = GoGame(size=5, player_color="B")
    game.passed["B"] = True
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= pass"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return kwargs["gtp_move"]

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message="slip msg")

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"], kwargs["rogue_msg"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        calls.append(("sansan_counter", game_arg is game, send_fn is send))
        return False

    async def fake_no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append(("no_regret", game_arg is game, send_fn is send))
        return False

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_erosion(game_arg, send_fn, **kwargs):
        calls.append(("erosion", game_arg is game, send_fn is send, kwargs["captured"]))
        return False

    async def fake_double_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "double_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            callable(kwargs["run_engine_command"]),
            kwargs["rogue_msg"],
            game.passed["B"],
            game.passed["W"],
        ))
        return True

    async def fake_coach(*_args):
        calls.append(("coach",))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_no_regret = s.try_apply_no_regret_bonus
    original_prepare = s._prepare_player_turn_modifiers
    original_erosion = s.apply_erosion_komi_counter
    original_double_pass = s.try_finalize_double_pass
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s.try_apply_no_regret_bonus = fake_no_regret_bonus
    s._prepare_player_turn_modifiers = fake_prepare
    s.apply_erosion_komi_counter = fake_erosion
    s.try_finalize_double_pass = fake_double_pass
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s.try_apply_no_regret_bonus = original_no_regret
        s._prepare_player_turn_modifiers = original_prepare
        s.apply_erosion_komi_counter = original_erosion
        s.try_finalize_double_pass = original_double_pass
        s._run_coach_turn_if_needed = original_coach

    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("suspicious_fallback", True, "pass"),
        ("resign", True, True, "pass"),
        ("slip", True, "pass"),
        ("retry", True, "pass", "slip msg"),
        ("sansan_counter", True, True),
        ("no_regret", True, True),
        ("prepare", True),
        ("erosion", True, True, 0),
        ("send", "game_state", None, None),
        ("double_pass", True, True, "W", "pass", True, "slip msg", True, True),
    ]


def test_server_ai_move_delegates_double_pass_after_game_state() -> None:
    asyncio.run(_server_ai_move_delegates_double_pass_after_game_state())


async def _server_ai_move_delegates_non_terminal_finish_response() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp"), payload.get("msg")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    async def fake_suspicious_fallback(game_arg, **kwargs):
        calls.append(("suspicious_fallback", game_arg is game, kwargs["gtp_move"]))
        return kwargs["gtp_move"]

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return AiMoveResolution(kwargs["gtp_move"])

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment("D3", message="slip msg")

    async def fake_retry(game_arg, **kwargs):
        calls.append(("retry", game_arg is game, kwargs["gtp_move"], kwargs["rogue_msg"]))
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def fake_sansan_counter(game_arg, send_fn, **kwargs):
        calls.append(("sansan_counter", game_arg is game, send_fn is send))
        return False

    async def fake_no_regret_bonus(game_arg, send_fn, **kwargs):
        calls.append(("no_regret", game_arg is game, send_fn is send))
        return False

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_erosion(game_arg, send_fn, **kwargs):
        calls.append(("erosion", game_arg is game, send_fn is send, kwargs["captured"]))
        return False

    async def fake_double_pass(game_arg, send_fn, **kwargs):
        calls.append(("double_pass", game_arg is game, send_fn is send))
        return False

    async def fake_finish_response(game_arg, send_fn, **kwargs):
        calls.append((
            "finish_response",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["rogue_msg"],
            kwargs["run_coach_turn_if_needed"] is s._run_coach_turn_if_needed,
        ))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suspicious = s.apply_suspicious_pass_fallback
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_retry = s.retry_ai_move_avoiding_ko
    original_sansan_counter = s.try_apply_sansan_trap_counter
    original_no_regret = s.try_apply_no_regret_bonus
    original_prepare = s._prepare_player_turn_modifiers
    original_erosion = s.apply_erosion_komi_counter
    original_double_pass = s.try_finalize_double_pass
    original_finish_response = s.send_ai_move_and_run_coach
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_suspicious_pass_fallback = fake_suspicious_fallback
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s.retry_ai_move_avoiding_ko = fake_retry
    s.try_apply_sansan_trap_counter = fake_sansan_counter
    s.try_apply_no_regret_bonus = fake_no_regret_bonus
    s._prepare_player_turn_modifiers = fake_prepare
    s.apply_erosion_komi_counter = fake_erosion
    s.try_finalize_double_pass = fake_double_pass
    s.send_ai_move_and_run_coach = fake_finish_response
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_suspicious_pass_fallback = original_suspicious
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s.retry_ai_move_avoiding_ko = original_retry
        s.try_apply_sansan_trap_counter = original_sansan_counter
        s.try_apply_no_regret_bonus = original_no_regret
        s._prepare_player_turn_modifiers = original_prepare
        s.apply_erosion_komi_counter = original_erosion
        s.try_finalize_double_pass = original_double_pass
        s.send_ai_move_and_run_coach = original_finish_response

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("suspicious_fallback", True, "C3"),
        ("resign", True, True, "C3"),
        ("slip", True, "C3"),
        ("retry", True, "D3", "slip msg"),
        ("sansan_counter", True, True),
        ("no_regret", True, True),
        ("prepare", True),
        ("erosion", True, True, 0),
        ("send", "game_state", None, None),
        ("double_pass", True, True),
        ("finish_response", True, True, "W", "D3", (3, 2), "slip msg", True),
    ]


def test_server_ai_move_delegates_non_terminal_finish_response() -> None:
    asyncio.run(_server_ai_move_delegates_non_terminal_finish_response())


async def _resolve_ai_resign_move_keeps_non_resign_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(_game, _color):
        calls.append(("no_resign",))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="C3",
        rogue_cards=set(),
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("C3")
    assert game.game_over is False
    assert calls == []


def test_resolve_ai_resign_move_keeps_non_resign_move() -> None:
    asyncio.run(_resolve_ai_resign_move_keeps_non_resign_move())


async def _resolve_ai_resign_move_uses_no_resign_with_rogue_card() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="RESIGN",
        rogue_cards={"suboptimal"},
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("D3")
    assert game.game_over is False
    assert calls == [("no_resign", True, "W")]


def test_resolve_ai_resign_move_uses_no_resign_with_rogue_card() -> None:
    asyncio.run(_resolve_ai_resign_move_uses_no_resign_with_rogue_card())


async def _resolve_ai_resign_move_ends_game_without_rogue_card() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def no_resign(_game, _color):
        calls.append(("no_resign",))
        return "D3"

    result = await resolve_ai_resign_move(
        game,
        send,
        color="W",
        gtp_move="resign",
        rogue_cards=set(),
        no_resign_move=no_resign,
    )

    assert result == AiMoveResolution("resign", completed=True)
    assert game.game_over is True
    assert game.winner == "B"
    assert game.moves == []
    assert calls == [
        ("send", {
            "type": "game_over",
            "winner": "B",
            "score": None,
            "reason": "ai_resign",
        }),
    ]


def test_resolve_ai_resign_move_ends_game_without_rogue_card() -> None:
    asyncio.run(_resolve_ai_resign_move_ends_game_without_rogue_card())


async def _server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append((
            "resign",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["rogue_cards"],
            kwargs["no_resign_move"] is s._ai_move_no_resign,
        ))
        return AiMoveResolution("RESIGN", completed=True)

    def fake_slip(*_args, **_kwargs):
        calls.append(("slip",))
        return AiMoveAdjustment("C3")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip

    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("resign", True, True, "W", "RESIGN", set(), True),
    ]


def test_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete() -> None:
    asyncio.run(_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete())


async def _server_ai_move_resign_flow_replacement_continues_to_slip() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_suboptimal_flow(*_args, **_kwargs):
        calls.append(("suboptimal_flow",))
        return False

    async def fake_resign(game_arg, send_fn, **kwargs):
        calls.append(("resign", game_arg is game, send_fn is send, kwargs["gtp_move"], "suboptimal" in kwargs["rogue_cards"]))
        return AiMoveResolution("D3")

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_resign = s.resolve_ai_resign_move
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s.resolve_ai_resign_move = fake_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s.resolve_ai_resign_move = original_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow",),
        ("generate", "W", True, True),
        ("resign", True, True, "RESIGN", True),
        ("slip", True, "D3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("coach", True, True),
    ]


def test_server_ai_move_resign_flow_replacement_continues_to_slip() -> None:
    asyncio.run(_server_ai_move_resign_flow_replacement_continues_to_slip())


async def _server_ai_move_real_resign_helper_rogue_replacement_continues() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    async def fake_suboptimal_flow(*_args, **_kwargs):
        calls.append(("suboptimal_flow",))
        return False

    async def fake_no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D3"

    def fake_slip(game_arg, **kwargs):
        calls.append(("slip", game_arg is game, kwargs["gtp_move"]))
        return AiMoveAdjustment(kwargs["gtp_move"])

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_no_resign = s._ai_move_no_resign
    original_slip = s.apply_slip_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s._ai_move_no_resign = fake_no_resign
    s.apply_slip_ai_move = fake_slip
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s._ai_move_no_resign = original_no_resign
        s.apply_slip_ai_move = original_slip
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "D3")
    assert game.board[2][3] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow",),
        ("generate", "W", True, True),
        ("no_resign", True, "W"),
        ("slip", True, "D3"),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "D3"),
        ("coach", True, True),
    ]


def test_server_ai_move_real_resign_helper_rogue_replacement_continues() -> None:
    asyncio.run(_server_ai_move_real_resign_helper_rogue_replacement_continues())


async def _server_ai_move_real_resign_helper_plain_resign_returns() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= RESIGN"

    def fake_slip(*_args, **_kwargs):
        calls.append(("slip",))
        return AiMoveAdjustment("C3")

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip

    assert game.game_over is True
    assert game.winner == "B"
    assert game.moves == []
    assert calls == [
        ("sync", True),
        ("generate", "W", True, True),
        ("send", {
            "type": "game_over",
            "winner": "B",
            "score": None,
            "reason": "ai_resign",
        }),
    ]


def test_server_ai_move_real_resign_helper_plain_resign_returns() -> None:
    asyncio.run(_server_ai_move_real_resign_helper_plain_resign_returns())


async def _try_finish_suboptimal_rogue_move_uses_nerf_backup_first() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx, end_idx):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="nerf",
        rogue_cards={"nerf", "time_press", "suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll",),
        ("choose", True, "W", 99, 0.5, 1, 5),
        ("finish", True, True, "W", "nerf", "D3", "弱化触发，AI 在多个备选点里误选了一手"),
    ]


def test_try_finish_suboptimal_rogue_move_uses_nerf_backup_first() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_uses_nerf_backup_first())


async def _try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(game_arg, color, visits, time_limit):
        calls.append(("choose", game_arg is game, color, visits, time_limit))
        return "E3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("choose", True, "W", 99, 0.5),
        ("finish", True, True, "W", "suboptimal", "E3", "次优之选触发，AI 采用了较弱备选点"),
    ]


def test_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature())


async def _try_finish_suboptimal_rogue_move_continues_after_miss_or_none() -> None:
    game = GoGame(size=5, player_color="B")
    rolls = iter([1.0, 0.0])
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        value = next(rolls)
        calls.append(("roll", value))
        return value

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx=2, end_idx=5):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        if (start_idx, end_idx) == (1, 4):
            return None
        return "E3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"nerf", "time_press", "suboptimal"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll", 1.0),
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 4),
        ("choose", True, "W", 99, 0.5, 2, 5),
        ("finish", True, True, "W", "suboptimal", "E3", "次优之选触发，AI 采用了较弱备选点"),
    ]


def test_try_finish_suboptimal_rogue_move_continues_after_miss_or_none() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_continues_after_miss_or_none())


async def _try_finish_suboptimal_rogue_move_continues_after_nerf_none() -> None:
    game = GoGame(size=5, player_color="B")
    rolls = iter([0.0, 0.0])
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        value = next(rolls)
        calls.append(("roll", value))
        return value

    async def choose_suboptimal_move(game_arg, color, visits, time_limit, *, start_idx, end_idx):
        calls.append(("choose", game_arg is game, color, visits, time_limit, start_idx, end_idx))
        if (start_idx, end_idx) == (1, 5):
            return None
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="time_press",
        rogue_cards={"nerf", "time_press"},
        ai_move_count=0,
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 5),
        ("roll", 0.0),
        ("choose", True, "W", 99, 0.5, 1, 4),
        ("finish", True, True, "W", "time_press", "D3", "限时压制触发，AI 仓促落在了备选点上"),
    ]


def test_try_finish_suboptimal_rogue_move_continues_after_nerf_none() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_continues_after_nerf_none())


async def _try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def choose_suboptimal_move(*_args, **_kwargs):
        calls.append(("choose",))
        return "D3"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_finish_suboptimal_rogue_move(
        game,
        send,
        color="W",
        card="suboptimal",
        rogue_cards={"nerf", "suboptimal"},
        ai_move_count=max(
            gameplay_config.ROGUE_NERF_BACKUP_AI_MOVES,
            gameplay_config.ROGUE_SUBOPTIMAL_AI_MOVES,
        ),
        visits=99,
        time_limit=0.5,
        roll_random=roll_random,
        choose_suboptimal_move=choose_suboptimal_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert calls == []


def test_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies() -> None:
    asyncio.run(_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies())


async def _server_ai_move_suboptimal_delegates_to_suboptimal_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_suboptimal_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "suboptimal_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            "suboptimal" in kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["roll_random"] is s.random.random,
            kwargs["choose_suboptimal_move"] is s._ai_move_suboptimal,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow

    assert calls == [
        ("sync", True),
        ("suboptimal_flow", True, True, "W", "suboptimal", True, 0, True, True, True, True, True),
    ]


def test_server_ai_move_suboptimal_delegates_to_suboptimal_flow() -> None:
    asyncio.run(_server_ai_move_suboptimal_delegates_to_suboptimal_flow())


async def _server_ai_move_suboptimal_flow_false_continues_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "suboptimal"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_suboptimal_flow(game_arg, send_fn, **kwargs):
        calls.append(("suboptimal_flow", game_arg is game, send_fn is send, kwargs["card"]))
        return False

    async def fake_generate(color, visits, time_limit):
        calls.append(("generate", color, isinstance(visits, int), isinstance(time_limit, float)))
        return "= C3"

    def fake_prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def fake_coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_suboptimal_flow = s.try_finish_suboptimal_rogue_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_suboptimal_rogue_move = original_suboptimal_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("suboptimal_flow", True, True, "suboptimal"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_suboptimal_flow_false_continues_to_normal_move() -> None:
    asyncio.run(_server_ai_move_suboptimal_flow_false_continues_to_normal_move())


async def _server_generate_ai_style_move_delegates_observer_style() -> None:
    game = GoGame(size=5, player_color="B")
    game.ai_observer = True
    game.ai_style = "balanced"
    game.ai_style_black = "territory"
    game.ai_style_white = "influence"
    calls = []

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_choose_or_generate(game_arg, **kwargs):
        calls.append((
            "choose_or_generate",
            game_arg is game,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["style"],
            kwargs["analyze_position"] is s._analyze_current_position,
            kwargs["choose_style_move"] is s.choose_ai_style_move,
            kwargs["generate_move"] is s._ai_generate_move,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            callable(kwargs["play_chosen_move"]),
        ))
        return "D4"

    original_sync = s._sync_board_to_katago
    original_choose_or_generate = s.choose_or_generate_ai_style_move
    s._sync_board_to_katago = fake_sync
    s.choose_or_generate_ai_style_move = fake_choose_or_generate
    try:
        gtp_move = await s._generate_ai_style_move(game, "B", 55, 2.0)
    finally:
        s._sync_board_to_katago = original_sync
        s.choose_or_generate_ai_style_move = original_choose_or_generate

    assert gtp_move == "D4"
    assert calls == [
        ("sync", True),
        ("choose_or_generate", True, "B", 55, 2.0, "territory", True, True, True, True, True),
    ]


def test_server_generate_ai_style_move_delegates_observer_style() -> None:
    asyncio.run(_server_generate_ai_style_move_delegates_observer_style())


async def _server_finish_ai_move_delegates_to_finalize_flow() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_finalize(game_arg, send_fn, **kwargs):
        calls.append((
            "finalize",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["no_resign_move"] is s._ai_move_no_resign,
            kwargs["retry_avoiding_ko"] is s._ai_retry_avoiding_ko,
            kwargs["check_capture_foul"] is s._check_capture_foul,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_coach_turn_if_needed"] is s._run_coach_turn_if_needed,
            callable(kwargs["run_engine_command"]),
        ))

    original_finalize = s.finalize_ai_move
    s.finalize_ai_move = fake_finalize
    try:
        await s._finish_ai_move(game, send, "W", "suboptimal", "D4", "message")
    finally:
        s.finalize_ai_move = original_finalize

    assert calls == [(
        "finalize",
        True,
        True,
        "W",
        "suboptimal",
        "D4",
        "message",
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    )]


def test_server_finish_ai_move_delegates_to_finalize_flow() -> None:
    asyncio.run(_server_finish_ai_move_delegates_to_finalize_flow())


if __name__ == "__main__":
    test_apply_ai_move_to_board_places_stone()
    test_apply_ai_move_to_board_records_pass()
    test_apply_ai_move_to_board_preserves_invalid_non_pass_as_move()
    test_apply_ai_move_to_board_returns_capture_count()
    test_apply_ai_move_to_board_appends_before_parse_and_place()
    test_apply_ai_move_placement_effects_syncs_between_counters()
    test_apply_ai_move_placement_effects_keeps_pending_sync_when_engine_not_ready()
    test_try_apply_sansan_trap_counter_skips_without_card_or_target()
    test_try_apply_sansan_trap_counter_skips_non_sansan_point()
    test_try_apply_sansan_trap_counter_applies_bonus_and_trap_bonus()
    test_try_apply_sansan_trap_counter_keeps_state_without_bonus_points()
    test_try_apply_no_regret_bonus_skips_without_card()
    test_try_apply_no_regret_bonus_skips_on_chance_miss()
    test_try_apply_no_regret_bonus_keeps_legacy_random_before_game_over_check()
    test_try_apply_no_regret_bonus_applies_bonus_and_sends_event()
    test_try_apply_no_regret_bonus_keeps_state_without_point_or_change()
    test_apply_erosion_komi_counter_skips_without_card_or_capture()
    test_apply_erosion_komi_counter_increases_komi_for_white_ai()
    test_apply_erosion_komi_counter_decreases_komi_for_black_ai()
    test_try_finalize_double_pass_skips_without_both_passes()
    test_try_finalize_double_pass_scores_and_sends_legacy_payloads()
    test_try_finalize_double_pass_keeps_legacy_non_b_score_winner()
    test_send_ai_move_and_run_coach_sends_coord_and_coach()
    test_send_ai_move_and_run_coach_sends_pass_and_rogue_msg_before_coach()
    test_choose_or_generate_ai_style_move_plays_style_choice()
    test_choose_or_generate_ai_style_move_balanced_falls_back_to_genmove()
    test_choose_or_generate_ai_style_move_analysis_error_falls_back()
    test_choose_or_generate_ai_style_move_choice_error_falls_back()
    test_try_choose_ai_style_move_returns_none_for_balanced()
    test_try_choose_ai_style_move_swallows_choice_errors()
    test_choose_ai_move_candidate_uses_forbidden_avoid_move()
    test_choose_ai_move_candidate_forbidden_none_does_not_genmove()
    test_choose_ai_move_candidate_uses_non_rogue_style_choice()
    test_choose_ai_move_candidate_rogue_cards_skip_style_choice()
    test_choose_ai_move_candidate_genmove_game_over_completes()
    test_choose_ai_move_candidate_genmove_error_completes_and_logs()
    test_finalize_ai_move_places_stone_and_sends_message()
    test_finalize_ai_move_resign_without_card_ends_game()
    test_finalize_ai_move_resign_with_card_uses_no_resign_move()
    test_finalize_ai_move_retries_ko_move()
    test_finalize_ai_move_delegates_non_terminal_finish_response()
    test_finalize_ai_move_double_pass_scores_without_coach_turn()
    test_finalize_ai_move_erosion_updates_komi_after_capture()
    test_finalize_forced_ai_pass_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_can_skip_history_push()
    test_try_finalize_forced_ai_stone_skips_state_on_engine_error()
    test_server_ai_move_dice_delegates_to_forced_pass()
    test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass()
    test_server_ai_move_mirror_delegates_to_forced_stone()
    test_server_ai_move_mirror_helper_false_falls_back_to_normal_move()
    test_server_ai_move_tengen_delegates_to_forced_stone_without_history()
    test_server_ai_move_tengen_helper_false_falls_back_to_followup()
    test_try_apply_puppet_ai_move_success_finishes_and_updates_uses()
    test_try_apply_puppet_ai_move_occupied_target_falls_back()
    test_try_apply_puppet_ai_move_illegal_target_falls_back()
    test_try_apply_puppet_ai_move_engine_error_falls_back()
    test_server_ai_move_puppet_delegates_to_puppet_flow()
    test_server_ai_move_puppet_helper_false_falls_back_to_normal_move()
    test_server_ai_move_puppet_without_target_skips_puppet_flow()
    test_apply_slip_ai_move_skips_without_card_or_playable_move()
    test_apply_slip_ai_move_skips_resign_without_random()
    test_apply_slip_ai_move_skips_on_chance_miss()
    test_apply_slip_ai_move_keeps_move_when_coord_parse_fails()
    test_apply_slip_ai_move_slips_to_legal_neighbor()
    test_apply_slip_ai_move_keeps_move_when_format_fails()
    test_apply_slip_ai_move_keeps_move_without_legal_neighbor()
    test_apply_suspicious_pass_fallback_skips_normal_move()
    test_apply_suspicious_pass_fallback_uses_fallback_and_logs()
    test_apply_suspicious_pass_fallback_keeps_pass_without_fallback()
    test_server_ai_move_suspicious_pass_fallback_runs_before_resign_and_slip()
    test_server_ai_move_style_choice_runs_suspicious_pass_fallback()
    test_server_ai_move_delegates_to_candidate_helper()
    test_server_ai_move_balanced_style_skips_style_helper()
    test_server_ai_move_rogue_cards_skip_style_helper()
    test_server_ai_move_style_without_playable_choice_falls_back_to_genmove()
    test_server_ai_move_genmove_game_over_returns_before_finalizing()
    test_server_ai_move_genmove_error_returns_before_finalizing()
    test_server_ai_move_forbidden_choice_runs_suspicious_pass_fallback()
    test_server_ai_move_suspicious_pass_without_fallback_keeps_pass()
    test_server_ai_move_slip_delegates_to_slip_adjustment()
    test_retry_ai_move_avoiding_ko_skips_pass_and_resign()
    test_retry_ai_move_avoiding_ko_preserves_non_ko_message()
    test_retry_ai_move_avoiding_ko_preserves_message_when_coord_parse_fails()
    test_retry_ai_move_avoiding_ko_retries_and_clears_message()
    test_server_ai_move_ko_guard_runs_after_slip_and_clears_message()
    test_server_ai_move_applies_final_move_through_board_helper()
    test_server_ai_move_delegates_sansan_trap_counter_and_syncs()
    test_server_ai_move_delegates_no_regret_bonus_and_syncs()
    test_server_ai_move_syncs_between_sansan_and_no_regret_effects()
    test_server_ai_move_delegates_erosion_after_prepare()
    test_server_ai_move_delegates_double_pass_after_game_state()
    test_server_ai_move_delegates_non_terminal_finish_response()
    test_resolve_ai_resign_move_keeps_non_resign_move()
    test_resolve_ai_resign_move_uses_no_resign_with_rogue_card()
    test_resolve_ai_resign_move_ends_game_without_rogue_card()
    test_server_ai_move_resign_delegates_to_resign_flow_and_returns_when_complete()
    test_server_ai_move_resign_flow_replacement_continues_to_slip()
    test_server_ai_move_real_resign_helper_rogue_replacement_continues()
    test_server_ai_move_real_resign_helper_plain_resign_returns()
    test_try_finish_suboptimal_rogue_move_uses_nerf_backup_first()
    test_try_finish_suboptimal_rogue_move_keeps_suboptimal_default_signature()
    test_try_finish_suboptimal_rogue_move_continues_after_miss_or_none()
    test_try_finish_suboptimal_rogue_move_continues_after_nerf_none()
    test_try_finish_suboptimal_rogue_move_skips_when_no_attempt_applies()
    test_server_ai_move_suboptimal_delegates_to_suboptimal_flow()
    test_server_ai_move_suboptimal_flow_false_continues_to_normal_move()
    test_server_generate_ai_style_move_delegates_observer_style()
    test_server_finish_ai_move_delegates_to_finalize_flow()
    print("ai_move_flow_smoke_test passed")
