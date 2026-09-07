from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.domain.game_state import GoGame


def smoke_undo_state_for_player_card_sources() -> int:
    cases = [
        ("no card", None, [], False),
        ("unrelated cards", "fog", ["dice"], False),
        ("ordinary no regret", "no_regret", [], True),
        ("ordinary quickthink", "quickthink", [], True),
        ("challenge no regret", None, ["no_regret"], True),
        ("challenge quickthink", None, ["quickthink"], True),
        ("mixed no regret", "fog", ["dice", "no_regret"], True),
        ("mixed quickthink", "fog", ["quickthink", "dice"], True),
        ("both sources", "quickthink", ["no_regret", "quickthink"], True),
    ]
    checked = 0
    for challenge_beta in (False, True):
        for label, rogue_card, challenge_cards, expected in cases:
            game = GoGame(size=9)
            game.challenge_beta = challenge_beta
            game.rogue_card = rogue_card
            game.challenge_cards = list(challenge_cards)

            # The server's undo guard checks held cards, regardless of mode flags.
            actual = game.to_state()["rogue_undo_disabled"]
            assert actual is expected, (label, challenge_beta, actual, expected)
            checked += 1
    return checked


def smoke_undo_state_refreshes_after_card_removal() -> int:
    game = GoGame(size=9)
    checked = 0
    for card in ("no_regret", "quickthink"):
        game.rogue_card = card
        assert game.to_state()["rogue_undo_disabled"] is True
        game.rogue_card = None
        assert game.to_state()["rogue_undo_disabled"] is False

        game.challenge_cards = [card]
        assert game.to_state()["rogue_undo_disabled"] is True
        game.challenge_cards.clear()
        assert game.to_state()["rogue_undo_disabled"] is False
        checked += 4
    return checked


if __name__ == "__main__":
    checked = smoke_undo_state_for_player_card_sources()
    checked += smoke_undo_state_refreshes_after_card_removal()
    print(f"game_state_undo_smoke_test passed ({checked} state checks)")
