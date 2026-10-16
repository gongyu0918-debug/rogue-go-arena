"""Authoritative deadline for the Rogue Quick Think card.

The client starts its countdown only once the Quick Think prompt is actually
painted and visible, and reports that with `quickthink_shown`. The server then
arms one deadline on a monotonic clock. Because the "shown" report and the
player's move each cross the network once, the two delays cancel out; a small
grace window absorbs jitter. Moves that arrive after the deadline are treated
as the timeout pass, and a prompt can only be armed once, so re-sending
`quickthink_shown` cannot buy extra time.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Optional

from app.config import gameplay as gameplay_config

Clock = Callable[[], float]


def quickthink_active(game: Any) -> bool:
    return (
        getattr(game, "rogue_card", None) == "quickthink"
        and not getattr(game, "two_player", False)
        and getattr(game, "rogue_quickthink_stage", 0) > 0
        and not getattr(game, "game_over", False)
        and game.current_player == game.player_color
    )


def quickthink_key(game: Any) -> str:
    """Identifies one prompt; matches the client's `rq:<move>:<stage>` key."""
    return f"rq:{len(game.moves)}:{game.rogue_quickthink_stage}"


def quickthink_seconds(game: Any) -> float:
    if game.rogue_quickthink_stage == 1:
        return float(gameplay_config.ROGUE_QUICKTHINK_FIRST_SECONDS)
    return float(gameplay_config.ROGUE_QUICKTHINK_SECOND_SECONDS)


def arm_quickthink(game: Any, key: str, *, clock: Clock = time.monotonic) -> Optional[float]:
    """Arm the deadline for the visible prompt; return seconds granted, else None."""
    if not quickthink_active(game) or key != quickthink_key(game):
        return None
    if getattr(game, "rogue_quickthink_armed_key", "") == key:
        return None  # already armed: a repeated report must not extend the time
    seconds = quickthink_seconds(game)
    game.rogue_quickthink_armed_key = key
    game.rogue_quickthink_deadline = clock() + seconds + gameplay_config.ROGUE_QUICKTHINK_GRACE_SECONDS
    return seconds


def quickthink_expired(game: Any, *, clock: Clock = time.monotonic) -> bool:
    """True when the current prompt was armed and its deadline has passed."""
    if not quickthink_active(game):
        return False
    if getattr(game, "rogue_quickthink_armed_key", "") != quickthink_key(game):
        return False
    deadline = getattr(game, "rogue_quickthink_deadline", None)
    return deadline is not None and clock() > deadline
