from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.config import gameplay as gameplay_config
from app.data import cards as card_data
from app.domain.game_state import GoGame
from app.gameplay.card_komi import card_komi_cap, card_komi_points, card_value_points, settle_card_komi


def smoke_every_offerable_card_has_a_measured_value() -> None:
    pool = set(card_data.offerable_rogue_card_ids()) | {
        c for c in card_data.CHALLENGE_BETA_POOL if c not in card_data.ROGUE_DISABLED_CARDS
    }
    missing = sorted(c for c in pool if "value_points" not in card_data.ROGUE_CARDS[c])
    assert not missing, f"cards without value_points: {missing}"


def smoke_points_follow_share_and_cap() -> None:
    share = gameplay_config.CARD_KOMI_SHARE
    assert card_komi_points([]) == 0
    one = card_komi_points(["sprout"])
    assert one == round(min(card_komi_cap(1), share * max(0.0, card_value_points("sprout"))) * 2) / 2
    for stage in range(1, 6):
        assert card_komi_points(list(card_data.ROGUE_CARDS), stage) == card_komi_cap(stage), "a huge deck is capped"
    assert card_komi_points(["sprout", "sprout"]) == one, "duplicates count once"


def smoke_caps_escalate_by_stage_under_the_ceiling() -> None:
    caps = [card_komi_cap(stage) for stage in range(1, 6)]
    assert caps == sorted(caps) and caps[0] < caps[-1], caps
    assert caps[0] <= 15, "stage 1 keeps the opening komi friendly"
    assert all(cap <= gameplay_config.CARD_KOMI_MAX for cap in caps)
    original = gameplay_config.CARD_KOMI_MAX
    try:
        gameplay_config.CARD_KOMI_MAX = 20.0
        assert card_komi_cap(5) == 20.0, "CARD_KOMI_MAX stays the overall ceiling"
    finally:
        gameplay_config.CARD_KOMI_MAX = original


def smoke_points_scale_with_board_size() -> None:
    full = card_komi_points(["momentum"], 1, 19)
    assert card_komi_points(["momentum"], 1, 13) < full
    assert card_komi_points(["momentum"], 1, 9) < card_komi_points(["momentum"], 1, 13)
    game = GoGame(size=9, komi=7.5, player_color="B")
    game.rogue_card = "momentum"
    assert settle_card_komi(game) == card_komi_points(["momentum"], 1, 9)


def smoke_settle_moves_komi_toward_the_ai_once() -> None:
    for player, sign in (("B", 1), ("W", -1)):
        game = GoGame(size=19, komi=7.5, player_color=player)
        game.rogue_card = "sprout"
        expected = card_komi_points(["sprout"])
        assert settle_card_komi(game) == expected
        assert game.komi == 7.5 + sign * expected, (player, game.komi)
        assert settle_card_komi(game) == 0, "settling twice charges nothing more"
        game.challenge_cards = ["god_hand"]
        delta = settle_card_komi(game)
        assert delta == card_komi_points(["god_hand", "sprout"]) - expected
        assert game.to_state()["card_komi_points"] == game.card_komi_points


def main() -> None:
    smoke_every_offerable_card_has_a_measured_value()
    smoke_points_follow_share_and_cap()
    smoke_caps_escalate_by_stage_under_the_ceiling()
    smoke_points_scale_with_board_size()
    smoke_settle_moves_komi_toward_the_ai_once()
    print("card komi smoke test: OK")


if __name__ == "__main__":
    main()
