from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import tempfile
from collections import Counter
from pathlib import Path

from app.data import cards as card_data
from app.gameplay import card_selection


def smoke_disabled_cards_are_never_offered() -> None:
    disabled = set(card_data.ROGUE_DISABLED_CARDS)
    assert {"mirror", "lowline", "komi_relief"} <= disabled, disabled
    for _ in range(300):
        assert not disabled & set(card_selection.pick_rogue_choices())
        assert not disabled & set(card_selection.pick_challenge_beta_choices([]))
        assert not disabled & set(card_selection.pick_rogue_choices(pool=list(card_data.TWO_PLAYER_ROGUE_POOL)))
    # Disabled cards stay in the catalog and in the AI's own pool.
    assert disabled <= set(card_data.ROGUE_CARDS)
    assert {"blackhole", "golden_corner", "fog"} <= set(card_data.ai_rogue_cards())


def smoke_weights_lean_the_draft() -> None:
    counts: Counter[str] = Counter()
    for _ in range(3000):
        counts.update(card_selection.pick_rogue_choices())
    favoured = [card for card, weight in card_data.ROGUE_OFFER_WEIGHTS.items() if weight > 1]
    plain = [card for card in card_data.offerable_rogue_card_ids() if card not in card_data.ROGUE_OFFER_WEIGHTS]
    assert favoured and plain
    favoured_avg = sum(counts[c] for c in favoured) / len(favoured)
    plain_avg = sum(counts[c] for c in plain) / len(plain)
    assert favoured_avg > 1.5 * plain_avg, (favoured_avg, plain_avg)
    assert len(set(card_selection.pick_rogue_choices())) == 3


def smoke_old_editor_override_gains_offers_and_new_cards() -> None:
    base = json.loads(card_data.CARD_CONFIG_BASE_PATH.read_text(encoding="utf-8"))
    old = json.loads(json.dumps(base))
    old.pop("offers")
    dropped = next(iter(old["cards"]["rogue"]))
    old["cards"]["rogue"].pop(dropped)
    for pool in old["pools"].values():
        if dropped in pool:
            pool.remove(dropped)
    old["challenge"]["categories"].pop(dropped, None)
    old["meta"]["rogue"].pop(dropped, None)

    original_user_path = card_data.CARD_CONFIG_USER_PATH
    with tempfile.TemporaryDirectory() as tmp:
        user_path = Path(tmp) / "cards.json"
        user_path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        card_data.CARD_CONFIG_USER_PATH = user_path
        try:
            assert card_data.reload_card_catalog() == []
            assert dropped in card_data.ROGUE_CARDS
            assert card_data.ROGUE_DISABLED_CARDS == set(base["offers"]["rogue_disabled"])
        finally:
            card_data.CARD_CONFIG_USER_PATH = original_user_path
            assert card_data.reload_card_catalog() == []


def smoke_invalid_offers_are_rejected() -> None:
    config = card_data.export_active_card_config()
    config["offers"] = {"rogue_disabled": ["no_such_card"], "rogue_weights": {"sprout": 0}}
    errors = card_data.validate_card_config(config)
    assert any("no_such_card" in e for e in errors), errors
    assert any("rogue_weights.sprout" in e for e in errors), errors


def main() -> None:
    smoke_disabled_cards_are_never_offered()
    smoke_weights_lean_the_draft()
    smoke_old_editor_override_gains_offers_and_new_cards()
    smoke_invalid_offers_are_rejected()
    print("card offer pool smoke ok")


if __name__ == "__main__":
    main()
