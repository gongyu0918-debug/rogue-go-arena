from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AiMovePlacement:
    coord: tuple[int, int] | None
    captured: int = 0


def place_auxiliary_ai_move_on_board(
    game: Any,
    color: str,
    gtp_move: str,
    coord: tuple[int, int] | None,
) -> AiMovePlacement:
    captured = 0
    game.moves.append((color, gtp_move))
    if gtp_move.upper() != "PASS" and coord:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    return AiMovePlacement(coord=coord, captured=captured)
