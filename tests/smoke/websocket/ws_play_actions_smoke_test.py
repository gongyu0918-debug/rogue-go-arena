from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
from app.config.gameplay import ROGUE_HANDICAP_REQUIRED_PASSES, ROGUE_METHODICAL_BASE_PLAYS
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_play_actions import handle_play


class FakeEngine:
    def __init__(self, *, ready: bool = True, response: str = "=") -> None:
        self.ready = ready
        self.response = response
        self.commands = []

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        return self.response


class FakeContext:
    def __init__(self, game: GoGame, *, engine: FakeEngine | None = None) -> None:
        self.game = game
        self.engine = engine or FakeEngine()
        self.sent = []
        self.errors = []
        self.forbidden_points = set()
        self.capture_checks = []
        self.player_effects = []
        self.ai_response_effects = []
        self.ai_moves = []
        self.background_games = []
        self.ultimate_records = []
        self.ultimate_effects = []
        self.shadow_games = []

    def restore_game(self):
        return self.game

    def engine_state_snapshot(self) -> dict:
        return {"message": "engine offline"}

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def run_in_executor(self, func, *args):
        return func(*args)

    def coord_to_gtp(self, x: int, y: int, size: int) -> str | None:
        return coord_to_gtp(x, y, size)

    def get_ai_rogue_forbidden_points(self, game) -> set:
        return set(self.forbidden_points)

    async def check_capture_foul(self, game, send_fn, color: str, captured: int, *, ultimate: bool) -> None:
        self.capture_checks.append((game, color, captured, ultimate))

    async def apply_player_rogue_move_effects(self, game, send_fn, x: int, y: int, color: str, captured: int) -> None:
        self.player_effects.append((game, x, y, color, captured))

    async def apply_ai_rogue_response_effects(self, game, send_fn, x: int, y: int, color: str) -> None:
        self.ai_response_effects.append((game, x, y, color))

    async def ai_move(self, game, send_fn) -> None:
        self.ai_moves.append(game)

    async def do_analysis_bg(self, game) -> None:
        self.background_games.append(game)

    def ultimate_get_territory_forbidden(self, game, cv_player: int):
        return set()

    def record_ultimate_player_action(self, game) -> None:
        self.ultimate_records.append(game)
        game.ultimate_move_count += 1

    def count_stones(self, game, color_value: int) -> int:
        return sum(1 for row in game.board for cell in row if cell == color_value)

    async def apply_ultimate_effect(self, game, send_fn, x: int, y: int, color: str, card_id: str) -> bool:
        self.ultimate_effects.append((game, x, y, color, card_id))
        return False

    async def resolve_pending_ultimate_shadow_links(self, game, send_fn) -> bool:
        self.shadow_games.append(game)
        return False

    async def sync_board_to_katago(self, game) -> None:
        return None

    async def ultimate_ai_move(self, game, send_fn) -> None:
        self.ai_moves.append(game)


def make_game(*, two_player: bool = False) -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=two_player)
    game.current_player = "B"
    return game


async def smoke_two_player_play_places_current_color_without_ai_turn() -> None:
    game = make_game(two_player=True)
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)

    assert ctx.engine.commands == ["play B E5"]
    assert game.board[4][4] == 1
    assert game.moves == [("B", "E5")]
    assert game.current_player == "W"
    assert ctx.capture_checks == [(game, "B", 0, False)]
    assert ctx.player_effects == [(game, 4, 4, "B", 0)]
    assert ctx.ai_response_effects == [(game, 4, 4, "B")]
    assert ctx.ai_moves == []
    assert ctx.background_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_state"]


async def smoke_ai_game_waits_for_ready_engine() -> None:
    game = make_game()
    ctx = FakeContext(game, engine=FakeEngine(ready=False))

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["engine offline"]
    assert game.moves == []
    assert ctx.sent == []


async def smoke_ai_observer_rejects_manual_play() -> None:
    game = make_game()
    game.ai_observer = True
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["AI 学习模式不接受人工落子"]
    assert game.moves == []
    assert ctx.engine.commands == []
    assert ctx.sent == []


async def smoke_rogue_handicap_requires_passes_before_play() -> None:
    game = make_game()
    game.rogue_card = "handicap_quest"
    game.rogue_handicap_passes = ROGUE_HANDICAP_REQUIRED_PASSES - 1
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["🏋️ 让子棋任务：还需虚手 1 次才能落子"]
    assert game.moves == []
    assert ctx.engine.commands == []


async def smoke_occupied_point_is_rejected_before_engine_play() -> None:
    game = make_game()
    game.board[4][4] = 1
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["该位置已有棋子"]
    assert game.moves == []
    assert ctx.engine.commands == []


async def smoke_ai_rogue_forbidden_point_is_rejected() -> None:
    game = make_game()
    ctx = FakeContext(game)
    ctx.forbidden_points = {(4, 4)}

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["这里已被 AI 的 Rogue 卡限制，当前不能落子"]
    assert game.moves == []
    assert ctx.engine.commands == []


async def smoke_puppet_reserved_point_is_rejected() -> None:
    game = make_game()
    game.rogue_card = "puppet"
    game.rogue_puppet_target = (4, 4)
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["该点已被傀儡术预留给 AI"]
    assert game.moves == []
    assert ctx.engine.commands == []


async def smoke_engine_rejects_invalid_play_without_mutating_board() -> None:
    game = make_game()
    ctx = FakeContext(game, engine=FakeEngine(response="? illegal move"))

    await handle_play(ctx, {"x": 4, "y": 4})

    assert ctx.errors == ["无效落子: E5"]
    assert game.board[4][4] == 0
    assert game.moves == []
    assert ctx.engine.commands == ["play B E5"]


async def smoke_rogue_skip_ai_keeps_player_turn() -> None:
    game = make_game()
    game.rogue_card = "twin"
    game.rogue_skip_ai = True
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)

    assert game.moves == [("B", "E5")]
    assert game.rogue_skip_ai is False
    assert game.current_player == game.player_color
    assert ctx.ai_moves == []
    assert ctx.background_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "game_state", "rogue_event"]


async def smoke_rogue_quickthink_bonus_skips_ai_once() -> None:
    game = make_game()
    game.rogue_card = "quickthink"
    game.rogue_quickthink_stage = 1
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)

    assert game.rogue_quickthink_stage == 2
    assert game.current_player == game.player_color
    assert ctx.ai_moves == []
    assert ctx.sent[-1] == {"type": "rogue_event", "msg": "⚡ 快速思考：1 秒追加手已开启"}
    assert ctx.background_games == [game]


async def smoke_rogue_methodical_keeps_player_until_quota_is_used() -> None:
    game = make_game()
    game.rogue_card = "methodical"
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})
    await asyncio.sleep(0)

    assert game.moves == [("B", "E5")]
    assert game.rogue_methodical_turns["B"] == 1
    assert game.rogue_methodical_remaining == ROGUE_METHODICAL_BASE_PLAYS - 1
    assert game.current_player == game.player_color
    assert ctx.ai_moves == []
    assert ctx.sent[-1] == {
        "type": "rogue_event",
        "msg": "📏 一板一眼：本回合还可继续落 1 子",
    }

    await handle_play(ctx, {"x": 5, "y": 4})
    await asyncio.sleep(0)

    assert game.moves == [("B", "E5"), ("B", "F5")]
    assert game.rogue_methodical_turns["B"] == 1
    assert game.rogue_methodical_remaining == 0
    assert game.current_player == game.ai_color
    assert ctx.ai_moves == [game]
    assert ctx.engine.commands == ["play B E5", "play B F5"]


async def smoke_play_dispatches_ultimate_games_to_ultimate_handler() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_player_card = "double"
    ctx = FakeContext(game)

    await handle_play(ctx, {"x": 4, "y": 4})

    assert game.moves == [("B", "E5")]
    assert game.ultimate_double_pending is True
    assert game.ultimate_extra_turn is True
    assert game.current_player == game.player_color
    assert ctx.ultimate_records == [game]
    assert ctx.ultimate_effects == [(game, 4, 4, "B", "double")]
    assert ctx.ai_moves == []
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "rogue_event"]


def smoke_ws_action_handlers_keep_play_action_name() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["play"] is handle_play


def smoke_play_action_annotations_resolve_runtime_context() -> None:
    hints = get_type_hints(ws_actions.WS_ACTION_HANDLERS["play"])
    assert hints["ctx"] is WebSocketActionContext
    assert hints["data"] is dict


async def main() -> None:
    await smoke_two_player_play_places_current_color_without_ai_turn()
    await smoke_ai_game_waits_for_ready_engine()
    await smoke_ai_observer_rejects_manual_play()
    await smoke_rogue_handicap_requires_passes_before_play()
    await smoke_occupied_point_is_rejected_before_engine_play()
    await smoke_ai_rogue_forbidden_point_is_rejected()
    await smoke_puppet_reserved_point_is_rejected()
    await smoke_engine_rejects_invalid_play_without_mutating_board()
    await smoke_rogue_skip_ai_keeps_player_turn()
    await smoke_rogue_quickthink_bonus_skips_ai_once()
    await smoke_rogue_methodical_keeps_player_until_quota_is_used()
    await smoke_play_dispatches_ultimate_games_to_ultimate_handler()
    smoke_ws_action_handlers_keep_play_action_name()
    smoke_play_action_annotations_resolve_runtime_context()
    print("ws play actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
