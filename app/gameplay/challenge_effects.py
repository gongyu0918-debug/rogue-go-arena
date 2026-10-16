from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config
from app.domain.event_text import event_text
from app.gameplay.rogue_effects import (
    challenge_category_counts_for_game,
    challenge_has_set,
)


RandomFloatFn = Callable[[], float]
WeakenRankFn = Callable[[str], str]

# Trap bonus sources arrive as Chinese card names; keyed messages send card ids.
TRAP_SOURCE_CARD_IDS = {"三三陷阱": "sansan_trap", "神之一手": "god_hand"}

CHALLENGE_SET_LABELS = {
    "derivative": "衍生",
    "trap": "陷阱",
    "zone": "限位",
    "restriction": "限制",
    "active": "主动",
}


@dataclass(frozen=True)
class ChallengeLevelDecayResult:
    new_level: str
    message: str


def apply_challenge_trap_bonus(
    game: Any,
    source_name: str,
    *,
    roll_random: RandomFloatFn,
    chance: float = gameplay_config.CHALLENGE_TRAP_EXTRA_TURN_CHANCE,
) -> str | None:
    if not challenge_has_set(game, "trap"):
        return None
    if roll_random() > chance:
        return None
    game.rogue_skip_ai = True
    return event_text(
        "challenge.trap_bonus",
        f"陷阱套装触发：{source_name} 额外夺得一次落子权",
        card=TRAP_SOURCE_CARD_IDS.get(source_name, source_name),
    )


def apply_challenge_level_decay(
    game: Any,
    *,
    roll_random: RandomFloatFn,
    weaken_rank_one_step: WeakenRankFn,
    rank_labels: Mapping[str, str],
    chance: float = gameplay_config.CHALLENGE_RESTRICTION_DECAY_CHANCE,
) -> ChallengeLevelDecayResult | None:
    if not challenge_has_set(game, "restriction"):
        return None
    if roll_random() >= chance:
        return None
    new_level = weaken_rank_one_step(game.level)
    if new_level == game.level:
        return None
    game.level = new_level
    label = rank_labels.get(game.level, game.level)
    return ChallengeLevelDecayResult(
        new_level=game.level,
        message=event_text("challenge.restriction_decay", f"限制套装触发：AI 临时下调至 {label}", rank=game.level),
    )


def challenge_set_bonus_status_message(
    game: Any,
    *,
    labels: Mapping[str, str] = CHALLENGE_SET_LABELS,
    min_count: int = gameplay_config.CHALLENGE_SET_MIN_COUNT,
) -> str | None:
    if not getattr(game, "challenge_beta", False):
        return None
    counts = challenge_category_counts_for_game(game)
    active = [key for key, count in counts.items() if count >= min_count]
    if not active:
        return None
    return event_text(
        "challenge.sets_active",
        f"闯关套装已激活：{' / '.join(labels[key] for key in active)}",
        sets=active,
    )
