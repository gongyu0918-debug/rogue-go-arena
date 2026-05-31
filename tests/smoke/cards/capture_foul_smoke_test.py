from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import app.config.gameplay as gameplay_config
import server as server_module
from app.domain.game_state import GoGame
from app.gameplay.capture_foul import check_capture_foul


def make_game() -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k")
    game.ai_color = "W"
    return game


def main() -> int:
    rogue = make_game()
    rogue.rogue_card = "capture_foul"
    partial = check_capture_foul(
        rogue,
        "W",
        gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD - 1,
        ultimate=False,
    )
    assert partial.triggered is False
    assert rogue.rogue_capture_foul_progress["W"] == gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD - 1
    assert rogue.komi == 7.5

    triggered = check_capture_foul(rogue, "W", 1, ultimate=False, random_value_fn=lambda: 0.0)
    assert triggered.triggered is True
    assert triggered.message == f"🧺 提子犯规！白棋 被罚 {gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY:.1f} 目"
    assert rogue.rogue_capture_foul_progress["W"] == 0
    assert rogue.komi == 7.5 - gameplay_config.ROGUE_CAPTURE_FOUL_KOMI_PENALTY

    player_capture = make_game()
    player_capture.rogue_card = "capture_foul"
    ignored = check_capture_foul(player_capture, "B", gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD, ultimate=False)
    assert ignored.triggered is False
    assert player_capture.komi == 7.5

    old_base = gameplay_config.ROGUE_CAPTURE_FOUL_BASE
    old_step = gameplay_config.ROGUE_CAPTURE_FOUL_STEP
    try:
        gameplay_config.ROGUE_CAPTURE_FOUL_BASE = 0.25
        gameplay_config.ROGUE_CAPTURE_FOUL_STEP = 0.0
        failed_roll = make_game()
        failed_roll.rogue_card = "capture_foul"
        no_trigger = check_capture_foul(
            failed_roll,
            "W",
            gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
            ultimate=False,
            random_value_fn=lambda: 0.99,
        )
        assert no_trigger.triggered is False
        assert failed_roll.rogue_capture_foul_progress["W"] == gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD
        assert failed_roll.komi == 7.5
    finally:
        gameplay_config.ROGUE_CAPTURE_FOUL_BASE = old_base
        gameplay_config.ROGUE_CAPTURE_FOUL_STEP = old_step

    ultimate = make_game()
    ultimate.ultimate = True
    ultimate.ultimate_player_card = "capture_foul"
    ultimate_partial = check_capture_foul(
        ultimate,
        "W",
        gameplay_config.ULTIMATE_CAPTURE_FOUL_THRESHOLD - 1,
        ultimate=True,
    )
    assert ultimate_partial.triggered is False
    assert ultimate.ultimate_capture_foul_progress["W"] == gameplay_config.ULTIMATE_CAPTURE_FOUL_THRESHOLD - 1

    ultimate_triggered = check_capture_foul(ultimate, "W", 1, ultimate=True)
    assert ultimate_triggered.triggered is True
    assert ultimate_triggered.message == f"🧺 提子犯规触发！白棋 被罚 {gameplay_config.ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY:.0f} 目"
    assert ultimate.ultimate_capture_foul_progress["W"] == 0
    assert ultimate.komi == 7.5 - gameplay_config.ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY

    ai_card = make_game()
    ai_card.ultimate = True
    ai_card.ultimate_ai_card = "capture_foul"
    ai_card_triggered = check_capture_foul(
        ai_card,
        "B",
        gameplay_config.ULTIMATE_CAPTURE_FOUL_THRESHOLD,
        ultimate=True,
    )
    assert ai_card_triggered.triggered is True
    assert ai_card.komi == 7.5 + gameplay_config.ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY

    async def wrapper_case() -> None:
        wrapper_game = make_game()
        wrapper_game.rogue_card = "capture_foul"
        sent: list[dict] = []
        commands: list[str] = []
        old_ready = server_module.engine.ready
        old_run_in_executor = server_module.run_in_executor
        try:
            server_module.engine.ready = True

            async def fake_run_in_executor(func, *args):
                if getattr(func, "__self__", None) is server_module.engine and getattr(func, "__name__", "") == "send_command":
                    commands.append(args[0])
                    return "="
                return func(*args)

            async def fake_send(payload):
                sent.append(payload)

            server_module.run_in_executor = fake_run_in_executor
            await server_module._check_capture_foul(
                wrapper_game,
                fake_send,
                "W",
                gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
                ultimate=False,
            )
        finally:
            server_module.run_in_executor = old_run_in_executor
            server_module.engine.ready = old_ready
        assert sent and sent[-1]["type"] == "rogue_event"
        assert commands == [f"komi {wrapper_game.komi}"]

    asyncio.run(wrapper_case())

    print("capture foul smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
