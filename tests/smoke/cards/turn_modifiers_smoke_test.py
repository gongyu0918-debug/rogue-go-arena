from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import random

import app.config.gameplay as gameplay_config
import server as s
from app.domain.game_state import GoGame
from app.gameplay import ai_moves, turn_modifiers


def make_game() -> GoGame:
    game = GoGame(size=9, player_color="B")
    game.current_player = "B"
    return game


def test_ai_rogue_forbidden_points() -> None:
    game = make_game()
    game.ai_rogue_seal_points = [(1, 1), (2, 2)]

    for card in ["blackhole", "golden_corner", "fog"]:
        game.ai_rogue_card = card
        assert turn_modifiers.get_ai_rogue_forbidden_points(game) == [(1, 1), (2, 2)]

    game.ai_rogue_card = "mirror"
    assert turn_modifiers.get_ai_rogue_forbidden_points(game) == []


def test_player_bonus_forbidden_points() -> None:
    game = make_game()
    game.ai_rogue_card = "fog"
    game.ai_rogue_seal_points = [(4, 4)]

    assert turn_modifiers.get_player_bonus_forbidden_points(game, "B") == {(4, 4)}
    assert turn_modifiers.get_player_bonus_forbidden_points(game, "W") == set()

    game.two_player = True
    assert turn_modifiers.get_player_bonus_forbidden_points(game, "B") == set()


def test_refresh_ai_rogue_fog_mask_and_point_modes() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"

    turn_modifiers.refresh_ai_rogue_player_turn(
        game,
        rng_factory=lambda: random.Random(1),
        pick_fog_mask_fn=lambda _size, _rng: [(3, 3), (3, 4)],
    )
    assert game.ai_rogue_seal_points == [(3, 3), (3, 4)]

    game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
    point_calls = [[(5, 5)], [(5, 5)]]

    def pick_duplicate_point(_game, _rng):
        return point_calls.pop(0) if point_calls else [(6, 6)]

    turn_modifiers.refresh_ai_rogue_player_turn(
        game,
        rng_factory=lambda: random.Random(2),
        pick_fog_point_fn=pick_duplicate_point,
    )
    assert game.ai_rogue_seal_points == [(5, 5)]

    game.current_player = "W"
    game.ai_rogue_seal_points = [(7, 7)]
    turn_modifiers.refresh_ai_rogue_player_turn(game)
    assert game.ai_rogue_seal_points == []


def test_pick_fog_point_uses_ai_previous_move_diamond() -> None:
    game = make_game()
    game.ai_color = "W"
    game.moves = [("B", "D4"), ("W", "E5")]
    game.board[4][4] = 2

    picked = turn_modifiers.pick_fog_point(game, random.Random(7))

    assert len(picked) == gameplay_config.ROGUE_FOG_POST_MASK_POINTS
    px, py = picked[0]
    assert abs(px - 4) + abs(py - 4) <= 1
    assert (px, py) != (4, 4)

    for px, py in [(3, 4), (5, 4), (4, 3), (4, 5)]:
        game.board[py][px] = 1
    assert turn_modifiers.pick_fog_point(game, random.Random(8)) == []


def test_lowline_allows_only_second_and_third_lines_for_first_five_ai_moves() -> None:
    game = make_game()

    restriction = ai_moves.lowline_allowed_points(game, ai_move_count=0)

    assert restriction is not None
    assert restriction.kind == "allow_only"
    assert (0, 0) not in restriction.points
    assert (1, 4) in restriction.points
    assert (2, 4) in restriction.points
    assert (3, 3) not in restriction.points
    assert ai_moves.lowline_allowed_points(
        game,
        ai_move_count=gameplay_config.ROGUE_LOWLINE_AI_MOVES,
    ) is None


def test_prepare_and_clear_quickthink_turns() -> None:
    game = make_game()
    game.rogue_card = "quickthink"
    game.ultimate = True
    game.ultimate_player_card = "quickthink"

    refresh_calls: list[GoGame] = []
    turn_modifiers.prepare_player_turn_modifiers(
        game,
        refresh_ai_rogue_player_turn_fn=refresh_calls.append,
    )
    assert refresh_calls == [game]
    assert game.rogue_quickthink_stage == 1
    assert game.ultimate_quickthink_active is True
    assert game.ultimate_quickthink_token == 1

    turn_modifiers.prepare_player_turn_modifiers(
        game,
        refresh_ai_rogue_player_turn_fn=refresh_calls.append,
    )
    assert game.ultimate_quickthink_token == 1

    game.rogue_quickthink_stage = 2
    game.ultimate_quickthink_turn_counted = True
    turn_modifiers.clear_player_turn_modifiers(game)
    assert game.rogue_quickthink_stage == 0
    assert game.ultimate_quickthink_active is False
    assert game.ultimate_quickthink_turn_counted is False


def test_methodical_ignores_challenge_card_loadout() -> None:
    game = make_game()
    game.rogue_card = "sprout"
    game.challenge_cards = ["methodical", "sprout"]

    turn_modifiers.prepare_player_turn_modifiers(game)

    assert game.rogue_methodical_remaining == 0
    assert game.rogue_methodical_turns["B"] == 0


def test_apply_ultimate_ai_move_result_records_stone_move() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "A9",
        (0, 0),
        count_turn=True,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == [game]
    assert game.moves == [("W", "A9")]
    assert game.board[0][0] == 2
    assert game.passed["W"] is False


def test_apply_ultimate_ai_move_result_records_pass_without_counting_double_bonus() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "pass",
        None,
        count_turn=False,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == []
    assert game.moves == [("W", "pass")]
    assert game.passed["W"] is True


def test_apply_ultimate_ai_move_result_treats_missing_coord_as_pass_state() -> None:
    game = make_game()
    turn_calls: list[GoGame] = []

    captured = turn_modifiers.apply_ultimate_ai_move_result(
        game,
        "W",
        "D4",
        None,
        count_turn=True,
        record_ultimate_turn_fn=turn_calls.append,
    )

    assert captured == 0
    assert turn_calls == [game]
    assert game.moves == [("W", "D4")]
    assert game.passed["W"] is True
    assert all(cell == 0 for row in game.board for cell in row)


def test_finish_ultimate_ai_normal_turn_prepares_player_and_pushes_history() -> None:
    game = make_game()
    game.ultimate = True
    game.current_player = "W"
    game.ultimate_extra_turn = True
    history_len = len(game._history)
    prepare_calls: list[GoGame] = []

    def prepare(game_arg):
        prepare_calls.append(game_arg)
        game_arg.rogue_quickthink_stage = 1

    turn_modifiers.finish_ultimate_ai_normal_turn(
        game,
        prepare_player_turn_modifiers_fn=prepare,
    )

    assert game.ultimate_extra_turn is False
    assert game.current_player == game.player_color
    assert prepare_calls == [game]
    assert len(game._history) == history_len + 1
    assert game._history[-1]["current_player"] == game.player_color
    assert game._history[-1]["rogue_quickthink_stage"] == 1


def test_choose_ultimate_ai_bonus_turn_picks_chain_bonus() -> None:
    game = make_game()

    bonus = turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="chain",
        gtp_move="D4",
        allow_double_bonus=True,
        chain_random=lambda: 0.0,
        chain_chance=0.5,
    )

    assert bonus is not None
    assert bonus.kind == "chain"
    assert bonus.message == "AI 的连珠棋触发，AI 将继续落子"
    assert bonus.next_allow_double_bonus is True


def test_choose_ultimate_ai_bonus_turn_skips_chain_miss() -> None:
    game = make_game()

    assert turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="chain",
        gtp_move="D4",
        allow_double_bonus=True,
        chain_random=lambda: 0.5,
        chain_chance=0.5,
    ) is None


def test_choose_ultimate_ai_bonus_turn_picks_double_bonus_once() -> None:
    game = make_game()

    bonus = turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="double",
        gtp_move="D4",
        allow_double_bonus=True,
        chain_random=lambda: 1.0,
        chain_chance=0.5,
    )
    blocked = turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="double",
        gtp_move="D4",
        allow_double_bonus=False,
        chain_random=lambda: 1.0,
        chain_chance=0.5,
    )

    assert bonus is not None
    assert bonus.kind == "double"
    assert bonus.message == "AI 的双刀流触发，AI 将继续落子"
    assert bonus.next_allow_double_bonus is False
    assert blocked is None


def test_choose_ultimate_ai_bonus_turn_blocks_pass_and_game_over() -> None:
    game = make_game()

    assert turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="chain",
        gtp_move="pass",
        allow_double_bonus=True,
        chain_random=lambda: 0.0,
        chain_chance=1.0,
    ) is None

    game.game_over = True
    assert turn_modifiers.choose_ultimate_ai_bonus_turn(
        game,
        ai_card="double",
        gtp_move="D4",
        allow_double_bonus=True,
        chain_random=lambda: 0.0,
        chain_chance=1.0,
    ) is None


def test_start_ultimate_ai_bonus_turn_sets_state() -> None:
    game = make_game()
    game.current_player = game.player_color

    turn_modifiers.start_ultimate_ai_bonus_turn(game, "W")

    assert game.ultimate_extra_turn is True
    assert game.current_player == "W"


async def _server_ultimate_ai_bonus_turn_sends_state_and_recurses() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_move_count = 3
    sent = []
    calls = []
    bonus = turn_modifiers.UltimateAiBonusTurn(
        kind="double",
        message="AI 的双刀流触发，AI 将继续落子",
        next_allow_double_bonus=False,
    )
    old_ai_move = s._ultimate_ai_move
    try:
        async def send(payload):
            sent.append(payload)

        async def fake_ai_move(game_arg, send_fn, allow_double_bonus=True):
            calls.append((game_arg, send_fn, allow_double_bonus))

        s._ultimate_ai_move = fake_ai_move
        recursed = await s._run_ultimate_ai_bonus_turn(game, send, "W", bonus)
    finally:
        s._ultimate_ai_move = old_ai_move

    assert recursed is True
    assert game.ultimate_extra_turn is True
    assert game.current_player == "W"
    assert sent[0] == {"type": "rogue_event", "msg": "AI 的双刀流触发，AI 将继续落子"}
    assert sent[1]["type"] == "game_state"
    assert sent[1]["ultimate_extra_turn"] is True
    assert sent[1]["current_player"] == "W"
    assert len(calls) == 1
    assert calls[0][0] is game
    assert calls[0][1] is send
    assert calls[0][2] is False


def test_server_ultimate_ai_bonus_turn_sends_state_and_recurses() -> None:
    asyncio.run(_server_ultimate_ai_bonus_turn_sends_state_and_recurses())


async def _server_ultimate_ai_bonus_turn_stops_at_move_limit() -> None:
    game = make_game()
    game.ultimate = True
    game.ultimate_move_count = 20
    sent = []
    calls = []
    bonus = turn_modifiers.UltimateAiBonusTurn(
        kind="chain",
        message="AI 的连珠棋触发，AI 将继续落子",
        next_allow_double_bonus=True,
    )
    old_ai_move = s._ultimate_ai_move
    try:
        async def send(payload):
            sent.append(payload)

        async def fake_ai_move(*args, **kwargs):
            calls.append((args, kwargs))

        s._ultimate_ai_move = fake_ai_move
        recursed = await s._run_ultimate_ai_bonus_turn(game, send, "W", bonus)
    finally:
        s._ultimate_ai_move = old_ai_move

    assert recursed is False
    assert calls == []
    assert game.ultimate_extra_turn is True
    assert game.current_player == "W"
    assert sent[0] == {"type": "rogue_event", "msg": "AI 的连珠棋触发，AI 将继续落子"}
    assert sent[1]["type"] == "game_state"


def test_server_ultimate_ai_bonus_turn_stops_at_move_limit() -> None:
    asyncio.run(_server_ultimate_ai_bonus_turn_stops_at_move_limit())


def test_server_wrapper_preserves_fog_monkeypatch() -> None:
    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"

    old_pick_fog_mask = s._pick_fog_mask
    try:
        s._pick_fog_mask = lambda _size, _rng: [(4, 4)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(4, 4)]
    finally:
        s._pick_fog_mask = old_pick_fog_mask

    game.moves = [("B", f"D{i}") for i in range(gameplay_config.ROGUE_FOG_AI_MOVES)]
    old_pick_fog_point = s._pick_fog_point
    try:
        s._pick_fog_point = lambda _game, _rng: [(5, 5)]
        s._refresh_ai_rogue_player_turn(game)
        assert game.ai_rogue_seal_points == [(5, 5)]
    finally:
        s._pick_fog_point = old_pick_fog_point


if __name__ == "__main__":
    test_ai_rogue_forbidden_points()
    test_player_bonus_forbidden_points()
    test_refresh_ai_rogue_fog_mask_and_point_modes()
    test_pick_fog_point_uses_ai_previous_move_diamond()
    test_lowline_allows_only_second_and_third_lines_for_first_five_ai_moves()
    test_prepare_and_clear_quickthink_turns()
    test_methodical_ignores_challenge_card_loadout()
    test_apply_ultimate_ai_move_result_records_stone_move()
    test_apply_ultimate_ai_move_result_records_pass_without_counting_double_bonus()
    test_apply_ultimate_ai_move_result_treats_missing_coord_as_pass_state()
    test_finish_ultimate_ai_normal_turn_prepares_player_and_pushes_history()
    test_choose_ultimate_ai_bonus_turn_picks_chain_bonus()
    test_choose_ultimate_ai_bonus_turn_skips_chain_miss()
    test_choose_ultimate_ai_bonus_turn_picks_double_bonus_once()
    test_choose_ultimate_ai_bonus_turn_blocks_pass_and_game_over()
    test_start_ultimate_ai_bonus_turn_sets_state()
    test_server_ultimate_ai_bonus_turn_sends_state_and_recurses()
    test_server_ultimate_ai_bonus_turn_stops_at_move_limit()
    test_server_wrapper_preserves_fog_monkeypatch()
    print("turn_modifiers_smoke_test passed")
