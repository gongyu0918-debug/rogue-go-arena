from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
import app.runtime.ws_ultimate_actions as ws_ultimate_actions
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.data.cards import ULTIMATE_CARDS
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_ultimate_actions import (
    handle_ultimate_play,
    handle_ultimate_quickthink_end,
    handle_ultimate_select_card,
)


class FakeEngine:
    ready = True


class FakeContext:
    def __init__(self, game: GoGame) -> None:
        self.game = game
        self.engine = FakeEngine()
        self.sent = []
        self.errors = []
        self.joseki_args = []
        self.ai_pick_excludes = []
        self.ai_moves = []
        self.background_games = []
        self.capture_checks = []
        self.player_action_games = []
        self.applied_effects = []
        self.shadow_games = []
        self.synced_games = []
        self.force_scores = []
        self.quickthink_finished = []
        self.territory_forbidden = set()

    def restore_game(self):
        return self.game

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    def pick_joseki_targets(self, size: int, count: int):
        self.joseki_args.append((size, count))
        return [(index, index) for index in range(count)]

    def random_hidden_center(self, size: int, radius: int, rng):
        return (size // 2, size // 2)

    def diamond_points(self, x: int, y: int, radius: int, size: int):
        return [(x, y), (x + 1, y)]

    def pick_ai_ultimate_card(self, *, exclude):
        self.ai_pick_excludes.append(tuple(exclude))
        return "meteor"

    def coord_to_gtp(self, x: int, y: int, size: int) -> str | None:
        return coord_to_gtp(x, y, size)

    async def ultimate_ai_move(self, game, send_fn) -> None:
        self.ai_moves.append(game)

    async def do_analysis_bg(self, game) -> None:
        self.background_games.append(game)

    def ultimate_get_territory_forbidden(self, game, cv_player: int):
        return set(self.territory_forbidden)

    def record_ultimate_player_action(self, game) -> None:
        self.player_action_games.append(game)
        game.ultimate_move_count += 1

    async def check_capture_foul(self, game, send_fn, color: str, captured: int, *, ultimate: bool) -> None:
        self.capture_checks.append((game, color, captured, ultimate))

    def count_stones(self, game, color_value: int) -> int:
        return sum(1 for row in game.board for cell in row if cell == color_value)

    async def apply_ultimate_effect(self, game, send_fn, x: int, y: int, color: str, card_id: str) -> bool:
        self.applied_effects.append((game, x, y, color, card_id))
        return False

    async def resolve_pending_ultimate_shadow_links(self, game, send_fn) -> bool:
        self.shadow_games.append(game)
        return False

    async def sync_board_to_katago(self, game) -> None:
        self.synced_games.append(game)

    async def ultimate_force_score(self, game, send_fn) -> None:
        self.force_scores.append(game)

    def finish_ultimate_quickthink_turn(self, game) -> None:
        self.quickthink_finished.append(game)
        game.ultimate_quickthink_active = False
        game.ultimate_quickthink_turn_counted = False


def make_ultimate_game() -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    game.ultimate = True
    game.current_player = "B"
    game.ultimate_offer_cards = list(ULTIMATE_CARDS)
    return game


async def smoke_select_joseki_card_honors_runtime_target_count() -> None:
    game = make_ultimate_game()
    ctx = FakeContext(game)
    original_count = ws_ultimate_actions.ULTIMATE_JOSEKI_TARGET_COUNT
    try:
        ws_ultimate_actions.ULTIMATE_JOSEKI_TARGET_COUNT = 2

        await handle_ultimate_select_card(ctx, {"card_id": "joseki_burst"})
        await asyncio.sleep(0)
    finally:
        ws_ultimate_actions.ULTIMATE_JOSEKI_TARGET_COUNT = original_count

    assert game.ultimate_player_card == "joseki_burst"
    assert game.ultimate_ai_card == "meteor"
    assert game.ultimate_offer_cards == []
    assert game.ultimate_joseki_targets == [(0, 0), (1, 1)]
    assert ctx.joseki_args == [(9, 2)]
    assert ctx.ai_pick_excludes == [("joseki_burst",)]
    assert [payload["type"] for payload in ctx.sent] == ["ultimate_cards_selected", "rogue_event"]
    assert ctx.background_games == [game]

    await handle_ultimate_select_card(ctx, {"card_id": "meteor"})
    assert ctx.errors == ["卡牌选择已失效，请使用当前卡牌报价"]
    assert game.ultimate_player_card == "joseki_burst"


async def smoke_chain_play_honors_runtime_extra_turn_chance() -> None:
    game = make_ultimate_game()
    game.ultimate_player_card = "chain"
    ctx = FakeContext(game)
    original_chance = ws_ultimate_actions.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
    original_random = ws_ultimate_actions.random.random
    try:
        ws_ultimate_actions.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE = 1.0
        ws_ultimate_actions.random.random = lambda: 0.5

        await handle_ultimate_play(ctx, game, {"x": 2, "y": 3}, "B")
    finally:
        ws_ultimate_actions.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE = original_chance
        ws_ultimate_actions.random.random = original_random

    assert game.board[3][2] == 1
    assert game.moves == [("B", "C6")]
    assert game.ultimate_move_count == 1
    assert game.ultimate_extra_turn is True
    assert game.current_player == game.player_color
    assert ctx.capture_checks == [(game, "B", 0, True)]
    assert ctx.applied_effects == [(game, 2, 3, "B", "chain")]
    assert ctx.ai_moves == []
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "rogue_event"]


async def smoke_play_dispatches_ultimate_double_bonus() -> None:
    game = make_ultimate_game()
    game.ultimate_player_card = "double"
    ctx = FakeContext(game)

    await ws_actions.WS_ACTION_HANDLERS["play"](ctx, {"x": 2, "y": 3})

    assert game.board[3][2] == 1
    assert game.moves == [("B", "C6")]
    assert game.ultimate_move_count == 1
    assert game.ultimate_extra_turn is True
    assert game.ultimate_double_pending is True
    assert game.current_player == game.player_color
    assert ctx.capture_checks == [(game, "B", 0, True)]
    assert ctx.applied_effects == [(game, 2, 3, "B", "double")]
    assert ctx.ai_moves == []
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "rogue_event"]


async def smoke_play_dispatches_ultimate_quickthink_body() -> None:
    game = make_ultimate_game()
    game.ultimate_player_card = "quickthink"
    ctx = FakeContext(game)

    await ws_actions.WS_ACTION_HANDLERS["play"](ctx, {"x": 2, "y": 3})

    assert game.board[3][2] == 1
    assert game.moves == [("B", "C6")]
    assert game.ultimate_move_count == 1
    assert game.ultimate_quickthink_active is True
    assert game.ultimate_quickthink_token == 1
    assert game.current_player == game.player_color
    assert ctx.capture_checks == [(game, "B", 0, True)]
    assert ctx.applied_effects == []
    assert ctx.ai_moves == []
    assert [payload["type"] for payload in ctx.sent] == ["game_state"]


async def smoke_territory_forbidden_blocks_ultimate_play() -> None:
    game = make_ultimate_game()
    game.ultimate_ai_card = "territory"
    ctx = FakeContext(game)
    ctx.territory_forbidden = {(2, 3)}

    await handle_ultimate_play(ctx, game, {"x": 2, "y": 3}, "B")

    assert ctx.errors == ["这里已被绝对领地封锁，不能在 AI 的禁区内落子"]
    assert game.board[3][2] == 0
    assert game.moves == []


async def smoke_quickthink_end_finishes_turn_and_starts_ai() -> None:
    game = make_ultimate_game()
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True
    ctx = FakeContext(game)

    await handle_ultimate_quickthink_end(ctx, {})
    await asyncio.sleep(0)

    assert game.ultimate_quickthink_active is False
    assert game.current_player == game.ai_color
    assert ctx.quickthink_finished == [game]
    assert ctx.ai_moves == [game]
    assert ctx.background_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_state"]


def smoke_ws_action_handlers_keep_ultimate_action_names() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["ultimate_select_card"] is handle_ultimate_select_card
    assert ws_actions.WS_ACTION_HANDLERS["ultimate_quickthink_end"] is handle_ultimate_quickthink_end


def smoke_ultimate_action_annotations_resolve_runtime_context() -> None:
    for handler in (
        handle_ultimate_play,
        ws_actions.WS_ACTION_HANDLERS["ultimate_select_card"],
        ws_actions.WS_ACTION_HANDLERS["ultimate_quickthink_end"],
    ):
        hints = get_type_hints(handler)
        assert hints["ctx"] is WebSocketActionContext
        assert hints["data"] is dict


async def main() -> None:
    await smoke_select_joseki_card_honors_runtime_target_count()
    await smoke_chain_play_honors_runtime_extra_turn_chance()
    await smoke_play_dispatches_ultimate_double_bonus()
    await smoke_play_dispatches_ultimate_quickthink_body()
    await smoke_territory_forbidden_blocks_ultimate_play()
    await smoke_quickthink_end_finishes_turn_and_starts_ai()
    smoke_ws_action_handlers_keep_ultimate_action_names()
    smoke_ultimate_action_annotations_resolve_runtime_context()
    print("ws ultimate actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
