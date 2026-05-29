from __future__ import annotations

import asyncio

from app.domain.game_state import GoGame
from app.gameplay.ultimate_ai_flow import (
    choose_ultimate_ai_move,
    apply_ultimate_ai_post_move_effects,
    finish_ultimate_ai_turn,
    opponent_color_value,
)


def make_game() -> GoGame:
    return GoGame(size=9, player_color="B")


def test_opponent_color_value_matches_legacy_mapping() -> None:
    assert opponent_color_value("B") == 2
    assert opponent_color_value("W") == 1


def fake_gtp_to_coord(gtp: str, _size: int) -> tuple[int, int] | None:
    return {
        "C3": (2, 2),
        "D4": (3, 3),
        "E5": (4, 4),
        "F6": (5, 5),
        "G7": (6, 6),
    }.get(gtp.upper())


def fake_coord_to_gtp(x: int, y: int, _size: int) -> str:
    return f"{x},{y}"


async def _choose_ultimate_ai_move_replaces_resign() -> None:
    game = make_game()
    calls = []

    async def generate_move():
        calls.append("generate")
        return "RESIGN"

    async def no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D4"

    async def unused_async(*_args, **_kwargs):
        calls.append("unused")
        return None

    choice = await choose_ultimate_ai_move(
        game,
        color="W",
        visits=100,
        forbidden=set(),
        generate_move=generate_move,
        no_resign_move=no_resign,
        undo_engine_move=lambda: calls.append("undo"),
        pick_ranked_legal_move=unused_async,
        pick_nonpass_fallback_move=unused_async,
        retry_avoiding_ko=lambda *_args: unused_async(),
        is_suspicious_ai_pass=lambda *_args: False,
        resolve_occupied_ai_move=lambda _game, _color, move, coord, **_kwargs: (move, coord),
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        log_fn=lambda msg: calls.append(("log", msg)),
    )

    assert choice.gtp_move == "D4"
    assert choice.coord == (3, 3)
    assert calls == ["generate", ("no_resign", True, "W")]


def test_choose_ultimate_ai_move_replaces_resign() -> None:
    asyncio.run(_choose_ultimate_ai_move_replaces_resign())


async def _choose_ultimate_ai_move_avoids_forbidden_and_suspicious_pass() -> None:
    game = make_game()
    calls = []

    async def forbidden_generate():
        return "C3"

    async def ranked(game_arg, color, visits, forbidden, *, time_limit):
        calls.append(("ranked", game_arg is game, color, visits, forbidden, time_limit))
        return "pass"

    forbidden_choice = await choose_ultimate_ai_move(
        game,
        color="W",
        visits=321,
        forbidden={(2, 2)},
        generate_move=forbidden_generate,
        no_resign_move=lambda *_args: None,
        undo_engine_move=lambda: calls.append("undo"),
        pick_ranked_legal_move=ranked,
        pick_nonpass_fallback_move=lambda *_args: None,
        retry_avoiding_ko=lambda *_args: None,
        is_suspicious_ai_pass=lambda *_args: False,
        resolve_occupied_ai_move=lambda _game, _color, move, coord, **_kwargs: (move, coord),
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        log_fn=lambda msg: calls.append(("log", msg)),
    )
    assert forbidden_choice.gtp_move == "pass"
    assert forbidden_choice.coord is None
    assert calls == [
        "undo",
        ("ranked", True, "W", 321, {(2, 2)}, 1.2),
    ]

    calls = []

    async def pass_generate():
        return "pass"

    async def fallback(game_arg, color, visits, forbidden):
        calls.append(("fallback", game_arg is game, color, visits, forbidden))
        return "E5"

    fallback_choice = await choose_ultimate_ai_move(
        game,
        color="W",
        visits=111,
        forbidden={(1, 1)},
        generate_move=pass_generate,
        no_resign_move=lambda *_args: None,
        undo_engine_move=lambda: calls.append("undo"),
        pick_ranked_legal_move=lambda *_args, **_kwargs: None,
        pick_nonpass_fallback_move=fallback,
        retry_avoiding_ko=lambda *_args: None,
        is_suspicious_ai_pass=lambda *_args: True,
        resolve_occupied_ai_move=lambda _game, _color, move, coord, **_kwargs: (move, coord),
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        log_fn=lambda msg: calls.append(("log", msg)),
    )

    assert fallback_choice.gtp_move == "E5"
    assert fallback_choice.coord == (4, 4)
    assert calls == [
        ("fallback", True, "W", 111, {(1, 1)}),
        ("log", "Suspicious early PASS in ultimate mode, replaced with E5"),
    ]


def test_choose_ultimate_ai_move_avoids_forbidden_and_suspicious_pass() -> None:
    asyncio.run(_choose_ultimate_ai_move_avoids_forbidden_and_suspicious_pass())


async def _choose_ultimate_ai_move_resolves_occupied_and_ko() -> None:
    game = make_game()
    calls = []
    game.is_ko = lambda x, y, color: calls.append(("ko", x, y, color)) or True

    async def generate_move():
        return "D4"

    async def retry(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "G7"

    def resolve_occupied(game_arg, color, move, coord, **kwargs):
        calls.append((
            "resolve",
            game_arg is game,
            color,
            move,
            coord,
            kwargs["coord_to_gtp"] is fake_coord_to_gtp,
        ))
        return "F6", (5, 5)

    choice = await choose_ultimate_ai_move(
        game,
        color="W",
        visits=100,
        forbidden=set(),
        generate_move=generate_move,
        no_resign_move=lambda *_args: None,
        undo_engine_move=lambda: calls.append("undo"),
        pick_ranked_legal_move=lambda *_args, **_kwargs: None,
        pick_nonpass_fallback_move=lambda *_args: None,
        retry_avoiding_ko=retry,
        is_suspicious_ai_pass=lambda *_args: False,
        resolve_occupied_ai_move=resolve_occupied,
        gtp_to_coord=fake_gtp_to_coord,
        coord_to_gtp=fake_coord_to_gtp,
        log_fn=lambda msg: calls.append(("log", msg)),
    )

    assert choice.gtp_move == "G7"
    assert choice.coord == (6, 6)
    assert calls == [
        ("resolve", True, "W", "D4", (3, 3), True),
        ("ko", 5, 5, "W"),
        ("retry", True, "W"),
    ]


def test_choose_ultimate_ai_move_resolves_occupied_and_ko() -> None:
    asyncio.run(_choose_ultimate_ai_move_resolves_occupied_and_ko())


async def _finish_ultimate_ai_turn_finishes_normal_turn() -> None:
    game = make_game()
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)
        calls.append(("send", payload["type"]))

    def apply_result(game_arg, color, move, coord, **kwargs):
        calls.append((
            "apply_result",
            game_arg is game,
            color,
            move,
            coord,
            kwargs["count_turn"],
            kwargs["record_ultimate_turn_fn"] is record_turn,
        ))
        return 2

    def record_turn(_game):
        calls.append("record_turn")

    async def capture_foul(game_arg, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", game_arg is game, send_fn is send, offender, captured, ultimate))

    async def post_effects(game_arg, send_fn, **kwargs):
        calls.append(("post", game_arg is game, send_fn is send, kwargs["ai_card"], kwargs["gtp_move"]))
        return False

    def choose_bonus(game_arg, **kwargs):
        calls.append(("choose_bonus", game_arg is game, kwargs["ai_card"], kwargs["allow_double_bonus"]))
        return None

    async def run_bonus(*_args):
        calls.append("run_bonus")
        return True

    def finish_normal(game_arg, **kwargs):
        calls.append(("finish_normal", game_arg is game, kwargs["prepare_player_turn_modifiers_fn"] is prepare))

    def prepare(_game):
        calls.append("prepare")

    async def force_score(*_args):
        calls.append("force_score")

    recursed = await finish_ultimate_ai_turn(
        game,
        send,
        color="W",
        ai_card="meteor",
        gtp_move="D4",
        coord=(3, 3),
        allow_double_bonus=True,
        chain_chance=0.25,
        chain_random=lambda: 0.5,
        apply_ai_move_result=apply_result,
        record_ultimate_turn=record_turn,
        check_capture_foul=capture_foul,
        post_move_effects=post_effects,
        count_stones=lambda *_args: 0,
        apply_ultimate_effect=lambda *_args: None,
        resolve_pending_ultimate_shadow_links=lambda *_args: None,
        sync_board_to_katago=lambda *_args: None,
        choose_bonus_turn=choose_bonus,
        run_bonus_turn=run_bonus,
        finish_normal_turn=finish_normal,
        prepare_player_turn_modifiers=prepare,
        force_score=force_score,
    )

    assert recursed is False
    assert calls == [
        ("apply_result", True, "W", "D4", (3, 3), True, True),
        ("capture_foul", True, True, "W", 2, True),
        ("send", "ai_move"),
        ("post", True, True, "meteor", "D4"),
        ("choose_bonus", True, "meteor", True),
        ("finish_normal", True, True),
        ("send", "game_state"),
    ]
    assert sent[0] == {"type": "ai_move", "gtp": "D4", "color": "W", "x": 3, "y": 3}


def test_finish_ultimate_ai_turn_finishes_normal_turn() -> None:
    asyncio.run(_finish_ultimate_ai_turn_finishes_normal_turn())


async def _finish_ultimate_ai_turn_handles_bonus_recursion() -> None:
    game = make_game()
    calls = []
    bonus = object()

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    async def post_effects(*_args, **_kwargs):
        calls.append("post")
        return False

    def choose_bonus(_game, **_kwargs):
        calls.append("choose_bonus")
        return bonus

    async def run_bonus(game_arg, send_fn, color, bonus_arg):
        calls.append(("run_bonus", game_arg is game, color, bonus_arg is bonus))
        return True

    recursed = await finish_ultimate_ai_turn(
        game,
        send,
        color="W",
        ai_card="double",
        gtp_move="D4",
        coord=(3, 3),
        allow_double_bonus=True,
        chain_chance=0.25,
        chain_random=lambda: 0.0,
        apply_ai_move_result=lambda *_args, **_kwargs: 0,
        record_ultimate_turn=lambda _game: None,
        check_capture_foul=capture_foul,
        post_move_effects=post_effects,
        count_stones=lambda *_args: 0,
        apply_ultimate_effect=lambda *_args: None,
        resolve_pending_ultimate_shadow_links=lambda *_args: None,
        sync_board_to_katago=lambda *_args: None,
        choose_bonus_turn=choose_bonus,
        run_bonus_turn=run_bonus,
        finish_normal_turn=lambda *_args, **_kwargs: calls.append("finish_normal"),
        prepare_player_turn_modifiers=lambda _game: None,
        force_score=lambda *_args: None,
    )

    assert recursed is True
    assert calls == [
        "capture_foul",
        ("send", "ai_move"),
        "post",
        "choose_bonus",
        ("run_bonus", True, "W", True),
    ]


def test_finish_ultimate_ai_turn_handles_bonus_recursion() -> None:
    asyncio.run(_finish_ultimate_ai_turn_handles_bonus_recursion())


async def _finish_ultimate_ai_turn_continues_when_bonus_does_not_recurse() -> None:
    game = make_game()
    calls = []
    bonus = object()

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    async def post_effects(*_args, **_kwargs):
        calls.append("post")
        return False

    def choose_bonus(_game, **_kwargs):
        calls.append("choose_bonus")
        return bonus

    async def run_bonus(game_arg, send_fn, color, bonus_arg):
        calls.append(("run_bonus", game_arg is game, color, bonus_arg is bonus))
        return False

    recursed = await finish_ultimate_ai_turn(
        game,
        send,
        color="W",
        ai_card="chain",
        gtp_move="D4",
        coord=(3, 3),
        allow_double_bonus=True,
        chain_chance=0.25,
        chain_random=lambda: 0.0,
        apply_ai_move_result=lambda *_args, **_kwargs: 0,
        record_ultimate_turn=lambda _game: None,
        check_capture_foul=capture_foul,
        post_move_effects=post_effects,
        count_stones=lambda *_args: 0,
        apply_ultimate_effect=lambda *_args: None,
        resolve_pending_ultimate_shadow_links=lambda *_args: None,
        sync_board_to_katago=lambda *_args: None,
        choose_bonus_turn=choose_bonus,
        run_bonus_turn=run_bonus,
        finish_normal_turn=lambda *_args, **_kwargs: calls.append("finish_normal"),
        prepare_player_turn_modifiers=lambda _game: None,
        force_score=lambda *_args: None,
    )

    assert recursed is False
    assert calls == [
        "capture_foul",
        ("send", "ai_move"),
        "post",
        "choose_bonus",
        ("run_bonus", True, "W", True),
        "finish_normal",
        ("send", "game_state"),
    ]


def test_finish_ultimate_ai_turn_continues_when_bonus_does_not_recurse() -> None:
    asyncio.run(_finish_ultimate_ai_turn_continues_when_bonus_does_not_recurse())


async def _finish_ultimate_ai_turn_force_scores_after_move_limit() -> None:
    game = make_game()
    game.ultimate_move_count = 20
    calls = []

    async def send(payload):
        calls.append(("send", payload["type"]))

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    async def post_effects(*_args, **_kwargs):
        calls.append("post")
        return False

    async def force_score(game_arg, send_fn):
        calls.append(("force_score", game_arg is game, send_fn is send))

    recursed = await finish_ultimate_ai_turn(
        game,
        send,
        color="W",
        ai_card=None,
        gtp_move="pass",
        coord=None,
        allow_double_bonus=False,
        chain_chance=0.25,
        chain_random=lambda: 1.0,
        apply_ai_move_result=lambda *_args, **_kwargs: 0,
        record_ultimate_turn=lambda _game: None,
        check_capture_foul=capture_foul,
        post_move_effects=post_effects,
        count_stones=lambda *_args: 0,
        apply_ultimate_effect=lambda *_args: None,
        resolve_pending_ultimate_shadow_links=lambda *_args: None,
        sync_board_to_katago=lambda *_args: None,
        choose_bonus_turn=lambda *_args, **_kwargs: None,
        run_bonus_turn=lambda *_args: None,
        finish_normal_turn=lambda *_args, **_kwargs: calls.append("finish_normal"),
        prepare_player_turn_modifiers=lambda _game: None,
        force_score=force_score,
    )

    assert recursed is False
    assert calls == [
        "capture_foul",
        ("send", "ai_move"),
        "post",
        "finish_normal",
        ("send", "game_state"),
        ("force_score", True, True),
    ]


def test_finish_ultimate_ai_turn_force_scores_after_move_limit() -> None:
    asyncio.run(_finish_ultimate_ai_turn_force_scores_after_move_limit())


async def _post_move_effects_syncs_and_checks_removed_stones() -> None:
    game = make_game()
    game.board[0][0] = 1
    game.board[1][1] = 1
    calls = []

    async def send(payload):
        calls.append(("send", payload))

    def count_stones(game_arg, color_value):
        return sum(cell == color_value for row in game_arg.board for cell in row)

    async def apply_effect(game_arg, send_fn, x, y, color, card):
        calls.append(("effect", x, y, color, card, send_fn is send))
        game_arg.board[0][0] = 0
        return True

    async def resolve_pending(game_arg, send_fn):
        calls.append(("pending", send_fn is send))
        return False

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def capture_foul(game_arg, send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate, send_fn is send))

    modified = await apply_ultimate_ai_post_move_effects(
        game,
        send,
        color="W",
        ai_card="meteor",
        gtp_move="D4",
        coord=(3, 3),
        count_stones=count_stones,
        apply_ultimate_effect=apply_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending,
        sync_board_to_katago=sync,
        check_capture_foul=capture_foul,
    )

    assert modified is True
    assert calls == [
        ("effect", 3, 3, "W", "meteor", True),
        ("pending", True),
        ("sync", True),
        ("capture_foul", "W", 1, True, True),
    ]


def test_post_move_effects_syncs_and_checks_removed_stones() -> None:
    asyncio.run(_post_move_effects_syncs_and_checks_removed_stones())


async def _post_move_effects_skips_card_effect_for_pass_but_resolves_pending() -> None:
    game = make_game()
    calls = []

    async def send(_payload):
        return None

    def count_stones(_game, _color_value):
        return 0

    async def apply_effect(*_args):
        calls.append("effect")
        return True

    async def resolve_pending(_game, _send_fn):
        calls.append("pending")
        return True

    async def sync(_game):
        calls.append("sync")

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    modified = await apply_ultimate_ai_post_move_effects(
        game,
        send,
        color="W",
        ai_card="meteor",
        gtp_move="pass",
        coord=(3, 3),
        count_stones=count_stones,
        apply_ultimate_effect=apply_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending,
        sync_board_to_katago=sync,
        check_capture_foul=capture_foul,
    )

    assert modified is True
    assert calls == ["pending", "sync"]


def test_post_move_effects_skips_card_effect_for_pass_but_resolves_pending() -> None:
    asyncio.run(_post_move_effects_skips_card_effect_for_pass_but_resolves_pending())


async def _post_move_effects_resolves_pending_without_ai_card() -> None:
    game = make_game()
    calls = []

    async def send(_payload):
        return None

    def count_stones(_game, _color_value):
        return 0

    async def apply_effect(*_args):
        calls.append("effect")
        return True

    async def resolve_pending(_game, _send_fn):
        calls.append("pending")
        return True

    async def sync(_game):
        calls.append("sync")

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    modified = await apply_ultimate_ai_post_move_effects(
        game,
        send,
        color="W",
        ai_card=None,
        gtp_move="D4",
        coord=(3, 3),
        count_stones=count_stones,
        apply_ultimate_effect=apply_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending,
        sync_board_to_katago=sync,
        check_capture_foul=capture_foul,
    )

    assert modified is True
    assert calls == ["pending", "sync"]


def test_post_move_effects_resolves_pending_without_ai_card() -> None:
    asyncio.run(_post_move_effects_resolves_pending_without_ai_card())


async def _post_move_effects_counts_pending_removed_stones() -> None:
    game = make_game()
    game.board[0][0] = 1
    calls = []

    async def send(_payload):
        return None

    def count_stones(game_arg, color_value):
        return sum(cell == color_value for row in game_arg.board for cell in row)

    async def apply_effect(*_args):
        calls.append("effect")
        return False

    async def resolve_pending(game_arg, _send_fn):
        calls.append("pending")
        game_arg.board[0][0] = 0
        return True

    async def sync(_game):
        calls.append("sync")

    async def capture_foul(_game, _send_fn, offender, captured, *, ultimate):
        calls.append(("capture_foul", offender, captured, ultimate))

    modified = await apply_ultimate_ai_post_move_effects(
        game,
        send,
        color="W",
        ai_card="meteor",
        gtp_move="D4",
        coord=(3, 3),
        count_stones=count_stones,
        apply_ultimate_effect=apply_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending,
        sync_board_to_katago=sync,
        check_capture_foul=capture_foul,
    )

    assert modified is True
    assert calls == [
        "effect",
        "pending",
        "sync",
        ("capture_foul", "W", 1, True),
    ]


def test_post_move_effects_counts_pending_removed_stones() -> None:
    asyncio.run(_post_move_effects_counts_pending_removed_stones())


async def _post_move_effects_skips_sync_when_unmodified() -> None:
    game = make_game()
    calls = []

    async def send(_payload):
        return None

    def count_stones(_game, _color_value):
        calls.append("count")
        return 0

    async def apply_effect(*_args):
        calls.append("effect")
        return False

    async def resolve_pending(*_args):
        calls.append("pending")
        return False

    async def sync(_game):
        calls.append("sync")

    async def capture_foul(*_args, **_kwargs):
        calls.append("capture_foul")

    modified = await apply_ultimate_ai_post_move_effects(
        game,
        send,
        color="W",
        ai_card="meteor",
        gtp_move="D4",
        coord=(3, 3),
        count_stones=count_stones,
        apply_ultimate_effect=apply_effect,
        resolve_pending_ultimate_shadow_links=resolve_pending,
        sync_board_to_katago=sync,
        check_capture_foul=capture_foul,
    )

    assert modified is False
    assert calls == ["count", "effect", "pending"]


def test_post_move_effects_skips_sync_when_unmodified() -> None:
    asyncio.run(_post_move_effects_skips_sync_when_unmodified())


if __name__ == "__main__":
    test_opponent_color_value_matches_legacy_mapping()
    test_choose_ultimate_ai_move_replaces_resign()
    test_choose_ultimate_ai_move_avoids_forbidden_and_suspicious_pass()
    test_choose_ultimate_ai_move_resolves_occupied_and_ko()
    test_finish_ultimate_ai_turn_finishes_normal_turn()
    test_finish_ultimate_ai_turn_handles_bonus_recursion()
    test_finish_ultimate_ai_turn_continues_when_bonus_does_not_recurse()
    test_finish_ultimate_ai_turn_force_scores_after_move_limit()
    test_post_move_effects_syncs_and_checks_removed_stones()
    test_post_move_effects_skips_card_effect_for_pass_but_resolves_pending()
    test_post_move_effects_resolves_pending_without_ai_card()
    test_post_move_effects_counts_pending_removed_stones()
    test_post_move_effects_skips_sync_when_unmodified()
    print("ultimate_ai_flow_smoke_test passed")
