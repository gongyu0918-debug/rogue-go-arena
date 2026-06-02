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
    assert triggered.message == f"🧺 提子犯规触发！白棋 提子达到 {gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD} 颗"
    assert triggered.beneficiary == "B"
    assert triggered.sync_komi is False
    assert rogue.rogue_capture_foul_progress["W"] == 0
    assert rogue.komi == 7.5

    player_capture = make_game()
    player_capture.rogue_card = "capture_foul"
    ignored = check_capture_foul(player_capture, "B", gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD, ultimate=False)
    assert ignored.triggered is False
    assert player_capture.komi == 7.5

    high_roll = make_game()
    high_roll.rogue_card = "capture_foul"
    deterministic = check_capture_foul(
        high_roll,
        "W",
        gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
        ultimate=False,
        random_value_fn=lambda: 0.99,
    )
    assert deterministic.triggered is True
    assert high_roll.rogue_capture_foul_progress["W"] == 0
    assert high_roll.komi == 7.5

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
    assert ultimate_triggered.sync_komi is True
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
        sync_calls: list[bool] = []
        old_pick_best = server_module._pick_best_point
        old_sync_board = server_module._sync_board_to_katago
        try:
            async def fake_pick_best(game_arg, color):
                assert game_arg is wrapper_game
                assert color == "B"
                return (4, 4)

            async def fake_sync_board(game_arg):
                sync_calls.append(game_arg is wrapper_game)

            async def fake_send(payload):
                sent.append(payload)

            server_module._pick_best_point = fake_pick_best
            server_module._sync_board_to_katago = fake_sync_board
            await server_module._check_capture_foul(
                wrapper_game,
                fake_send,
                "W",
                gameplay_config.ROGUE_CAPTURE_FOUL_THRESHOLD,
                ultimate=False,
            )
        finally:
            server_module._pick_best_point = old_pick_best
            server_module._sync_board_to_katago = old_sync_board
        assert sent and sent[-1]["type"] == "rogue_event"
        assert "推荐点 E5" in sent[-1]["msg"]
        assert wrapper_game.board[4][4] == 1
        assert sync_calls == [True]

    asyncio.run(wrapper_case())

    print("capture foul smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
