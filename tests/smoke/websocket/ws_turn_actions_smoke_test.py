from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
from app.config.gameplay import ROGUE_HANDICAP_REQUIRED_PASSES
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_turn_actions import handle_pass, handle_score, handle_undo


class FakeEngine:
    def __init__(self, *, ready: bool = True, final_score: str = "= W+2.5") -> None:
        self.ready = ready
        self.final_score = final_score
        self.commands = []

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        if command == "final_score":
            return self.final_score
        return "="


class FakeContext:
    def __init__(self, game: GoGame, *, engine: FakeEngine | None = None) -> None:
        self.game_id = "turn-actions"
        self.game = game
        self.engine = engine or FakeEngine()
        self.sent = []
        self.errors = []
        self.analysis_games = []
        self.background_games = []
        self.synced_games = []
        self.prepared_games = []
        self.ai_move_games = []
        self.ultimate_ai_games = []
        self.force_score_games = []
        self.ultimate_records = []
        self.finished_quickthink = []
        self.challenge_remaining_value = 1
        self.challenge_calls = []

    def restore_game(self):
        return self.game

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def run_in_executor(self, func, *args):
        return func(*args)

    async def ai_move(self, game, send_fn) -> None:
        self.ai_move_games.append(game)

    async def ultimate_ai_move(self, game, send_fn) -> None:
        self.ultimate_ai_games.append(game)

    async def ultimate_force_score(self, game, send_fn) -> None:
        self.force_score_games.append(game)
        game.game_over = True

    async def do_analysis_bg(self, game) -> None:
        self.background_games.append(game)

    async def do_analysis(self, game):
        self.analysis_games.append(game)
        return {"analysis_ready": True, "moves": len(game.moves)}

    async def sync_board_to_katago(self, game) -> None:
        self.synced_games.append(game)

    def prepare_player_turn_modifiers(self, game) -> None:
        self.prepared_games.append(game)

    def rogue_has(self, game, card_id: str) -> bool:
        return game.rogue_card == card_id

    def challenge_remaining(self, game, kind: str) -> int:
        self.challenge_calls.append((game, kind))
        return self.challenge_remaining_value

    def finish_ultimate_quickthink_turn(self, game) -> None:
        self.finished_quickthink.append(game)
        game.ultimate_quickthink_active = False

    def record_ultimate_player_action(self, game) -> None:
        self.ultimate_records.append(game)


def make_game(*, two_player: bool = False) -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=two_player)
    game.current_player = "B"
    return game


def add_move(game: GoGame, color: str, x: int, y: int) -> None:
    game.place_stone(x, y, color)
    game.moves.append((color, coord_to_gtp(x, y, game.size)))
    game.current_player = "W" if color == "B" else "B"
    game.push_history()


async def smoke_pass_records_two_player_pass_and_background_analysis() -> None:
    game = make_game(two_player=True)
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert ctx.engine.commands == ["play B pass"]
    assert game.moves == [("B", "pass")]
    assert game.passed["B"] is True
    assert game.current_player == "W"
    assert ctx.sent[-1]["type"] == "game_state"
    assert ctx.background_games == [game]
    assert ctx.ai_move_games == []


async def smoke_pass_completes_handicap_quest_and_runs_ai() -> None:
    game = make_game()
    game.rogue_card = "handicap_quest"
    game.rogue_handicap_passes = ROGUE_HANDICAP_REQUIRED_PASSES - 1
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert game.rogue_handicap_active is True
    assert ctx.engine.commands == ["play B pass"]
    assert ctx.sent[0]["type"] == "rogue_event"
    assert "让子棋任务完成" in ctx.sent[0]["msg"]
    assert ctx.sent[1]["type"] == "game_state"
    assert ctx.ai_move_games == [game]
    assert ctx.background_games == [game]


async def smoke_ultimate_pass_records_action_and_runs_ai() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_player_card = "double"
    game.ultimate_double_pending = True
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert ctx.ultimate_records == [game]
    assert ctx.finished_quickthink == [game]
    assert game.moves == [("B", "pass")]
    assert game.passed["B"] is True
    assert game.current_player == "W"
    assert game.ultimate_double_pending is False
    assert ctx.ultimate_ai_games == [game]
    assert ctx.background_games == [game]
    assert ctx.sent[-1]["type"] == "game_state"


async def smoke_ultimate_quickthink_pass_finishes_turn() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert ctx.finished_quickthink == [game]
    assert ctx.ultimate_records == []
    assert game.moves == []
    assert game.current_player == game.ai_color
    assert ctx.ultimate_ai_games == [game]
    assert ctx.background_games == [game]
    assert ctx.sent[-1]["type"] == "game_state"


async def smoke_ultimate_pass_force_scores_at_move_limit() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_player_card = "double"
    game.ultimate_move_count = 20
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert ctx.force_score_games == [game]
    assert ctx.ultimate_ai_games == []
    assert ctx.background_games == []
    assert game.game_over is True


async def smoke_ultimate_quickthink_pass_force_scores_at_move_limit() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True
    game.ultimate_move_count = 20
    ctx = FakeContext(game)

    await handle_pass(ctx, {})
    await asyncio.sleep(0)

    assert ctx.finished_quickthink == [game]
    assert ctx.force_score_games == [game]
    assert ctx.ultimate_ai_games == []
    assert ctx.background_games == []
    assert game.game_over is True


async def smoke_undo_restores_history_syncs_and_analyzes() -> None:
    game = make_game()
    add_move(game, "B", 4, 4)
    add_move(game, "W", 3, 3)
    ctx = FakeContext(game)

    await handle_undo(ctx, {})

    assert game.moves == []
    assert game.game_over is False
    assert game.winner is None
    assert ctx.synced_games == [game]
    assert ctx.prepared_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "analysis"]
    assert ctx.analysis_games == [game]


async def smoke_challenge_undo_checks_usage_gate_and_respects_limit() -> None:
    game = make_game()
    add_move(game, "B", 4, 4)
    game.challenge_beta = True
    game.challenge_usage["undo"] = 0
    original_undo_history = game.undo_history
    observed_usage_before_restore = []

    def undo_history(steps: int) -> bool:
        observed_usage_before_restore.append(game.challenge_usage["undo"])
        return original_undo_history(steps)

    game.undo_history = undo_history
    allowed_ctx = FakeContext(game)

    await handle_undo(allowed_ctx, {})

    assert allowed_ctx.challenge_calls == [(game, "undo")]
    assert observed_usage_before_restore == [1]
    assert allowed_ctx.errors == []
    assert [payload["type"] for payload in allowed_ctx.sent] == ["game_state", "analysis"]

    blocked_game = make_game()
    add_move(blocked_game, "B", 4, 4)
    blocked_game.challenge_beta = True
    blocked_game.challenge_usage["undo"] = 0
    blocked_ctx = FakeContext(blocked_game)
    blocked_ctx.challenge_remaining_value = 0

    await handle_undo(blocked_ctx, {})

    assert blocked_ctx.challenge_calls == [(blocked_game, "undo")]
    assert blocked_game.challenge_usage["undo"] == 0
    assert blocked_ctx.errors == ["测试版闯关：悔棋次数已用完"]
    assert blocked_ctx.sent == []
    assert blocked_ctx.synced_games == []


async def smoke_undo_respects_no_regret_guard() -> None:
    game = make_game()
    add_move(game, "B", 4, 4)
    game.rogue_card = "no_regret"
    ctx = FakeContext(game)

    await handle_undo(ctx, {})

    assert ctx.errors == ["这张卡会禁用悔棋"]
    assert ctx.sent == []
    assert ctx.synced_games == []


async def smoke_observer_rejects_user_turn_mutations() -> None:
    pass_game = make_game()
    pass_game.ai_observer = True
    pass_ctx = FakeContext(pass_game)
    await handle_pass(pass_ctx, {})

    undo_game = make_game()
    undo_game.ai_observer = True
    add_move(undo_game, "B", 4, 4)
    undo_ctx = FakeContext(undo_game)
    await handle_undo(undo_ctx, {})

    score_game = make_game()
    score_game.ai_observer = True
    score_ctx = FakeContext(score_game)
    await handle_score(score_ctx, {})

    expected_error = "AI 学习模式不接受人工操作"
    assert pass_ctx.errors == [expected_error]
    assert pass_game.moves == []
    assert pass_ctx.engine.commands == []
    assert undo_ctx.errors == [expected_error]
    assert len(undo_game.moves) == 1
    assert undo_ctx.synced_games == []
    assert score_ctx.errors == [expected_error]
    assert score_game.game_over is False
    assert score_ctx.engine.commands == []


async def smoke_score_syncs_engine_and_marks_winner() -> None:
    game = make_game()
    ctx = FakeContext(game, engine=FakeEngine(final_score="= W+2.5"))

    await handle_score(ctx, {})

    assert ctx.synced_games == [game]
    assert ctx.engine.commands == ["final_score"]
    assert game.game_over is True
    assert game.winner == "W"
    assert ctx.sent == [
        {
            "type": "game_over",
            "winner": "W",
            "score": "W+2.5",
            "reason": "score",
        }
    ]


async def smoke_score_parses_black_and_draw_results() -> None:
    black_game = make_game()
    black_ctx = FakeContext(black_game, engine=FakeEngine(final_score="= B+1.5"))
    await handle_score(black_ctx, {})
    assert black_game.winner == "B"
    assert black_ctx.sent[-1]["score"] == "B+1.5"

    draw_game = make_game()
    draw_ctx = FakeContext(draw_game, engine=FakeEngine(final_score="= 0"))
    await handle_score(draw_ctx, {})
    assert draw_game.winner == "draw"
    assert draw_ctx.sent[-1]["score"] == "0"


def smoke_ws_action_handlers_keep_turn_action_names() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["pass"] is handle_pass
    assert ws_actions.WS_ACTION_HANDLERS["undo"] is handle_undo
    assert ws_actions.WS_ACTION_HANDLERS["score"] is handle_score


def smoke_turn_action_annotations_resolve_runtime_context() -> None:
    for action in ("pass", "undo", "score"):
        handler = ws_actions.WS_ACTION_HANDLERS[action]
        hints = get_type_hints(handler)
        assert hints["ctx"] is WebSocketActionContext
        assert hints["data"] is dict


async def main() -> None:
    await smoke_pass_records_two_player_pass_and_background_analysis()
    await smoke_pass_completes_handicap_quest_and_runs_ai()
    await smoke_ultimate_pass_records_action_and_runs_ai()
    await smoke_ultimate_quickthink_pass_finishes_turn()
    await smoke_ultimate_pass_force_scores_at_move_limit()
    await smoke_ultimate_quickthink_pass_force_scores_at_move_limit()
    await smoke_undo_restores_history_syncs_and_analyzes()
    await smoke_challenge_undo_checks_usage_gate_and_respects_limit()
    await smoke_undo_respects_no_regret_guard()
    await smoke_observer_rejects_user_turn_mutations()
    await smoke_score_syncs_engine_and_marks_winner()
    await smoke_score_parses_black_and_draw_results()
    smoke_ws_action_handlers_keep_turn_action_names()
    smoke_turn_action_annotations_resolve_runtime_context()
    print("ws turn actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
