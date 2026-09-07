from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.domain.sgf import gtp_to_sgf


def _matches_replayed_position(game: Any, board: list[list[int]], moves: list) -> bool:
    replay = GoGame(size=game.size, komi=game.komi)
    replay.board = [row[:] for row in board]
    for color, move in moves:
        if color not in {"B", "W"}:
            return False
        if move.upper() == "PASS":
            replay.ko_point = None
            continue
        coord = gtp_to_coord(move, game.size)
        if coord is None or replay.board[coord[1]][coord[0]] != 0:
            return False
        if replay.place_stone(*coord, color) < 0:
            return False
    return replay.board == game.board and replay.ko_point == getattr(game, "ko_point", None)


def _sync_position(game: Any) -> tuple[list[list[int]], list]:
    moves = list(getattr(game, "moves", []))
    empty_board = [[0] * game.size for _ in range(game.size)]
    if _matches_replayed_position(game, empty_board, moves):
        return empty_board, moves

    # Cards can change the board without a normal move. Keep that exact setup,
    # but reconstruct and replay the latest ko capture so the engine sees its ban.
    ko = getattr(game, "ko_point", None)
    if ko is not None and moves:
        color, move = moves[-1]
        coord = gtp_to_coord(move, game.size)
        if coord is not None and ko[2] == (2 if color == "B" else 1):
            before_capture = [row[:] for row in game.board]
            before_capture[coord[1]][coord[0]] = 0
            before_capture[ko[1]][ko[0]] = ko[2]
            if _matches_replayed_position(game, before_capture, [moves[-1]]):
                return before_capture, [moves[-1]]
    return game.board, []


def build_board_sync_sgf(game: Any) -> str:
    board, moves = _sync_position(game)
    sgf = f"(;GM[1]FF[4]CA[UTF-8]RU[chinese]SZ[{game.size}]KM[{game.komi}]"
    first_player = moves[0][0] if moves else getattr(game, "current_player", None)
    if first_player in {"B", "W"}:
        sgf += f"PL[{first_player}]"
    blacks: list[str] = []
    whites: list[str] = []
    for y in range(game.size):
        for x in range(game.size):
            if board[y][x] == 1:
                blacks.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
            elif board[y][x] == 2:
                whites.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
    if blacks:
        sgf += "AB" + "".join(f"[{point}]" for point in blacks)
    if whites:
        sgf += "AW" + "".join(f"[{point}]" for point in whites)
    for color, move in moves:
        sgf += f";{color}[{gtp_to_sgf(move, game.size)}]"
    return sgf + ")"


def has_gtp_unsafe_whitespace(path: str) -> bool:
    return any(ch.isspace() for ch in path)


def gtp_safe_sync_sgf_path(
    game: Any,
    *,
    base_dir: Path,
    env: Mapping[str, str] | None = None,
    temp_dir: str | None = None,
    process_id: int | None = None,
) -> str:
    runtime_env = os.environ if env is None else env
    base_drive = Path(base_dir).anchor
    candidates = [
        runtime_env.get("ROGUE_GO_ARENA_GTP_TMP"),
        tempfile.gettempdir() if temp_dir is None else temp_dir,
        os.path.join(base_drive, "rogue-go-arena-gtp") if base_drive else None,
        os.path.join(runtime_env.get("PUBLIC", r"C:\Users\Public"), "rogue-go-arena-gtp"),
        r"C:\Temp\rogue-go-arena-gtp",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.abspath(candidate)
        if has_gtp_unsafe_whitespace(candidate):
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            pid = os.getpid() if process_id is None else process_id
            filename = f"sync-{pid}-{id(game)}.sgf"
            return Path(candidate, filename).as_posix()
        except OSError:
            continue
    raise RuntimeError("No whitespace-free writable path available for KataGo SGF sync")


def sync_board_to_katago_locked(
    game: Any,
    engine: Any,
    *,
    base_dir: Path,
    env: Mapping[str, str] | None = None,
    temp_dir: str | None = None,
    process_id: int | None = None,
) -> str:
    sgf = build_board_sync_sgf(game)
    path = gtp_safe_sync_sgf_path(
        game,
        base_dir=base_dir,
        env=env,
        temp_dir=temp_dir,
        process_id=process_id,
    )
    Path(path).write_text(sgf, encoding="utf-8")
    response = engine._send_command_locked(f"loadsgf {path}")
    if response.lstrip().startswith("?"):
        raise RuntimeError(f"KataGo board sync failed: {response}")
    return path
