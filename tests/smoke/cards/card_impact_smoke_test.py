from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import random

import server as s
from app.domain.game_state import GoGame
from app.gameplay import card_impact as ci

# Captured from `kata-raw-nn 0` on KataGo v1.16.4 (policy rows trimmed).
RAW_NN_RESPONSE = """= symmetry 0
whiteWin 0.638053
whiteLoss 0.360952
noResult 0.000995
whiteLead 1.185
whiteScoreSelfplay 1.952
policy
-0.0001 0.0002"""


def make_game(player: str = "B") -> GoGame:
    game = GoGame(size=9, player_color=player)
    game.rogue_enabled = True
    game.rogue_card = "sprout"
    return game


def run(coro):
    return asyncio.run(coro)


def collect():
    sent: list[dict] = []

    async def send(payload):
        sent.append(payload)

    return sent, send


def smoke_parse_raw_nn() -> None:
    assert ci.parse_raw_nn(RAW_NN_RESPONSE) == (0.638053, 1.185)
    assert ci.parse_raw_nn("= symmetry 0\nwhiteWin 0.5") is None
    assert ci.parse_raw_nn("? unknown command") is None


def smoke_no_change_sends_nothing() -> None:
    game = make_game()
    sent, send = collect()
    before = ci.take_snapshot(game)
    assert run(ci.resolve_card_impact(game, send, before, "B", card_id="sprout",
                                      forbidden=set(), measure=None, ultimate_twins=set())) is None
    assert sent == [] and game.rogue_evolution_charge == 0


def smoke_impact_is_reported_from_player_perspective() -> None:
    for player, expected_delta in (("B", 0.2), ("W", -0.2)):
        game = make_game(player)
        sent, send = collect()
        game.board[4][4] = 2 if player == "B" else 1  # an enemy stone the card removes
        before = ci.take_snapshot(game)
        game.board[4][4] = 0
        game.board[2][2] = 1 if player == "B" else 2

        async def measure(_game, _before):
            return (0.6, 3.0), (0.4, -1.0)  # white win / lead before, after

        payload = run(ci.resolve_card_impact(game, send, before, player, card_id="sprout",
                                             forbidden=set(), measure=measure, ultimate_twins=set()))
        assert payload["type"] == "card_impact" and payload["measured"]
        assert payload["stones_gained"] == 1 and payload["enemy_stones_lost"] == 1
        assert abs(payload["winrate_delta"] - expected_delta) < 1e-9, payload
        assert payload["lead_delta"] == (4.0 if player == "B" else -4.0)
        assert payload["evolution"] == {"level": 1, "charge": 1, "floor": 0, "next": 3, "max_level": 3}


def smoke_evolution_levels_up_and_echoes_safely() -> None:
    game = make_game()
    forbidden = {(3, 2)}
    events: list[dict] = []
    for turn in range(ci.EVOLUTION_THRESHOLDS[0] + 1):
        sent, send = collect()
        before = ci.take_snapshot(game)
        anchor = (2, 2 + 2 * turn)
        game.board[anchor[1]][anchor[0]] = 1
        run(ci.resolve_card_impact(game, send, before, "B", card_id="god_hand", forbidden=forbidden,
                                   measure=None, ultimate_twins={"god_hand"}, rng=random.Random(turn)))
        events.extend(sent)
    evolved = [e for e in events if e["type"] == "card_evolved"]
    assert len(evolved) == 1 and evolved[0]["level"] == 2 and evolved[0]["ultimate_twin"] == "god_hand"
    impacts = [e for e in events if e["type"] == "card_impact"]
    assert all(not e["echo_points"] for e in impacts[:3]), "level 1 never echoes"
    echo = impacts[3]["echo_points"]
    assert len(echo) == 1, impacts[3]
    x, y = echo[0]
    assert (x, y) not in forbidden and game.board[y][x] == 1
    group = game.get_group(x, y)
    liberties = {(nx, ny) for gx, gy in group for nx, ny in game.neighbors(gx, gy) if game.board[ny][nx] == 0}
    assert len(liberties) >= 2


def smoke_echo_never_captures() -> None:
    game = make_game()
    game.rogue_evolution_level = 2
    # White (2,0) is in atari with its last liberty at (2,1). The new card stone
    # at (2,2) has (2,1) as its only empty neighbour, so echoing there would capture.
    for x, y in [(1, 0), (3, 0), (1, 2), (3, 2), (2, 3)]:
        game.board[y][x] = 1
    game.board[0][2] = 2
    assert game.is_legal_move(2, 1, "B")
    before = ci.take_snapshot(game)
    game.board[2][2] = 1
    sent, send = collect()
    payload = run(ci.resolve_card_impact(game, send, before, "B", card_id="sprout", forbidden=set(),
                                         measure=None, ultimate_twins=set(), rng=random.Random(1)))
    assert game.board[0][2] == 2 and game.board[1][2] == 0, "echo must not capture"
    assert payload["echo_points"] == []


def smoke_komi_only_trigger_echoes_komi() -> None:
    game = make_game("W")
    game.rogue_card = "erosion"
    game.rogue_evolution_level = 3
    before = ci.take_snapshot(game)
    game.komi += 4
    sent, send = collect()
    payload = run(ci.resolve_card_impact(game, send, before, "W", card_id="erosion", forbidden=set(),
                                         measure=None, ultimate_twins=set()))
    assert payload["echo_komi"] == 2.0 and game.komi == 7.5 + 4 + 2
    assert payload["komi_gain"] == 6.0


def smoke_server_hook_reports_card_effects() -> None:
    game = make_game()
    sent, send = collect()

    async def fake_effects(game_arg, send_fn, **_kwargs):
        game_arg.board[3][3] = 1

    original = s.apply_player_rogue_move_effects_adapter
    original_ready = s.engine.ready
    s.apply_player_rogue_move_effects_adapter = fake_effects
    s.engine.ready = False
    try:
        run(s._apply_player_rogue_move_effects(game, send, 0, 0, "B", 0))
        game.two_player = True
        run(s._apply_player_rogue_move_effects(game, send, 0, 0, "B", 0))
    finally:
        s.apply_player_rogue_move_effects_adapter = original
        s.engine.ready = original_ready
    impacts = [m for m in sent if m["type"] == "card_impact"]
    assert len(impacts) == 1, sent
    assert impacts[0]["measured"] is False and impacts[0]["stones_gained"] == 1
    assert game.to_state()["rogue_evolution"] == {"level": 1, "charge": 1, "floor": 0, "next": 3, "max_level": 3}


def main() -> None:
    smoke_parse_raw_nn()
    smoke_no_change_sends_nothing()
    smoke_impact_is_reported_from_player_perspective()
    smoke_evolution_levels_up_and_echoes_safely()
    smoke_echo_never_captures()
    smoke_komi_only_trigger_echoes_komi()
    smoke_server_hook_reports_card_effects()
    print("card impact smoke ok")


if __name__ == "__main__":
    main()
