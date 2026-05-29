from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable
from typing import Any


RunInExecutorFn = Callable[[Callable[[], Any]], Awaitable[Any]]
SyncBoardFn = Callable[[Any], Awaitable[None]]
VisitsFn = Callable[..., int]
AnalyzeFn = Callable[..., tuple[list[Any], list[Any]]]
ParseAnalysisFn = Callable[..., dict[str, Any]]
CoordParser = Callable[[str, int], tuple[int, int] | None]
LogFn = Callable[[str], None]
TracebackFn = Callable[[], None]


def empty_analysis_result() -> dict[str, Any]:
    return {
        "winrate": 0.5,
        "score": 0.0,
        "top_moves": [],
        "ownership": [],
        "analysis_ready": False,
    }


async def analyze_current_position(
    game: Any,
    *,
    color: str | None = None,
    engine_ready: bool,
    sync_board: SyncBoardFn,
    get_game_visits: VisitsFn,
    analyze: AnalyzeFn,
    parse_analysis: ParseAnalysisFn,
    run_in_executor: RunInExecutorFn,
    log_fn: LogFn | None = None,
    traceback_fn: TracebackFn | None = None,
) -> dict[str, Any]:
    if not engine_ready:
        result = empty_analysis_result()
        game.last_analysis = copy.deepcopy(result)
        return result

    await sync_board(game)
    analyze_color = color or game.current_player
    analysis_visits = max(80, min(get_game_visits(game.level, len(game.moves)) // 2, 1000))

    def _analyze() -> dict[str, Any]:
        try:
            lines, ownership = analyze(
                analyze_color,
                visits=analysis_visits,
                interval=50,
                duration=1.0,
                extra_args=["rootInfo", "true", "ownership", "true"],
            )
            result = parse_analysis(
                lines,
                ownership,
                game.size,
                to_move_color=analyze_color,
            )
            if log_fn is not None:
                log_fn(
                    f"[Analysis] top_moves={len(result.get('top_moves', []))} "
                    f"winrate={result.get('winrate')}"
                )
            return result
        except Exception as ex:
            if log_fn is not None:
                log_fn(f"[Analysis] error: {ex}")
            if traceback_fn is not None:
                traceback_fn()
            return empty_analysis_result()

    result = await run_in_executor(_analyze)
    game.last_analysis = copy.deepcopy(result)
    return result


async def estimate_side_winrate(
    game: Any,
    color: str,
    *,
    engine_ready: bool,
    sync_board: SyncBoardFn,
    analyze: AnalyzeFn,
    parse_analysis: ParseAnalysisFn,
    run_in_executor: RunInExecutorFn,
) -> float:
    if not engine_ready:
        return 0.5
    await sync_board(game)

    def _analyze() -> float:
        try:
            lines, ownership = analyze(
                game.current_player,
                visits=120,
                interval=50,
                duration=0.7,
                extra_args=["rootInfo", "true", "ownership", "false"],
            )
            result = parse_analysis(
                lines,
                ownership,
                game.size,
                to_move_color=game.current_player,
            )
            black_wr = float(result.get("winrate", 0.5))
            return black_wr if color == "B" else 1.0 - black_wr
        except Exception:
            return 0.5

    try:
        return max(0.0, min(1.0, float(await run_in_executor(_analyze))))
    except Exception:
        return 0.5


async def pick_analysis_point(
    game: Any,
    color: str,
    *,
    start_index: int = 0,
    engine_ready: bool,
    get_game_visits: VisitsFn,
    analyze: AnalyzeFn,
    parse_analysis: ParseAnalysisFn,
    run_in_executor: RunInExecutorFn,
    gtp_to_coord: CoordParser,
) -> tuple[int, int] | None:
    if not engine_ready:
        return None

    def _analyze() -> list[dict[str, Any]]:
        visits = max(120, min(get_game_visits(game.level, len(game.moves), mode="rogue"), 800))
        lines, _ = analyze(
            color,
            visits=visits,
            interval=40,
            duration=1.2,
            extra_args=["rootInfo", "true"],
        )
        result = parse_analysis(lines, [], game.size, to_move_color=color)
        return result.get("top_moves", [])

    try:
        top_moves = await run_in_executor(_analyze)
    except Exception:
        return None

    for candidate in top_moves[start_index:]:
        move = candidate.get("move") or candidate.get("gtp")
        if not move or move.upper() == "PASS":
            continue
        coord = gtp_to_coord(move, game.size)
        if coord and game.board[coord[1]][coord[0]] == 0:
            return coord
    return None


async def pick_second_best_point(
    game: Any,
    color: str,
    *,
    engine_ready: bool,
    get_game_visits: VisitsFn,
    analyze: AnalyzeFn,
    parse_analysis: ParseAnalysisFn,
    run_in_executor: RunInExecutorFn,
    gtp_to_coord: CoordParser,
) -> tuple[int, int] | None:
    return await pick_analysis_point(
        game,
        color,
        start_index=1,
        engine_ready=engine_ready,
        get_game_visits=get_game_visits,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=run_in_executor,
        gtp_to_coord=gtp_to_coord,
    )


async def pick_best_point(
    game: Any,
    color: str,
    *,
    engine_ready: bool,
    get_game_visits: VisitsFn,
    analyze: AnalyzeFn,
    parse_analysis: ParseAnalysisFn,
    run_in_executor: RunInExecutorFn,
    gtp_to_coord: CoordParser,
) -> tuple[int, int] | None:
    return await pick_analysis_point(
        game,
        color,
        start_index=0,
        engine_ready=engine_ready,
        get_game_visits=get_game_visits,
        analyze=analyze,
        parse_analysis=parse_analysis,
        run_in_executor=run_in_executor,
        gtp_to_coord=gtp_to_coord,
    )
