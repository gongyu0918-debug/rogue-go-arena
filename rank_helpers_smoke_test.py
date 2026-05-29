from __future__ import annotations

from types import SimpleNamespace

import app.config.gameplay as gameplay_config
from app.gameplay.ai_moves import (
    RANK_ORDER,
    plan_rogue_ai_search,
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
