"""Quick Think's bonus window, with a cooldown and a per-game cap.

Quick Think gives the player 2 seconds to move; moving in time opens a short
window for a bonus move. Opening the window on every turn let a fast player
take a bonus move all game (about +363 points in self-play), so the window
now opens at most every ROGUE_QUICKTHINK_COOLDOWN_TURNS player turns and at
most ROGUE_QUICKTHINK_MAX_BONUS times per game (0 = no cap). Turns without a
window are ordinary turns with no time pressure.
"""
from __future__ import annotations

from typing import Any

import app.config.gameplay as gameplay_config


def arm_quickthink_window(game: Any) -> bool:
    """Start a player turn for Quick Think; return True when the window opens."""
    if getattr(game, "rogue_quickthink_stage", 0) != 0:
        return False
    cap = int(gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS)
    opened = int(getattr(game, "rogue_quickthink_windows", 0))
    if cap > 0 and opened >= cap:
        return False
    wait = int(getattr(game, "rogue_quickthink_wait", 0))
    if wait > 0:
        game.rogue_quickthink_wait = wait - 1
        return False
    game.rogue_quickthink_stage = 1
    game.rogue_quickthink_windows = opened + 1
    game.rogue_quickthink_wait = max(1, int(gameplay_config.ROGUE_QUICKTHINK_COOLDOWN_TURNS)) - 1
    return True


def quickthink_windows_left(game: Any) -> int | None:
    cap = int(gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS)
    if cap <= 0:
        return None
    return max(0, cap - int(getattr(game, "rogue_quickthink_windows", 0)))
