from __future__ import annotations

import datetime
from typing import Any

from app.domain.coordinates import GTP_COLUMNS


def gtp_to_sgf(gtp_move: str, size: int = 19) -> str:
    """Convert a GTP move such as D4 to SGF coordinates such as dd."""
    if gtp_move.upper() == "PASS":
        return ""
    try:
        col = GTP_COLUMNS.index(gtp_move[0].upper())
        row = size - int(gtp_move[1:])
        return chr(ord("a") + col) + chr(ord("a") + row)
    except (ValueError, IndexError):
        return ""


def generate_sgf(game: Any) -> str:
    """Generate the SGF export string for the current game state."""
    dt = datetime.date.today().isoformat()
    header = (
        f"(;GM[1]FF[4]CA[UTF-8]AP[rogue-go-arena:1.0]"
        f"SZ[{game.size}]KM[{game.komi}]"
        f"DT[{dt}]PB[{('Player' if game.player_color == 'B' else 'AI')}]"
        f"PW[{('Player' if game.player_color == 'W' else 'AI')}]"
        f"RE[{('B' if game.winner == 'B' else 'W') + '+' if game.winner else '?'}]"
    )
    if game.handicap > 0:
        header += f"HA[{game.handicap}]"
    header += "\n"
    body = ""
    for color, gtp in game.moves:
        sgf_coord = gtp_to_sgf(gtp, game.size)
        prop = "B" if color == "B" else "W"
        body += f";{prop}[{sgf_coord}]\n"
    return header + body + ")\n"
