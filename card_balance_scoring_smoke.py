from __future__ import annotations

from app.gameplay.card_balance_scoring import (
    CardBalanceInputs,
    MoveEligibilitySample,
    score_card_balance,
)


def main() -> int:
    baseline = score_card_balance(CardBalanceInputs(
        card_id="baseline",
        holder_advantage_points=0.0,
        eligibility_samples=[MoveEligibilitySample(legal_points=300)],
    ))
    assert baseline["ai_strength_score"] > 95
    assert baseline["ai_strength_band"] == "too_strong"
    assert baseline["challenge_band"] == "target"

    quickthink_like = score_card_balance(CardBalanceInputs(
        card_id="quickthink",
        holder_advantage_points=8.0,
        eligibility_samples=[
            MoveEligibilitySample(legal_points=300, extra_turns=1),
            MoveEligibilitySample(legal_points=290, extra_turns=1),
        ],
        player_bonus_turns=1,
    ))
    assert quickthink_like["ai_strength_score"] < baseline["ai_strength_score"]
    assert quickthink_like["rogue_fun_score"] >= quickthink_like["challenge_score"]

    restriction_like = score_card_balance(CardBalanceInputs(
        card_id="tengen",
        holder_advantage_points=2.0,
        eligibility_samples=[
            MoveEligibilitySample(legal_points=300, ai_allowed_points=1, forced_ai_points=1),
            MoveEligibilitySample(legal_points=299, ai_allowed_points=13),
        ],
    ))
    assert restriction_like["eligibility"]["ai_candidate_ratio"] < 0.05
    assert restriction_like["ai_strength_score"] < baseline["ai_strength_score"]

    weakener = score_card_balance(CardBalanceInputs(
        card_id="nerf",
        holder_advantage_points=10.0,
        eligibility_samples=[MoveEligibilitySample(legal_points=300, ai_search_scale=0.05)],
        ai_search_scale=0.05,
    ))
    assert weakener["ai_strength_band"] == "too_weak"

    print("card balance scoring smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
