from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import sys

sys.argv = ["card_balance_eval.py"]

import card_balance_eval as balance  # noqa: E402
import server as s  # noqa: E402


def make_game(card_id: str | None = None) -> s.GoGame:
    game = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    game.rogue_card = card_id
    game.current_player = game.player_color
    return game


async def exercise_rogue_quickthink_turn() -> None:
    game = make_game("quickthink")
    game.rogue_quickthink_stage = 1
    ai_calls = {"count": 0}

    async def fake_choose(game_arg, color, visits, prefer_targets=None, forbidden=None):
        for y in range(game_arg.size):
            for x in range(game_arg.size):
                if game_arg.board[y][x] == 0:
                    return s.coord_to_gtp(x, y, game_arg.size), (x, y)
        return "pass", None

    async def fake_player_effect(*_args, **_kwargs):
        return None

    async def fake_ai_move(game_arg, _send):
        ai_calls["count"] += 1
        game_arg.current_player = game_arg.player_color
        s._prepare_player_turn_modifiers(game_arg)

    original_choose = balance.choose_legal_player_move
    original_effect = s._apply_player_rogue_move_effects
    original_ai_move = s._ai_move
    try:
        balance.choose_legal_player_move = fake_choose
        s._apply_player_rogue_move_effects = fake_player_effect
        s._ai_move = fake_ai_move

        first = await balance.play_player_rogue_turn(game)
        assert ai_calls["count"] == 0
        assert first == {"extra_turns": 1, "skipped_ai_turns": 1}
        assert game.current_player == game.player_color
        assert game.rogue_quickthink_stage == 2

        second = await balance.play_player_rogue_turn(game)
        assert ai_calls["count"] == 1
        assert second == {"extra_turns": 0, "skipped_ai_turns": 0}
        assert game.rogue_quickthink_stage == 1
    finally:
        balance.choose_legal_player_move = original_choose
        s._apply_player_rogue_move_effects = original_effect
        s._ai_move = original_ai_move


async def exercise_ultimate_quickthink_window() -> None:
    game = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    game.ultimate = True
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True
    ai_calls = {"count": 0}

    async def fake_choose(game_arg, color, visits, prefer_targets=None, forbidden=None):
        for y in range(game_arg.size):
            for x in range(game_arg.size):
                if game_arg.board[y][x] == 0:
                    return s.coord_to_gtp(x, y, game_arg.size), (x, y)
        return "pass", None

    async def fake_ai_move(game_arg, _send):
        ai_calls["count"] += 1
        game_arg.current_player = game_arg.player_color

    original_choose = balance.choose_legal_player_move
    original_ai_move = s._ultimate_ai_move
    original_seconds = s.ULTIMATE_QUICKTHINK_SECONDS
    try:
        balance.choose_legal_player_move = fake_choose
        s._ultimate_ai_move = fake_ai_move
        s.ULTIMATE_QUICKTHINK_SECONDS = 3

        first = await balance.play_player_ultimate_turn(game)
        second = await balance.play_player_ultimate_turn(game)
        third = await balance.play_player_ultimate_turn(game)

        assert first == {"extra_turns": 1, "skipped_ai_turns": 1}
        assert second == {"extra_turns": 1, "skipped_ai_turns": 1}
        assert third == {"extra_turns": 0, "skipped_ai_turns": 0}
        assert ai_calls["count"] == 1
        assert not game.ultimate_quickthink_active
    finally:
        balance.choose_legal_player_move = original_choose
        s._ultimate_ai_move = original_ai_move
        s.ULTIMATE_QUICKTHINK_SECONDS = original_seconds


async def exercise_ultimate_final_turn_tempo() -> None:
    game = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    game.ultimate = True
    game.ultimate_player_card = "wall"
    game.ultimate_move_count = 19

    async def fake_choose(game_arg, color, visits, prefer_targets=None, forbidden=None):
        for y in range(game_arg.size):
            for x in range(game_arg.size):
                if game_arg.board[y][x] == 0:
                    return s.coord_to_gtp(x, y, game_arg.size), (x, y)
        return "pass", None

    async def fake_force_score(game_arg, _send):
        game_arg.game_over = True

    original_choose = balance.choose_legal_player_move
    original_force_score = s._ultimate_force_score
    try:
        balance.choose_legal_player_move = fake_choose
        s._ultimate_force_score = fake_force_score

        tempo = await balance.play_player_ultimate_turn(game)
        assert tempo == {"extra_turns": 0, "skipped_ai_turns": 0}
        assert game.game_over
    finally:
        balance.choose_legal_player_move = original_choose
        s._ultimate_force_score = original_force_score


def main() -> int:
    asyncio.run(exercise_rogue_quickthink_turn())
    asyncio.run(exercise_ultimate_quickthink_window())
    asyncio.run(exercise_ultimate_final_turn_tempo())

    sansan = make_game("sansan")
    sansan_sample = balance.sample_rogue_move_eligibility(sansan, "sansan")
    assert sansan_sample.ai_allowed_points == 36

    sansan_trap = make_game("sansan_trap")
    trap_sample = balance.sample_rogue_move_eligibility(sansan_trap, "sansan_trap")
    assert trap_sample.ai_allowed_points is None

    shadow = make_game("shadow")
    shadow.moves.append((shadow.ai_color, s.coord_to_gtp(4, 4, shadow.size)))
    original_shadow_chance = s.gameplay_config.ROGUE_SHADOW_CHANCE
    try:
        s.gameplay_config.ROGUE_SHADOW_CHANCE = 0.0
        shadow_open = balance.sample_rogue_move_eligibility(shadow, "shadow")
        s.gameplay_config.ROGUE_SHADOW_CHANCE = 1.0
        shadow_forced = balance.sample_rogue_move_eligibility(shadow, "shadow")
    finally:
        s.gameplay_config.ROGUE_SHADOW_CHANCE = original_shadow_chance
    assert shadow_open.ai_allowed_points == shadow_open.legal_points
    assert shadow_forced.ai_allowed_points is not None
    assert shadow_forced.ai_allowed_points < shadow_open.ai_allowed_points

    territory = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    territory.ultimate = True
    territory.ultimate_player_card = "territory"
    territory.board[4][4] = 1
    territory_sample = balance.sample_ultimate_move_eligibility(territory, "territory")
    assert territory_sample.ai_forbidden_points > 0
    assert territory_sample.ai_forbidden_points < len(
        s._ultimate_get_territory_forbidden(territory, 1 if territory.ai_color == "B" else 2)
    )
    assert territory_sample.player_forbidden_points == 0

    quick_run = {
        "holder_advantage": 6.0,
        "eligibility_samples": [
            {
                "legal_points": 300,
                "ai_forbidden_points": 0,
                "ai_allowed_points": None,
                "forced_ai_points": 0,
                "player_forbidden_points": 0,
                "extra_turns": 5,
                "skipped_ai_turns": 5,
                "ai_search_scale": 1.0,
            }
        ],
    }
    quick = balance.merge_scored_runs("quickthink", [quick_run])
    assert quick["ai_strength_band"] == "too_weak"
    assert quick["tempo"]["player_bonus_turns"] >= 5

    print("card balance eval smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
