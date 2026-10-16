"""The run's difficulty curve: five stages that hand the AI more each time.

The player plays White in a run. Each stage gives the AI (Black) some
handicap stones and some komi points; the difficulty and (later) the
player's cards add komi points on top. Small steps are komi, big steps are
stones placed before the first move, so nothing interrupts play.

Values live in app/config/gameplay.py (RUN_STAGE<n>_AI_STONES and
RUN_STAGE<n>_KOMI_POINTS) and can be tuned in the card editor.
"""
from __future__ import annotations

from dataclasses import dataclass

import app.config.gameplay as gameplay_config

RUN_STAGES = 5
EVEN_KOMI = 7.5
HANDICAP_KOMI = 0.5
# Rough value of a handicap game over an even one, for display only:
# n stones = Black keeps the first move without komi (~7) plus ~14 per extra stone.
FIRST_MOVE_POINTS = 7.0
STONE_POINTS = 14.0


def clamp_stage(stage: int) -> int:
    return min(max(int(stage or 1), 1), RUN_STAGES)


def stage_ai_stones(stage: int) -> int:
    stones = int(getattr(gameplay_config, f"RUN_STAGE{clamp_stage(stage)}_AI_STONES", 0))
    return stones if stones >= 2 else 0


def stage_komi_points(stage: int) -> float:
    return float(getattr(gameplay_config, f"RUN_STAGE{clamp_stage(stage)}_KOMI_POINTS", 0.0))


def handicap_points(stones: int) -> float:
    return 0.0 if stones < 2 else FIRST_MOVE_POINTS + STONE_POINTS * (stones - 1)


@dataclass(frozen=True)
class RunSetup:
    stage: int
    handicap: int          # AI (Black) handicap stones
    komi: float            # White's (the player's) komi
    stage_points: float    # the stage's komi points for the AI
    difficulty_points: float
    card_points: float

    @property
    def ai_points(self) -> float:
        """About how many points the AI gets over an even game."""
        return handicap_points(self.handicap) + self.stage_points + self.difficulty_points + self.card_points


def run_stage_setup(stage: int, difficulty_points: float = 0.0, card_points: float = 0.0) -> RunSetup:
    stage = clamp_stage(stage)
    stones = stage_ai_stones(stage)
    stage_points = stage_komi_points(stage)
    base = HANDICAP_KOMI if stones else EVEN_KOMI
    komi = base - (stage_points + difficulty_points + card_points)
    return RunSetup(stage, stones, komi, stage_points, float(difficulty_points), float(card_points))
