from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.runtime.analysis import (
    analyze_current_position,
    empty_analysis_result,
    estimate_side_winrate,
    pick_analysis_point,
)


async def _run_callable(func):
    return func()


async def _fail_async(*_args, **_kwargs):
    raise AssertionError("unexpected async dependency call")


def _fail_sync(*_args, **_kwargs):
    raise AssertionError("unexpected sync dependency call")


async def _analyze_current_position_not_ready_sets_empty_snapshot() -> None:
    game = GoGame(size=9)

    result = await analyze_current_position(
        game,
        engine_ready=False,
        sync_board=_fail_async,
        get_game_visits=_fail_sync,
        analyze=_fail_sync,
        parse_analysis=_fail_sync,
        run_in_executor=_fail_async,
    )

    assert result == empty_analysis_result()
    assert game.last_analysis == result
    assert game.last_analysis is not result
    result["top_moves"].append({"move": "D4"})
    assert game.last_analysis["top_moves"] == []


def test_analyze_current_position_not_ready_sets_empty_snapshot() -> None:
    asyncio.run(_analyze_current_position_not_ready_sets_empty_snapshot())


async def _analyze_current_position_ready_uses_engine_analysis() -> None:
    game = GoGame(size=9, level="a3d")
    game.current_player = "W"
    game.moves.append(("B", "E5"))
    calls = []

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 300

    def analyze(color, **kwargs):
        calls.append(("analyze", color, kwargs))
        return ["line"], ["own"]

    def parse_analysis(lines, ownership, size, to_move_color):
        calls.append(("parse", lines, ownership, size, to_move_color))
        return {
            "winrate": 0.62,
            "score": 1.5,
            "top_moves": [{"move": "D4"}],
            "ownership": [0.1],
            "analysis_ready": True,
        }

    logs = []
    result = await analyze_current_position(
        game,
        engine_ready=True,
        sync_board=sync_board,
        get_game_visits=get_visits,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=_run_callable,
        log_fn=logs.append,
    )

    assert result["winrate"] == 0.62
    assert game.last_analysis == result
    assert game.last_analysis is not result
    result["top_moves"].append({"move": "E5"})
    assert game.last_analysis["top_moves"] == [{"move": "D4"}]
    assert calls == [
        ("sync", True),
        ("visits", "a3d", 1, None),
        (
            "analyze",
            "W",
            {
                "visits": 150,
                "interval": 50,
                "duration": 1.0,
                "extra_args": ["rootInfo", "true", "ownership", "true"],
            },
        ),
        ("parse", ["line"], ["own"], 9, "W"),
    ]
    assert logs == ["[Analysis] top_moves=1 winrate=0.62"]


def test_analyze_current_position_ready_uses_engine_analysis() -> None:
    asyncio.run(_analyze_current_position_ready_uses_engine_analysis())


async def _analyze_current_position_error_preserves_empty_fallback_and_traceback() -> None:
    game = GoGame(size=9)
    calls = []

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def get_visits(_level, _move_count, mode=None):
        calls.append(("visits", mode))
        return 300

    def analyze(*_args, **_kwargs):
        calls.append(("analyze",))
        raise RuntimeError("analysis failed")

    logs = []
    result = await analyze_current_position(
        game,
        engine_ready=True,
        sync_board=sync_board,
        get_game_visits=get_visits,
        analyze=analyze,
        parse_analysis=_fail_sync,
        run_in_executor=_run_callable,
        log_fn=logs.append,
        traceback_fn=lambda: calls.append(("traceback",)),
    )

    assert result == empty_analysis_result()
    assert game.last_analysis == result
    assert calls == [
        ("sync", True),
        ("visits", None),
        ("analyze",),
        ("traceback",),
    ]
    assert logs == ["[Analysis] error: analysis failed"]


def test_analyze_current_position_error_preserves_empty_fallback_and_traceback() -> None:
    asyncio.run(_analyze_current_position_error_preserves_empty_fallback_and_traceback())


async def _estimate_side_winrate_clamps_and_inverts() -> None:
    game = GoGame(size=9)
    game.current_player = "B"
    calls = []

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    def analyze(color, **kwargs):
        calls.append(("analyze", color, kwargs))
        return ["line"], []

    def parse_analysis(_lines, _ownership, _size, to_move_color):
        assert to_move_color == "B"
        return {"winrate": 1.25}

    black_wr = await estimate_side_winrate(
        game,
        "B",
        engine_ready=True,
        sync_board=sync_board,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=_run_callable,
    )
    white_wr = await estimate_side_winrate(
        game,
        "W",
        engine_ready=True,
        sync_board=sync_board,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=_run_callable,
    )

    assert black_wr == 1.0
    assert white_wr == 0.0
    assert calls == [
        ("sync", True),
        (
            "analyze",
            "B",
            {
                "visits": 120,
                "interval": 50,
                "duration": 0.7,
                "extra_args": ["rootInfo", "true", "ownership", "false"],
            },
        ),
        ("sync", True),
        (
            "analyze",
            "B",
            {
                "visits": 120,
                "interval": 50,
                "duration": 0.7,
                "extra_args": ["rootInfo", "true", "ownership", "false"],
            },
        ),
    ]


def test_estimate_side_winrate_clamps_and_inverts() -> None:
    asyncio.run(_estimate_side_winrate_clamps_and_inverts())


async def _pick_analysis_point_skips_pass_occupied_and_start_index() -> None:
    game = GoGame(size=9, level="a3d")
    game.board[6][2] = 1
    calls = []

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 950

    def analyze(color, **kwargs):
        calls.append(("analyze", color, kwargs))
        return ["line"], []

    def parse_analysis(lines, ownership, size, to_move_color):
        calls.append(("parse", lines, ownership, size, to_move_color))
        return {
            "top_moves": [
                {"move": "A1"},
                {"move": "PASS"},
                {"gtp": "C3"},
                {"move": "D4"},
            ]
        }

    point = await pick_analysis_point(
        game,
        "W",
        start_index=1,
        engine_ready=True,
        get_game_visits=get_visits,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=_run_callable,
        gtp_to_coord=gtp_to_coord,
    )

    assert point == (3, 5)
    assert calls == [
        ("visits", "a3d", 0, "rogue"),
        (
            "analyze",
            "W",
            {
                "visits": 800,
                "interval": 40,
                "duration": 1.2,
                "extra_args": ["rootInfo", "true"],
            },
        ),
        ("parse", ["line"], [], 9, "W"),
    ]


def test_pick_analysis_point_skips_pass_occupied_and_start_index() -> None:
    asyncio.run(_pick_analysis_point_skips_pass_occupied_and_start_index())


async def _server_analysis_wrapper_uses_patchable_dependencies() -> None:
    game = GoGame(size=9, level="a3d")
    calls = []

    async def sync_board(game_arg):
        calls.append(("sync", game_arg is game))

    async def run_executor(func, *args):
        calls.append(("executor", len(args)))
        return func(*args)

    def get_visits(level, move_count, mode=None):
        calls.append(("visits", level, move_count, mode))
        return 300

    def analyze(color, **kwargs):
        calls.append(("analyze", color, kwargs))
        return ["line"], ["own"]

    def parse_analysis(_lines, _ownership, size, to_move_color):
        calls.append(("parse", size, to_move_color))
        return {
            "winrate": 0.44,
            "score": 0.0,
            "top_moves": [],
            "ownership": [],
            "analysis_ready": True,
        }

    original_ready = s.engine.ready
    original_sync = s._sync_board_to_katago
    original_run_executor = s.run_in_executor
    original_get_visits = s.get_game_visits
    original_analyze = s.engine.analyze
    original_parse = s.engine.parse_analysis
    s.engine.ready = True
    s._sync_board_to_katago = sync_board
    s.run_in_executor = run_executor
    s.get_game_visits = get_visits
    s.engine.analyze = analyze
    s.engine.parse_analysis = parse_analysis
    try:
        result = await s._analyze_current_position(game, "W")
    finally:
        s.engine.ready = original_ready
        s._sync_board_to_katago = original_sync
        s.run_in_executor = original_run_executor
        s.get_game_visits = original_get_visits
        s.engine.analyze = original_analyze
        s.engine.parse_analysis = original_parse

    assert result["winrate"] == 0.44
    assert calls == [
        ("sync", True),
        ("visits", "a3d", 0, None),
        ("executor", 0),
        (
            "analyze",
            "W",
            {
                "visits": 150,
                "interval": 50,
                "duration": 1.0,
                "extra_args": ["rootInfo", "true", "ownership", "true"],
            },
        ),
        ("parse", 9, "W"),
    ]


def test_server_analysis_wrapper_uses_patchable_dependencies() -> None:
    asyncio.run(_server_analysis_wrapper_uses_patchable_dependencies())


async def _server_pick_point_wrappers_use_patchable_analysis_point() -> None:
    game = GoGame(size=9)
    calls = []

    async def fake_pick_analysis_point(game_arg, color, *, start_index=0):
        calls.append((game_arg is game, color, start_index))
        return (start_index, start_index + 1)

    original_pick_analysis_point = s._pick_analysis_point
    s._pick_analysis_point = fake_pick_analysis_point
    try:
        best = await s._pick_best_point(game, "B")
        second = await s._pick_second_best_point(game, "W")
    finally:
        s._pick_analysis_point = original_pick_analysis_point

    assert best == (0, 1)
    assert second == (1, 2)
    assert calls == [
        (True, "B", 0),
        (True, "W", 1),
    ]


def test_server_pick_point_wrappers_use_patchable_analysis_point() -> None:
    asyncio.run(_server_pick_point_wrappers_use_patchable_analysis_point())


if __name__ == "__main__":
    test_analyze_current_position_not_ready_sets_empty_snapshot()
    test_analyze_current_position_ready_uses_engine_analysis()
    test_analyze_current_position_error_preserves_empty_fallback_and_traceback()
    test_estimate_side_winrate_clamps_and_inverts()
    test_pick_analysis_point_skips_pass_occupied_and_start_index()
    test_server_analysis_wrapper_uses_patchable_dependencies()
    test_server_pick_point_wrappers_use_patchable_analysis_point()
    print("analysis_smoke_test passed")
