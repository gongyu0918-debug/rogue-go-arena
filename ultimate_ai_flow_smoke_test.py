from __future__ import annotations

import asyncio

from app.domain.game_state import GoGame
from app.gameplay.ultimate_ai_flow import (
    apply_ultimate_ai_post_move_effects,
    opponent_color_value,
)


def make_game() -> GoGame:
    return GoGame(size=9, player_color="B")


def test_opponent_color_value_matches_legacy_mapping() -> None:
    assert opponent_color_value("B") == 2
    assert opponent_color_value("W") == 1


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
    test_post_move_effects_syncs_and_checks_removed_stones()
    test_post_move_effects_skips_card_effect_for_pass_but_resolves_pending()
    test_post_move_effects_resolves_pending_without_ai_card()
    test_post_move_effects_counts_pending_removed_stones()
    test_post_move_effects_skips_sync_when_unmodified()
    print("ultimate_ai_flow_smoke_test passed")
