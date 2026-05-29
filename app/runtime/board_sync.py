from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def build_board_sync_sgf(game: Any) -> str:
    sgf = f"(;GM[1]SZ[{game.size}]KM[{game.komi}]"
    blacks: list[str] = []
    whites: list[str] = []
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] == 1:
                blacks.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
            elif game.board[y][x] == 2:
                whites.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
    if blacks:
        sgf += "AB" + "".join(f"[{point}]" for point in blacks)
    if whites:
        sgf += "AW" + "".join(f"[{point}]" for point in whites)
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
    engine._send_command_locked(f"loadsgf {path}")
    return path
