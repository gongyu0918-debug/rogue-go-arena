from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import tempfile
from pathlib import Path

from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.runtime.engine_gateway import EngineRuntimeGateway


class DummyLock:
    def __init__(self) -> None:
        self.entries = 0

    def __enter__(self):
        self.entries += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyEngine:
    def __init__(self) -> None:
        self.ready = True
        self.command_lock = DummyLock()
        self.commands: list[str] = []
        self.analysis_calls: list[tuple[str, dict]] = []

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        return "="

    def _send_command_locked(self, command: str) -> str:
        self.commands.append(command)
        return "="

    def analyze(self, color: str, **kwargs):
        self.analysis_calls.append((color, kwargs))
        return ["line"], ["own"]

    def parse_analysis(self, _lines, ownership, size, to_move_color):
        return {
            "winrate": 0.61,
            "score": 2.5,
            "top_moves": [{"move": "D4"}, {"move": "E5"}],
            "ownership": ownership,
            "analysis_ready": True,
            "size": size,
            "to_move_color": to_move_color,
        }


async def run_executor(func, *args):
    return func(*args)


def get_visits(level, move_count, mode=None):
    assert level == "a3d"
    assert move_count == 1
    return 420 if mode is None else 640


async def main():
    game = GoGame(size=9, level="a3d")
    game.current_player = "W"
    game.moves.append(("B", "E5"))
    game.board[4][4] = 1
    engine = DummyEngine()

    with tempfile.TemporaryDirectory() as tmp:
        gateway = EngineRuntimeGateway(
            engine=engine,
            base_dir=Path(tmp),
            get_game_visits=get_visits,
            gtp_to_coord=gtp_to_coord,
            run_in_executor=run_executor,
            log_fn=lambda message: None,
            traceback_fn=lambda: None,
        )

        assert await gateway.send_command("name") == "="
        await gateway.sync_komi(game)
        await gateway.sync_board(game)
        sync_path = engine.commands[-1].split(" ", 1)[1]
        assert Path(sync_path).exists()
        assert engine.command_lock.entries == 1
        assert gateway.has_gtp_unsafe_whitespace("has space") is True
        assert " " not in gateway.gtp_safe_sync_sgf_path(game)

    async def fake_sync_board(game_arg):
        assert game_arg is game

    analysis = await gateway.analyze_current_position(game, sync_board=fake_sync_board)
    assert analysis["winrate"] == 0.61
    assert game.last_analysis == analysis
    assert game.last_analysis is not analysis

    best = await gateway.pick_best_point(game, "B")
    second = await gateway.pick_second_best_point(game, "B")
    assert best == (3, 5)
    assert second is None
    assert [command.split(" ", 1)[0] for command in engine.commands] == ["name", "komi", "loadsgf"]
    assert engine.analysis_calls[0][0] == "W"
    assert engine.analysis_calls[1][0] == "B"
    assert engine.analysis_calls[2][0] == "B"
    print("engine gateway smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
