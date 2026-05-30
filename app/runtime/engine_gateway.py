from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.runtime.analysis import (
    analyze_current_position as analyze_current_position_state,
    empty_analysis_result as empty_analysis_result_state,
    estimate_side_winrate as estimate_side_winrate_state,
    pick_analysis_point as pick_analysis_point_state,
    pick_best_point as pick_best_point_state,
    pick_second_best_point as pick_second_best_point_state,
)
from app.runtime.board_sync import (
    gtp_safe_sync_sgf_path as build_gtp_safe_sync_sgf_path,
    has_gtp_unsafe_whitespace as check_gtp_unsafe_whitespace,
    sync_board_to_katago_locked as sync_board_to_katago_locked_state,
)


RunInExecutorFn = Callable[..., Awaitable[Any]]
VisitsFn = Callable[..., int]
CoordParser = Callable[[str, int], tuple[int, int] | None]
SyncBoardFn = Callable[[Any], Awaitable[None]]
LogFn = Callable[[str], None]
TracebackFn = Callable[[], None]


class EngineRuntimeGateway:
    def __init__(
        self,
        *,
        engine: Any,
        base_dir: Path,
        get_game_visits: VisitsFn,
        gtp_to_coord: CoordParser,
        run_in_executor: RunInExecutorFn,
        log_fn: LogFn = print,
        traceback_fn: TracebackFn = traceback.print_exc,
    ) -> None:
        self.engine = engine
        self.base_dir = base_dir
        self.get_game_visits = get_game_visits
        self.gtp_to_coord = gtp_to_coord
        self.run_in_executor = run_in_executor
        self.log_fn = log_fn
        self.traceback_fn = traceback_fn

    def bind_runtime(
        self,
        *,
        engine: Any | None = None,
        get_game_visits: VisitsFn | None = None,
        gtp_to_coord: CoordParser | None = None,
        run_in_executor: RunInExecutorFn | None = None,
        log_fn: LogFn | None = None,
        traceback_fn: TracebackFn | None = None,
    ) -> None:
        if engine is not None:
            self.engine = engine
        if get_game_visits is not None:
            self.get_game_visits = get_game_visits
        if gtp_to_coord is not None:
            self.gtp_to_coord = gtp_to_coord
        if run_in_executor is not None:
            self.run_in_executor = run_in_executor
        if log_fn is not None:
            self.log_fn = log_fn
        if traceback_fn is not None:
            self.traceback_fn = traceback_fn

    async def send_command(self, command: str) -> str:
        return await self.run_in_executor(self.engine.send_command, command)

    async def sync_komi(self, game: Any) -> None:
        if self.engine.ready:
            await self.send_command(f"komi {game.komi}")

    def sync_board_locked(self, game: Any) -> str:
        return sync_board_to_katago_locked_state(game, self.engine, base_dir=self.base_dir)

    @staticmethod
    def has_gtp_unsafe_whitespace(path: str) -> bool:
        return check_gtp_unsafe_whitespace(path)

    def gtp_safe_sync_sgf_path(self, game: Any) -> str:
        return build_gtp_safe_sync_sgf_path(game, base_dir=self.base_dir)

    async def sync_board(self, game: Any) -> None:
        def _do() -> None:
            with self.engine.command_lock:
                self.sync_board_locked(game)

        await self.run_in_executor(_do)

    @staticmethod
    def empty_analysis_result() -> dict[str, Any]:
        return empty_analysis_result_state()

    async def analyze_current_position(
        self,
        game: Any,
        color: str | None = None,
        *,
        sync_board: SyncBoardFn | None = None,
    ) -> dict[str, Any]:
        return await analyze_current_position_state(
            game,
            color=color,
            engine_ready=self.engine.ready,
            sync_board=sync_board or self.sync_board,
            get_game_visits=self.get_game_visits,
            analyze=self.engine.analyze,
            parse_analysis=self.engine.parse_analysis,
            run_in_executor=self.run_in_executor,
            log_fn=self.log_fn,
            traceback_fn=self.traceback_fn,
        )

    async def estimate_side_winrate(
        self,
        game: Any,
        color: str,
        *,
        sync_board: SyncBoardFn | None = None,
    ) -> float:
        return await estimate_side_winrate_state(
            game,
            color,
            engine_ready=self.engine.ready,
            sync_board=sync_board or self.sync_board,
            analyze=self.engine.analyze,
            parse_analysis=self.engine.parse_analysis,
            run_in_executor=self.run_in_executor,
        )

    async def pick_analysis_point(
        self,
        game: Any,
        color: str,
        *,
        start_index: int = 0,
    ) -> tuple[int, int] | None:
        return await pick_analysis_point_state(
            game,
            color,
            start_index=start_index,
            engine_ready=self.engine.ready,
            get_game_visits=self.get_game_visits,
            analyze=self.engine.analyze,
            parse_analysis=self.engine.parse_analysis,
            run_in_executor=self.run_in_executor,
            gtp_to_coord=self.gtp_to_coord,
        )

    async def pick_second_best_point(self, game: Any, color: str) -> tuple[int, int] | None:
        return await pick_second_best_point_state(
            game,
            color,
            engine_ready=self.engine.ready,
            get_game_visits=self.get_game_visits,
            analyze=self.engine.analyze,
            parse_analysis=self.engine.parse_analysis,
            run_in_executor=self.run_in_executor,
            gtp_to_coord=self.gtp_to_coord,
        )

    async def pick_best_point(self, game: Any, color: str) -> tuple[int, int] | None:
        return await pick_best_point_state(
            game,
            color,
            engine_ready=self.engine.ready,
            get_game_visits=self.get_game_visits,
            analyze=self.engine.analyze,
            parse_analysis=self.engine.parse_analysis,
            run_in_executor=self.run_in_executor,
            gtp_to_coord=self.gtp_to_coord,
        )
