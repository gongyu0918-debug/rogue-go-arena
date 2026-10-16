from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from app.gameplay.difficulty import difficulty_points
from app.gameplay.run_curve import RUN_STAGES, clamp_stage, run_stage_setup
from app.runtime.game_input_validation import VALID_HANDICAPS


def main() -> None:
    assert RUN_STAGES == 5
    assert clamp_stage(0) == 1 and clamp_stage(9) == RUN_STAGES

    setups = [run_stage_setup(stage) for stage in range(1, RUN_STAGES + 1)]
    points = [round(s.ai_points, 1) for s in setups]
    assert points == sorted(points) and len(set(points)) == RUN_STAGES, f"each stage must be harder: {points}"
    assert points[0] == 0, "stage 1 is an even game"
    assert setups[0].handicap == 0 and setups[0].komi == 7.5
    for s in setups:
        assert s.handicap in VALID_HANDICAPS
        if s.handicap:
            assert s.handicap >= 2
    assert setups[-1].handicap >= 2, "the last stages start with AI stones"
    print("run curve points:", points)

    # Difficulty shifts the whole curve through komi only.
    for stage in range(1, RUN_STAGES + 1):
        normal = run_stage_setup(stage, difficulty_points("normal"))
        beginner = run_stage_setup(stage, difficulty_points("beginner"))
        hard = run_stage_setup(stage, difficulty_points("hard"))
        assert beginner.handicap == normal.handicap == hard.handicap
        assert beginner.komi - normal.komi == -difficulty_points("beginner")
        assert normal.komi - hard.komi == difficulty_points("hard")
        assert beginner.ai_points < normal.ai_points < hard.ai_points

    # Card points (step 5) also come off the player's komi.
    assert run_stage_setup(2, 0, 4).komi == run_stage_setup(2).komi - 4
    print("run curve smoke test: OK")


if __name__ == "__main__":
    main()
