"""Card-strength komi: the stronger your cards, the more komi the AI receives.

Each Rogue card has a measured value_points in cards.json: about how many
points it gains its holder in a game against the standard AI. The AI gets
CARD_KOMI_SHARE of the total for the cards you hold, capped per stage, so a
strong deck still wins comfortably, just not by sixty. Rogue mode (one card,
one game) uses ROGUE_CARD_KOMI_SHARE and ROGUE_CARD_KOMI_MAX instead. The charge is
settled when cards are picked, before the first move, never mid-game.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import app.config.gameplay as gameplay_config
from app.data import cards as card_data
from app.gameplay.run_curve import board_scale


def card_value_points(card_id: str, rogue_mode: bool = False) -> float:
    """The card's measured value; Rogue mode prefers rogue_points, measured in
    single Rogue-mode games, since one card can be worth far more there."""
    card = card_data.ROGUE_CARDS.get(card_id) or {}
    value = card.get("value_points", gameplay_config.CARD_DEFAULT_POINTS)
    if rogue_mode:
        value = card.get("rogue_points", value)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def card_komi_cap(stage: int = 1) -> float:
    """The cap for a stage (Quick Game counts as stage 1), never above CARD_KOMI_MAX."""
    stage = min(max(int(stage or 1), 1), 5)
    stage_cap = float(getattr(gameplay_config, f"CARD_KOMI_MAX_STAGE{stage}", gameplay_config.CARD_KOMI_MAX))
    return min(stage_cap, float(gameplay_config.CARD_KOMI_MAX))


def card_komi_points(
    card_ids: Iterable[str], stage: int = 1, size: int = 19, rogue_mode: bool = False,
) -> float:
    """Points the AI receives for this set of held cards, scaled to the board.

    Runs use the stage's share and cap; Rogue mode (a single game) has its own."""
    total = sum(max(0.0, card_value_points(card_id, rogue_mode)) for card_id in dict.fromkeys(card_ids) if card_id)
    if rogue_mode:
        points = min(float(gameplay_config.ROGUE_CARD_KOMI_MAX), gameplay_config.ROGUE_CARD_KOMI_SHARE * total)
    else:
        points = min(card_komi_cap(stage), gameplay_config.CARD_KOMI_SHARE * total)
    return round(points * board_scale(size) * 2) / 2


def held_card_ids(game: Any) -> list[str]:
    cards = list(getattr(game, "challenge_cards", []) or [])
    if getattr(game, "rogue_card", None):
        cards.append(game.rogue_card)
    return list(dict.fromkeys(cards))


def settle_card_komi(game: Any) -> float:
    """Bring the AI's card komi in line with the cards held now; return the change.

    Komi is White's bonus, so points for the AI raise it when the AI is White.
    """
    run = bool(getattr(game, "challenge_beta", False))
    stage = getattr(game, "challenge_stage", 0) if run else 1
    target = card_komi_points(held_card_ids(game), stage or 1, getattr(game, "size", 19), rogue_mode=not run)
    delta = target - float(getattr(game, "card_komi_points", 0.0))
    if delta:
        game.komi = game.komi + delta if game.ai_color == "W" else game.komi - delta
        game.card_komi_points = target
    return delta
