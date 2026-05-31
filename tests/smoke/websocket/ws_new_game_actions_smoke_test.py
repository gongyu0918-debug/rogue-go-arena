from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from typing import get_type_hints

import app.runtime.ws_actions as ws_actions
from app.domain.coordinates import gtp_to_coord
from app.domain.game_state import GoGame
from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_new_game_actions import handle_new_game


class FakeEngine:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.commands = []
        self.visits = []

    def set_visits(self, visits: int) -> str:
        self.visits.append(visits)
        return "="

    def send_command(self, command: str) -> str:
        self.commands.append(command)
        if command.startswith("fixed_handicap "):
            return "= D4 F4"
        return "="


class FakeActiveGames:
    def __init__(self) -> None:
        self.pruned = 0
        self.games = {}

    def prune(self) -> None:
        self.pruned += 1

    def set(self, game_id: str, game: GoGame) -> None:
        self.games[game_id] = game


class FakeContext:
    def __init__(self, *, engine: FakeEngine | None = None, config_errors: list[str] | None = None) -> None:
        self.game_id = "new-game-actions"
        self.GoGame = GoGame
        self.engine = engine or FakeEngine()
        self.active_games = FakeActiveGames()
        self.config_errors = config_errors or []
        self.game = None
        self.sent = []
        self.errors = []
        self.visit_calls = []
        self.challenge_loadouts = []
        self.ultimate_choice_calls = []
        self.rogue_choice_calls = []
        self.challenge_choice_calls = []
        self.ai_moves = []
        self.observer_games = []
        self.background_games = []

    def reload_live_card_config(self) -> list[str]:
        return list(self.config_errors)

    async def send(self, payload: dict) -> None:
        self.sent.append(payload)

    async def send_error(self, message: str) -> None:
        self.errors.append(message)

    async def run_in_executor(self, func, *args):
        return func(*args)

    def get_game_visits(self, level: str, move_count: int, mode: str = "normal") -> int:
        self.visit_calls.append((level, move_count, mode))
        return 321

    def gtp_to_coord(self, gtp: str, size: int):
        return gtp_to_coord(gtp, size)

    async def apply_challenge_rogue_loadout(self, game, send_fn) -> None:
        self.challenge_loadouts.append(game)

    def pick_ultimate_choices(self, count: int):
        self.ultimate_choice_calls.append(count)
        return ["chain", "double", "meteor"][:count]

    def pick_rogue_choices(self, count: int, *, pool=None):
        self.rogue_choice_calls.append((count, tuple(pool) if pool is not None else None))
        source = list(pool) if pool is not None else ["twin", "exchange", "fog"]
        return source[:count]

    def pick_challenge_beta_choices(self, current_cards, count: int, *, pool):
        self.challenge_choice_calls.append((tuple(current_cards), count, tuple(pool)))
        return list(pool[:count])

    async def ai_move(self, game, send_fn) -> None:
        self.ai_moves.append(game)

    async def run_ai_observer_loop(self, game, send_fn) -> None:
        self.observer_games.append(game)

    async def do_analysis_bg(self, game) -> None:
        self.background_games.append(game)

    def engine_state_snapshot(self) -> dict:
        return {"phase": "ready", "message": "ready"}


async def smoke_config_error_stops_before_game_creation() -> None:
    ctx = FakeContext(config_errors=["bad card config"])

    await handle_new_game(ctx, {"two_player": True})

    assert ctx.errors == ["卡牌配置加载失败：bad card config"]
    assert ctx.active_games.pruned == 0
    assert ctx.game is None
    assert ctx.sent == []


async def smoke_normal_new_game_initializes_engine_and_stores_game() -> None:
    ctx = FakeContext()

    await handle_new_game(ctx, {"size": 9, "komi": 7.5, "level": "5k"})
    await asyncio.sleep(0)

    game = ctx.game
    assert game is ctx.active_games.games[ctx.game_id]
    assert game.size == 9
    assert game.level == "5k"
    assert game.ai_style == "balanced"
    assert ctx.active_games.pruned == 1
    assert ctx.visit_calls == [("5k", 0, "normal")]
    assert ctx.engine.visits == [321]
    assert ctx.engine.commands == ["boardsize 9", "clear_board", "komi 7.5", "kata-set-rules chinese"]
    assert [payload["type"] for payload in ctx.sent] == ["game_start"]
    assert ctx.background_games == [game]


async def smoke_ultimate_new_game_sends_offer() -> None:
    ctx = FakeContext()

    await handle_new_game(ctx, {"size": 9, "ultimate": True})
    await asyncio.sleep(0)

    assert ctx.game.ultimate is True
    assert ctx.ultimate_choice_calls == [3]
    assert [payload["type"] for payload in ctx.sent] == ["game_start", "ultimate_offer"]
    assert [card["id"] for card in ctx.sent[-1]["cards"]] == ["chain", "double", "meteor"]
    assert ctx.background_games == [ctx.game]


async def smoke_two_player_rogue_new_game_uses_two_player_pool_without_engine() -> None:
    ctx = FakeContext(engine=FakeEngine(ready=False))

    await handle_new_game(ctx, {"size": 9, "two_player": True, "rogue": True})

    assert ctx.game.two_player is True
    assert ctx.game.rogue_enabled is True
    assert ctx.engine.commands == []
    assert [payload["type"] for payload in ctx.sent] == ["game_start", "rogue_offer"]
    assert ctx.rogue_choice_calls[0][0] == 3
    assert ctx.rogue_choice_calls[0][1] is not None


async def smoke_challenge_new_game_applies_existing_loadout_and_skips_offer() -> None:
    ctx = FakeContext()

    await handle_new_game(
        ctx,
        {
            "size": 9,
            "challenge_beta": True,
            "challenge_stage": 1,
            "challenge_cards": ["twin"],
            "challenge_limits": {"undo": 2, "hint": 3, "coach": 1},
            "challenge_refreshes": 1,
        },
    )
    await asyncio.sleep(0)

    game = ctx.game
    assert game.challenge_beta is True
    assert game.rogue_enabled is True
    assert game.ai_rogue_enabled is False
    assert game.challenge_cards == ["twin"]
    assert game.challenge_limits == {"undo": 2, "hint": 3, "coach": 1}
    assert ctx.challenge_loadouts == [game]
    assert [payload["type"] for payload in ctx.sent] == ["game_start"]
    assert ctx.challenge_choice_calls == []
    assert ctx.background_games == [game]


def smoke_ws_action_handlers_keep_new_game_action_name() -> None:
    assert ws_actions.WS_ACTION_HANDLERS["new_game"] is handle_new_game


def smoke_new_game_action_annotations_resolve_runtime_context() -> None:
    hints = get_type_hints(ws_actions.WS_ACTION_HANDLERS["new_game"])
    assert hints["ctx"] is WebSocketActionContext
    assert hints["data"] is dict


async def main() -> None:
    await smoke_config_error_stops_before_game_creation()
    await smoke_normal_new_game_initializes_engine_and_stores_game()
    await smoke_ultimate_new_game_sends_offer()
    await smoke_two_player_rogue_new_game_uses_two_player_pool_without_engine()
    await smoke_challenge_new_game_applies_existing_loadout_and_skips_offer()
    smoke_ws_action_handlers_keep_new_game_action_name()
    smoke_new_game_action_annotations_resolve_runtime_context()
    print("ws new game actions smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
