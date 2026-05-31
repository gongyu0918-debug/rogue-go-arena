from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
import app.config.gameplay as gameplay_config
import app.gameplay.turn_modifiers as turn_modifiers
import app.gameplay.ultimate_effects as ultimate_effects
from app.domain.coordinates import coord_to_gtp
from app.domain.game_state import GoGame
from app.gameplay.effect_utils import line_points_between
from app.gameplay.ultimate_effects import (
    BoardEffectResult,
    FoolishWisdomWaveResult,
    apply_ultimate_card_effect,
    apply_ultimate_foolish_wisdom_wave,
    apply_ultimate_five_in_row,
    apply_ultimate_last_stand,
    get_ultimate_territory_forbidden_points,
    resolve_pending_shadow_links,
)
from app.gameplay.turn_modifiers import record_ultimate_player_action


def make_game(size: int = 9) -> GoGame:
    return GoGame(size=size, player_color="B")


class IdentityRng:
    def shuffle(self, _items) -> None:
        return None


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


def test_apply_ultimate_last_stand_marks_done_and_reports_counts() -> None:
    game = make_game()
    game.board[0][0] = 2
    game.board[0][1] = 2

    result = apply_ultimate_last_stand(
        game,
        "B",
        rng=IdentityRng(),
        clear_count=1,
        spawn_count=2,
    )

    assert result.modified is True
    assert result.messages == ["🫀 起死回生发动，绝境反扑：清掉 1 颗敌子，并补下 2 颗己棋"]
    assert game.ultimate_last_stand_done["B"] is True
    assert sum(1 for row in game.board for cell in row if cell == 2) == 1
    assert sum(1 for row in game.board for cell in row if cell == 1) == 2

    second = apply_ultimate_last_stand(game, "B", rng=IdentityRng(), clear_count=1, spawn_count=2)
    assert second.modified is False
    assert second.messages == []


def test_apply_ultimate_last_stand_does_not_mark_done_without_changes() -> None:
    game = make_game(size=5)
    for y in range(game.size):
        for x in range(game.size):
            game.board[y][x] = 1

    result = apply_ultimate_last_stand(
        game,
        "B",
        rng=IdentityRng(),
        clear_count=1,
        spawn_count=2,
    )

    assert result.modified is False
    assert result.messages == []
    assert game.ultimate_last_stand_done["B"] is False


def test_apply_ultimate_last_stand_reads_live_config_counts() -> None:
    game = make_game()
    game.board[0][0] = 2

    old_clear = gameplay_config.ULTIMATE_LAST_STAND_CLEAR_COUNT
    old_spawn = gameplay_config.ULTIMATE_LAST_STAND_SPAWN_COUNT
    try:
        gameplay_config.ULTIMATE_LAST_STAND_CLEAR_COUNT = 0
        gameplay_config.ULTIMATE_LAST_STAND_SPAWN_COUNT = 1
        result = apply_ultimate_last_stand(game, "B", rng=IdentityRng())
    finally:
        gameplay_config.ULTIMATE_LAST_STAND_CLEAR_COUNT = old_clear
        gameplay_config.ULTIMATE_LAST_STAND_SPAWN_COUNT = old_spawn

    assert result.modified is True
    assert result.messages == ["🫀 起死回生发动，绝境反扑：清掉 0 颗敌子，并补下 1 颗己棋"]
    assert game.board[0][0] == 2
    assert sum(1 for row in game.board for cell in row if cell == 1) == 1


def test_apply_ultimate_five_in_row_reports_counts_and_seen_lines() -> None:
    game = make_game()
    for x in range(5):
        game.board[4][x] = 1
    game.board[7][8] = 2
    game.board[8][8] = 2
    expected_line = tuple((x, 4) for x in range(5))

    result = apply_ultimate_five_in_row(
        game,
        "B",
        rng=IdentityRng(),
        clear_count=1,
        spawn_count=2,
    )

    assert result.modified is True
    assert result.messages == ["🎯 五子连珠爆发连锁 1 次：随机清除 1 颗敌子，并补下 2 颗己棋"]
    assert expected_line in game.ultimate_five_in_row_seen
    assert sum(1 for row in game.board for cell in row if cell == 2) == 1
    assert game.board[0][0] == 1
    assert game.board[0][1] == 1


def test_apply_ultimate_five_in_row_marks_seen_without_board_change() -> None:
    game = make_game()
    for x in range(5):
        game.board[4][x] = 1
    expected_line = tuple((x, 4) for x in range(5))

    result = apply_ultimate_five_in_row(
        game,
        "B",
        rng=IdentityRng(),
        clear_count=0,
        spawn_count=0,
    )

    assert result.modified is False
    assert result.messages == []
    assert expected_line in game.ultimate_five_in_row_seen


def test_apply_ultimate_five_in_row_chains_new_lines_created_by_spawn() -> None:
    game = make_game()
    for x in range(5):
        game.board[4][x] = 1

    result = apply_ultimate_five_in_row(
        game,
        "B",
        rng=IdentityRng(),
        clear_count=0,
        spawn_count=5,
    )

    assert result.modified is True
    assert result.messages == ["🎯 五子连珠爆发连锁 2 次：随机清除 0 颗敌子，并补下 10 颗己棋"]
    assert tuple((x, 4) for x in range(5)) in game.ultimate_five_in_row_seen
    assert tuple((x, 0) for x in range(5)) in game.ultimate_five_in_row_seen


def test_apply_ultimate_five_in_row_reads_live_config_counts() -> None:
    game = make_game()
    for x in range(5):
        game.board[4][x] = 1
    game.board[8][8] = 2

    old_clear = gameplay_config.ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT
    old_spawn = gameplay_config.ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT
    try:
        gameplay_config.ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT = 0
        gameplay_config.ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT = 1
        result = apply_ultimate_five_in_row(game, "B", rng=IdentityRng())
    finally:
        gameplay_config.ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT = old_clear
        gameplay_config.ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT = old_spawn

    assert result.modified is True
    assert result.messages == ["🎯 五子连珠爆发连锁 1 次：随机清除 0 颗敌子，并补下 1 颗己棋"]
    assert game.board[8][8] == 2
    assert game.board[0][0] == 1


def test_apply_ultimate_foolish_wisdom_wave_generates_and_reports() -> None:
    game = make_game()
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1

    result = apply_ultimate_foolish_wisdom_wave(
        game,
        "B",
        wave=1,
        rng=IdentityRng(),
        fill_count=2,
    )

    assert result.modified is True
    assert result.generated == 2
    assert result.detected_shapes == 1
    assert result.message == "🪤 大智若愚第 1 波发动，识别到 1 个愚形，生成 2 颗己方棋子"
    assert len(game.ultimate_fool_shapes) == 1
    assert game.board[0][0] == 1
    assert game.board[0][1] == 1


def test_apply_ultimate_foolish_wisdom_wave_marks_seen_without_batch() -> None:
    game = make_game()
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1

    result = apply_ultimate_foolish_wisdom_wave(
        game,
        "B",
        wave=1,
        rng=IdentityRng(),
        fill_count=0,
    )

    assert result.modified is False
    assert result.message is None
    assert result.generated == 0
    assert result.detected_shapes == 1
    assert result.has_more is False
    assert len(game.ultimate_fool_shapes) == 1


def test_apply_ultimate_foolish_wisdom_wave_reports_zero_placed_batch() -> None:
    game = make_game()
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1
    old_spawn = ultimate_effects.spawn_bonus_points
    try:
        def fake_spawn(_game, points, _color):
            assert points
            return []

        ultimate_effects.spawn_bonus_points = fake_spawn
        result = apply_ultimate_foolish_wisdom_wave(
            game,
            "B",
            wave=1,
            rng=IdentityRng(),
            fill_count=2,
        )
    finally:
        ultimate_effects.spawn_bonus_points = old_spawn

    assert result.modified is False
    assert result.generated == 0
    assert result.detected_shapes == 1
    assert result.message == "🪤 大智若愚第 1 波发动，识别到 1 个愚形，生成 0 颗己方棋子"
    assert len(game.ultimate_fool_shapes) == 1


def test_apply_ultimate_foolish_wisdom_wave_reads_live_config_count() -> None:
    game = make_game()
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1

    old_fill = gameplay_config.ULTIMATE_FOOLISH_FILL_COUNT
    try:
        gameplay_config.ULTIMATE_FOOLISH_FILL_COUNT = 1
        result = apply_ultimate_foolish_wisdom_wave(game, "B", wave=1, rng=IdentityRng())
    finally:
        gameplay_config.ULTIMATE_FOOLISH_FILL_COUNT = old_fill

    assert result.modified is True
    assert result.generated == 1
    assert result.message == "🪤 大智若愚第 1 波发动，识别到 1 个愚形，生成 1 颗己方棋子"
    assert game.board[0][0] == 1


async def _ultimate_card_effect_prefers_board_effect() -> None:
    game = make_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def board_effect(effect_game, **kwargs):
        calls.append(("board", effect_game is game, kwargs["card"]))
        return BoardEffectResult(True, ["board event"])

    def state_effect(*_args, **_kwargs):
        calls.append("state")
        return BoardEffectResult(True, ["state event"])

    async def trigger(*_args, **_kwargs):
        calls.append("trigger")
        return True

    modified = await apply_ultimate_card_effect(
        game,
        send,
        x=1,
        y=2,
        color="B",
        card="meteor",
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=lambda _gtp, _size: None,
        trigger_five_in_row_fn=trigger,
        trigger_last_stand_fn=trigger,
        apply_board_effect_fn=board_effect,
        apply_state_effect_fn=state_effect,
    )

    assert modified is True
    assert calls == [("board", True, "meteor")]
    assert sent == [{"type": "rogue_event", "msg": "board event"}]


def test_ultimate_card_effect_prefers_board_effect() -> None:
    asyncio.run(_ultimate_card_effect_prefers_board_effect())


async def _ultimate_card_effect_dispatches_state_and_special_triggers() -> None:
    game = make_game()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def no_board(*_args, **_kwargs):
        calls.append("board")
        return None

    def state_effect(effect_game, **kwargs):
        calls.append(("state", effect_game is game, kwargs["coord_to_gtp"] is coord_to_gtp))
        return BoardEffectResult(False, ["state event"])

    async def five_trigger(effect_game, send_fn, color):
        calls.append(("five", effect_game is game, send_fn is send, color))
        return True

    async def last_trigger(effect_game, send_fn, color):
        calls.append(("last", effect_game is game, send_fn is send, color))
        return False

    state_modified = await apply_ultimate_card_effect(
        game,
        send,
        x=1,
        y=2,
        color="B",
        card="shadow_clone",
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=lambda _gtp, _size: None,
        trigger_five_in_row_fn=five_trigger,
        trigger_last_stand_fn=last_trigger,
        apply_board_effect_fn=no_board,
        apply_state_effect_fn=state_effect,
    )
    five_modified = await apply_ultimate_card_effect(
        game,
        send,
        x=1,
        y=2,
        color="B",
        card="five_in_row",
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=lambda _gtp, _size: None,
        trigger_five_in_row_fn=five_trigger,
        trigger_last_stand_fn=last_trigger,
        apply_board_effect_fn=no_board,
        apply_state_effect_fn=lambda *_args, **_kwargs: None,
    )
    last_modified = await apply_ultimate_card_effect(
        game,
        send,
        x=1,
        y=2,
        color="W",
        card="last_stand",
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=lambda _gtp, _size: None,
        trigger_five_in_row_fn=five_trigger,
        trigger_last_stand_fn=last_trigger,
        apply_board_effect_fn=no_board,
        apply_state_effect_fn=lambda *_args, **_kwargs: None,
    )

    assert state_modified is False
    assert five_modified is True
    assert last_modified is False
    assert calls == [
        "board",
        ("state", True, True),
        "board",
        ("five", True, True, "B"),
        "board",
        ("last", True, True, "W"),
    ]
    assert sent == [{"type": "rogue_event", "msg": "state event"}]


def test_ultimate_card_effect_dispatches_state_and_special_triggers() -> None:
    asyncio.run(_ultimate_card_effect_dispatches_state_and_special_triggers())


async def _ultimate_card_effect_resolves_default_hooks_late() -> None:
    game = make_game()
    sent = []
    calls = []
    old_board = ultimate_effects.apply_ultimate_board_effect
    try:
        async def send(payload):
            sent.append(payload)

        async def trigger(*_args, **_kwargs):
            calls.append("trigger")
            return False

        def patched_board(effect_game, **kwargs):
            calls.append(("patched_board", effect_game is game, kwargs["card"]))
            return BoardEffectResult(True, ["patched board"])

        ultimate_effects.apply_ultimate_board_effect = patched_board
        modified = await ultimate_effects.apply_ultimate_card_effect(
            game,
            send,
            x=1,
            y=2,
            color="B",
            card="meteor",
            coord_to_gtp=coord_to_gtp,
            gtp_to_coord=lambda _gtp, _size: None,
            trigger_five_in_row_fn=trigger,
            trigger_last_stand_fn=trigger,
        )
    finally:
        ultimate_effects.apply_ultimate_board_effect = old_board

    assert modified is True
    assert calls == [("patched_board", True, "meteor")]
    assert sent == [{"type": "rogue_event", "msg": "patched board"}]


def test_ultimate_card_effect_resolves_default_hooks_late() -> None:
    asyncio.run(_ultimate_card_effect_resolves_default_hooks_late())


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


async def _server_ultimate_last_stand_high_winrate_guard() -> None:
    game = make_game()
    game.board[0][0] = 2
    original_board = [row[:] for row in game.board]
    sent = []
    old_estimate = s._estimate_side_winrate
    try:
        async def high_winrate(_game, _color):
            return 0.9

        s._estimate_side_winrate = high_winrate
        result = await s._trigger_ultimate_last_stand(game, sent.append, "B")
    finally:
        s._estimate_side_winrate = old_estimate

    assert result is False
    assert sent == []
    assert game.board == original_board
    assert game.ultimate_last_stand_done["B"] is False


def test_server_ultimate_last_stand_high_winrate_guard() -> None:
    asyncio.run(_server_ultimate_last_stand_high_winrate_guard())


async def _server_ultimate_five_in_row_sends_events() -> None:
    game = make_game()
    sent = []
    old_apply = s.apply_ultimate_five_in_row
    try:
        async def send(payload):
            sent.append(payload)

        def fake_apply(effect_game, color, *, rng):
            assert effect_game is game
            assert color == "B"
            assert rng is not None
            return BoardEffectResult(modified=True, messages=["first", "second"])

        s.apply_ultimate_five_in_row = fake_apply
        result = await s._trigger_ultimate_five_in_row(game, send, "B")
    finally:
        s.apply_ultimate_five_in_row = old_apply

    assert result is True
    assert sent == [
        {"type": "rogue_event", "msg": "first"},
        {"type": "rogue_event", "msg": "second"},
    ]


def test_server_ultimate_five_in_row_sends_events() -> None:
    asyncio.run(_server_ultimate_five_in_row_sends_events())


async def _server_ultimate_foolish_wisdom_sends_waves_sleep_and_summary() -> None:
    game = make_game()
    sent = []
    sleeps = []
    calls = []
    rng_ids = []
    old_apply = s.apply_ultimate_foolish_wisdom_wave
    old_sleep = s.asyncio.sleep
    try:
        async def send(payload):
            sent.append(payload)

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        def fake_apply(effect_game, color, *, wave, rng):
            assert effect_game is game
            assert color == "B"
            assert rng is not None
            calls.append(wave)
            rng_ids.append(id(rng))
            if wave == 1:
                return FoolishWisdomWaveResult(
                    modified=True,
                    message="wave 1",
                    generated=2,
                    detected_shapes=1,
                    has_more=True,
                )
            return FoolishWisdomWaveResult(
                modified=False,
                message="wave 2",
                generated=0,
                detected_shapes=1,
                has_more=False,
            )

        s.apply_ultimate_foolish_wisdom_wave = fake_apply
        s.asyncio.sleep = fake_sleep
        result = await s._apply_ultimate_effect(game, send, 2, 3, "B", "foolish_wisdom")
    finally:
        s.apply_ultimate_foolish_wisdom_wave = old_apply
        s.asyncio.sleep = old_sleep

    assert result is True
    assert calls == [1, 2]
    assert len(set(rng_ids)) == 1
    assert sleeps == [s.ULTIMATE_FOOLISH_CHAIN_DELAY]
    assert sent == [
        {"type": "rogue_event", "msg": "wave 1"},
        {"type": "rogue_event", "msg": "wave 2"},
        {"type": "rogue_event", "msg": "🪤 大智若愚连锁结束，本次共生成 2 颗己方棋子"},
    ]


def test_server_ultimate_foolish_wisdom_sends_waves_sleep_and_summary() -> None:
    asyncio.run(_server_ultimate_foolish_wisdom_sends_waves_sleep_and_summary())


if __name__ == "__main__":
    test_record_ultimate_player_action_counts_normal_and_double_turns()
    test_record_ultimate_player_action_counts_quickthink_once()
    test_server_record_ultimate_player_action_preserves_turn_hook()
    test_gameplay_record_ultimate_player_action_resolves_turn_hook_late()
    test_ultimate_territory_forbidden_points_use_opponent_stones()
    test_ultimate_territory_radius_reads_live_config()
    test_apply_ultimate_last_stand_marks_done_and_reports_counts()
    test_apply_ultimate_last_stand_does_not_mark_done_without_changes()
    test_apply_ultimate_last_stand_reads_live_config_counts()
    test_apply_ultimate_five_in_row_reports_counts_and_seen_lines()
    test_apply_ultimate_five_in_row_marks_seen_without_board_change()
    test_apply_ultimate_five_in_row_chains_new_lines_created_by_spawn()
    test_apply_ultimate_five_in_row_reads_live_config_counts()
    test_apply_ultimate_foolish_wisdom_wave_generates_and_reports()
    test_apply_ultimate_foolish_wisdom_wave_marks_seen_without_batch()
    test_apply_ultimate_foolish_wisdom_wave_reports_zero_placed_batch()
    test_apply_ultimate_foolish_wisdom_wave_reads_live_config_count()
    test_ultimate_card_effect_prefers_board_effect()
    test_ultimate_card_effect_dispatches_state_and_special_triggers()
    test_ultimate_card_effect_resolves_default_hooks_late()
    test_resolve_pending_shadow_links_waits_until_trigger_move()
    test_resolve_pending_shadow_links_draws_line_and_resets_ko()
    test_resolve_pending_shadow_links_clears_triggered_unchanged_link_without_message()
    test_resolve_pending_shadow_links_keeps_only_untriggered_pending_links()
    test_server_resolve_pending_shadow_links_sends_events()
    test_server_ultimate_last_stand_high_winrate_guard()
    test_server_ultimate_five_in_row_sends_events()
    test_server_ultimate_foolish_wisdom_sends_waves_sleep_and_summary()
    print("ultimate_helpers_smoke_test passed")
