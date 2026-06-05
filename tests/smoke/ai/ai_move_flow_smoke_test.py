from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import app.config.gameplay as gameplay_config
import app.gameplay.ai_move_flow as ai_move_flow
import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.turn_modifiers import prepare_player_turn_modifiers
from app.gameplay.ai_move_flow import (
    AiMoveAdjustment,
    AiMoveCandidate,
    AiMovePlacement,
    AiMovePreparation,
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
    finish_ai_turn_response,
    finish_prepared_ai_move,
    GeneratedMoveCandidateDeps,
    GeneratedMoveFinishDeps,
    GeneratedMovePreparationDeps,
    prepare_generated_ai_move,
    refresh_fog_restriction_points,
    resolve_ai_resign_move,
    retry_ai_move_avoiding_ko,
    send_ai_move_and_run_coach,
    try_apply_no_regret_bonus,
    try_apply_puppet_ai_move,
    try_apply_sansan_trap_counter,
    try_finish_forced_rogue_ai_move,
    try_finish_generated_ai_move,
    try_finish_rogue_restriction_ai_move,
    try_choose_ai_style_move,
    try_finalize_double_pass,
    try_finalize_forced_ai_stone,
    try_finish_suboptimal_rogue_move,
)
from app.runtime.generated_ai_adapters import (
    build_generated_move_candidate_deps,
    build_generated_move_finish_deps,
    build_generated_move_preparation_deps,
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


def _finish_prepared_ai_move_deps(**overrides):
    async def sync(_game):
        return None

    async def sansan_counter(_game, _send, **_kwargs):
        return False

    async def no_regret_bonus(_game, _send, **_kwargs):
        return False

    async def trap_bonus(_game, _send, _label):
        return None

    async def pick_best_point(_game, _color):
        return None

    async def check_capture_foul(_game, _send, _offender, _captured, *, ultimate):
        return None

    async def erosion(_game, _send, **_kwargs):
        return False

    async def run_command(_command):
        return "="

    async def double_pass(_game, _send, **_kwargs):
        return False

    async def ai_response(_game, _send, **_kwargs):
        return None

    async def coach(_game, _send):
        return None

    deps = {
        "gtp_to_coord": gtp_to_coord,
        "sync_board_to_engine": sync,
        "engine_is_ready": lambda: True,
        "apply_move_to_board": apply_ai_move_to_board,
        "apply_sansan_trap_counter": sansan_counter,
        "try_no_regret_bonus": no_regret_bonus,
        "trap_stones": 3,
        "get_sansan_points": lambda _size: [(2, 2)],
        "adjacent_points": lambda _x, _y, _size: [],
        "shuffle_points": lambda _points: None,
        "spawn_bonus_points": lambda _game, _points, _color: [],
        "coord_to_gtp": s.coord_to_gtp,
        "apply_trap_bonus": trap_bonus,
        "no_regret_chance": 0.25,
        "roll_random": lambda: 1.0,
        "has_rogue_card": lambda _game, _card: False,
        "pick_best_point": pick_best_point,
        "check_capture_foul": check_capture_foul,
        "prepare_player_turn_modifiers": lambda _game: None,
        "apply_erosion_counter": erosion,
        "erosion_shift": 0.5,
        "run_erosion_command": run_command,
        "erosion_message": lambda capture_count, komi: f"erosion {capture_count} {komi}",
        "finalize_double_pass": double_pass,
        "run_double_pass_command": run_command,
        "send_ai_move_response": ai_response,
        "run_coach_turn_if_needed": coach,
    }
    deps.update(overrides)
    return deps


async def _finish_prepared_ai_move_skips_completed_or_missing_gtp() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def placement(*_args, **_kwargs):
        raise AssertionError("placement should not run for completed or missing moves")

    async def finish(*_args, **_kwargs):
        raise AssertionError("finish should not run for completed or missing moves")

    for prepared_move in (
        AiMovePreparation(None, completed=True),
        AiMovePreparation("C3", completed=True),
        AiMovePreparation(None),
    ):
        handled = await finish_prepared_ai_move(
            game,
            send,
            color="W",
            card=None,
            prepared_move=prepared_move,
            apply_placement_effects=placement,
            finish_turn_response=finish,
            **_finish_prepared_ai_move_deps(),
        )
        assert handled is True

    assert calls == []


def test_finish_prepared_ai_move_skips_completed_or_missing_gtp() -> None:
    asyncio.run(_finish_prepared_ai_move_skips_completed_or_missing_gtp())


async def _finish_prepared_ai_move_places_then_finishes_response() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def erosion(_game, _send, **_kwargs):
        return False

    async def run_erosion(command):
        return f"erosion {command}"

    def erosion_message(capture_count, komi):
        return f"erosion {capture_count} {komi}"

    async def double_pass(_game, _send, **_kwargs):
        return False

    async def run_double_pass(command):
        return f"double {command}"

    async def ai_response(_game, _send, **_kwargs):
        return None

    async def coach(_game, _send):
        return None

    async def placement(game_arg, send_fn, **kwargs):
        calls.append((
            "placement",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["needs_sync"],
            kwargs["gtp_to_coord"] is deps["gtp_to_coord"],
            kwargs["sync_board_to_engine"] is deps["sync_board_to_engine"],
            kwargs["engine_is_ready"] is deps["engine_is_ready"],
            kwargs["apply_move_to_board"] is deps["apply_move_to_board"],
            kwargs["apply_sansan_trap_counter"] is deps["apply_sansan_trap_counter"],
            kwargs["try_no_regret_bonus"] is deps["try_no_regret_bonus"],
            kwargs["trap_stones"],
            kwargs["get_sansan_points"] is deps["get_sansan_points"],
            kwargs["adjacent_points"] is deps["adjacent_points"],
            kwargs["shuffle_points"] is deps["shuffle_points"],
            kwargs["spawn_bonus_points"] is deps["spawn_bonus_points"],
            kwargs["coord_to_gtp"] is deps["coord_to_gtp"],
            kwargs["apply_trap_bonus"] is deps["apply_trap_bonus"],
            kwargs["no_regret_chance"],
            kwargs["roll_random"] is deps["roll_random"],
            kwargs["has_rogue_card"] is deps["has_rogue_card"],
            kwargs["pick_best_point"] is deps["pick_best_point"],
        ))
        return AiMovePlacement(coord=(2, 2), captured=2)

    async def finish(game_arg, send_fn, **kwargs):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["captured"],
            kwargs["rogue_msg"],
            kwargs["prepare_player_turn_modifiers"] is prepare,
            kwargs["apply_erosion_counter"] is erosion,
            kwargs["erosion_shift"],
            kwargs["run_erosion_command"] is run_erosion,
            kwargs["erosion_message"] is erosion_message,
            kwargs["finalize_double_pass"] is double_pass,
            kwargs["run_double_pass_command"] is run_double_pass,
            kwargs["send_ai_move_response"] is ai_response,
            kwargs["run_coach_turn_if_needed"] is coach,
        ))
        return False

    deps = _finish_prepared_ai_move_deps(
        prepare_player_turn_modifiers=prepare,
        apply_erosion_counter=erosion,
        run_erosion_command=run_erosion,
        erosion_message=erosion_message,
        finalize_double_pass=double_pass,
        run_double_pass_command=run_double_pass,
        send_ai_move_response=ai_response,
        run_coach_turn_if_needed=coach,
    )

    handled = await finish_prepared_ai_move(
        game,
        send,
        color="W",
        card="sansan_trap",
        prepared_move=AiMovePreparation("C3", needs_sync=True, message="slip msg"),
        apply_placement_effects=placement,
        finish_turn_response=finish,
        **deps,
    )

    assert handled is False
    assert calls == [
        (
            "placement",
            True,
            True,
            "W",
            "sansan_trap",
            "C3",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            3,
            True,
            True,
            True,
            True,
            True,
            True,
            0.25,
            True,
            True,
            True,
        ),
        (
            "finish",
            True,
            True,
            "W",
            "sansan_trap",
            "C3",
            (2, 2),
            2,
            "slip msg",
            True,
            True,
            0.5,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
    ]


def test_finish_prepared_ai_move_places_then_finishes_response() -> None:
    asyncio.run(_finish_prepared_ai_move_places_then_finishes_response())


async def _finish_prepared_ai_move_returns_double_pass_handled() -> None:
    game = GoGame(size=5, player_color="B")

    async def send(_payload):
        return None

    async def placement(_game, _send, **_kwargs):
        return AiMovePlacement(coord=None, captured=0)

    async def finish(_game, _send, **_kwargs):
        return True

    handled = await finish_prepared_ai_move(
        game,
        send,
        color="W",
        card=None,
        prepared_move=AiMovePreparation("pass"),
        apply_placement_effects=placement,
        finish_turn_response=finish,
        **_finish_prepared_ai_move_deps(),
    )

    assert handled is True


def test_finish_prepared_ai_move_returns_double_pass_handled() -> None:
    asyncio.run(_finish_prepared_ai_move_returns_double_pass_handled())


class FixedFogRandom:
    def __init__(self, roll: float) -> None:
        self.roll = roll

    def random(self) -> float:
        return self.roll


async def _refresh_fog_restriction_late_can_target_best_point() -> None:
    game = GoGame(size=9, player_color="B")
    game.rogue_card = "fog"
    game.current_player = game.ai_color
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    async def pick_best(game_arg, color):
        calls.append(("best", game_arg is game, color))
        return (2, 2)

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=gameplay_config.ROGUE_FOG_AI_MOVES,
        color=game.ai_color,
        make_rng=lambda: FixedFogRandom(0.49),
        challenge_zone_points=lambda _game, points: points,
        pick_fog_mask=lambda _size, _rng: [(1, 1)],
        pick_fog_point=lambda _game, _rng: [(5, 5)],
        pick_best_point=pick_best,
    )

    assert handled is True
    assert game.rogue_seal_points == [(2, 2)]
    assert calls == [("best", True, game.ai_color)]
    assert [payload["type"] for payload in sent] == ["game_state", "rogue_event"]


def test_refresh_fog_restriction_late_can_target_best_point() -> None:
    asyncio.run(_refresh_fog_restriction_late_can_target_best_point())


async def _refresh_fog_restriction_late_falls_back_to_random_point() -> None:
    game = GoGame(size=9, player_color="B")
    game.rogue_card = "fog"
    game.current_player = game.ai_color
    calls = []

    async def send(_payload):
        return None

    async def pick_best(_game, _color):
        calls.append(("best",))
        return (2, 2)

    handled = await refresh_fog_restriction_points(
        game,
        send,
        rogue_cards={"fog"},
        ai_move_count=gameplay_config.ROGUE_FOG_AI_MOVES,
        color=game.ai_color,
        make_rng=lambda: FixedFogRandom(0.5),
        challenge_zone_points=lambda _game, points: points,
        pick_fog_mask=lambda _size, _rng: [(1, 1)],
        pick_fog_point=lambda _game, _rng: [(5, 5)],
        pick_best_point=pick_best,
    )

    assert handled is True
    assert game.rogue_seal_points == [(5, 5)]
    assert calls == []


def test_refresh_fog_restriction_late_falls_back_to_random_point() -> None:
    asyncio.run(_refresh_fog_restriction_late_falls_back_to_random_point())


def _try_finish_generated_ai_move_deps(**overrides):
    async def choose_avoid_move(_game, _color, _visits, _time_limit, _forbidden):
        return None

    async def analyze_position(_game, _color):
        return {}

    def choose_style_move(_game, _color, _top_moves, _style, *, gtp_to_coord):
        return None

    async def generate_move(_color, _visits, _time_limit):
        return "= C3"

    def log_error(_msg):
        return None

    async def suspicious_fallback(_game, **kwargs):
        return kwargs["gtp_move"]

    async def fallback_move(_game, _color, _visits):
        return None

    async def resign_move(_game, _send, **kwargs):
        return AiMoveResolution(kwargs["gtp_move"])

    async def no_resign(_game, _color):
        return "pass"

    def slip_move(_game, **kwargs):
        return AiMoveAdjustment(kwargs["gtp_move"])

    def choose_point(points):
        return points[0]

    def slip_adjacent_points(_x, _y, _size):
        return []

    async def retry_ko(_game, **kwargs):
        return AiMoveAdjustment(kwargs["gtp_move"], message=kwargs["rogue_msg"])

    async def retry_avoiding_ko(_game, _color):
        return "pass"

    async def placement_effects(_game, _send, **_kwargs):
        return AiMovePlacement(coord=None, captured=0)

    async def finish_response(_game, _send, **_kwargs):
        return False

    async def check_capture_foul(_game, _send, _offender, _captured, *, ultimate):
        return None

    finish_deps = _finish_prepared_ai_move_deps()
    async def choose_candidate(_game, **_kwargs):
        return AiMoveCandidate("C3")

    async def prepare_move(_game, _send, **kwargs):
        return AiMovePreparation(kwargs["gtp_move"])

    async def finish_move(_game, _send, **_kwargs):
        return False

    refs = {
        "choose_candidate": choose_candidate,
        "prepare_move": prepare_move,
        "finish_move": finish_move,
        "choose_avoid_move": choose_avoid_move,
        "analyze_position": analyze_position,
        "choose_style_move": choose_style_move,
        "generate_move": generate_move,
        "log_error": log_error,
        "apply_suspicious_pass_fallback_fn": suspicious_fallback,
        "is_suspicious_pass": lambda _game, _gtp, _color: False,
        "pick_nonpass_fallback_move": fallback_move,
        "undo_engine_move": lambda: None,
        "run_engine_command": lambda _command: None,
        "log_event": lambda _msg: None,
        "resolve_resign_move": resign_move,
        "no_resign_move": no_resign,
        "apply_slip_move": slip_move,
        "roll_random": lambda: 1.0,
        "choose_point": choose_point,
        "gtp_to_coord": gtp_to_coord,
        "coord_to_gtp": s.coord_to_gtp,
        "slip_adjacent_points": slip_adjacent_points,
        "retry_ko_move": retry_ko,
        "retry_avoiding_ko": retry_avoiding_ko,
        "apply_placement_effects": placement_effects,
        "finish_turn_response": finish_response,
        "sync_board_to_engine": finish_deps["sync_board_to_engine"],
        "engine_is_ready": lambda: True,
        "apply_move_to_board": apply_ai_move_to_board,
        "apply_sansan_trap_counter": finish_deps["apply_sansan_trap_counter"],
        "try_no_regret_bonus": finish_deps["try_no_regret_bonus"],
        "trap_stones": 3,
        "get_sansan_points": lambda _size: [(2, 2)],
        "trap_adjacent_points": lambda _x, _y, _size: [],
        "shuffle_points": lambda _points: None,
        "spawn_bonus_points": lambda _game, _points, _color: [],
        "apply_trap_bonus": finish_deps["apply_trap_bonus"],
        "no_regret_chance": 0.25,
        "has_rogue_card": lambda _game, _card: False,
        "pick_best_point": finish_deps["pick_best_point"],
        "check_capture_foul": check_capture_foul,
        "prepare_player_turn_modifiers": lambda _game: None,
        "apply_erosion_counter": finish_deps["apply_erosion_counter"],
        "erosion_shift": 0.5,
        "run_erosion_command": finish_deps["run_erosion_command"],
        "erosion_message": lambda capture_count, komi: f"erosion {capture_count} {komi}",
        "finalize_double_pass": finish_deps["finalize_double_pass"],
        "run_double_pass_command": finish_deps["run_double_pass_command"],
        "send_ai_move_response": finish_deps["send_ai_move_response"],
        "run_coach_turn_if_needed": finish_deps["run_coach_turn_if_needed"],
    }
    refs.update(overrides)
    return SimpleNamespace(
        candidate=GeneratedMoveCandidateDeps(
            choose_candidate=refs["choose_candidate"],
            choose_avoid_move=refs["choose_avoid_move"],
            analyze_position=refs["analyze_position"],
            choose_style_move=refs["choose_style_move"],
            generate_move=refs["generate_move"],
            gtp_to_coord=refs["gtp_to_coord"],
            log_error=refs["log_error"],
        ),
        preparation=GeneratedMovePreparationDeps(
            prepare_move=refs["prepare_move"],
            apply_suspicious_pass_fallback_fn=refs["apply_suspicious_pass_fallback_fn"],
            is_suspicious_pass=refs["is_suspicious_pass"],
            pick_nonpass_fallback_move=refs["pick_nonpass_fallback_move"],
            undo_engine_move=refs["undo_engine_move"],
            run_engine_command=refs["run_engine_command"],
            log_event=refs["log_event"],
            resolve_resign_move=refs["resolve_resign_move"],
            no_resign_move=refs["no_resign_move"],
            apply_slip_move=refs["apply_slip_move"],
            roll_random=refs["roll_random"],
            choose_point=refs["choose_point"],
            gtp_to_coord=refs["gtp_to_coord"],
            coord_to_gtp=refs["coord_to_gtp"],
            adjacent_points=refs["slip_adjacent_points"],
            retry_ko_move=refs["retry_ko_move"],
            retry_avoiding_ko=refs["retry_avoiding_ko"],
        ),
        finish=GeneratedMoveFinishDeps(
            finish_move=refs["finish_move"],
            apply_placement_effects=refs["apply_placement_effects"],
            finish_turn_response=refs["finish_turn_response"],
            gtp_to_coord=refs["gtp_to_coord"],
            sync_board_to_engine=refs["sync_board_to_engine"],
            engine_is_ready=refs["engine_is_ready"],
            apply_move_to_board=refs["apply_move_to_board"],
            apply_sansan_trap_counter=refs["apply_sansan_trap_counter"],
            try_no_regret_bonus=refs["try_no_regret_bonus"],
            trap_stones=refs["trap_stones"],
            get_sansan_points=refs["get_sansan_points"],
            adjacent_points=refs["trap_adjacent_points"],
            shuffle_points=refs["shuffle_points"],
            spawn_bonus_points=refs["spawn_bonus_points"],
            coord_to_gtp=refs["coord_to_gtp"],
            apply_trap_bonus=refs["apply_trap_bonus"],
            no_regret_chance=refs["no_regret_chance"],
            roll_random=refs["roll_random"],
            has_rogue_card=refs["has_rogue_card"],
            pick_best_point=refs["pick_best_point"],
            check_capture_foul=refs["check_capture_foul"],
            prepare_player_turn_modifiers=refs["prepare_player_turn_modifiers"],
            apply_erosion_counter=refs["apply_erosion_counter"],
            erosion_shift=refs["erosion_shift"],
            run_erosion_command=refs["run_erosion_command"],
            erosion_message=refs["erosion_message"],
            finalize_double_pass=refs["finalize_double_pass"],
            run_double_pass_command=refs["run_double_pass_command"],
            send_ai_move_response=refs["send_ai_move_response"],
            run_coach_turn_if_needed=refs["run_coach_turn_if_needed"],
        ),
        refs=refs,
    )


async def _try_finish_generated_ai_move_stops_on_completed_candidate() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def candidate(game_arg, **kwargs):
        calls.append((
            "candidate",
            game_arg is game,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["rogue_cards"],
            kwargs["forbidden"],
            kwargs["choose_avoid_move"] is deps.candidate.choose_avoid_move,
            kwargs["log_error"] is deps.candidate.log_error,
        ))
        return AiMoveCandidate(None, completed=True)

    async def prepare(*_args, **_kwargs):
        raise AssertionError("prepare should not run after completed candidate")

    async def finish(*_args, **_kwargs):
        raise AssertionError("finish should not run after completed candidate")

    deps = _try_finish_generated_ai_move_deps(
        choose_candidate=candidate,
        prepare_move=prepare,
        finish_move=finish,
    )
    handled = await try_finish_generated_ai_move(
        game,
        send,
        color="W",
        card=None,
        rogue_cards={"fog"},
        forbidden=[(1, 1)],
        visits=123,
        time_limit=4.5,
        candidate_deps=deps.candidate,
        preparation_deps=deps.preparation,
        finish_deps=deps.finish,
    )

    assert handled is True
    assert calls == [
        ("candidate", True, "W", 123, 4.5, {"fog"}, [(1, 1)], True, True),
    ]


def test_try_finish_generated_ai_move_stops_on_completed_candidate() -> None:
    asyncio.run(_try_finish_generated_ai_move_stops_on_completed_candidate())


async def _try_finish_generated_ai_move_runs_prepare_then_finish() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def candidate(game_arg, **kwargs):
        calls.append((
            "candidate",
            game_arg is game,
            kwargs["color"],
            kwargs["forbidden"],
            kwargs["generate_move"] is deps.candidate.generate_move,
            kwargs["gtp_to_coord"] is deps.candidate.gtp_to_coord,
        ))
        return AiMoveCandidate("D4")

    async def prepare(game_arg, send_fn, **kwargs):
        calls.append((
            "prepare",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["visits"],
            kwargs["rogue_cards"],
            kwargs["apply_suspicious_pass_fallback_fn"] is deps.preparation.apply_suspicious_pass_fallback_fn,
            kwargs["is_suspicious_pass"] is deps.preparation.is_suspicious_pass,
            kwargs["pick_nonpass_fallback_move"] is deps.preparation.pick_nonpass_fallback_move,
            kwargs["resolve_resign_move"] is deps.preparation.resolve_resign_move,
            kwargs["apply_slip_move"] is deps.preparation.apply_slip_move,
            kwargs["roll_random"] is deps.preparation.roll_random,
            kwargs["choose_point"] is deps.preparation.choose_point,
            kwargs["coord_to_gtp"] is deps.preparation.coord_to_gtp,
            kwargs["adjacent_points"] is deps.preparation.adjacent_points,
            kwargs["retry_ko_move"] is deps.preparation.retry_ko_move,
        ))
        return AiMovePreparation("C3", needs_sync=True, message="slip msg")

    async def finish(game_arg, send_fn, **kwargs):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["prepared_move"],
            kwargs["apply_placement_effects"] is deps.finish.apply_placement_effects,
            kwargs["finish_turn_response"] is deps.finish.finish_turn_response,
            kwargs["sync_board_to_engine"] is deps.finish.sync_board_to_engine,
            kwargs["apply_sansan_trap_counter"] is deps.finish.apply_sansan_trap_counter,
            kwargs["try_no_regret_bonus"] is deps.finish.try_no_regret_bonus,
            kwargs["trap_stones"],
            kwargs["adjacent_points"] is deps.finish.adjacent_points,
            kwargs["roll_random"] is deps.finish.roll_random,
            kwargs["prepare_player_turn_modifiers"] is deps.finish.prepare_player_turn_modifiers,
            kwargs["finalize_double_pass"] is deps.finish.finalize_double_pass,
            kwargs["run_coach_turn_if_needed"] is deps.finish.run_coach_turn_if_needed,
        ))
        return False

    deps = _try_finish_generated_ai_move_deps(
        choose_candidate=candidate,
        prepare_move=prepare,
        finish_move=finish,
    )
    handled = await try_finish_generated_ai_move(
        game,
        send,
        color="W",
        card="sansan_trap",
        rogue_cards={"slip"},
        forbidden=[],
        visits=77,
        time_limit=3.0,
        candidate_deps=deps.candidate,
        preparation_deps=deps.preparation,
        finish_deps=deps.finish,
    )

    assert handled is False
    assert calls == [
        ("candidate", True, "W", [], True, True),
        (
            "prepare",
            True,
            True,
            "W",
            "D4",
            77,
            {"slip"},
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
        ),
        (
            "finish",
            True,
            True,
            "W",
            "sansan_trap",
            AiMovePreparation("C3", needs_sync=True, message="slip msg"),
            True,
            True,
            True,
            True,
            True,
            3,
            True,
            True,
            True,
            True,
            True,
        ),
    ]


def test_try_finish_generated_ai_move_runs_prepare_then_finish() -> None:
    asyncio.run(_try_finish_generated_ai_move_runs_prepare_then_finish())


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


async def _finish_ai_turn_response_double_pass_skips_ai_move_response() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    def prepare(game_arg):
        calls.append(("prepare", game_arg is game, game.current_player))

    async def erosion(game_arg, send_fn, **kwargs):
        calls.append((
            "erosion",
            game_arg is game,
            send_fn is send,
            kwargs["card"],
            kwargs["captured"],
            kwargs["shift_per_capture"],
            kwargs["run_engine_command"] is run_erosion_command,
            kwargs["message"](2, 7.5),
        ))
        return True

    async def run_erosion_command(command):
        calls.append(("erosion_engine", command))
        return "="

    async def run_double_pass_command(command):
        calls.append(("double_engine", command))
        return "="

    async def check_capture_foul(game_arg, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", game_arg is game, send_fn is send, offender, captured, ultimate))

    async def double_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "double_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["run_engine_command"] is run_double_pass_command,
            kwargs["rogue_msg"],
        ))
        return True

    async def ai_response(*_args, **_kwargs):
        raise AssertionError("ai response should not run after double pass")

    async def coach(*_args, **_kwargs):
        raise AssertionError("coach should not run after double pass")

    handled = await finish_ai_turn_response(
        game,
        send,
        color="W",
        card="erosion",
        gtp_move="pass",
        coord=None,
        captured=2,
        rogue_msg="slip msg",
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare,
        apply_erosion_counter=erosion,
        erosion_shift=0.5,
        run_erosion_command=run_erosion_command,
        erosion_message=lambda capture_count, komi: f"erosion {capture_count} {komi}",
        finalize_double_pass=double_pass,
        run_double_pass_command=run_double_pass_command,
        send_ai_move_response=ai_response,
        run_coach_turn_if_needed=coach,
    )

    assert handled is True
    assert calls == [
        ("prepare", True, "B"),
        ("capture_foul", True, True, "W", 2, False),
        ("erosion", True, True, "erosion", 2, 0.5, True, "erosion 2 7.5"),
        ("send", "game_state", None),
        ("double_pass", True, True, "W", "pass", True, "slip msg"),
    ]


def test_finish_ai_turn_response_double_pass_skips_ai_move_response() -> None:
    asyncio.run(_finish_ai_turn_response_double_pass_skips_ai_move_response())


async def _finish_ai_turn_response_nonterminal_sends_ai_move_response() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"], payload.get("gtp")))

    def prepare(game_arg):
        calls.append(("prepare", game_arg is game, game.current_player))

    async def erosion(game_arg, send_fn, **kwargs):
        calls.append(("erosion", game_arg is game, send_fn is send, kwargs["captured"]))
        return False

    async def run_erosion_command(command):
        calls.append(("erosion_engine", command))
        return "="

    async def run_double_pass_command(command):
        calls.append(("double_engine", command))
        return "="

    async def check_capture_foul(game_arg, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", game_arg is game, send_fn is send, offender, captured, ultimate))

    async def double_pass(game_arg, send_fn, **kwargs):
        calls.append(("double_pass", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return False

    async def ai_response(game_arg, send_fn, **kwargs):
        calls.append((
            "ai_response",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["rogue_msg"],
            kwargs["run_coach_turn_if_needed"] is coach,
        ))

    async def coach(_game, _send):
        calls.append(("coach",))

    handled = await finish_ai_turn_response(
        game,
        send,
        color="W",
        card=None,
        gtp_move="C3",
        coord=(2, 2),
        captured=0,
        rogue_msg=None,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare,
        apply_erosion_counter=erosion,
        erosion_shift=0.5,
        run_erosion_command=run_erosion_command,
        erosion_message=lambda capture_count, komi: f"erosion {capture_count} {komi}",
        finalize_double_pass=double_pass,
        run_double_pass_command=run_double_pass_command,
        send_ai_move_response=ai_response,
        run_coach_turn_if_needed=coach,
    )

    assert handled is False
    assert calls == [
        ("prepare", True, "B"),
        ("capture_foul", True, True, "W", 0, False),
        ("erosion", True, True, 0),
        ("send", "game_state", None),
        ("double_pass", True, True, "C3"),
        ("ai_response", True, True, "W", "C3", (2, 2), None, True),
    ]


def test_finish_ai_turn_response_nonterminal_sends_ai_move_response() -> None:
    asyncio.run(_finish_ai_turn_response_nonterminal_sends_ai_move_response())


async def _finish_ai_turn_response_methodical_rearms_next_player_turn() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "methodical"
    game.ai_color = "W"
    game.current_player = "W"
    game.rogue_methodical_turns["B"] = 1
    game.rogue_methodical_remaining = 0
    sent = []

    async def send(payload):
        sent.append(payload)

    async def check_capture_foul(_game, _send, _offender, _captured, *, ultimate):
        return None

    async def erosion(_game, _send, **_kwargs):
        return False

    async def run_command(_command):
        return "="

    async def double_pass(_game, _send, **_kwargs):
        return False

    async def ai_response(_game, _send, **_kwargs):
        sent.append({"type": "ai_response_probe"})

    async def coach(_game, _send):
        return None

    handled = await finish_ai_turn_response(
        game,
        send,
        color="W",
        card="methodical",
        gtp_move="C3",
        coord=(2, 2),
        captured=0,
        rogue_msg=None,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn_modifiers,
        apply_erosion_counter=erosion,
        erosion_shift=0.5,
        run_erosion_command=run_command,
        erosion_message=lambda capture_count, komi: f"erosion {capture_count} {komi}",
        finalize_double_pass=double_pass,
        run_double_pass_command=run_command,
        send_ai_move_response=ai_response,
        run_coach_turn_if_needed=coach,
    )

    assert handled is False
    assert game.current_player == game.player_color
    assert game.rogue_methodical_turns["B"] == 2
    assert game.rogue_methodical_remaining == gameplay_config.ROGUE_METHODICAL_BASE_PLAYS
    assert [payload["type"] for payload in sent] == ["game_state", "ai_response_probe"]
    assert sent[0]["current_player"] == game.player_color
    assert sent[0]["rogue_methodical_remaining"] == gameplay_config.ROGUE_METHODICAL_BASE_PLAYS


def test_finish_ai_turn_response_methodical_rearms_next_player_turn() -> None:
    asyncio.run(_finish_ai_turn_response_methodical_rearms_next_player_turn())


async def _finish_ai_turn_response_capture_foul_gifts_before_game_state() -> None:
    game = GoGame(size=9, komi=7.5, player_color="B")
    game.rogue_card = "capture_foul"
    game.ai_color = "W"
    sent = []
    syncs = []

    async def send(payload):
        sent.append(payload)

    async def pick_best_point(game_arg, color):
        assert game_arg is game
        assert color == "B"
        return (4, 4)

    async def sync_board(game_arg):
        syncs.append(game_arg)

    def prepare(game_arg):
        assert game_arg is game

    async def erosion(_game, _send_fn, **_kwargs):
        return False

    async def run_command(_command):
        return "="

    async def double_pass(_game, _send_fn, **_kwargs):
        return False

    async def ai_response(game_arg, send_fn, **kwargs):
        assert game_arg is game
        await send_fn(
            {
                "type": "ai_move",
                "gtp": kwargs["gtp_move"],
                "color": kwargs["color"],
            }
        )

    async def coach(_game, _send_fn):
        raise AssertionError("coach should not run in this path")

    old_pick = s._pick_best_point
    old_sync = s._sync_board_to_katago
    try:
        s._pick_best_point = pick_best_point
        s._sync_board_to_katago = sync_board
        handled = await finish_ai_turn_response(
            game,
            send,
            color="W",
            card="capture_foul",
            gtp_move="D4",
            coord=(3, 5),
            captured=gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
            rogue_msg=None,
            check_capture_foul=s._check_capture_foul,
            prepare_player_turn_modifiers=prepare,
            apply_erosion_counter=erosion,
            erosion_shift=0,
            run_erosion_command=run_command,
            erosion_message=lambda capture_count, komi: f"{capture_count}:{komi}",
            finalize_double_pass=double_pass,
            run_double_pass_command=run_command,
            send_ai_move_response=ai_response,
            run_coach_turn_if_needed=coach,
        )
    finally:
        s._pick_best_point = old_pick
        s._sync_board_to_katago = old_sync

    assert handled is False
    assert syncs == [game]
    assert game.board[4][4] == 1
    assert game.rogue_capture_foul_progress["W"] == 0

    event_index = next(i for i, payload in enumerate(sent) if payload["type"] == "rogue_event")
    state_index = next(i for i, payload in enumerate(sent) if payload["type"] == "game_state")
    assert event_index < state_index
    assert "提子犯规" in sent[event_index]["msg"]
    assert sent[state_index]["board"][4][4] == 1
    assert sent[-1]["type"] == "ai_move"


def test_finish_ai_turn_response_capture_foul_gifts_before_game_state() -> None:
    asyncio.run(_finish_ai_turn_response_capture_foul_gifts_before_game_state())


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

    assert result == AiMoveCandidate(None, completed=True, error_message="AI 引擎落子失败：? illegal move")
    assert calls == [
        ("generate", "W", 77, 4.0),
        ("log", "[AI] genmove returned error: ? illegal move"),
    ]


def test_choose_ai_move_candidate_genmove_error_completes_and_logs() -> None:
    asyncio.run(_choose_ai_move_candidate_genmove_error_completes_and_logs())


async def _prepare_generated_ai_move_runs_adjustment_chain() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def suspicious(game_arg, **kwargs):
        calls.append((
            "suspicious",
            game_arg is game,
            kwargs["gtp_move"],
            kwargs["visits"],
            kwargs["is_suspicious_pass"] is is_suspicious,
            kwargs["pick_fallback_move"] is fallback,
            kwargs["log_event"] is log_event,
            kwargs["log_prefix"],
        ))
        return "D3"

    def is_suspicious(_game, _move, _color):
        return False

    async def fallback(_game, _color, _visits, _forbidden=None):
        return None

    def log_event(message):
        calls.append(("log", message))

    async def resign(game_arg, send_fn, **kwargs):
        calls.append((
            "resign",
            game_arg is game,
            send_fn is send,
            kwargs["gtp_move"],
            kwargs["rogue_cards"],
            kwargs["no_resign_move"] is no_resign,
        ))
        return AiMoveResolution("E4")

    async def no_resign(_game, _color):
        return "A1"

    def slip(game_arg, **kwargs):
        calls.append((
            "slip",
            game_arg is game,
            kwargs["gtp_move"],
            kwargs["roll_random"] is roll_random,
            kwargs["choose_point"] is choose_point,
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["coord_to_gtp"] is coord_to_gtp,
            kwargs["adjacent_points"] is adjacent_points,
        ))
        return AiMoveAdjustment("C2", needs_sync=True, message="slip msg")

    def roll_random():
        return 0.0

    def choose_point(points):
        return points[0]

    def gtp_to_coord(_gtp, _size):
        return (1, 1)

    def coord_to_gtp(_x, _y, _size):
        return "B2"

    def adjacent_points(_x, _y, _size):
        return []

    async def retry_ko(game_arg, **kwargs):
        calls.append((
            "retry",
            game_arg is game,
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["retry_avoiding_ko"] is retry_avoiding_ko,
        ))
        return AiMoveAdjustment("C2", message="slip msg")

    async def retry_avoiding_ko(_game, _color):
        return "A1"

    result = await prepare_generated_ai_move(
        game,
        send,
        color="W",
        gtp_move="pass",
        visits=123,
        rogue_cards={"slip"},
        apply_suspicious_pass_fallback_fn=suspicious,
        is_suspicious_pass=is_suspicious,
        pick_nonpass_fallback_move=fallback,
        log_event=log_event,
        resolve_resign_move=resign,
        no_resign_move=no_resign,
        apply_slip_move=slip,
        roll_random=roll_random,
        choose_point=choose_point,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        adjacent_points=adjacent_points,
        retry_ko_move=retry_ko,
        retry_avoiding_ko=retry_avoiding_ko,
    )

    assert result == AiMovePreparation("C2", needs_sync=True, message="slip msg")
    assert calls == [
        ("suspicious", True, "pass", 123, True, True, True, "Suspicious early PASS in rogue/normal mode"),
        ("resign", True, True, "D3", {"slip"}, True),
        ("slip", True, "E4", True, True, True, True, True),
        ("retry", True, "C2", "slip msg", True, True),
    ]


def test_prepare_generated_ai_move_runs_adjustment_chain() -> None:
    asyncio.run(_prepare_generated_ai_move_runs_adjustment_chain())


async def _prepare_generated_ai_move_stops_on_completed_resign() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def suspicious(_game, **kwargs):
        calls.append(("suspicious", kwargs["gtp_move"]))
        return "RESIGN"

    async def resign(_game, _send_fn, **kwargs):
        calls.append(("resign", kwargs["gtp_move"]))
        return AiMoveResolution("RESIGN", completed=True)

    result = await prepare_generated_ai_move(
        game,
        send,
        color="W",
        gtp_move="pass",
        visits=123,
        rogue_cards=set(),
        apply_suspicious_pass_fallback_fn=suspicious,
        is_suspicious_pass=lambda *_args: False,
        pick_nonpass_fallback_move=lambda *_args: None,
        log_event=lambda _msg: None,
        resolve_resign_move=resign,
        no_resign_move=lambda *_args: None,
        apply_slip_move=lambda *_args, **_kwargs: calls.append("slip"),
        roll_random=lambda: 0.0,
        choose_point=lambda points: points[0],
        gtp_to_coord=lambda _gtp, _size: None,
        coord_to_gtp=lambda _x, _y, _size: None,
        adjacent_points=lambda _x, _y, _size: [],
        retry_ko_move=lambda *_args, **_kwargs: calls.append("retry"),
        retry_avoiding_ko=lambda *_args: None,
    )

    assert result == AiMovePreparation("RESIGN", completed=True)
    assert calls == [("suspicious", "pass"), ("resign", "RESIGN")]


def test_prepare_generated_ai_move_stops_on_completed_resign() -> None:
    asyncio.run(_prepare_generated_ai_move_stops_on_completed_resign())


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


async def _finalize_ai_move_engine_error_sends_error_without_mutating_board() -> None:
    game = GoGame(size=5, player_color="B")
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    async def check_capture_foul(*_args, **_kwargs):
        calls.append("capture")

    def prepare_player_turn(_game):
        calls.append("prepare")

    await finalize_ai_move(
        game,
        send,
        color="W",
        card=None,
        gtp_move="? timeout",
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_unused_no_resign,
        retry_avoiding_ko=_unused_retry_ko,
        check_capture_foul=check_capture_foul,
        prepare_player_turn_modifiers=prepare_player_turn,
        run_engine_command=lambda _command: asyncio.sleep(0, result="="),
        run_coach_turn_if_needed=lambda *_args: asyncio.sleep(0),
    )

    assert game.moves == []
    assert game.board == [[0 for _ in range(5)] for _ in range(5)]
    assert calls == []
    assert sent == [{"type": "error", "message": "AI 引擎落子失败：? timeout"}]


def test_finalize_ai_move_engine_error_sends_error_without_mutating_board() -> None:
    asyncio.run(_finalize_ai_move_engine_error_sends_error_without_mutating_board())


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


def _setup_four_stone_capture(game: GoGame) -> tuple[int, int]:
    black_group = [(3, 3), (4, 3), (3, 4), (4, 4)]
    target = (5, 4)
    white_shell = [(2, 3), (3, 2), (4, 2), (5, 3), (2, 4), (3, 5), (4, 5)]
    for x, y in black_group:
        game.board[y][x] = 1
    for x, y in white_shell:
        game.board[y][x] = 2
    return target


async def _try_finish_restriction_forced_stone_runs_capture_foul_before_state() -> None:
    game = GoGame(size=9, komi=7.5, player_color="B")
    game.ai_color = "W"
    game.rogue_card = "capture_foul"
    target = _setup_four_stone_capture(game)
    sent = []
    syncs = []

    async def send(payload):
        sent.append(payload)

    async def run_engine_command(command):
        assert command == "play W F5"
        return "="

    async def pick_best_point(game_arg, color):
        assert game_arg is game
        assert color == "B"
        return (0, 0)

    async def sync_board(game_arg):
        syncs.append(game_arg)

    def prepare_player_turn(game_arg):
        assert game_arg is game

    async def unused(*_args, **_kwargs):
        raise AssertionError("restriction fallback should not run after forced target")

    def choose_tengen_target(game_arg, ai_move_count):
        assert game_arg is game
        assert ai_move_count == 0
        return SimpleNamespace(coord=target, message="天元 forced")

    old_pick = s._pick_best_point
    old_sync = s._sync_board_to_katago
    try:
        s._pick_best_point = pick_best_point
        s._sync_board_to_katago = sync_board
        handled = await try_finish_rogue_restriction_ai_move(
            game,
            send,
            color="W",
            card="capture_foul",
            rogue_cards={"tengen", "capture_foul"},
            ai_move_count=0,
            visits=100,
            time_limit=1.0,
            choose_tengen_target=choose_tengen_target,
            tengen_followup_points=lambda *_args: None,
            gravity_allowed_points=lambda *_args: None,
            lowline_allowed_points=lambda *_args: None,
            sansan_opening_restriction=lambda *_args: None,
            coord_to_gtp=s.coord_to_gtp,
            finalize_forced_stone=try_finalize_forced_ai_stone,
            prepare_player_turn_modifiers=prepare_player_turn,
            run_engine_command=run_engine_command,
            choose_allowed_move=unused,
            choose_avoid_move=unused,
            finish_ai_move=unused,
            finish_allowed_restriction_move=unused,
            finish_sansan_restriction_move=unused,
            check_capture_foul=s._check_capture_foul,
        )
    finally:
        s._pick_best_point = old_pick
        s._sync_board_to_katago = old_sync

    assert handled is True
    assert syncs == [game]
    assert game.captures["W"] == gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD
    assert game.rogue_capture_foul_progress["W"] == 0
    assert game.board[0][0] == 1

    event_index = next(i for i, payload in enumerate(sent) if payload["type"] == "rogue_event")
    state_index = next(i for i, payload in enumerate(sent) if payload["type"] == "game_state")
    assert event_index < state_index
    assert "提子犯规" in sent[event_index]["msg"]
    assert sent[state_index]["board"][0][0] == 1
    assert sent[state_index]["captures"]["W"] == gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD


def test_try_finish_restriction_forced_stone_runs_capture_foul_before_state() -> None:
    asyncio.run(_try_finish_restriction_forced_stone_runs_capture_foul_before_state())


async def _try_finish_forced_rogue_ai_move_dice_preempts_later_cards() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def forced_pass(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_pass",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["message"],
            kwargs["prepare_player_turn_modifiers"] is prepare,
            kwargs["run_engine_command"] is run_engine,
        ))

    async def forced_stone(*_args, **_kwargs):
        raise AssertionError("dice should preempt mirror")

    async def puppet(*_args, **_kwargs):
        raise AssertionError("dice should preempt puppet")

    def prepare(_game):
        calls.append(("prepare",))

    async def run_engine(_command):
        calls.append(("engine",))
        return "="

    handled = await try_finish_forced_rogue_ai_move(
        game,
        send,
        color="W",
        card="dice",
        rogue_cards={"dice", "mirror", "puppet"},
        roll_random=roll_random,
        dice_pass_chance=1.0,
        mirror_chance=1.0,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        mirror_coord=lambda x, y, size: (size - 1 - x, size - 1 - y),
        prepare_player_turn_modifiers=prepare,
        run_engine_command=run_engine,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=lambda *_args: None,
    )

    assert handled is True
    assert calls == [
        ("roll",),
        ("forced_pass", True, True, "W", "掷骰触发，AI 这手选择虚手", True, True),
    ]


def test_try_finish_forced_rogue_ai_move_dice_preempts_later_cards() -> None:
    asyncio.run(_try_finish_forced_rogue_ai_move_dice_preempts_later_cards())


async def _try_finish_forced_rogue_ai_move_mirror_forces_stone() -> None:
    game = GoGame(size=5, player_color="B")
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def forced_pass(*_args, **_kwargs):
        raise AssertionError("mirror should not force pass")

    async def forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs["prepare_player_turn_modifiers"] is prepare,
            kwargs["run_engine_command"] is run_engine,
        ))
        return True

    async def puppet(*_args, **_kwargs):
        raise AssertionError("mirror success should preempt puppet")

    def prepare(_game):
        calls.append(("prepare",))

    async def run_engine(_command):
        calls.append(("engine",))
        return "="

    handled = await try_finish_forced_rogue_ai_move(
        game,
        send,
        color="W",
        card="mirror",
        rogue_cards={"mirror", "puppet"},
        roll_random=roll_random,
        dice_pass_chance=1.0,
        mirror_chance=1.0,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=lambda _x, _y, _size: "D3",
        mirror_coord=lambda _x, _y, _size: (3, 2),
        prepare_player_turn_modifiers=prepare,
        run_engine_command=run_engine,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=lambda *_args: None,
    )

    assert handled is True
    assert calls == [
        ("roll",),
        ("forced_stone", True, True, "W", "D3", (3, 2), "镜像触发，AI 在对称点 D3 落子", True, True),
    ]


def test_try_finish_forced_rogue_ai_move_mirror_forces_stone() -> None:
    asyncio.run(_try_finish_forced_rogue_ai_move_mirror_forces_stone())


async def _try_finish_forced_rogue_ai_move_mirror_false_falls_through() -> None:
    game = GoGame(size=5, player_color="B")
    game.moves.append(("B", "B2"))
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def roll_random():
        calls.append(("roll",))
        return 0.0

    async def forced_pass(*_args, **_kwargs):
        raise AssertionError("mirror false should not force pass")

    async def forced_stone(game_arg, send_fn, **kwargs):
        calls.append(("forced_stone", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return False

    async def puppet(*_args, **_kwargs):
        raise AssertionError("puppet should not run without a target")

    handled = await try_finish_forced_rogue_ai_move(
        game,
        send,
        color="W",
        card="mirror",
        rogue_cards={"mirror", "puppet"},
        roll_random=roll_random,
        dice_pass_chance=1.0,
        mirror_chance=1.0,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=lambda _x, _y, _size: "D3",
        mirror_coord=lambda _x, _y, _size: (3, 2),
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=lambda *_args: None,
    )

    assert handled is False
    assert calls == [
        ("roll",),
        ("forced_stone", True, True, "D3"),
    ]


def test_try_finish_forced_rogue_ai_move_mirror_false_falls_through() -> None:
    asyncio.run(_try_finish_forced_rogue_ai_move_mirror_false_falls_through())


async def _try_finish_forced_rogue_ai_move_exchange_clears_skip() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_skip_ai = True
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def forced_pass(game_arg, send_fn, **kwargs):
        calls.append(("forced_pass", game_arg is game, send_fn is send, kwargs["message"]))

    async def forced_stone(*_args, **_kwargs):
        raise AssertionError("exchange should not force stone")

    async def puppet(*_args, **_kwargs):
        raise AssertionError("exchange should preempt puppet")

    handled = await try_finish_forced_rogue_ai_move(
        game,
        send,
        color="W",
        card="exchange",
        rogue_cards={"exchange", "puppet"},
        roll_random=lambda: 1.0,
        dice_pass_chance=0.0,
        mirror_chance=0.0,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        mirror_coord=lambda x, y, size: (size - 1 - x, size - 1 - y),
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=lambda *_args: None,
    )

    assert handled is True
    assert game.rogue_skip_ai is False
    assert calls == [
        ("forced_pass", True, True, "乾坤挪移生效，AI 本回合虚手并把回合交还给你"),
    ]


def test_try_finish_forced_rogue_ai_move_exchange_clears_skip() -> None:
    asyncio.run(_try_finish_forced_rogue_ai_move_exchange_clears_skip())


async def _try_finish_forced_rogue_ai_move_puppet_delegates_target() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_puppet_target = (2, 2)
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def forced_pass(*_args, **_kwargs):
        raise AssertionError("puppet should not force pass")

    async def forced_stone(*_args, **_kwargs):
        raise AssertionError("puppet should not force mirror stone")

    async def puppet(game_arg, send_fn, **kwargs):
        calls.append((
            "puppet",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["target"],
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["run_engine_command"] is run_engine,
            kwargs["finish_ai_move"] is finish_ai_move,
        ))
        return True

    async def run_engine(_command):
        calls.append(("engine",))
        return "="

    async def finish_ai_move(*_args):
        calls.append(("finish",))

    handled = await try_finish_forced_rogue_ai_move(
        game,
        send,
        color="W",
        card="puppet",
        rogue_cards={"puppet"},
        roll_random=lambda: 1.0,
        dice_pass_chance=0.0,
        mirror_chance=0.0,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=s.coord_to_gtp,
        mirror_coord=lambda x, y, size: (size - 1 - x, size - 1 - y),
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=run_engine,
        finalize_forced_pass=forced_pass,
        finalize_forced_stone=forced_stone,
        apply_puppet_move=puppet,
        finish_ai_move=finish_ai_move,
    )

    assert handled is True
    assert calls == [
        ("puppet", True, True, "W", "puppet", (2, 2), True, True, True),
    ]


def test_try_finish_forced_rogue_ai_move_puppet_delegates_target() -> None:
    asyncio.run(_try_finish_forced_rogue_ai_move_puppet_delegates_target())


async def _server_ai_move_delegates_to_forced_rogue_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "dice"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_forced_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["roll_random"] is s.random.random,
            kwargs["dice_pass_chance"] == s.ROGUE_DICE_PASS_CHANCE,
            kwargs["mirror_chance"] == s.ROGUE_MIRROR_CHANCE,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["mirror_coord"] is s._mirror_coord,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_engine_command"] is s._send_engine_command,
            kwargs["finalize_forced_pass"] is s.finalize_forced_ai_pass,
            kwargs["finalize_forced_stone"] is s.try_finalize_forced_ai_stone,
            kwargs["apply_puppet_move"] is s.try_apply_puppet_ai_move,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_forced_flow = s.try_finish_forced_rogue_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_forced_rogue_ai_move = fake_forced_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_forced_rogue_ai_move = original_forced_flow

    assert calls == [
        ("sync", True),
        (
            "forced_flow",
            True,
            True,
            "W",
            "dice",
            {"dice"},
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
            True,
        ),
    ]


def test_server_ai_move_delegates_to_forced_rogue_flow() -> None:
    asyncio.run(_server_ai_move_delegates_to_forced_rogue_flow())


async def _server_forced_rogue_turn_helper_binds_runtime_globals() -> None:
    game = GoGame(size=5, player_color="B")
    turn = s.AiTurnSnapshot(
        color="W",
        card="puppet",
        rogue_cards={"puppet", "mirror"},
        move_count=3,
        ai_move_count=1,
    )
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def run_engine(command):
        calls.append(("engine", command))
        return command

    async def fake_forced_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["roll_random"] is s.random.random,
            kwargs["dice_pass_chance"] == s.ROGUE_DICE_PASS_CHANCE,
            kwargs["mirror_chance"] == s.ROGUE_MIRROR_CHANCE,
            kwargs["gtp_to_coord"] is s.gtp_to_coord,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["mirror_coord"] is s._mirror_coord,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_engine_command"] is run_engine,
            kwargs["finalize_forced_pass"] is s.finalize_forced_ai_pass,
            kwargs["finalize_forced_stone"] is s.try_finalize_forced_ai_stone,
            kwargs["apply_puppet_move"] is s.try_apply_puppet_ai_move,
            kwargs["finish_ai_move"] is s._finish_ai_move,
        ))
        return True

    async def fake_forced_pass(*_args, **_kwargs):
        calls.append(("forced_pass",))

    async def fake_forced_stone(*_args, **_kwargs):
        calls.append(("forced_stone",))
        return False

    async def fake_puppet(*_args, **_kwargs):
        calls.append(("puppet",))
        return False

    def fake_prepare(_game):
        calls.append(("prepare",))

    async def fake_finish(*_args, **_kwargs):
        calls.append(("finish",))

    original_forced_flow = s.try_finish_forced_rogue_ai_move
    original_forced_pass = s.finalize_forced_ai_pass
    original_forced_stone = s.try_finalize_forced_ai_stone
    original_puppet = s.try_apply_puppet_ai_move
    original_prepare = s._prepare_player_turn_modifiers
    original_finish = s._finish_ai_move
    s.try_finish_forced_rogue_ai_move = fake_forced_flow
    s.finalize_forced_ai_pass = fake_forced_pass
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s.try_apply_puppet_ai_move = fake_puppet
    s._prepare_player_turn_modifiers = fake_prepare
    s._finish_ai_move = fake_finish
    try:
        handled = await s._try_finish_forced_rogue_ai_turn(game, send, turn, run_engine)
    finally:
        s.try_finish_forced_rogue_ai_move = original_forced_flow
        s.finalize_forced_ai_pass = original_forced_pass
        s.try_finalize_forced_ai_stone = original_forced_stone
        s.try_apply_puppet_ai_move = original_puppet
        s._prepare_player_turn_modifiers = original_prepare
        s._finish_ai_move = original_finish

    assert handled is True
    assert calls == [(
        "forced_flow",
        True,
        True,
        "W",
        "puppet",
        {"puppet", "mirror"},
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
        True,
    )]


def test_server_forced_rogue_turn_helper_binds_runtime_globals() -> None:
    asyncio.run(_server_forced_rogue_turn_helper_binds_runtime_globals())


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


async def _server_ai_move_tengen_delegates_to_forced_stone_with_history() -> None:
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
            kwargs.get("push_history", True),
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
            True,
            True,
            True,
        ),
    ]


def test_server_ai_move_tengen_delegates_to_forced_stone_with_history() -> None:
    asyncio.run(_server_ai_move_tengen_delegates_to_forced_stone_with_history())


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
            kwargs.get("push_history", True),
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
        ("forced_stone", True, True, "C3", True),
        ("followup", True, 0),
        ("allow_only", True, "W", [(0, 0)]),
        ("finish", True, True, "W", "tengen", "C3", "天元后续限制"),
    ]


def test_server_ai_move_tengen_helper_false_falls_back_to_followup() -> None:
    asyncio.run(_server_ai_move_tengen_helper_false_falls_back_to_followup())


async def _try_finish_rogue_restriction_ai_move_tengen_target_preempts_followup() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def choose_tengen(game_arg, ai_count):
        calls.append(("tengen_target", game_arg is game, ai_count))
        return SimpleNamespace(coord=(2, 2), message="天元强制")

    def tengen_followup(*_args):
        raise AssertionError("tengen target success should skip followup")

    def gravity(*_args):
        raise AssertionError("tengen target success should skip gravity")

    async def forced_stone(game_arg, send_fn, **kwargs):
        calls.append((
            "forced_stone",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["gtp_move"],
            kwargs["coord"],
            kwargs["message"],
            kwargs.get("push_history", True),
        ))
        return True

    async def choose_allowed(*_args):
        raise AssertionError("tengen target success should skip allowed move")

    async def choose_avoid(*_args):
        raise AssertionError("tengen target success should skip avoid move")

    async def finish(*_args):
        raise AssertionError("tengen target success should skip finish_ai_move")

    handled = await try_finish_rogue_restriction_ai_move(
        game,
        send,
        color="W",
        card="tengen",
        rogue_cards={"tengen", "gravity"},
        ai_move_count=0,
        visits=33,
        time_limit=1.0,
        choose_tengen_target=choose_tengen,
        tengen_followup_points=tengen_followup,
        gravity_allowed_points=gravity,
        lowline_allowed_points=lambda *_args: None,
        sansan_opening_restriction=lambda *_args: None,
        coord_to_gtp=lambda _x, _y, _size: "C3",
        finalize_forced_stone=forced_stone,
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=choose_avoid,
        finish_ai_move=finish,
        finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
    )

    assert handled is True
    assert calls == [
        ("tengen_target", True, 0),
        ("forced_stone", True, True, "W", "C3", (2, 2), "天元强制", True),
    ]


def test_try_finish_rogue_restriction_ai_move_tengen_target_preempts_followup() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_tengen_target_preempts_followup())


async def _try_finish_rogue_restriction_ai_move_tengen_false_falls_back() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def forced_stone(game_arg, send_fn, **kwargs):
        calls.append(("forced_stone", game_arg is game, send_fn is send, kwargs["gtp_move"]))
        return False

    async def choose_allowed(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return "D4"

    async def finish(*args):
        calls.append(("finish", args[0] is game, args[1] is send, args[2:]))

    handled = await try_finish_rogue_restriction_ai_move(
        game,
        send,
        color="W",
        card="tengen",
        rogue_cards={"tengen"},
        ai_move_count=1,
        visits=44,
        time_limit=2.0,
        choose_tengen_target=lambda _game, _count: SimpleNamespace(coord=(2, 2), message="天元强制"),
        tengen_followup_points=lambda _game, _count: SimpleNamespace(points=[(1, 1)], message="天元后续"),
        gravity_allowed_points=lambda *_args: None,
        lowline_allowed_points=lambda *_args: None,
        sansan_opening_restriction=lambda *_args: None,
        coord_to_gtp=lambda _x, _y, _size: "C3",
        finalize_forced_stone=forced_stone,
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=lambda *_args: None,
        finish_ai_move=finish,
        finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
    )

    assert handled is True
    assert calls == [
        ("forced_stone", True, True, "C3"),
        ("allowed", True, "W", 44, 2.0, [(1, 1)]),
        ("finish", True, True, ("W", "tengen", "D4", "天元后续")),
    ]


def test_try_finish_rogue_restriction_ai_move_tengen_false_falls_back() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_tengen_false_falls_back())


async def _try_finish_rogue_restriction_ai_move_tengen_unplayable_target_falls_back() -> None:
    async def run_case(label, setup_game):
        game = GoGame(size=5, player_color="B")
        setup_game(game)
        calls = []

        async def send(payload):
            calls.append(("send", payload))

        async def forced_stone(*_args, **_kwargs):
            raise AssertionError(f"{label} tengen target should skip forced finalize")

        async def choose_allowed(game_arg, color, visits, time_limit, points):
            calls.append((label, "allowed", game_arg is game, color, visits, time_limit, points))
            return "D4"

        async def finish(*args):
            calls.append((label, "finish", args[0] is game, args[1] is send, args[2:]))

        handled = await try_finish_rogue_restriction_ai_move(
            game,
            send,
            color="W",
            card="tengen",
            rogue_cards={"tengen"},
            ai_move_count=1,
            visits=44,
            time_limit=2.0,
            choose_tengen_target=lambda _game, _count: SimpleNamespace(coord=(2, 2), message="天元强制"),
            tengen_followup_points=lambda _game, _count: SimpleNamespace(points=[(1, 1)], message="天元后续"),
            gravity_allowed_points=lambda *_args: None,
            lowline_allowed_points=lambda *_args: None,
            sansan_opening_restriction=lambda *_args: None,
            coord_to_gtp=lambda _x, _y, _size: "C3",
            finalize_forced_stone=forced_stone,
            prepare_player_turn_modifiers=lambda _game: None,
            run_engine_command=lambda _command: None,
            choose_allowed_move=choose_allowed,
            choose_avoid_move=lambda *_args: None,
            finish_ai_move=finish,
            finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
            finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
        )

        assert handled is True
        assert calls == [
            (label, "allowed", True, "W", 44, 2.0, [(1, 1)]),
            (label, "finish", True, True, ("W", "tengen", "D4", "天元后续")),
        ]

    await run_case("occupied", lambda game: game.board[2].__setitem__(2, 1))
    await run_case("ko", lambda game: setattr(game, "ko_point", (2, 2, 2)))


def test_try_finish_rogue_restriction_ai_move_tengen_unplayable_target_falls_back() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_tengen_unplayable_target_falls_back())


async def _try_finish_rogue_restriction_ai_move_gravity_preempts_later() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        return "C4"

    async def finish(*args):
        calls.append(("finish", args[0] is game, args[1] is send, args[2:]))

    handled = await try_finish_rogue_restriction_ai_move(
        game,
        send,
        color="W",
        card="gravity",
        rogue_cards={"gravity", "lowline", "sansan"},
        ai_move_count=2,
        visits=55,
        time_limit=3.0,
        choose_tengen_target=lambda *_args: None,
        tengen_followup_points=lambda *_args: None,
        gravity_allowed_points=lambda _game, _count: SimpleNamespace(points=[(2, 1)], message="重力限制"),
        lowline_allowed_points=lambda *_args: (_ for _ in ()).throw(AssertionError("gravity should skip lowline")),
        sansan_opening_restriction=lambda *_args: (_ for _ in ()).throw(AssertionError("gravity should skip sansan")),
        coord_to_gtp=lambda _x, _y, _size: "C4",
        finalize_forced_stone=lambda *_args, **_kwargs: None,
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=lambda *_args: None,
        finish_ai_move=finish,
        finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
    )

    assert handled is True
    assert calls == [
        ("allowed", True, "W", 55, 3.0, [(2, 1)]),
        ("finish", True, True, ("W", "gravity", "C4", "重力限制")),
    ]


def test_try_finish_rogue_restriction_ai_move_gravity_preempts_later() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_gravity_preempts_later())


async def _try_finish_rogue_restriction_ai_move_lowline_after_gravity_miss() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed(game_arg, color, visits, time_limit, points):
        calls.append(("allowed", game_arg is game, color, visits, time_limit, points))
        if points == [(4, 4)]:
            return None
        return "C2"

    async def finish(*args):
        calls.append(("finish", args[0] is game, args[1] is send, args[2:]))

    handled = await try_finish_rogue_restriction_ai_move(
        game,
        send,
        color="W",
        card="lowline",
        rogue_cards={"gravity", "lowline", "sansan"},
        ai_move_count=3,
        visits=77,
        time_limit=5.0,
        choose_tengen_target=lambda *_args: None,
        tengen_followup_points=lambda *_args: None,
        gravity_allowed_points=lambda _game, _count: SimpleNamespace(points=[(4, 4)], message="重力限制"),
        lowline_allowed_points=lambda _game, _count: SimpleNamespace(points=[(1, 1)], message="低线限制"),
        sansan_opening_restriction=lambda *_args: (_ for _ in ()).throw(AssertionError("lowline should skip sansan")),
        coord_to_gtp=lambda _x, _y, _size: "C2",
        finalize_forced_stone=lambda *_args, **_kwargs: None,
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=lambda *_args: None,
        finish_ai_move=finish,
        finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
    )

    assert handled is True
    assert calls == [
        ("allowed", True, "W", 77, 5.0, [(4, 4)]),
        ("allowed", True, "W", 77, 5.0, [(1, 1)]),
        ("finish", True, True, ("W", "lowline", "C2", "低线限制")),
    ]


def test_try_finish_rogue_restriction_ai_move_lowline_after_gravity_miss() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_lowline_after_gravity_miss())


async def _try_finish_rogue_restriction_ai_move_sansan_uses_avoid() -> None:
    game = GoGame(size=5, player_color="B")
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def choose_allowed(*_args):
        raise AssertionError("avoid-style sansan should not use allowed move")

    async def choose_avoid(game_arg, color, visits, time_limit, points):
        calls.append(("avoid", game_arg is game, color, visits, time_limit, points))
        return "D4"

    async def finish(*args):
        calls.append(("finish", args[0] is game, args[1] is send, args[2:]))

    handled = await try_finish_rogue_restriction_ai_move(
        game,
        send,
        color="W",
        card="sansan",
        rogue_cards={"sansan"},
        ai_move_count=0,
        visits=66,
        time_limit=4.0,
        choose_tengen_target=lambda *_args: None,
        tengen_followup_points=lambda *_args: None,
        gravity_allowed_points=lambda *_args: None,
        lowline_allowed_points=lambda *_args: None,
        sansan_opening_restriction=lambda _game, _count: SimpleNamespace(kind="avoid", points=[(0, 0)], message="三三限制"),
        coord_to_gtp=lambda _x, _y, _size: "D4",
        finalize_forced_stone=lambda *_args, **_kwargs: None,
        prepare_player_turn_modifiers=lambda _game: None,
        run_engine_command=lambda _command: None,
        choose_allowed_move=choose_allowed,
        choose_avoid_move=choose_avoid,
        finish_ai_move=finish,
        finish_allowed_restriction_move=ai_move_flow.try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=ai_move_flow.try_finish_sansan_restriction_move,
    )

    assert handled is True
    assert calls == [
        ("avoid", True, "W", 66, 4.0, [(0, 0)]),
        ("finish", True, True, ("W", "sansan", "D4", "三三限制")),
    ]


def test_try_finish_rogue_restriction_ai_move_sansan_uses_avoid() -> None:
    asyncio.run(_try_finish_rogue_restriction_ai_move_sansan_uses_avoid())


async def _server_ai_move_delegates_to_rogue_restriction_flow() -> None:
    game = GoGame(size=5, player_color="B")
    game.rogue_card = "gravity"
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def fake_sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def fake_restriction_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "restriction_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            isinstance(kwargs["visits"], int),
            isinstance(kwargs["time_limit"], float),
            kwargs["choose_tengen_target"] is s.choose_tengen_target,
            kwargs["tengen_followup_points"] is s.tengen_followup_points,
            kwargs["gravity_allowed_points"] is s.gravity_allowed_points,
            kwargs["lowline_allowed_points"] is s.lowline_allowed_points,
            kwargs["sansan_opening_restriction"] is s.sansan_opening_restriction,
            kwargs["coord_to_gtp"] is s.coord_to_gtp,
            kwargs["finalize_forced_stone"] is s.try_finalize_forced_ai_stone,
            kwargs["prepare_player_turn_modifiers"] is s._prepare_player_turn_modifiers,
            kwargs["run_engine_command"] is s._send_engine_command,
            kwargs["choose_allowed_move"] is s._ai_move_avoid_points_allow_only,
            kwargs["choose_avoid_move"] is s._ai_move_avoid_points,
            kwargs["finish_ai_move"] is s._finish_ai_move,
            kwargs["finish_allowed_restriction_move"] is s.try_finish_allowed_restriction_move,
            kwargs["finish_sansan_restriction_move"] is s.try_finish_sansan_restriction_move,
        ))
        return True

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_restriction_flow = s.try_finish_rogue_restriction_ai_move
    s.engine.ready = True
    s._sync_board_to_katago = fake_sync
    s.try_finish_rogue_restriction_ai_move = fake_restriction_flow
    try:
        await s._ai_move(game, send)
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.try_finish_rogue_restriction_ai_move = original_restriction_flow

    assert calls == [
        ("sync", True),
        (
            "restriction_flow",
            True,
            True,
            "W",
            "gravity",
            {"gravity"},
            0,
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
            True,
            True,
            True,
            True,
            True,
        ),
    ]


def test_server_ai_move_delegates_to_rogue_restriction_flow() -> None:
    asyncio.run(_server_ai_move_delegates_to_rogue_restriction_flow())


async def _server_rogue_restriction_turn_helper_binds_runtime_globals() -> None:
    game = GoGame(size=5, player_color="B")
    turn = s.AiTurnSnapshot(
        color="W",
        card="gravity",
        rogue_cards={"gravity", "lowline"},
        move_count=4,
        ai_move_count=2,
    )
    ai_plan = s.AiMovePlan(
        mode="rogue",
        effective_level="5k",
        visits=88,
        time_limit=2.5,
        move_count=4,
        ai_move_count=2,
    )
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def run_engine(command):
        calls.append(("engine", command))
        return command

    def fake_tengen(_game, _count):
        calls.append(("tengen",))
        return None

    def fake_tengen_followup(_game, _count):
        calls.append(("tengen_followup",))
        return None

    def fake_gravity(_game, _count):
        calls.append(("gravity",))
        return None

    def fake_lowline(_game, _count):
        calls.append(("lowline",))
        return None

    def fake_sansan(_game, _count):
        calls.append(("sansan",))
        return None

    def fake_coord_to_gtp(_x, _y, _size):
        return "C3"

    async def fake_forced_stone(*_args, **_kwargs):
        calls.append(("forced_stone",))
        return False

    def fake_prepare(_game):
        calls.append(("prepare",))

    async def fake_allowed(*_args, **_kwargs):
        calls.append(("allowed",))
        return None

    async def fake_avoid(*_args, **_kwargs):
        calls.append(("avoid",))
        return None

    async def fake_finish(*_args, **_kwargs):
        calls.append(("finish",))

    async def fake_allowed_finish(*_args, **_kwargs):
        calls.append(("allowed_finish",))
        return False

    async def fake_sansan_finish(*_args, **_kwargs):
        calls.append(("sansan_finish",))
        return False

    async def fake_restriction_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "restriction_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["choose_tengen_target"] is fake_tengen,
            kwargs["tengen_followup_points"] is fake_tengen_followup,
            kwargs["gravity_allowed_points"] is fake_gravity,
            kwargs["lowline_allowed_points"] is fake_lowline,
            kwargs["sansan_opening_restriction"] is fake_sansan,
            kwargs["coord_to_gtp"] is fake_coord_to_gtp,
            kwargs["finalize_forced_stone"] is fake_forced_stone,
            kwargs["prepare_player_turn_modifiers"] is fake_prepare,
            kwargs["run_engine_command"] is run_engine,
            kwargs["choose_allowed_move"] is fake_allowed,
            kwargs["choose_avoid_move"] is fake_avoid,
            kwargs["finish_ai_move"] is fake_finish,
            kwargs["finish_allowed_restriction_move"] is fake_allowed_finish,
            kwargs["finish_sansan_restriction_move"] is fake_sansan_finish,
        ))
        return True

    originals = {
        "restriction_flow": s.try_finish_rogue_restriction_ai_move,
        "tengen": s.choose_tengen_target,
        "tengen_followup": s.tengen_followup_points,
        "gravity": s.gravity_allowed_points,
        "lowline": s.lowline_allowed_points,
        "sansan": s.sansan_opening_restriction,
        "coord_to_gtp": s.coord_to_gtp,
        "forced_stone": s.try_finalize_forced_ai_stone,
        "prepare": s._prepare_player_turn_modifiers,
        "allowed": s._ai_move_avoid_points_allow_only,
        "avoid": s._ai_move_avoid_points,
        "finish": s._finish_ai_move,
        "allowed_finish": s.try_finish_allowed_restriction_move,
        "sansan_finish": s.try_finish_sansan_restriction_move,
    }
    s.try_finish_rogue_restriction_ai_move = fake_restriction_flow
    s.choose_tengen_target = fake_tengen
    s.tengen_followup_points = fake_tengen_followup
    s.gravity_allowed_points = fake_gravity
    s.lowline_allowed_points = fake_lowline
    s.sansan_opening_restriction = fake_sansan
    s.coord_to_gtp = fake_coord_to_gtp
    s.try_finalize_forced_ai_stone = fake_forced_stone
    s._prepare_player_turn_modifiers = fake_prepare
    s._ai_move_avoid_points_allow_only = fake_allowed
    s._ai_move_avoid_points = fake_avoid
    s._finish_ai_move = fake_finish
    s.try_finish_allowed_restriction_move = fake_allowed_finish
    s.try_finish_sansan_restriction_move = fake_sansan_finish
    try:
        handled = await s._try_finish_rogue_restriction_ai_turn(
            game,
            send,
            turn,
            ai_plan,
            run_engine,
        )
    finally:
        s.try_finish_rogue_restriction_ai_move = originals["restriction_flow"]
        s.choose_tengen_target = originals["tengen"]
        s.tengen_followup_points = originals["tengen_followup"]
        s.gravity_allowed_points = originals["gravity"]
        s.lowline_allowed_points = originals["lowline"]
        s.sansan_opening_restriction = originals["sansan"]
        s.coord_to_gtp = originals["coord_to_gtp"]
        s.try_finalize_forced_ai_stone = originals["forced_stone"]
        s._prepare_player_turn_modifiers = originals["prepare"]
        s._ai_move_avoid_points_allow_only = originals["allowed"]
        s._ai_move_avoid_points = originals["avoid"]
        s._finish_ai_move = originals["finish"]
        s.try_finish_allowed_restriction_move = originals["allowed_finish"]
        s.try_finish_sansan_restriction_move = originals["sansan_finish"]

    assert handled is True
    assert calls == [(
        "restriction_flow",
        True,
        True,
        "W",
        "gravity",
        {"gravity", "lowline"},
        2,
        88,
        2.5,
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
        True,
        True,
        True,
    )]


def test_server_rogue_restriction_turn_helper_binds_runtime_globals() -> None:
    asyncio.run(_server_rogue_restriction_turn_helper_binds_runtime_globals())


async def _server_shadow_and_suboptimal_turn_helpers_bind_runtime_globals() -> None:
    game = GoGame(size=5, player_color="B")
    shadow_turn = s.AiTurnSnapshot(
        color="W",
        card="shadow",
        rogue_cards={"shadow"},
        move_count=6,
        ai_move_count=3,
    )
    shadow_plan = s.AiMovePlan(
        mode="rogue",
        effective_level="4k",
        visits=77,
        time_limit=1.25,
        move_count=6,
        ai_move_count=3,
    )
    suboptimal_turn = s.AiTurnSnapshot(
        color="W",
        card="suboptimal",
        rogue_cards={"nerf", "suboptimal"},
        move_count=7,
        ai_move_count=4,
    )
    suboptimal_plan = s.AiMovePlan(
        mode="rogue",
        effective_level="3k",
        visits=66,
        time_limit=1.75,
        move_count=7,
        ai_move_count=4,
    )
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def fake_random():
        calls.append(("random",))
        return 0.25

    def fake_gtp_to_coord(gtp, size):
        calls.append(("gtp_to_coord", gtp, size))
        return (1, 2)

    def fake_shadow_followup(game_arg, color, ai_move_count, *, gtp_to_coord):
        calls.append((
            "shadow_followup",
            game_arg is game,
            color,
            ai_move_count,
            gtp_to_coord is fake_gtp_to_coord,
        ))
        return [gtp_to_coord("C3", game_arg.size)]

    async def fake_allowed(*_args, **_kwargs):
        calls.append(("allowed",))
        return None

    async def fake_suboptimal_move(*_args, **_kwargs):
        calls.append(("suboptimal_move",))
        return None

    async def fake_finish(*_args, **_kwargs):
        calls.append(("finish",))

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
            kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["roll_random"] is fake_random,
            restriction,
            kwargs["choose_allowed_move"] is fake_allowed,
            kwargs["finish_ai_move"] is fake_finish,
        ))
        return True

    async def fake_suboptimal_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "suboptimal_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["ai_move_count"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["roll_random"] is fake_random,
            kwargs["choose_suboptimal_move"] is fake_suboptimal_move,
            kwargs["finish_ai_move"] is fake_finish,
        ))
        return True

    originals = {
        "shadow_flow": s.try_finish_shadow_restriction_move,
        "suboptimal_flow": s.try_finish_suboptimal_rogue_move,
        "random": s.random.random,
        "shadow_followup": s.shadow_followup_points,
        "gtp_to_coord": s.gtp_to_coord,
        "allowed": s._ai_move_avoid_points_allow_only,
        "suboptimal_move": s._ai_move_suboptimal,
        "finish": s._finish_ai_move,
    }
    s.try_finish_shadow_restriction_move = fake_shadow_flow
    s.try_finish_suboptimal_rogue_move = fake_suboptimal_flow
    s.random.random = fake_random
    s.shadow_followup_points = fake_shadow_followup
    s.gtp_to_coord = fake_gtp_to_coord
    s._ai_move_avoid_points_allow_only = fake_allowed
    s._ai_move_suboptimal = fake_suboptimal_move
    s._finish_ai_move = fake_finish
    try:
        shadow_handled = await s._try_finish_shadow_rogue_ai_turn(
            game,
            send,
            shadow_turn,
            shadow_plan,
        )
        suboptimal_handled = await s._try_finish_suboptimal_rogue_ai_turn(
            game,
            send,
            suboptimal_turn,
            suboptimal_plan,
        )
    finally:
        s.try_finish_shadow_restriction_move = originals["shadow_flow"]
        s.try_finish_suboptimal_rogue_move = originals["suboptimal_flow"]
        s.random.random = originals["random"]
        s.shadow_followup_points = originals["shadow_followup"]
        s.gtp_to_coord = originals["gtp_to_coord"]
        s._ai_move_avoid_points_allow_only = originals["allowed"]
        s._ai_move_suboptimal = originals["suboptimal_move"]
        s._finish_ai_move = originals["finish"]

    assert shadow_handled is True
    assert suboptimal_handled is True
    assert calls == [
        ("shadow_followup", True, "W", 3, True),
        ("gtp_to_coord", "C3", 5),
        (
            "shadow_flow",
            True,
            True,
            "W",
            "shadow",
            {"shadow"},
            3,
            77,
            1.25,
            True,
            [(1, 2)],
            True,
            True,
        ),
        (
            "suboptimal_flow",
            True,
            True,
            "W",
            "suboptimal",
            {"nerf", "suboptimal"},
            4,
            66,
            1.75,
            True,
            True,
            True,
        ),
    ]


def test_server_shadow_and_suboptimal_turn_helpers_bind_runtime_globals() -> None:
    asyncio.run(_server_shadow_and_suboptimal_turn_helpers_bind_runtime_globals())


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

    def undo_engine_move():
        calls.append(("undo",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    def log_event(message):
        calls.append(("log", message))

    result = await apply_suspicious_pass_fallback(
        game,
        color="W",
        gtp_move="pass",
        visits=48,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_fallback_move,
        undo_engine_move=undo_engine_move,
        run_engine_command=run_engine_command,
        log_event=log_event,
        log_prefix="Suspicious early PASS in rogue/normal mode",
    )

    assert result == "D3"
    assert calls == [
        ("suspicious", True, "pass", "W"),
        ("undo",),
        ("fallback", True, "W", 48),
        ("engine", "play W D3"),
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

    def undo_engine_move():
        calls.append(("undo",))

    async def run_engine_command(command):
        calls.append(("engine", command))
        return "="

    def log_event(message):
        calls.append(("log", message))

    result = await apply_suspicious_pass_fallback(
        game,
        color="W",
        gtp_move="pass",
        visits=12,
        is_suspicious_pass=is_suspicious_pass,
        pick_fallback_move=pick_fallback_move,
        undo_engine_move=undo_engine_move,
        run_engine_command=run_engine_command,
        log_event=log_event,
        log_prefix="Suspicious early PASS in rogue/normal mode",
    )

    assert result == "pass"
    assert calls == [
        ("suspicious", True, "pass", "W"),
        ("undo",),
        ("fallback", True, "W", 12),
        ("engine", "play W pass"),
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


def test_server_generated_ai_move_deps_bind_runtime_globals() -> None:
    calls = []

    async def fake_candidate(*_args, **_kwargs):
        return AiMoveCandidate("C3")

    async def fake_generate(*_args, **_kwargs):
        return "= C3"

    def fake_slip(*_args, **kwargs):
        return AiMoveAdjustment(kwargs["gtp_move"])

    async def fake_finish(*_args, **_kwargs):
        return False

    async def fake_sync(_game):
        return None

    async def fake_run_command(command):
        calls.append(("double_engine", command))
        return command

    original_send_command = s.engine.send_command
    original_ready = s.engine.ready
    original_candidate = s.choose_ai_move_candidate
    original_generate = s._ai_generate_move
    original_slip = s.apply_slip_ai_move
    original_finish = s.finish_prepared_ai_move
    original_sync = s._sync_board_to_katago
    s.engine.ready = True
    s.choose_ai_move_candidate = fake_candidate
    s._ai_generate_move = fake_generate
    s.apply_slip_ai_move = fake_slip
    s.finish_prepared_ai_move = fake_finish
    s._sync_board_to_katago = fake_sync
    try:
        candidate_deps = build_generated_move_candidate_deps(
            s._generated_ai_move_candidate_binding(),
        )
        preparation_deps = build_generated_move_preparation_deps(
            s._generated_ai_move_preparation_binding(),
        )
        finish_deps = build_generated_move_finish_deps(
            s._generated_ai_move_finish_binding(fake_run_command),
        )
        first_ready = finish_deps.engine_is_ready()
        s.engine.ready = False
        second_ready = finish_deps.engine_is_ready()
        s.engine.send_command = lambda command: calls.append(("erosion_engine", command)) or f"= {command}"
        erosion_result = asyncio.run(finish_deps.run_erosion_command("kata-set-param komi 6.5"))
        double_result = asyncio.run(finish_deps.run_double_pass_command("final_score"))
    finally:
        s.engine.send_command = original_send_command
        s.engine.ready = original_ready
        s.choose_ai_move_candidate = original_candidate
        s._ai_generate_move = original_generate
        s.apply_slip_ai_move = original_slip
        s.finish_prepared_ai_move = original_finish
        s._sync_board_to_katago = original_sync

    assert candidate_deps.choose_candidate is fake_candidate
    assert candidate_deps.choose_avoid_move is s._ai_move_avoid_points
    assert candidate_deps.generate_move is fake_generate
    assert candidate_deps.gtp_to_coord is s.gtp_to_coord
    assert preparation_deps.prepare_move is s.prepare_generated_ai_move
    assert preparation_deps.apply_slip_move is fake_slip
    assert preparation_deps.adjacent_points is s._adjacent_points
    assert finish_deps.finish_move is fake_finish
    assert finish_deps.sync_board_to_engine is fake_sync
    assert finish_deps.adjacent_points is s._adjacent8_points
    assert finish_deps.run_erosion_command is s._send_engine_command
    assert finish_deps.run_double_pass_command is fake_run_command
    assert first_ready is True
    assert second_ready is False
    assert erosion_result == "= kata-set-param komi 6.5"
    assert double_result == "final_score"
    assert calls == [
        ("erosion_engine", "kata-set-param komi 6.5"),
        ("double_engine", "final_score"),
    ]


def test_server_engine_command_helper_binds_runtime_send_command() -> None:
    calls = []

    def fake_send_command(command):
        calls.append(command)
        return f"= {command}"

    original_send_command = s.engine.send_command
    s.engine.send_command = fake_send_command
    try:
        result = asyncio.run(s._send_engine_command("final_score"))
    finally:
        s.engine.send_command = original_send_command

    assert result == "= final_score"
    assert calls == ["final_score"]


def test_server_sync_engine_komi_uses_ready_gate_and_runtime_command() -> None:
    game = GoGame(size=5, komi=6.5, player_color="B")
    calls = []

    def fake_send_command(command):
        calls.append(command)
        return f"= {command}"

    original_ready = s.engine.ready
    original_send_command = s.engine.send_command
    s.engine.send_command = fake_send_command
    try:
        s.engine.ready = False
        asyncio.run(s._sync_engine_komi(game))
        s.engine.ready = True
        asyncio.run(s._sync_engine_komi(game))
    finally:
        s.engine.ready = original_ready
        s.engine.send_command = original_send_command

    assert calls == ["komi 6.5"]


async def _server_finish_observer_double_pass_scores_once() -> None:
    calls = []
    game = GoGame(size=5, player_color="B")

    async def send(payload):
        calls.append(("send", payload))

    async def fake_send_command(command):
        calls.append(("engine", command))
        return "= W+2.5"

    original_send_command = s._send_engine_command
    s._send_engine_command = fake_send_command
    try:
        skipped = await s._finish_observer_double_pass(game, send)
        game.passed["B"] = True
        game.passed["W"] = True
        finished = await s._finish_observer_double_pass(game, send)
    finally:
        s._send_engine_command = original_send_command

    assert skipped is False
    assert finished is True
    assert game.game_over is True
    assert game.winner == "W"
    assert calls == [
        ("engine", "final_score"),
        ("send", {
            "type": "game_over",
            "winner": "W",
            "score": "W+2.5",
            "reason": "double_pass",
        }),
    ]


def test_server_finish_observer_double_pass_scores_once() -> None:
    asyncio.run(_server_finish_observer_double_pass_scores_once())


def test_server_apply_observer_ai_move_to_board_preserves_legacy_pass_flags() -> None:
    game = GoGame(size=5, player_color="B")

    original_gtp_to_coord = s.gtp_to_coord
    def fake_gtp_to_coord(gtp, size):
        if gtp == "bad":
            return None
        return original_gtp_to_coord(gtp, size)

    s.gtp_to_coord = fake_gtp_to_coord
    try:
        placed = s._apply_observer_ai_move_to_board(game, "W", "C3")
        passed = s._apply_observer_ai_move_to_board(game, "B", "pass")
        invalid = s._apply_observer_ai_move_to_board(game, "W", "bad")
    finally:
        s.gtp_to_coord = original_gtp_to_coord

    assert placed == AiMovePlacement(coord=(2, 2), captured=0)
    assert passed == AiMovePlacement(coord=None, captured=0)
    assert invalid == AiMovePlacement(coord=None, captured=0)
    assert game.moves == [("W", "C3"), ("B", "pass"), ("W", "bad")]
    assert game.board[2][2] == 2
    assert game.passed["B"] is True
    assert game.passed["W"] is True


def test_server_place_auxiliary_ai_move_on_board_preserves_pass_flags() -> None:
    game = GoGame(size=5, player_color="B")

    placed = s._place_auxiliary_ai_move_on_board(game, "W", "C3", (2, 2))
    passed = s._place_auxiliary_ai_move_on_board(game, "B", "pass", None)
    invalid = s._place_auxiliary_ai_move_on_board(game, "W", "bad", None)

    assert placed == AiMovePlacement(coord=(2, 2), captured=0)
    assert passed == AiMovePlacement(coord=None, captured=0)
    assert invalid == AiMovePlacement(coord=None, captured=0)
    assert game.moves == [("W", "C3"), ("B", "pass"), ("W", "bad")]
    assert game.board[2][2] == 2
    assert game.passed["B"] is True
    assert game.passed["W"] is True


async def _server_choose_coach_ai_move_normalizes_resign_and_retries_ko() -> None:
    game = GoGame(size=5, player_color="B", level="5k")
    game.moves.append(("B", "A1"))
    calls = []

    def fake_visits(level, move_count, mode=None, **_kwargs):
        calls.append(("visits", level, move_count, mode))
        return 1

    async def fake_generate(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "RESIGN"

    original_visits = s.get_game_visits
    original_generate = s._generate_ai_style_move
    s.get_game_visits = fake_visits
    s._generate_ai_style_move = fake_generate
    try:
        resigned_move, resigned_coord = await s._choose_coach_ai_move(game, "B")
    finally:
        s.get_game_visits = original_visits
        s._generate_ai_style_move = original_generate

    assert resigned_move == "pass"
    assert resigned_coord is None
    assert calls == [
        ("visits", "5k", 1, "rogue"),
        ("generate", True, "B", s.ROGUE_COACH_VISITS, min(s.MAX_MOVE_TIME, 8.0)),
    ]

    calls.clear()

    async def fake_generate_ko(game_arg, color, visits, time_limit):
        calls.append(("generate", game_arg is game, color, visits, time_limit))
        return "C3"

    def fake_gtp_to_coord(gtp, size):
        calls.append(("coord", gtp, size))
        return {"C3": (2, 2), "D3": (3, 2)}.get(gtp)

    async def fake_retry(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "D3"

    def fake_is_ko(x, y, color):
        calls.append(("ko", x, y, color))
        return (x, y, color) == (2, 2, "B")

    original_visits = s.get_game_visits
    original_generate = s._generate_ai_style_move
    original_gtp_to_coord = s.gtp_to_coord
    original_retry = s._ai_retry_avoiding_ko
    original_is_ko = game.is_ko
    s.get_game_visits = fake_visits
    s._generate_ai_style_move = fake_generate_ko
    s.gtp_to_coord = fake_gtp_to_coord
    s._ai_retry_avoiding_ko = fake_retry
    game.is_ko = fake_is_ko
    try:
        ko_move, ko_coord = await s._choose_coach_ai_move(game, "B")
    finally:
        s.get_game_visits = original_visits
        s._generate_ai_style_move = original_generate
        s.gtp_to_coord = original_gtp_to_coord
        s._ai_retry_avoiding_ko = original_retry
        game.is_ko = original_is_ko

    assert ko_move == "D3"
    assert ko_coord == (3, 2)
    assert calls == [
        ("visits", "5k", 1, "rogue"),
        ("generate", True, "B", s.ROGUE_COACH_VISITS, min(s.MAX_MOVE_TIME, 8.0)),
        ("coord", "C3", 5),
        ("ko", 2, 2, "B"),
        ("retry", True, "B"),
        ("coord", "D3", 5),
    ]


def test_server_choose_coach_ai_move_normalizes_resign_and_retries_ko() -> None:
    asyncio.run(_server_choose_coach_ai_move_normalizes_resign_and_retries_ko())


async def _server_generated_turn_helper_binds_runtime_globals() -> None:
    game = GoGame(size=5, player_color="B")
    turn = s.AiTurnSnapshot(
        color="W",
        card="seal",
        rogue_cards={"seal", "fog"},
        move_count=9,
        ai_move_count=4,
    )
    ai_plan = s.AiMovePlan(
        mode="rogue",
        effective_level="2k",
        visits=111,
        time_limit=3.25,
        move_count=9,
        ai_move_count=4,
    )
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    async def run_engine(command):
        calls.append(("engine", command))
        return f"= {command}"

    def fake_challenge_zone(game_arg, point):
        calls.append(("challenge_zone", game_arg is game, point))
        return [(3, 3)]

    def fake_forbidden(game_arg, rogue_cards, ai_move_count, *, challenge_zone_points):
        challenge_points = challenge_zone_points(game_arg, (1, 1))
        calls.append((
            "forbidden",
            game_arg is game,
            rogue_cards,
            ai_move_count,
            challenge_zone_points is fake_challenge_zone,
            challenge_points,
        ))
        return [(0, 0), *challenge_points]

    async def fake_generated_flow(game_arg, send_fn, **kwargs):
        calls.append((
            "generated_flow",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["rogue_cards"],
            kwargs["forbidden"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["candidate_deps"].choose_candidate is s.choose_ai_move_candidate,
            kwargs["preparation_deps"].prepare_move is s.prepare_generated_ai_move,
            kwargs["finish_deps"].run_double_pass_command is run_engine,
        ))
        engine_result = await kwargs["finish_deps"].run_double_pass_command("final_score")
        calls.append(("generated_engine", engine_result))
        return True

    original_candidate_binding = s._generated_ai_move_candidate_binding
    original_preparation_binding = s._generated_ai_move_preparation_binding
    original_finish_binding = s._generated_ai_move_finish_binding

    def fake_candidate_binding():
        calls.append(("candidate_binding",))
        return original_candidate_binding()

    def fake_preparation_binding():
        calls.append(("preparation_binding",))
        return original_preparation_binding()

    def fake_finish_binding(run_engine_command):
        calls.append(("finish_binding", run_engine_command is run_engine))
        return original_finish_binding(run_engine_command)

    originals = {
        "forbidden": s.rogue_forbidden_points,
        "challenge_zone": s._challenge_zone_points,
        "candidate_binding": s._generated_ai_move_candidate_binding,
        "preparation_binding": s._generated_ai_move_preparation_binding,
        "finish_binding": s._generated_ai_move_finish_binding,
        "generated_flow": s.try_finish_generated_ai_move,
    }
    s.rogue_forbidden_points = fake_forbidden
    s._challenge_zone_points = fake_challenge_zone
    s._generated_ai_move_candidate_binding = fake_candidate_binding
    s._generated_ai_move_preparation_binding = fake_preparation_binding
    s._generated_ai_move_finish_binding = fake_finish_binding
    s.try_finish_generated_ai_move = fake_generated_flow
    try:
        handled = await s._try_finish_generated_ai_turn(
            game,
            send,
            turn,
            ai_plan,
            run_engine,
        )
    finally:
        s.rogue_forbidden_points = originals["forbidden"]
        s._challenge_zone_points = originals["challenge_zone"]
        s._generated_ai_move_candidate_binding = originals["candidate_binding"]
        s._generated_ai_move_preparation_binding = originals["preparation_binding"]
        s._generated_ai_move_finish_binding = originals["finish_binding"]
        s.try_finish_generated_ai_move = originals["generated_flow"]

    assert handled is True
    assert calls == [
        ("challenge_zone", True, (1, 1)),
        ("forbidden", True, {"seal", "fog"}, 4, True, [(3, 3)]),
        ("candidate_binding",),
        ("preparation_binding",),
        ("finish_binding", True),
        (
            "generated_flow",
            True,
            True,
            "W",
            "seal",
            {"seal", "fog"},
            [(0, 0), (3, 3)],
            111,
            3.25,
            True,
            True,
            True,
        ),
        ("engine", "final_score"),
        ("generated_engine", "= final_score"),
    ]


def test_server_generated_turn_helper_binds_runtime_globals() -> None:
    asyncio.run(_server_generated_turn_helper_binds_runtime_globals())


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
        ("send", "error"),
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

    def fake_undo():
        calls.append(("undo",))

    async def fake_send_engine(command):
        calls.append(("engine", command))
        return "="

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
    original_undo = s._undo_engine_move_locked
    original_send_engine = s._send_engine_command
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
    s._undo_engine_move_locked = fake_undo
    s._send_engine_command = fake_send_engine
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
        s._undo_engine_move_locked = original_undo
        s._send_engine_command = original_send_engine
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
        ("undo",),
        ("pick_fallback", True, "W", True),
        ("engine", "play W pass"),
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
            kwargs["play_chosen_move"] is s._send_engine_command,
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
            kwargs["run_engine_command"] is s._send_engine_command,
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
    test_finish_prepared_ai_move_skips_completed_or_missing_gtp()
    test_finish_prepared_ai_move_places_then_finishes_response()
    test_finish_prepared_ai_move_returns_double_pass_handled()
    test_refresh_fog_restriction_late_can_target_best_point()
    test_refresh_fog_restriction_late_falls_back_to_random_point()
    test_try_finish_generated_ai_move_stops_on_completed_candidate()
    test_try_finish_generated_ai_move_runs_prepare_then_finish()
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
    test_finish_ai_turn_response_double_pass_skips_ai_move_response()
    test_finish_ai_turn_response_nonterminal_sends_ai_move_response()
    test_finish_ai_turn_response_methodical_rearms_next_player_turn()
    test_finish_ai_turn_response_capture_foul_gifts_before_game_state()
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
    test_prepare_generated_ai_move_runs_adjustment_chain()
    test_prepare_generated_ai_move_stops_on_completed_resign()
    test_finalize_ai_move_places_stone_and_sends_message()
    test_finalize_ai_move_resign_without_card_ends_game()
    test_finalize_ai_move_resign_with_card_uses_no_resign_move()
    test_finalize_ai_move_engine_error_sends_error_without_mutating_board()
    test_finalize_ai_move_retries_ko_move()
    test_finalize_ai_move_delegates_non_terminal_finish_response()
    test_finalize_ai_move_double_pass_scores_without_coach_turn()
    test_finalize_ai_move_erosion_updates_komi_after_capture()
    test_finalize_forced_ai_pass_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_sends_legacy_payloads()
    test_try_finalize_forced_ai_stone_can_skip_history_push()
    test_try_finalize_forced_ai_stone_skips_state_on_engine_error()
    test_try_finish_restriction_forced_stone_runs_capture_foul_before_state()
    test_try_finish_forced_rogue_ai_move_dice_preempts_later_cards()
    test_try_finish_forced_rogue_ai_move_mirror_forces_stone()
    test_try_finish_forced_rogue_ai_move_mirror_false_falls_through()
    test_try_finish_forced_rogue_ai_move_exchange_clears_skip()
    test_try_finish_forced_rogue_ai_move_puppet_delegates_target()
    test_server_ai_move_delegates_to_forced_rogue_flow()
    test_server_forced_rogue_turn_helper_binds_runtime_globals()
    test_server_ai_move_dice_delegates_to_forced_pass()
    test_server_ai_move_exchange_clears_skip_and_delegates_to_forced_pass()
    test_server_ai_move_mirror_delegates_to_forced_stone()
    test_server_ai_move_mirror_helper_false_falls_back_to_normal_move()
    test_server_ai_move_tengen_delegates_to_forced_stone_with_history()
    test_server_ai_move_tengen_helper_false_falls_back_to_followup()
    test_try_finish_rogue_restriction_ai_move_tengen_target_preempts_followup()
    test_try_finish_rogue_restriction_ai_move_tengen_false_falls_back()
    test_try_finish_rogue_restriction_ai_move_tengen_unplayable_target_falls_back()
    test_try_finish_rogue_restriction_ai_move_gravity_preempts_later()
    test_try_finish_rogue_restriction_ai_move_lowline_after_gravity_miss()
    test_try_finish_rogue_restriction_ai_move_sansan_uses_avoid()
    test_server_ai_move_delegates_to_rogue_restriction_flow()
    test_server_rogue_restriction_turn_helper_binds_runtime_globals()
    test_server_shadow_and_suboptimal_turn_helpers_bind_runtime_globals()
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
    test_server_generated_ai_move_deps_bind_runtime_globals()
    test_server_engine_command_helper_binds_runtime_send_command()
    test_server_sync_engine_komi_uses_ready_gate_and_runtime_command()
    test_server_finish_observer_double_pass_scores_once()
    test_server_apply_observer_ai_move_to_board_preserves_legacy_pass_flags()
    test_server_place_auxiliary_ai_move_on_board_preserves_pass_flags()
    test_server_choose_coach_ai_move_normalizes_resign_and_retries_ko()
    test_server_generated_turn_helper_binds_runtime_globals()
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
