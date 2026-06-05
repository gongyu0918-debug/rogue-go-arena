from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import tempfile
from pathlib import Path
from types import SimpleNamespace

import server as s
from app.runtime.board_sync import (
    build_board_sync_sgf,
    gtp_safe_sync_sgf_path,
    has_gtp_unsafe_whitespace,
    sync_board_to_katago_locked,
)


class DummyEngine:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def _send_command_locked(self, command: str) -> str:
        self.commands.append(command)
        return "="


def make_game(size: int = 9):
    board = [[0] * size for _ in range(size)]
    return SimpleNamespace(size=size, komi=6.5, board=board)


def test_build_board_sync_sgf() -> None:
    game = make_game()
    game.board[0][0] = 1
    game.board[2][3] = 1
    game.board[1][4] = 2
    game.board[8][8] = 2

    sgf = build_board_sync_sgf(game)

    assert sgf == "(;GM[1]FF[4]CA[UTF-8]RU[chinese]SZ[9]KM[6.5]AB[aa][dc]AW[eb][ii])"
    assert sgf.index("AB[aa][dc]") < sgf.index("AW[eb][ii]")


def test_gtp_safe_sync_sgf_path_skips_whitespace_candidates() -> None:
    game = make_game()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        safe_dir = root / "safe"
        unsafe_dir = root / "has space"
        path = gtp_safe_sync_sgf_path(
            game,
            base_dir=root,
            env={
                "ROGUE_GO_ARENA_GTP_TMP": str(unsafe_dir),
                "PUBLIC": str(unsafe_dir),
            },
            temp_dir=str(safe_dir),
            process_id=123,
        )

    assert " " not in path
    assert "sync-123-" in Path(path).name
    assert has_gtp_unsafe_whitespace(str(unsafe_dir)) is True


def test_gtp_safe_sync_sgf_path_prefers_safe_env_candidate() -> None:
    game = make_game()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_dir = root / "env-safe"
        temp_dir = root / "temp-safe"
        path = gtp_safe_sync_sgf_path(
            game,
            base_dir=root,
            env={
                "ROGUE_GO_ARENA_GTP_TMP": str(env_dir),
                "PUBLIC": str(root / "public-safe"),
            },
            temp_dir=str(temp_dir),
            process_id=234,
        )

    assert Path(path).parent == env_dir
    assert "sync-234-" in Path(path).name


def test_sync_board_to_katago_locked_writes_sgf_and_loads_it() -> None:
    game = make_game()
    game.board[0][0] = 1
    game.board[8][8] = 2
    engine = DummyEngine()

    with tempfile.TemporaryDirectory() as tmp:
        path = sync_board_to_katago_locked(
            game,
            engine,
            base_dir=Path(tmp),
            env={},
            temp_dir=str(Path(tmp) / "sync"),
            process_id=456,
        )
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")

    assert content == build_board_sync_sgf(game)
    assert engine.commands == [f"loadsgf {path}"]
    assert " " not in path


def test_server_wrappers_preserve_sync_behavior() -> None:
    game = make_game()
    game.board[0][0] = 1
    engine = DummyEngine()

    old_engine = s.engine
    try:
        s.engine = engine
        s._sync_board_to_katago_locked(game)
    finally:
        s.engine = old_engine

    loadsgf_cmds = [cmd for cmd in engine.commands if cmd.startswith("loadsgf ")]
    assert loadsgf_cmds
    path = loadsgf_cmds[-1].split(" ", 1)[1]
    assert " " not in path
    assert s.Path(path).exists()
    wrapper_path = s._gtp_safe_sync_sgf_path(game)
    assert " " not in wrapper_path
    assert s.Path(wrapper_path).parent.exists()
    assert s._has_gtp_unsafe_whitespace("has space") is True


if __name__ == "__main__":
    test_build_board_sync_sgf()
    test_gtp_safe_sync_sgf_path_skips_whitespace_candidates()
    test_gtp_safe_sync_sgf_path_prefers_safe_env_candidate()
    test_sync_board_to_katago_locked_writes_sgf_and_loads_it()
    test_server_wrappers_preserve_sync_behavior()
    print("board_sync_smoke_test passed")
