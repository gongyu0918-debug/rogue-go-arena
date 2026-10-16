from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

from app.config import gameplay as gameplay_config
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.gameplay.ai_rally import plan_ai_rally, rally_cap, rally_lead_needed, try_apply_ai_rally
from app.gameplay.effect_utils import spawn_bonus_points


def make_game(*, lead: float, moves: int = 60, player: str = "B", stage: int = 0) -> GoGame:
    game = GoGame(size=19, player_color=player)
    game.rogue_enabled = True
    game.challenge_stage = stage
    game.moves = [("B" if i % 2 == 0 else "W", "PASS") for i in range(moves)]
    score = lead if player == "B" else -lead
    game.last_analysis = {"winrate": 0.9, "score": score, "top_moves": [], "ownership": [], "analysis_ready": True}
    return game


def smoke_close_games_are_left_alone() -> None:
    assert plan_ai_rally(make_game(lead=gameplay_config.AI_RALLY_LEAD - 0.5)) is None
    assert plan_ai_rally(make_game(lead=-30)) is None
    plan = plan_ai_rally(make_game(lead=gameplay_config.AI_RALLY_LEAD))
    assert plan is not None and plan.stones == 1
    assert plan_ai_rally(make_game(lead=2 * gameplay_config.AI_RALLY_LEAD)).stones == 2


def smoke_lead_is_read_from_the_players_side() -> None:
    assert plan_ai_rally(make_game(lead=20, player="W")) is not None
    game = make_game(lead=20, player="W")
    game.last_analysis["score"] = 20  # Black (the AI) leads
    assert plan_ai_rally(game) is None


def smoke_needs_fresh_analysis_and_a_rogue_game() -> None:
    game = make_game(lead=40)
    game.last_analysis["analysis_ready"] = False
    assert plan_ai_rally(game) is None
    for flag in ("two_player", "ai_observer", "ultimate", "game_over"):
        game = make_game(lead=40)
        setattr(game, flag, True)
        assert plan_ai_rally(game) is None, flag
    game = make_game(lead=40)
    game.rogue_enabled = False
    assert plan_ai_rally(game) is None
    assert plan_ai_rally(make_game(lead=40, moves=gameplay_config.AI_RALLY_MIN_MOVES - 1)) is None


def smoke_later_stages_rally_sooner_and_more_often() -> None:
    assert rally_lead_needed(2) < rally_lead_needed(1)
    assert rally_lead_needed(99) == gameplay_config.AI_RALLY_MIN_LEAD
    assert rally_cap(2) > rally_cap(1)
    lead = (rally_lead_needed(1) + rally_lead_needed(2)) / 2
    assert plan_ai_rally(make_game(lead=lead, stage=1)) is None
    assert plan_ai_rally(make_game(lead=lead, stage=2)) is not None


def smoke_cap_zero_turns_it_off() -> None:
    original = gameplay_config.AI_RALLY_MAX_PER_GAME
    try:
        gameplay_config.AI_RALLY_MAX_PER_GAME = 0
        assert plan_ai_rally(make_game(lead=80, stage=2)) is None
    finally:
        gameplay_config.AI_RALLY_MAX_PER_GAME = original


def smoke_rally_places_ai_stones_then_cools_down_and_caps() -> None:
    game = make_game(lead=20)
    sent: list[dict] = []
    picks = iter([(3, 3), (15, 15), (3, 15), (15, 3), (9, 9), (9, 3)])

    async def send(message):
        sent.append(message)

    async def pick_best_point(g, color):
        assert color == g.ai_color
        return next(picks)

    async def sync(_g):
        return None

    async def rally():
        return await try_apply_ai_rally(
            game, send, pick_best_point=pick_best_point, spawn_bonus_points=spawn_bonus_points,
            sync_board_to_engine=sync, coord_to_gtp=coord_to_gtp,
        )

    assert asyncio.run(rally())
    assert game.board[3][3] == 2 and game.ai_rally_count == 1
    assert sent[-1]["msg"].key == "ai.rally"
    assert sent[-1]["msg"].params["points"] == ["D16"]
    assert not asyncio.run(rally()), "cooldown"
    fired = 1
    for _ in range(gameplay_config.AI_RALLY_MAX_PER_GAME + 2):
        game.moves.extend([("B", "PASS")] * gameplay_config.AI_RALLY_COOLDOWN_MOVES)
        fired += asyncio.run(rally())
    assert fired == gameplay_config.AI_RALLY_MAX_PER_GAME, fired
    assert sent[-1]["msg"].params["remaining"] == 0


def main() -> None:
    smoke_close_games_are_left_alone()
    smoke_lead_is_read_from_the_players_side()
    smoke_needs_fresh_analysis_and_a_rogue_game()
    smoke_later_stages_rally_sooner_and_more_often()
    smoke_cap_zero_turns_it_off()
    smoke_rally_places_ai_stones_then_cools_down_and_caps()
    print("ai rally smoke test: OK")


if __name__ == "__main__":
    main()
