"""Difficulty: one setting on the start screen instead of picking the AI's rank.

The AI always plays at the standard strength; difficulty changes the handicap.
Card games (Quick Game and runs) use a points scale, where positive points
favour the AI and are paid as komi. Plain games carry no cards, so against the
fixed AI they use traditional handicap stones instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config

DIFFICULTIES = ("beginner", "easy", "normal", "hard")
DEFAULT_DIFFICULTY = "normal"
BASE_KOMI = 7.5
HANDICAP_KOMI = 0.5


def normalize_difficulty(value: Any) -> str | None:
    """A known difficulty id, or None when the client did not pick one."""
    text = str(value).strip().lower() if value is not None else ""
    return text if text in DIFFICULTIES else None


def difficulty_points(difficulty: str) -> float:
    """Points the difficulty hands the AI in card games (negative helps the player)."""
    return float(getattr(gameplay_config, f"DIFFICULTY_{difficulty.upper()}_POINTS"))


def plain_handicap_stones(difficulty: str) -> int:
    return int(getattr(gameplay_config, f"DIFFICULTY_{difficulty.upper()}_STONES"))


def komi_for_ai_points(points_for_ai: float, ai_color: str, base: float = BASE_KOMI) -> float:
    """Komi is White's bonus, so points for the AI raise it when the AI is White."""
    return base + points_for_ai if ai_color == "W" else base - points_for_ai


@dataclass(frozen=True)
class PlainSetup:
    handicap: int
    komi: float
    player_color: str


def plain_game_setup(difficulty: str, player_color: str) -> PlainSetup:
    """Handicap stones for the player; with stones the player takes Black, as in Go."""
    stones = plain_handicap_stones(difficulty)
    if stones >= 2:
        return PlainSetup(handicap=stones, komi=HANDICAP_KOMI, player_color="B")
    return PlainSetup(handicap=0, komi=BASE_KOMI, player_color=player_color)
