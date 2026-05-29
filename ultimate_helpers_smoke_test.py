import asyncio

import server as s
import app.config.gameplay as gameplay_config
import app.gameplay.turn_modifiers as turn_modifiers
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.gameplay.effect_utils import line_points_between
from app.gameplay.ultimate_effects import (
    get_ultimate_territory_forbidden_points,
    resolve_pending_shadow_links,
)
from app.gameplay.turn_modifiers import record_ultimate_player_action


def make_game() -> GoGame:
    return GoGame(size=9, player_color="B")


def test_record_ultimate_player_action_counts_normal_and_double_turns() -> None:
    game = make_game()
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1

    game.ultimate_double_pending = True
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1

    game.ultimate_double_pending = False
    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 2


def test_record_ultimate_player_action_counts_quickthink_once() -> None:
    game = make_game()
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True

    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1
    assert game.ultimate_quickthink_turn_counted is True

    record_ultimate_player_action(game)
    assert game.ultimate_move_count == 1


def test_server_record_ultimate_player_action_preserves_turn_hook() -> None:
    game = make_game()
    calls: list[GoGame] = []
    old_record = s._record_ultimate_turn
    try:
        s._record_ultimate_turn = calls.append
        s._record_ultimate_player_action(game)
        assert calls == [game]
        assert game.ultimate_move_count == 0
    finally:
        s._record_ultimate_turn = old_record


def test_gameplay_record_ultimate_player_action_resolves_turn_hook_late() -> None:
    game = make_game()
    calls: list[GoGame] = []
    old_record = turn_modifiers.record_ultimate_turn
    try:
        turn_modifiers.record_ultimate_turn = calls.append
        turn_modifiers.record_ultimate_player_action(game)
        assert calls == [game]
        assert game.ultimate_move_count == 0
    finally:
        turn_modifiers.record_ultimate_turn = old_record


def test_ultimate_territory_forbidden_points_use_opponent_stones() -> None:
    game = make_game()
    game.board[4][4] = 2
    game.board[0][0] = 1

    forbidden = get_ultimate_territory_forbidden_points(game, 1)
    assert (4, 4) in forbidden
    assert (4, 2) in forbidden
    assert (2, 4) in forbidden
    assert (2, 2) in forbidden
    assert (1, 4) not in forbidden
    assert (4, 1) not in forbidden
    assert (0, 0) not in forbidden
    assert len(forbidden) == 25

    black_owner_forbidden = get_ultimate_territory_forbidden_points(game, 2)
    assert (0, 0) in black_owner_forbidden
    assert (2, 2) in black_owner_forbidden
    assert (3, 0) not in black_owner_forbidden

    assert s._ultimate_get_territory_forbidden(game, 1) == get_ultimate_territory_forbidden_points(game, 1)


def test_ultimate_territory_radius_reads_live_config() -> None:
    game = make_game()
    game.board[4][4] = 2

    old_radius = gameplay_config.ULTIMATE_TERRITORY_RADIUS
    try:
        gameplay_config.ULTIMATE_TERRITORY_RADIUS = 1
        forbidden = get_ultimate_territory_forbidden_points(game, 1)
        assert forbidden == {(4, 4), (4, 3), (4, 5), (3, 4), (5, 4)}
    finally:
        gameplay_config.ULTIMATE_TERRITORY_RADIUS = old_radius


def test_resolve_pending_shadow_links_waits_until_trigger_move() -> None:
    game = make_game()
    game.ultimate_move_count = 1
    link = {
        "from": (2, 2),
        "to": (4, 2),
        "color": 1,
        "trigger_move": 2,
    }
    game.ultimate_shadow_clone_links = [link]

    result = resolve_pending_shadow_links(
        game,
        coord_to_gtp=coord_to_gtp,
        line_points_between=line_points_between,
    )

    assert result.modified is False
    assert result.messages == []
    assert game.ultimate_shadow_clone_links == [link]


def test_resolve_pending_shadow_links_draws_line_and_resets_ko() -> None:
    game = make_game()
    game.ultimate_move_count = 2
    game.ko_point = (0, 0, 1)
    game.ultimate_shadow_clone_links = [{
        "from": (2, 2),
        "to": (4, 2),
        "color": 1,
        "trigger_move": 2,
    }]

    result = resolve_pending_shadow_links(
        game,
        coord_to_gtp=coord_to_gtp,
        line_points_between=line_points_between,
    )

    assert result.modified is True
    assert result.messages == ["👥 影分身连线完成：C7 连到 E7，铺开 3 颗同色棋"]
    assert game.board[2][2] == 1
    assert game.board[2][3] == 1
    assert game.board[2][4] == 1
    assert game.ultimate_shadow_clone_links == []
    assert game.ko_point is None


def test_resolve_pending_shadow_links_clears_triggered_unchanged_link_without_message() -> None:
    game = make_game()
    game.ultimate_move_count = 2
    game.ko_point = (0, 0, 1)
    for x in (2, 3, 4):
        game.board[2][x] = 1
    game.ultimate_shadow_clone_links = [{
        "from": (2, 2),
        "to": (4, 2),
        "color": 1,
        "trigger_move": 2,
    }]

    result = resolve_pending_shadow_links(
        game,
        coord_to_gtp=coord_to_gtp,
        line_points_between=line_points_between,
    )

    assert result.modified is False
    assert result.messages == []
    assert game.ultimate_shadow_clone_links == []
    assert game.ko_point == (0, 0, 1)


def test_resolve_pending_shadow_links_keeps_only_untriggered_pending_links() -> None:
    game = make_game()
    game.ultimate_move_count = 2
    pending_link = {
        "from": (0, 0),
        "to": (0, 2),
        "color": 1,
        "trigger_move": 3,
    }
    triggered_link = {
        "from": (2, 2),
        "to": (4, 2),
        "color": 1,
        "trigger_move": 2,
    }
    game.ultimate_shadow_clone_links = [pending_link, triggered_link]

    result = resolve_pending_shadow_links(
        game,
        coord_to_gtp=coord_to_gtp,
        line_points_between=line_points_between,
    )

    assert result.modified is True
    assert result.messages == ["👥 影分身连线完成：C7 连到 E7，铺开 3 颗同色棋"]
    assert game.ultimate_shadow_clone_links == [pending_link]


async def _server_resolve_pending_shadow_links_sends_events() -> None:
    game = make_game()
    game.ultimate_move_count = 2
    game.ultimate_shadow_clone_links = [{
        "from": (2, 2),
        "to": (4, 2),
        "color": 1,
        "trigger_move": 2,
    }]
    sent = []

    async def send(payload):
        sent.append(payload)

    modified = await s._resolve_pending_ultimate_shadow_links(game, send)

    assert modified is True
    assert sent == [{
        "type": "rogue_event",
        "msg": "👥 影分身连线完成：C7 连到 E7，铺开 3 颗同色棋",
    }]


def test_server_resolve_pending_shadow_links_sends_events() -> None:
    asyncio.run(_server_resolve_pending_shadow_links_sends_events())


if __name__ == "__main__":
    test_record_ultimate_player_action_counts_normal_and_double_turns()
    test_record_ultimate_player_action_counts_quickthink_once()
    test_server_record_ultimate_player_action_preserves_turn_hook()
    test_gameplay_record_ultimate_player_action_resolves_turn_hook_late()
    test_ultimate_territory_forbidden_points_use_opponent_stones()
    test_ultimate_territory_radius_reads_live_config()
    test_resolve_pending_shadow_links_waits_until_trigger_move()
    test_resolve_pending_shadow_links_draws_line_and_resets_ko()
    test_resolve_pending_shadow_links_clears_triggered_unchanged_link_without_message()
    test_resolve_pending_shadow_links_keeps_only_untriggered_pending_links()
    test_server_resolve_pending_shadow_links_sends_events()
    print("ultimate_helpers_smoke_test passed")
