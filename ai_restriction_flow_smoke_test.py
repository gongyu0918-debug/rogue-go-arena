from __future__ import annotations

import asyncio

import app.config.gameplay as gameplay_config
import server as s
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import (
    refresh_fog_restriction_points,
    try_finish_allowed_restriction_move,
    try_finish_sansan_restriction_move,
    try_finish_shadow_restriction_move,
)


class Restriction:
    def __init__(self, points=None, message="restriction message", kind="allow_only"):
        self.points = [(0, 0)] if points is None else points
        self.message = message
        self.kind = kind


async def _try_finish_allowed_restriction_move_finishes_when_move_found() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1), (2, 2)], message="allowed only")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("choose", game_arg is game, color, visits, time_limit, points))
        return "C3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_allowed_restriction_move(
        game,
        send,
        color="W",
        card="gravity",
        restriction=restriction,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("choose", True, "W", 123, 1.5, [(1, 1), (2, 2)]),
        ("finish", True, True, "W", "gravity", "C3", "allowed only"),
    ]


def test_try_finish_allowed_restriction_move_finishes_when_move_found() -> None:
    asyncio.run(_try_finish_allowed_restriction_move_finishes_when_move_found())


async def _try_finish_allowed_restriction_move_skips_when_no_restriction_or_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(*args):
        calls.append(("choose", args))
        return None

    async def finish_ai_move(*args):
        calls.append(("finish", args))

    assert await try_finish_allowed_restriction_move(
        game,
        send,
        color="W",
        card="gravity",
        restriction=None,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    ) is False

    assert calls == []

    assert await try_finish_allowed_restriction_move(
        game,
        send,
        color="W",
        card="gravity",
        restriction=Restriction(),
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    ) is False

    assert calls == [("choose", (game, "W", 123, 1.5, [(0, 0)]))]


def test_try_finish_allowed_restriction_move_skips_when_no_restriction_or_move() -> None:
    asyncio.run(_try_finish_allowed_restriction_move_skips_when_no_restriction_or_move())


async def _server_ai_move_gravity_delegates_to_restriction_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "gravity"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_gravity_allowed_points(game_arg, ai_move_count):
        calls.append(("gravity", game_arg is game, ai_move_count))
        return Restriction(message="gravity message")

    async def fake_restriction_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "restriction",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["restriction"].message,
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_gravity_allowed_points = s.gravity_allowed_points
    original_restriction_flow = s.try_finish_allowed_restriction_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.gravity_allowed_points = fake_gravity_allowed_points
    s.try_finish_allowed_restriction_move = fake_restriction_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.gravity_allowed_points = original_gravity_allowed_points
        s.try_finish_allowed_restriction_move = original_restriction_flow

    assert calls == [
        ("sync", True),
        ("gravity", True, 0),
        ("restriction", True, True, "W", "gravity", "gravity message", True, True, True, True),
    ]


def test_server_ai_move_gravity_delegates_to_restriction_flow() -> None:
    asyncio.run(_server_ai_move_gravity_delegates_to_restriction_flow())


async def _server_ai_move_lowline_restriction_false_continues_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "lowline"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_lowline_allowed_points(game_arg, ai_move_count):
        calls.append(("lowline", game_arg is game, ai_move_count))
        return Restriction(message="lowline message")

    async def fake_restriction_flow(game_arg, send_fn, **kwargs):
        calls.append(("restriction", game_arg is game, send_fn is send, kwargs["card"]))
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
    original_lowline_allowed_points = s.lowline_allowed_points
    original_restriction_flow = s.try_finish_allowed_restriction_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.lowline_allowed_points = fake_lowline_allowed_points
    s.try_finish_allowed_restriction_move = fake_restriction_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.lowline_allowed_points = original_lowline_allowed_points
        s.try_finish_allowed_restriction_move = original_restriction_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("lowline", True, 0),
        ("restriction", True, True, "lowline"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_lowline_restriction_false_continues_to_normal_move() -> None:
    asyncio.run(_server_ai_move_lowline_restriction_false_continues_to_normal_move())


async def _refresh_fog_restriction_points_skips_without_fog() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def make_rng():
        calls.append(("rng",))
        return object()

    def challenge_zone_points(*_args):
        calls.append(("zone",))
        return []

    def pick_fog_mask(*_args):
        calls.append(("mask",))
        return []

    def pick_fog_point(*_args):
        calls.append(("point",))
        return []

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"sansan"},
        ai_move_count=0,
        make_rng=make_rng,
        challenge_zone_points=challenge_zone_points,
        pick_fog_mask=pick_fog_mask,
        pick_fog_point=pick_fog_point,
    )

    assert handled is False
    assert game.rogue_seal_points == []
    assert calls == []


def test_refresh_fog_restriction_points_skips_without_fog() -> None:
    asyncio.run(_refresh_fog_restriction_points_skips_without_fog())


async def _refresh_fog_restriction_points_uses_opening_mask() -> None:
    game = GoGame(size=5, player_color="B")
    rng = object()
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    def make_rng():
        calls.append(("rng",))
        return rng

    def challenge_zone_points(game_arg, points):
        calls.append(("zone", game_arg is game, points))
        return points

    def pick_fog_mask(size, rng_arg):
        calls.append(("mask", size, rng_arg is rng))
        return [(1, 1), (2, 2)]

    def pick_fog_point(*_args):
        calls.append(("point",))
        return []

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=0,
        make_rng=make_rng,
        challenge_zone_points=challenge_zone_points,
        pick_fog_mask=pick_fog_mask,
        pick_fog_point=pick_fog_point,
    )

    assert handled is True
    assert game.rogue_seal_points == [(1, 1), (2, 2)]
    assert calls == [
        ("rng",),
        ("mask", 5, True),
        ("zone", True, [(1, 1), (2, 2)]),
        ("send", "game_state", None),
        ("send", "rogue_event", "🌫 战争迷雾刷新：3×3 禁区本回合对 AI 禁止落子"),
    ]


def test_refresh_fog_restriction_points_uses_opening_mask() -> None:
    asyncio.run(_refresh_fog_restriction_points_uses_opening_mask())


async def _refresh_fog_restriction_points_dedupes_late_points() -> None:
    game = GoGame(size=5, player_color="B")
    rng = object()
    pick_batches = [[(1, 1), (2, 2)]]
    pick_batches.extend([[(2, 2), (3, 3)] for _ in range(gameplay_config.ROGUE_FOG_POST_MASK_POINTS - 1)])
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    def make_rng():
        calls.append(("rng",))
        return rng

    def challenge_zone_points(game_arg, points):
        calls.append(("zone", game_arg is game, points))
        return points

    def pick_fog_mask(*_args):
        calls.append(("mask",))
        return []

    def pick_fog_point(game_arg, rng_arg):
        calls.append(("point", game_arg is game, rng_arg is rng))
        return pick_batches.pop(0)

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=gameplay_config.ROGUE_FOG_AI_MOVES,
        make_rng=make_rng,
        challenge_zone_points=challenge_zone_points,
        pick_fog_mask=pick_fog_mask,
        pick_fog_point=pick_fog_point,
    )

    assert handled is True
    assert game.rogue_seal_points == [(1, 1), (2, 2), (3, 3)]
    assert calls[0] == ("rng",)
    assert calls.count(("point", True, True)) == gameplay_config.ROGUE_FOG_POST_MASK_POINTS
    assert calls[-2:] == [
        ("send", "game_state", None),
        ("send", "rogue_event", f"🌫 战争迷雾残留：本回合随机封锁 {gameplay_config.ROGUE_FOG_POST_MASK_POINTS} 个 AI 禁着点"),
    ]


def test_refresh_fog_restriction_points_dedupes_late_points() -> None:
    asyncio.run(_refresh_fog_restriction_points_dedupes_late_points())


async def _refresh_fog_restriction_points_uses_late_challenge_zone_results() -> None:
    game = GoGame(size=5, player_color="B")
    rng = object()
    challenge_batches = [[(4, 4), (2, 2)]]
    challenge_batches.extend([[(2, 2), (3, 3)] for _ in range(gameplay_config.ROGUE_FOG_POST_MASK_POINTS - 1)])
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("msg")))

    def make_rng():
        calls.append(("rng",))
        return rng

    def challenge_zone_points(game_arg, points):
        zone_points = challenge_batches.pop(0)
        calls.append(("zone", game_arg is game, points, zone_points))
        return zone_points

    def pick_fog_point(game_arg, rng_arg):
        calls.append(("point", game_arg is game, rng_arg is rng))
        return [(0, 0)]

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=gameplay_config.ROGUE_FOG_AI_MOVES,
        make_rng=make_rng,
        challenge_zone_points=challenge_zone_points,
        pick_fog_mask=lambda _size, _rng: [],
        pick_fog_point=pick_fog_point,
    )

    assert handled is True
    assert game.rogue_seal_points == [(4, 4), (2, 2), (3, 3)]
    assert calls[0] == ("rng",)
    assert calls.count(("point", True, True)) == gameplay_config.ROGUE_FOG_POST_MASK_POINTS
    assert calls[-2:] == [
        ("send", "game_state", None),
        ("send", "rogue_event", f"🌫 战争迷雾残留：本回合随机封锁 {gameplay_config.ROGUE_FOG_POST_MASK_POINTS} 个 AI 禁着点"),
    ]


def test_refresh_fog_restriction_points_uses_late_challenge_zone_results() -> None:
    asyncio.run(_refresh_fog_restriction_points_uses_late_challenge_zone_results())


async def _refresh_fog_restriction_points_sends_state_without_empty_event() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"]))

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=0,
        make_rng=object,
        challenge_zone_points=lambda _game, points: points,
        pick_fog_mask=lambda _size, _rng: [],
        pick_fog_point=lambda _game, _rng: [(1, 1)],
    )

    assert handled is True
    assert game.rogue_seal_points == []
    assert calls == [("send", "game_state")]


def test_refresh_fog_restriction_points_sends_state_without_empty_event() -> None:
    asyncio.run(_refresh_fog_restriction_points_sends_state_without_empty_event())


async def _server_ai_move_fog_delegates_to_fog_refresh_and_continues() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "fog"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_fog_refresh(game_arg, send_fn, **kwargs):
        calls.append((
            "fog",
            game_arg is game,
            send_fn is send,
            "fog" in kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            callable(kwargs["make_rng"]),
            kwargs["challenge_zone_points"] is s._challenge_zone_points,
            kwargs["pick_fog_mask"] is s._pick_fog_mask,
            kwargs["pick_fog_point"] is s._pick_fog_point,
        ))
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
    original_fog_refresh = s.refresh_fog_restriction_points
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.refresh_fog_restriction_points = fake_fog_refresh
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.refresh_fog_restriction_points = original_fog_refresh
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("fog", True, True, True, 0, True, True, True, True),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_fog_delegates_to_fog_refresh_and_continues() -> None:
    asyncio.run(_server_ai_move_fog_delegates_to_fog_refresh_and_continues())


async def _try_finish_sansan_restriction_move_uses_allowed_move() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1)], message="sansan allowed")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return "C3"

    async def choose_avoid_move(*args):
        calls.append(("avoid", args))
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_sansan_restriction_move(
        game,
        send,
        color="W",
        card="sansan",
        restriction=restriction,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        choose_avoid_move=choose_avoid_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("allowed", True, "W", 123, 1.5, [(1, 1)]),
        ("finish", True, True, "W", "sansan", "C3", "sansan allowed"),
    ]


def test_try_finish_sansan_restriction_move_uses_allowed_move() -> None:
    asyncio.run(_try_finish_sansan_restriction_move_uses_allowed_move())


async def _try_finish_sansan_restriction_move_falls_back_to_avoid_move() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1)], message="sansan fallback")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return None

    async def choose_avoid_move(game_arg, color, visits, time_limit, points):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, points))
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_sansan_restriction_move(
        game,
        send,
        color="W",
        card="sansan",
        restriction=restriction,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        choose_avoid_move=choose_avoid_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("allowed", True, "W", 123, 1.5, [(1, 1)]),
        ("avoid", True, "W", 123, 1.5, [(1, 1)]),
        ("finish", True, True, "W", "sansan", "D3", "sansan fallback"),
    ]


def test_try_finish_sansan_restriction_move_falls_back_to_avoid_move() -> None:
    asyncio.run(_try_finish_sansan_restriction_move_falls_back_to_avoid_move())


async def _try_finish_sansan_restriction_move_non_allow_only_uses_avoid_move() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1)], message="sansan avoid", kind="avoid")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(*args):
        calls.append(("allowed", args))
        return "C3"

    async def choose_avoid_move(game_arg, color, visits, time_limit, points):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, points))
        return "D3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_sansan_restriction_move(
        game,
        send,
        color="W",
        card="sansan",
        restriction=restriction,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        choose_avoid_move=choose_avoid_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("avoid", True, "W", 123, 1.5, [(1, 1)]),
        ("finish", True, True, "W", "sansan", "D3", "sansan avoid"),
    ]


def test_try_finish_sansan_restriction_move_non_allow_only_uses_avoid_move() -> None:
    asyncio.run(_try_finish_sansan_restriction_move_non_allow_only_uses_avoid_move())


async def _try_finish_sansan_restriction_move_finishes_none_avoid_result() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1)], message="sansan none")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return None

    async def choose_avoid_move(game_arg, color, visits, time_limit, points):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, points))
        return None

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_sansan_restriction_move(
        game,
        send,
        color="W",
        card="sansan",
        restriction=restriction,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        choose_avoid_move=choose_avoid_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("allowed", True, "W", 123, 1.5, [(1, 1)]),
        ("avoid", True, "W", 123, 1.5, [(1, 1)]),
        ("finish", True, True, "W", "sansan", None, "sansan none"),
    ]


def test_try_finish_sansan_restriction_move_finishes_none_avoid_result() -> None:
    asyncio.run(_try_finish_sansan_restriction_move_finishes_none_avoid_result())


async def _try_finish_sansan_restriction_move_skips_when_no_restriction() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed_move(*args):
        calls.append(("allowed", args))
        return "C3"

    async def choose_avoid_move(*args):
        calls.append(("avoid", args))
        return "D3"

    async def finish_ai_move(*args):
        calls.append(("finish", args))

    handled = await try_finish_sansan_restriction_move(
        game,
        send,
        color="W",
        card="sansan",
        restriction=None,
        visits=123,
        time_limit=1.5,
        choose_allowed_move=choose_allowed_move,
        choose_avoid_move=choose_avoid_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert calls == []


def test_try_finish_sansan_restriction_move_skips_when_no_restriction() -> None:
    asyncio.run(_try_finish_sansan_restriction_move_skips_when_no_restriction())


async def _server_ai_move_sansan_delegates_to_sansan_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "sansan"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_sansan_restriction(game_arg, ai_move_count):
        calls.append(("sansan", game_arg is game, ai_move_count))
        return Restriction(message="sansan restriction")

    async def fake_sansan_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "sansan_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["restriction"].message,
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["choose_avoid_move"] is s._ai_move_avoid_points,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_sansan_restriction = s.sansan_opening_restriction
    original_sansan_flow = s.try_finish_sansan_restriction_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.sansan_opening_restriction = fake_sansan_restriction
    s.try_finish_sansan_restriction_move = fake_sansan_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.sansan_opening_restriction = original_sansan_restriction
        s.try_finish_sansan_restriction_move = original_sansan_flow

    assert calls == [
        ("sync", True),
        ("sansan", True, 0),
        ("sansan_flow", True, True, "W", "sansan", "sansan restriction", True, True, True, True, True),
    ]


def test_server_ai_move_sansan_delegates_to_sansan_flow() -> None:
    asyncio.run(_server_ai_move_sansan_delegates_to_sansan_flow())


async def _server_ai_move_sansan_flow_false_continues_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "sansan"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_sansan_restriction(game_arg, ai_move_count):
        calls.append(("sansan", game_arg is game, ai_move_count))
        return Restriction(message="sansan restriction")

    async def fake_sansan_flow(game_arg, send_fn, **kwargs):
        calls.append(("sansan_flow", game_arg is game, send_fn is send, kwargs["card"]))
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
    original_sansan_restriction = s.sansan_opening_restriction
    original_sansan_flow = s.try_finish_sansan_restriction_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.sansan_opening_restriction = fake_sansan_restriction
    s.try_finish_sansan_restriction_move = fake_sansan_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.sansan_opening_restriction = original_sansan_restriction
        s.try_finish_sansan_restriction_move = original_sansan_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("sansan", True, 0),
        ("sansan_flow", True, True, "sansan"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_sansan_flow_false_continues_to_normal_move() -> None:
    asyncio.run(_server_ai_move_sansan_flow_false_continues_to_normal_move())


async def _server_ai_move_tengen_followup_delegates_after_target_miss() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "tengen"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_choose_tengen_target(game_arg, ai_move_count):
        calls.append(("target", game_arg is game, ai_move_count))
        return None

    def fake_tengen_followup_points(game_arg, ai_move_count):
        calls.append(("followup", game_arg is game, ai_move_count))
        return Restriction(message="tengen followup")

    async def fake_restriction_flow(game_arg, send_fn, **kwargs):
        calls.append(("restriction", game_arg is game, send_fn is send, kwargs["card"], kwargs["restriction"].message))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_choose_tengen_target = s.choose_tengen_target
    original_tengen_followup_points = s.tengen_followup_points
    original_restriction_flow = s.try_finish_allowed_restriction_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.choose_tengen_target = fake_choose_tengen_target
    s.tengen_followup_points = fake_tengen_followup_points
    s.try_finish_allowed_restriction_move = fake_restriction_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.choose_tengen_target = original_choose_tengen_target
        s.tengen_followup_points = original_tengen_followup_points
        s.try_finish_allowed_restriction_move = original_restriction_flow

    assert calls == [
        ("sync", True),
        ("target", True, 0),
        ("followup", True, 0),
        ("restriction", True, True, "tengen", "tengen followup"),
    ]


def test_server_ai_move_tengen_followup_delegates_after_target_miss() -> None:
    asyncio.run(_server_ai_move_tengen_followup_delegates_after_target_miss())


async def _try_finish_shadow_restriction_move_finishes_when_triggered() -> None:
    game = GoGame(size=5, player_color="B")
    restriction = Restriction(points=[(1, 1)], message="shadow message")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("random",))
        return 0.0

    def choose_restriction(game_arg, color, ai_move_count):
        calls.append(("shadow", game_arg is game, color, ai_move_count))
        return restriction

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return "C3"

    async def finish_ai_move(game_arg, send_fn, color, card, gtp_move, rogue_msg):
        calls.append(("finish", game_arg is game, send_fn is send, color, card, gtp_move, rogue_msg))

    handled = await try_finish_shadow_restriction_move(
        game,
        send,
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        ai_move_count=2,
        visits=123,
        time_limit=1.5,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("random",),
        ("shadow", True, "W", 2),
        ("allowed", True, "W", 123, 1.5, [(1, 1)]),
        ("finish", True, True, "W", "shadow", "C3", "shadow message"),
    ]


def test_try_finish_shadow_restriction_move_finishes_when_triggered() -> None:
    asyncio.run(_try_finish_shadow_restriction_move_finishes_when_triggered())


async def _try_finish_shadow_restriction_move_skips_without_card_or_chance() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("random",))
        return 1.0

    def choose_restriction(*_args):
        calls.append(("shadow",))
        return Restriction()

    async def choose_allowed_move(*_args):
        calls.append(("allowed",))
        return "C3"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    no_card_handled = await try_finish_shadow_restriction_move(
        game,
        send,
        color="W",
        card=None,
        rogue_cards=set(),
        ai_move_count=0,
        visits=123,
        time_limit=1.5,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )
    chance_miss_handled = await try_finish_shadow_restriction_move(
        game,
        send,
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        ai_move_count=0,
        visits=123,
        time_limit=1.5,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )

    assert no_card_handled is False
    assert chance_miss_handled is False
    assert calls == [("random",)]


def test_try_finish_shadow_restriction_move_skips_without_card_or_chance() -> None:
    asyncio.run(_try_finish_shadow_restriction_move_skips_without_card_or_chance())


async def _try_finish_shadow_restriction_move_skips_on_chance_boundary() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("random",))
        return gameplay_config.ROGUE_SHADOW_CHANCE

    def choose_restriction(*_args):
        calls.append(("shadow",))
        return Restriction()

    async def choose_allowed_move(*_args):
        calls.append(("allowed",))
        return "C3"

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_finish_shadow_restriction_move(
        game,
        send,
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        ai_move_count=0,
        visits=123,
        time_limit=1.5,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert calls == [("random",)]


def test_try_finish_shadow_restriction_move_skips_on_chance_boundary() -> None:
    asyncio.run(_try_finish_shadow_restriction_move_skips_on_chance_boundary())


async def _try_finish_shadow_restriction_move_false_when_no_restriction_move() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("random",))
        return 0.0

    def choose_restriction(game_arg, color, ai_move_count):
        calls.append(("shadow", game_arg is game, color, ai_move_count))
        return Restriction(points=[(1, 1)], message="shadow message")

    async def choose_allowed_move(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return None

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_finish_shadow_restriction_move(
        game,
        send,
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        ai_move_count=2,
        visits=123,
        time_limit=1.5,
        roll_random=roll_random,
        choose_restriction=choose_restriction,
        choose_allowed_move=choose_allowed_move,
        finish_ai_move=finish_ai_move,
    )

    assert handled is False
    assert calls == [
        ("random",),
        ("shadow", True, "W", 2),
        ("allowed", True, "W", 123, 1.5, [(1, 1)]),
    ]


def test_try_finish_shadow_restriction_move_false_when_no_restriction_move() -> None:
    asyncio.run(_try_finish_shadow_restriction_move_false_when_no_restriction_move())


async def _server_ai_move_shadow_delegates_to_restriction_flow_when_triggered() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "shadow"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_shadow_followup_points(game_arg, color, ai_move_count, *, gtp_to_coord):
        calls.append(("shadow", game_arg is game, color, ai_move_count, gtp_to_coord is s.gtp_to_coord))
        return Restriction(message="shadow message")

    async def fake_shadow_flow(game_arg, send_fn, **kwargs):
        restriction = kwargs["choose_restriction"](
            game_arg,
            kwargs["color"],
            kwargs["ai_move_count"],
        )
        calls.append((
            "shadow_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            "shadow" in kwargs["rogue_cards"],
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["roll_random"] is s.random.random,
            restriction.message,
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_shadow_followup_points = s.shadow_followup_points
    original_shadow_flow = s.try_finish_shadow_restriction_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.shadow_followup_points = fake_shadow_followup_points
    s.try_finish_shadow_restriction_move = fake_shadow_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.shadow_followup_points = original_shadow_followup_points
        s.try_finish_shadow_restriction_move = original_shadow_flow

    assert calls == [
        ("sync", True),
        ("shadow", True, "W", 0, True),
        ("shadow_flow", True, True, "W", "shadow", True, True, True, True, "shadow message", True, True),
    ]


def test_server_ai_move_shadow_delegates_to_restriction_flow_when_triggered() -> None:
    asyncio.run(_server_ai_move_shadow_delegates_to_restriction_flow_when_triggered())


async def _server_ai_move_shadow_flow_false_continues_to_normal_move() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "shadow"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_shadow_flow(game_arg, send_fn, **kwargs):
        calls.append(("shadow_flow", game_arg is game, send_fn is send, kwargs["card"]))
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
    original_shadow_flow = s.try_finish_shadow_restriction_move
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_shadow_restriction_move = fake_shadow_flow
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_shadow_restriction_move = original_shadow_flow
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("shadow_flow", True, True, "shadow"),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_shadow_flow_false_continues_to_normal_move() -> None:
    asyncio.run(_server_ai_move_shadow_flow_false_continues_to_normal_move())


async def _server_ai_move_shadow_chance_miss_uses_real_helper_and_continues() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "shadow"
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    def fake_random():
        calls.append(("random",))
        return 1.0

    def fake_shadow_followup_points(*_args, **_kwargs):
        calls.append(("shadow",))
        return Restriction(message="shadow message")

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
    original_shadow_followup_points = s.shadow_followup_points
    original_generate = s._ai_generate_move
    original_prepare = s._prepare_player_turn_modifiers
    original_coach = s._run_coach_turn_if_needed
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.random.random = fake_random
    s.shadow_followup_points = fake_shadow_followup_points
    s._ai_generate_move = fake_generate
    s._prepare_player_turn_modifiers = fake_prepare
    s._run_coach_turn_if_needed = fake_coach
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.random.random = original_random
        s.shadow_followup_points = original_shadow_followup_points
        s._ai_generate_move = original_generate
        s._prepare_player_turn_modifiers = original_prepare
        s._run_coach_turn_if_needed = original_coach

    assert game.moves[-1] == ("W", "C3")
    assert game.board[2][2] == 2
    assert calls == [
        ("sync", True),
        ("random",),
        ("generate", "W", True, True),
        ("prepare", True),
        ("send", "game_state", None),
        ("send", "ai_move", "C3"),
        ("coach", True, True),
    ]


def test_server_ai_move_shadow_chance_miss_uses_real_helper_and_continues() -> None:
    asyncio.run(_server_ai_move_shadow_chance_miss_uses_real_helper_and_continues())


if __name__ == "__main__":
    test_try_finish_allowed_restriction_move_finishes_when_move_found()
    test_try_finish_allowed_restriction_move_skips_when_no_restriction_or_move()
    test_server_ai_move_gravity_delegates_to_restriction_flow()
    test_server_ai_move_lowline_restriction_false_continues_to_normal_move()
    test_refresh_fog_restriction_points_skips_without_fog()
    test_refresh_fog_restriction_points_uses_opening_mask()
    test_refresh_fog_restriction_points_dedupes_late_points()
    test_refresh_fog_restriction_points_uses_late_challenge_zone_results()
    test_refresh_fog_restriction_points_sends_state_without_empty_event()
    test_server_ai_move_fog_delegates_to_fog_refresh_and_continues()
    test_try_finish_sansan_restriction_move_uses_allowed_move()
    test_try_finish_sansan_restriction_move_falls_back_to_avoid_move()
    test_try_finish_sansan_restriction_move_non_allow_only_uses_avoid_move()
    test_try_finish_sansan_restriction_move_finishes_none_avoid_result()
    test_try_finish_sansan_restriction_move_skips_when_no_restriction()
    test_server_ai_move_sansan_delegates_to_sansan_flow()
    test_server_ai_move_sansan_flow_false_continues_to_normal_move()
    test_server_ai_move_tengen_followup_delegates_after_target_miss()
    test_try_finish_shadow_restriction_move_finishes_when_triggered()
    test_try_finish_shadow_restriction_move_skips_without_card_or_chance()
    test_try_finish_shadow_restriction_move_skips_on_chance_boundary()
    test_try_finish_shadow_restriction_move_false_when_no_restriction_move()
    test_server_ai_move_shadow_delegates_to_restriction_flow_when_triggered()
    test_server_ai_move_shadow_flow_false_continues_to_normal_move()
    test_server_ai_move_shadow_chance_miss_uses_real_helper_and_continues()
    print("ai_restriction_flow_smoke_test passed")
