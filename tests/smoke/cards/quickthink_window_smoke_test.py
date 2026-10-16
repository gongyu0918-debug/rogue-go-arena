from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.config import gameplay as gameplay_config
from app.domain.game_state import GoGame
from app.gameplay.quickthink_window import arm_quickthink_window, quickthink_windows_left
from app.gameplay.turn_modifiers import prepare_player_turn_modifiers


def play_turns(game: GoGame, turns: int) -> list[bool]:
    """Simulate player turns: arm, then end the turn (the stage resets)."""
    opened = []
    for _ in range(turns):
        opened.append(arm_quickthink_window(game))
        game.rogue_quickthink_stage = 0
    return opened


def smoke_window_has_a_cooldown_and_a_cap() -> None:
    cooldown = gameplay_config.ROGUE_QUICKTHINK_COOLDOWN_TURNS
    cap = gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS
    assert cooldown > 1 and cap > 0
    game = GoGame(size=19, player_color="B")
    opened = play_turns(game, cooldown * (cap + 5))
    assert sum(opened) == cap, "never more windows than the cap"
    first = [i for i, was_open in enumerate(opened) if was_open]
    assert first[0] == 0, "the first turn opens a window"
    assert all(b - a == cooldown for a, b in zip(first, first[1:])), first
    assert quickthink_windows_left(game) == 0


def smoke_limits_off_restores_every_turn() -> None:
    saved = (gameplay_config.ROGUE_QUICKTHINK_COOLDOWN_TURNS, gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS)
    try:
        gameplay_config.ROGUE_QUICKTHINK_COOLDOWN_TURNS = 1
        gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS = 0
        game = GoGame(size=19, player_color="B")
        assert all(play_turns(game, 50))
        assert quickthink_windows_left(game) is None
    finally:
        gameplay_config.ROGUE_QUICKTHINK_COOLDOWN_TURNS, gameplay_config.ROGUE_QUICKTHINK_MAX_BONUS = saved


def smoke_turn_start_uses_the_window() -> None:
    game = GoGame(size=19, player_color="B")
    game.rogue_enabled = True
    game.rogue_card = "quickthink"
    game.current_player = "B"
    prepare_player_turn_modifiers(game)
    assert game.rogue_quickthink_stage == 1
    game.rogue_quickthink_stage = 0
    prepare_player_turn_modifiers(game)
    assert game.rogue_quickthink_stage == 0, "the next turn is on cooldown: no window, no time pressure"
    state = game.to_state()
    assert state["rogue_quickthink_stage"] == 0


def main() -> None:
    smoke_window_has_a_cooldown_and_a_cap()
    smoke_limits_off_restores_every_turn()
    smoke_turn_start_uses_the_window()
    print("quickthink window smoke test: OK")


if __name__ == "__main__":
    main()
