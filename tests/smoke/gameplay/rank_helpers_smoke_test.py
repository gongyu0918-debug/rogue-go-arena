from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from types import SimpleNamespace

import app.config.gameplay as gameplay_config
from app.gameplay.ai_moves import (
    RANK_ORDER,
    compute_game_visits,
    plan_rogue_ai_search,
    standard_rank_equivalent,
    weaken_rank,
    weaken_rank_one_step,
)


def main() -> int:
    assert RANK_ORDER == tuple(gameplay_config.RANK_VISITS.keys())
    assert weaken_rank("a5d", 1) == "a4d"
    assert weaken_rank("a5d", 5) == "1k"
    assert weaken_rank("3k", 1) == "4k"
    assert weaken_rank("18k", 1) == "18k"
    assert weaken_rank("unknown", 3) == "unknown"
    assert weaken_rank_one_step("p1d") == "a9d"

    # The standard AI: a fixed search budget that weakens from the nearest weaker rank.
    standard = gameplay_config.STANDARD_AI_LEVEL
    assert standard not in RANK_ORDER
    late = gameplay_config.OPENING_MOVE_THRESHOLD + 1
    assert compute_game_visits(standard, late) == gameplay_config.STANDARD_AI_VISITS
    assert compute_game_visits(standard, late, "rogue") == gameplay_config.STANDARD_AI_VISITS
    assert compute_game_visits(standard, late, cpu_mode=True) == min(gameplay_config.STANDARD_AI_VISITS, gameplay_config.CPU_MAX_VISITS)
    equivalent = standard_rank_equivalent()
    assert gameplay_config.RANK_VISITS[equivalent] < gameplay_config.STANDARD_AI_VISITS
    assert weaken_rank(standard, 0) == standard
    assert weaken_rank_one_step(standard) == equivalent
    assert weaken_rank(standard, 8) == weaken_rank(equivalent, 7)
    assert gameplay_config.RANK_VISITS[weaken_rank(standard, 8)] < gameplay_config.STANDARD_AI_VISITS * 0.1

    game = SimpleNamespace(level="a5d")
    move_count = gameplay_config.OPENING_MOVE_THRESHOLD + 5

    def fake_visits(_level: str, _move_count: int, _mode: str) -> int:
        return 1000

    nerf = plan_rogue_ai_search(
        game,
        {"nerf"},
        move_count=move_count,
        ai_move_count=0,
        get_game_visits=fake_visits,
        weaken_rank=weaken_rank,
    )
    assert nerf.mode == "rogue"
    assert nerf.effective_level == weaken_rank("a5d", 8)
    assert nerf.visits == max(30, int(1000 * gameplay_config.ROGUE_NERF_FACTOR))

    time_press = plan_rogue_ai_search(
        game,
        {"time_press"},
        move_count=move_count,
        ai_move_count=0,
        get_game_visits=fake_visits,
        weaken_rank=weaken_rank,
    )
    assert time_press.effective_level == weaken_rank("a5d", 5)
    assert time_press.visits == gameplay_config.ROGUE_TIME_PRESS_MAX_VISITS
    assert time_press.time_limit == gameplay_config.ROGUE_TIME_PRESS_MAX_TIME

    combined = plan_rogue_ai_search(
        game,
        {"nerf", "time_press"},
        move_count=move_count,
        ai_move_count=0,
        get_game_visits=fake_visits,
        weaken_rank=weaken_rank,
    )
    assert combined.effective_level == weaken_rank(weaken_rank("a5d", 8), 5)
    assert combined.visits == gameplay_config.ROGUE_TIME_PRESS_MAX_VISITS
    assert combined.time_limit == gameplay_config.ROGUE_TIME_PRESS_MAX_TIME

    print("rank helpers smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
