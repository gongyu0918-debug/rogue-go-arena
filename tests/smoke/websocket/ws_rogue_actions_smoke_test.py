from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
import app.runtime.ws_rogue_actions as ws_rogue_actions
from app.config.gameplay import ROGUE_SEAL_POINT_COUNT
from app.data.cards import ROGUE_CARDS
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_rogue_actions import (
    handle_challenge_refresh_offer,
    handle_rogue_seal_point,
    handle_rogue_select_card,
    handle_rogue_use_coach,
    handle_rogue_use_exchange,
    handle_rogue_use_puppet,
    handle_rogue_use_twin,
)


class FakeEngine:
    ready = True


class FakeContext:
    def __init__(self, game: GoGame) -> None:
        self.game = game
        self.engine = FakeEngine()
        self.sent = []
        self.errors = []
        self.challenge_loadouts = []
        self.activated_cards = []
        self.activated_ai_cards = []
        self.ai_move_games = []
        self.background_games = []
        self.picked_challenge_args = []
        self.challenge_zone_inputs = []
        self.coach_games = []
        self.synced_games = []

    def restore_game(self):
        return self.game

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def apply_challenge_rogue_loadout(self, game, send_fn) -> None:
        self.challenge_loadouts.append(game)

    async def activate_rogue_card(self, game, send_fn, card_id: str) -> None:
        self.activated_cards.append((game, card_id))
        game.rogue_card = card_id

    async def activate_ai_rogue_card(self, game, send_fn, card_id: str) -> None:
        self.activated_ai_cards.append((game, card_id))
        game.ai_rogue_card = card_id

    def pick_ai_rogue_card(self, *, exclude):
        assert exclude == ["puppet"]
        return "dice"

    def pick_challenge_beta_choices(self, current_cards, count: int, *, pool):
        self.picked_challenge_args.append((tuple(current_cards), count, tuple(pool)))
        return list(pool[:count])

    async def ai_move(self, game, send_fn) -> None:
        self.ai_move_games.append(game)

    async def do_analysis_bg(self, game) -> None:
        self.background_games.append(game)

    def challenge_zone_points(self, game, points):
        self.challenge_zone_inputs.append((game, list(points)))
        return list(reversed(points))

    def coord_to_gtp(self, x: int, y: int, size: int) -> str | None:
        return coord_to_gtp(x, y, size)

    async def sync_board_to_katago(self, game) -> None:
        self.synced_games.append(game)
        return None

    def challenge_remaining(self, game, kind: str) -> int:
        return 1

    async def run_coach_turn_if_needed(self, game, send_fn) -> None:
        self.coach_games.append(game)


def make_game() -> GoGame:
    game = GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=False)
    game.current_player = "B"
    game.rogue_offer_cards = list(ROGUE_CARDS)
    return game


async def smoke_select_card_activates_player_and_ai_cards() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.current_player = game.ai_color
    ctx = FakeContext(game)

    await handle_rogue_select_card(ctx, {"card_id": "puppet"})
    await asyncio.sleep(0)

    assert ctx.activated_cards == [(game, "puppet")]
    assert ctx.activated_ai_cards == [(game, "dice")]
    assert game.ai_rogue_card == "dice"
    assert game.rogue_offer_cards == []
    assert ctx.ai_move_games == [game]
    assert ctx.background_games == [game]

    await handle_rogue_select_card(ctx, {"card_id": "twin"})
    assert ctx.errors == ["卡牌选择已失效，请使用当前卡牌报价"]
    assert ctx.activated_cards == [(game, "puppet")]


async def smoke_challenge_select_card_uses_offer_and_loadout() -> None:
    game = make_game()
    game.challenge_beta = True
    game.challenge_offer_cards = ["twin", "exchange", "fog"]
    ctx = FakeContext(game)

    await handle_rogue_select_card(ctx, {"card_id": "twin"})

    assert game.challenge_cards == ["twin"]
    assert game.challenge_offer_cards == []
    assert ctx.challenge_loadouts == [game]
    assert ctx.sent[-1]["type"] == "rogue_card_selected"
    assert ctx.sent[-1]["card_id"] == "twin"


async def smoke_challenge_refresh_offer_rebuilds_offer_pool() -> None:
    game = make_game()
    game.challenge_beta = True
    game.challenge_stage = 2
    game.challenge_cards = ["twin"]
    game.challenge_refreshes = 1
    ctx = FakeContext(game)

    await handle_challenge_refresh_offer(ctx, {})

    assert game.challenge_refreshes == 0
    assert len(game.challenge_offer_cards) == 3
    assert ctx.picked_challenge_args[0][0] == ("twin",)
    assert ctx.picked_challenge_args[0][1] == 3
    assert "twin" not in ctx.picked_challenge_args[0][2]
    assert ctx.sent[-1]["type"] == "rogue_offer"
    assert ctx.sent[-1]["challenge_beta"] is True
    assert ctx.sent[-1]["refresh_remaining"] == 0


async def smoke_seal_points_complete_and_start_ai_turn() -> None:
    game = make_game()
    game.challenge_beta = True
    game.rogue_waiting_seal = True
    game.current_player = game.ai_color
    ctx = FakeContext(game)

    for index in range(ROGUE_SEAL_POINT_COUNT):
        await handle_rogue_seal_point(ctx, {"x": index, "y": index})
    await asyncio.sleep(0)

    assert game.rogue_waiting_seal is False
    assert game.rogue_seal_points == list(reversed([(i, i) for i in range(ROGUE_SEAL_POINT_COUNT)]))
    assert ctx.challenge_zone_inputs == [(game, [(i, i) for i in range(ROGUE_SEAL_POINT_COUNT)])]
    assert [payload["type"] for payload in ctx.sent][-2:] == ["rogue_seal_update", "rogue_seal_done"]
    assert ctx.ai_move_games == [game]
    assert ctx.background_games == [game]


async def smoke_twin_use_sets_skip_and_updates_uses() -> None:
    game = make_game()
    game.rogue_card = "twin"
    game.rogue_uses["twin"] = 1
    ctx = FakeContext(game)

    await handle_rogue_use_twin(ctx, {})

    assert game.rogue_uses["twin"] == 0
    assert game.rogue_skip_ai is True
    assert [payload["type"] for payload in ctx.sent] == ["rogue_event", "rogue_uses_update"]


async def smoke_puppet_use_sets_forced_target() -> None:
    game = make_game()
    game.rogue_card = "puppet"
    game.rogue_uses["puppet"] = 1
    ctx = FakeContext(game)

    await handle_rogue_use_puppet(ctx, {"x": 2, "y": 3})
    await asyncio.sleep(0)

    assert game.rogue_puppet_target == (2, 3)
    assert game.rogue_uses["puppet"] == 1
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "rogue_event"]
    assert ctx.background_games == [game]


async def smoke_exchange_use_moves_opponent_stone() -> None:
    game = make_game()
    game.rogue_card = "exchange"
    game.rogue_uses["exchange"] = 1
    game.board[1][1] = 2
    ctx = FakeContext(game)

    await handle_rogue_use_exchange(ctx, {"from_x": 1, "from_y": 1, "to_x": 3, "to_y": 4})
    await asyncio.sleep(0)

    assert game.board[1][1] == 0
    assert game.board[4][3] == 2
    assert game.ko_point is None
    assert game.rogue_uses["exchange"] == 0
    assert ctx.synced_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_state", "rogue_event", "rogue_uses_update"]
    assert ctx.background_games == [game]


async def smoke_coach_use_honors_runtime_turn_count() -> None:
    game = make_game()
    game.rogue_card = "coach_mode"
    game.rogue_uses["coach_mode"] = 1
    ctx = FakeContext(game)
    original_turns = ws_rogue_actions.ROGUE_COACH_BASE_TURNS
    try:
        ws_rogue_actions.ROGUE_COACH_BASE_TURNS = 2

        await handle_rogue_use_coach(ctx, {})
        await asyncio.sleep(0)
    finally:
        ws_rogue_actions.ROGUE_COACH_BASE_TURNS = original_turns

    assert game.rogue_uses["coach_mode"] == 0
    assert game.rogue_coach_moves_left == 2
    assert game.rogue_coach_bonus_checked is False
    assert ctx.coach_games == [game]
    assert [payload["type"] for payload in ctx.sent] == ["rogue_event", "rogue_uses_update", "game_state"]
    assert ctx.background_games == [game]


def smoke_ws_action_handlers_keep_rogue_action_names() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["rogue_select_card"] is handle_rogue_select_card
    assert ws_actions.WS_ACTION_HANDLERS["challenge_refresh_offer"] is handle_challenge_refresh_offer
    assert ws_actions.WS_ACTION_HANDLERS["rogue_seal_point"] is handle_rogue_seal_point
    assert ws_actions.WS_ACTION_HANDLERS["rogue_use_puppet"] is handle_rogue_use_puppet
    assert ws_actions.WS_ACTION_HANDLERS["rogue_use_twin"] is handle_rogue_use_twin
    assert ws_actions.WS_ACTION_HANDLERS["rogue_use_exchange"] is handle_rogue_use_exchange
    assert ws_actions.WS_ACTION_HANDLERS["rogue_use_coach"] is handle_rogue_use_coach


def smoke_rogue_action_annotations_resolve_runtime_context() -> None:
    for action in (
        "rogue_select_card",
        "challenge_refresh_offer",
        "rogue_seal_point",
        "rogue_use_puppet",
        "rogue_use_twin",
        "rogue_use_exchange",
        "rogue_use_coach",
    ):
        hints = get_type_hints(ws_actions.WS_ACTION_HANDLERS[action])
        assert hints["ctx"] is WebSocketActionContext
        assert hints["data"] is dict


async def main() -> None:
    await smoke_select_card_activates_player_and_ai_cards()
    await smoke_challenge_select_card_uses_offer_and_loadout()
    await smoke_challenge_refresh_offer_rebuilds_offer_pool()
    await smoke_seal_points_complete_and_start_ai_turn()
    await smoke_twin_use_sets_skip_and_updates_uses()
    await smoke_puppet_use_sets_forced_target()
    await smoke_exchange_use_moves_opponent_stone()
    await smoke_coach_use_honors_runtime_turn_count()
    smoke_ws_action_handlers_keep_rogue_action_names()
    smoke_rogue_action_annotations_resolve_runtime_context()
    print("ws rogue actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
