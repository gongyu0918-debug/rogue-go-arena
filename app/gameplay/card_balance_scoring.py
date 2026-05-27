from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any


BOARD_AREA = 19 * 19
TARGET_AI_MIN = 42.0
TARGET_AI_MAX = 72.0
TARGET_CHALLENGE_MIN = 45.0
TARGET_CHALLENGE_MAX = 76.0


@dataclass(frozen=True)
class MoveEligibilitySample:
    legal_points: int
    ai_forbidden_points: int = 0
    ai_allowed_points: int | None = None
    forced_ai_points: int = 0
    player_legal_points: int | None = None
    player_forbidden_points: int = 0
    extra_turns: int = 0
    skipped_ai_turns: int = 0
    ai_search_scale: float = 1.0

    @property
    def ai_candidate_ratio(self) -> float:
        legal = max(1, self.legal_points)
        if self.ai_allowed_points is not None:
            return clamp(self.ai_allowed_points / legal)
        return clamp((legal - self.ai_forbidden_points) / legal)

    @property
    def player_candidate_ratio(self) -> float:
        legal = max(1, self.player_legal_points if self.player_legal_points is not None else self.legal_points)
        return clamp((legal - self.player_forbidden_points) / legal)


@dataclass(frozen=True)
class CardBalanceInputs:
    card_id: str
    holder_advantage_points: float
    eligibility_samples: list[MoveEligibilitySample] = field(default_factory=list)
    ai_search_scale: float = 1.0
    player_bonus_turns: int = 0
    ai_denial_turns: int = 0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_band(value: float, low: float, high: float) -> str:
    if value < low:
        return "too_weak"
    if value > high:
        return "too_strong"
    return "target"


def mean_or_default(values: list[float], default: float) -> float:
    return float(mean(values)) if values else default


def summarize_move_eligibility(samples: list[MoveEligibilitySample]) -> dict[str, float]:
    if not samples:
        return {
            "ai_candidate_ratio": 1.0,
            "player_candidate_ratio": 1.0,
            "forced_ai_points": 0.0,
            "extra_turns": 0.0,
            "skipped_ai_turns": 0.0,
            "ai_search_scale": 1.0,
        }
    return {
        "ai_candidate_ratio": round(mean_or_default([s.ai_candidate_ratio for s in samples], 1.0), 4),
        "player_candidate_ratio": round(mean_or_default([s.player_candidate_ratio for s in samples], 1.0), 4),
        "forced_ai_points": round(mean_or_default([float(s.forced_ai_points) for s in samples], 0.0), 2),
        "extra_turns": round(mean_or_default([float(s.extra_turns) for s in samples], 0.0), 2),
        "skipped_ai_turns": round(mean_or_default([float(s.skipped_ai_turns) for s in samples], 0.0), 2),
        "ai_search_scale": round(mean_or_default([s.ai_search_scale for s in samples], 1.0), 4),
    }


def ai_strength_score(inputs: CardBalanceInputs) -> float:
    eligibility = summarize_move_eligibility(inputs.eligibility_samples)
    ai_mobility = eligibility["ai_candidate_ratio"]
    player_mobility = eligibility["player_candidate_ratio"]
    average_search_scale = clamp((inputs.ai_search_scale + eligibility["ai_search_scale"]) / 2.0)
    forced_pressure = clamp(eligibility["forced_ai_points"] / 8.0)
    turn_denial = clamp((inputs.ai_denial_turns + eligibility["skipped_ai_turns"]) / 4.0)
    player_turn_burst = clamp((inputs.player_bonus_turns + eligibility["extra_turns"]) / 5.0)
    score_pressure = clamp((inputs.holder_advantage_points + 15.0) / 30.0)

    raw = (
        100.0
        * average_search_scale
        * (0.68 + 0.32 * ai_mobility)
        * (1.0 - 0.20 * forced_pressure)
        * (1.0 - 0.24 * turn_denial)
        * (1.0 - 0.64 * player_turn_burst)
    )
    player_restriction_bonus = 1.0 + 0.10 * (1.0 - player_mobility)
    score_modifier = 1.10 - (0.20 * score_pressure)
    return round(max(0.0, min(100.0, raw * player_restriction_bonus * score_modifier)), 2)


def challenge_score(inputs: CardBalanceInputs) -> float:
    strength = ai_strength_score(inputs)
    advantage = clamp((inputs.holder_advantage_points + 12.0) / 24.0)
    eligibility = summarize_move_eligibility(inputs.eligibility_samples)
    restriction_tension = 1.0 - eligibility["ai_candidate_ratio"]
    turn_swing = clamp((
        inputs.player_bonus_turns
        + inputs.ai_denial_turns
        + eligibility["extra_turns"]
        + eligibility["skipped_ai_turns"]
    ) / 6.0)
    raw = (strength * 0.58) + ((1.0 - advantage) * 100.0 * 0.28) + (restriction_tension * 100.0 * 0.10) + (turn_swing * 100.0 * 0.04)
    return round(max(0.0, min(100.0, raw)), 2)


def rogue_fun_score(inputs: CardBalanceInputs) -> float:
    challenge = challenge_score(inputs)
    eligibility = summarize_move_eligibility(inputs.eligibility_samples)
    volatility = clamp(
        (abs(inputs.holder_advantage_points) / 16.0)
        + (1.0 - eligibility["ai_candidate_ratio"])
        + ((
            inputs.player_bonus_turns
            + inputs.ai_denial_turns
            + eligibility["extra_turns"]
            + eligibility["skipped_ai_turns"]
        ) / 8.0)
    )
    raw = (challenge * 0.72) + (volatility * 100.0 * 0.28)
    return round(max(0.0, min(100.0, raw)), 2)


def score_card_balance(inputs: CardBalanceInputs) -> dict[str, Any]:
    ai_score = ai_strength_score(inputs)
    challenge = challenge_score(inputs)
    fun = rogue_fun_score(inputs)
    eligibility = summarize_move_eligibility(inputs.eligibility_samples)
    player_bonus_turns = inputs.player_bonus_turns + eligibility["extra_turns"]
    ai_denial_turns = inputs.ai_denial_turns + eligibility["skipped_ai_turns"]
    return {
        "card": inputs.card_id,
        "ai_strength_score": ai_score,
        "ai_strength_band": score_band(ai_score, TARGET_AI_MIN, TARGET_AI_MAX),
        "challenge_score": challenge,
        "challenge_band": score_band(challenge, TARGET_CHALLENGE_MIN, TARGET_CHALLENGE_MAX),
        "rogue_fun_score": fun,
        "eligibility": eligibility,
        "tempo": {
            "player_bonus_turns": round(player_bonus_turns, 2),
            "ai_denial_turns": round(ai_denial_turns, 2),
            "ai_search_scale": round(inputs.ai_search_scale, 4),
        },
    }
