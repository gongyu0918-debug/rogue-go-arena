from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config


@dataclass(frozen=True)
class CaptureFoulResult:
    triggered: bool
    message: str | None = None


def apply_score_penalty(game: Any, offender: str, amount: float) -> None:
    if offender == "B":
        game.komi += amount
    else:
        game.komi -= amount


def check_capture_foul(
    game: Any,
    offender: str,
    captured: int,
    *,
    ultimate: bool,
    random_value_fn: Callable[[], float] | None = None,
) -> CaptureFoulResult:
    if captured <= 0:
        return CaptureFoulResult(False)
    if ultimate:
        return _check_ultimate_capture_foul(game, offender, captured)
    return _check_rogue_capture_foul(game, offender, captured, random_value_fn or random.random)


def _check_ultimate_capture_foul(
    game: Any,
    offender: str,
    captured: int,
) -> CaptureFoulResult:
    player_has = game.ultimate and game.ultimate_player_card == "capture_foul"
    ai_has = game.ultimate and game.ultimate_ai_card == "capture_foul"
    if not (player_has or ai_has):
        return CaptureFoulResult(False)
    if player_has and offender != game.ai_color:
        return CaptureFoulResult(False)
    if ai_has and offender != game.player_color:
        return CaptureFoulResult(False)

    progress = game.ultimate_capture_foul_progress
    progress[offender] += captured
    if progress[offender] < gameplay_config.ULTIMATE_CAPTURE_FOUL_THRESHOLD:
        return CaptureFoulResult(False)

    apply_score_penalty(game, offender, gameplay_config.ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY)
    progress[offender] = 0
    return CaptureFoulResult(
        True,
        f"🧺 提子犯规触发！{_color_label(offender)} 被罚 {gameplay_config.ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY:.0f} 目",
    )


def _check_rogue_capture_foul(
    game: Any,
    offender: str,
    captured: int,
    random_value_fn: Callable[[], float],
) -> CaptureFoulResult:
    if game.rogue_card != "capture_foul":
        return CaptureFoulResult(False)
    if offender != game.ai_color:
        return CaptureFoulResult(False)

    progress = game.rogue_capture_foul_progress
    progress[offender] += captured
    if progress[offender] < gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD:
        return CaptureFoulResult(False)

    chance = min(
        1.0,
        gameplay_config.ROGUE_CAPTURE_FOUL_BASE
        + max(0, progress[offender] - gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD)
        * gameplay_config.ROGUE_CAPTURE_FOUL_STEP,
    )
    if random_value_fn() > chance:
        return CaptureFoulResult(False)

    apply_score_penalty(game, offender, gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY)
    progress[offender] = 0
    return CaptureFoulResult(
        True,
        f"🧺 提子犯规！{_color_label(offender)} 被罚 {gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY:.1f} 目",
    )


def _color_label(color: str) -> str:
    return "黑棋" if color == "B" else "白棋"
