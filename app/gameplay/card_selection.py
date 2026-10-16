from __future__ import annotations

import random
import time
from typing import Optional

from app.config import gameplay as gameplay_config
from app.data.cards import (
    CHALLENGE_BETA_POOL,
    ROGUE_FEATURED_CARDS,
    ULTIMATE_FEATURED_CARDS,
    ai_rogue_cards,
    ai_ultimate_cards,
    challenge_card_category,
    challenge_category_counts,
    featured_rogue_cards,
    featured_ultimate_cards,
    rogue_card_ids,
    ultimate_card_ids,
)


def pick_rogue_choices(n: int = 3, pool: Optional[list[str]] = None) -> list[str]:
    rng = random.Random(time.time_ns())
    keys = rogue_card_ids(pool)
    rng.shuffle(keys)
    choices = keys[:n]
    if choices and not any(card in ROGUE_FEATURED_CARDS for card in choices):
        featured_pool = featured_rogue_cards(keys)
        if featured_pool:
            choices[-1] = rng.choice(featured_pool)
    return _dedupe_fill(choices, keys, n)


def pick_challenge_beta_choices(
    selected_cards: list[str],
    n: int = 3,
    pool: Optional[list[str]] = None,
) -> list[str]:
    rng = random.Random(time.time_ns())
    base_pool = rogue_card_ids(pool or CHALLENGE_BETA_POOL, exclude=selected_cards)
    if len(base_pool) <= n:
        return base_pool[:n]

    weights = {card_id: 1.0 for card_id in base_pool}
    counts = challenge_category_counts(selected_cards)
    for card_id in base_pool:
        category = challenge_card_category(card_id)
        if category and counts.get(category, 0) > 0:
            weights[card_id] += gameplay_config.CHALLENGE_STAGE_BIAS_WEIGHT * counts[category]

    choices = _weighted_unique_sample(base_pool, n, weights, rng)
    if choices and not any(card in ROGUE_FEATURED_CARDS for card in choices):
        featured_pool = featured_rogue_cards(base_pool)
        if featured_pool:
            choices[-1] = rng.choice(featured_pool)
    return choices


def pick_ai_rogue_card(exclude: Optional[list[str]] = None) -> str:
    rng = random.Random(time.time_ns())
    pool = ai_rogue_cards(exclude)
    return rng.choice(pool or ai_rogue_cards())


def pick_ultimate_choices(n: int = 3, exclude: Optional[list[str]] = None) -> list[str]:
    rng = random.Random(time.time_ns())
    keys = ultimate_card_ids(exclude)
    rng.shuffle(keys)
    choices = keys[:n]
    if choices and not any(card in ULTIMATE_FEATURED_CARDS for card in choices):
        featured_pool = featured_ultimate_cards(keys)
        if featured_pool:
            choices[-1] = rng.choice(featured_pool)
    return _dedupe_fill(choices, keys, n)


def pick_ai_ultimate_card(exclude: Optional[list[str]] = None) -> str:
    rng = random.Random(time.time_ns())
    pool = ai_ultimate_cards(exclude)
    return rng.choice(pool or ai_ultimate_cards())


def _dedupe_fill(choices: list[str], keys: list[str], n: int) -> list[str]:
    unique_choices: list[str] = []
    for card in choices:
        if card not in unique_choices:
            unique_choices.append(card)
    for card in keys:
        if len(unique_choices) >= n:
            break
        if card not in unique_choices:
            unique_choices.append(card)
    return unique_choices[:n]


def _weighted_unique_sample(
    pool: list[str],
    n: int,
    weights: dict[str, float],
    rng: random.Random,
) -> list[str]:
    available = list(pool)
    chosen: list[str] = []
    while available and len(chosen) < n:
        total = sum(max(0.01, weights.get(card_id, 1.0)) for card_id in available)
        roll = rng.random() * total
        upto = 0.0
        picked = available[-1]
        for card_id in available:
            upto += max(0.01, weights.get(card_id, 1.0))
            if upto >= roll:
                picked = card_id
                break
        chosen.append(picked)
        available.remove(picked)
    return chosen
