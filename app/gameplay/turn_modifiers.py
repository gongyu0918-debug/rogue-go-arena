from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any

import app.config.gameplay as gameplay_config
from app.gameplay.effect_utils import get_square_points


def pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    cx = rng.randint(0, size - 1)
    cy = rng.randint(0, size - 1)
    return get_square_points(cx, cy, gameplay_config.ROGUE_FOG_MASK_RADIUS, size)


def pick_fog_point(game: Any, rng: random.Random) -> list[tuple[int, int]]:
    candidates = [
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
        if game.board[y][x] == 0
    ]
    if not candidates:
        return []
    return [rng.choice(candidates)]


def get_ai_rogue_forbidden_points(game: Any) -> list[tuple[int, int]]:
    card = game.ai_rogue_card
    if card in {"blackhole", "golden_corner", "fog"}:
        return list(game.ai_rogue_seal_points)
    return []


def get_player_bonus_forbidden_points(game: Any, color: str) -> set[tuple[int, int]]:
    if game.two_player:
        return set()
    if color != game.player_color:
        return set()
    return set(get_ai_rogue_forbidden_points(game))


def record_ultimate_turn(game: Any) -> None:
    game.ultimate_move_count += 1


def apply_ultimate_ai_move_result(
    game: Any,
    color: str,
    gtp_move: str,
    coord: tuple[int, int] | None,
    *,
    count_turn: bool,
    record_ultimate_turn_fn: Callable[[Any], None] | None = None,
) -> int:
    record_turn = record_ultimate_turn if record_ultimate_turn_fn is None else record_ultimate_turn_fn
    if count_turn:
        record_turn(game)
    game.moves.append((color, gtp_move))

    if gtp_move.upper() != "PASS" and coord is not None:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
        return captured

    game.passed[color] = True
    return 0


def record_ultimate_player_action(
    game: Any,
    *,
    record_ultimate_turn_fn: Callable[[Any], None] | None = None,
) -> None:
    record_turn = record_ultimate_turn if record_ultimate_turn_fn is None else record_ultimate_turn_fn
    if game.ultimate_player_card == "quickthink" and game.ultimate_quickthink_active:
        if not game.ultimate_quickthink_turn_counted:
            record_turn(game)
            game.ultimate_quickthink_turn_counted = True
        return
    if not game.ultimate_double_pending:
        record_turn(game)


def finish_ultimate_quickthink_turn(game: Any) -> None:
    game.ultimate_quickthink_active = False
    game.ultimate_quickthink_turn_counted = False


def refresh_ai_rogue_player_turn(
    game: Any,
    *,
    rng_factory: Callable[[], random.Random] | None = None,
    pick_fog_mask_fn: Callable[[int, random.Random], list[tuple[int, int]]] = pick_fog_mask,
    pick_fog_point_fn: Callable[[Any, random.Random], list[tuple[int, int]]] = pick_fog_point,
) -> None:
    if game.two_player or not game.ai_rogue_enabled:
        return
    if game.ai_rogue_card != "fog":
        return
    if game.current_player != game.player_color:
        game.ai_rogue_seal_points = []
        return

    rng = rng_factory() if rng_factory else random.Random(time.time_ns())
    player_move_count = sum(
        1
        for color, move in game.moves
        if color == game.player_color and move.upper() != "PASS"
    )
    if player_move_count < gameplay_config.ROGUE_FOG_AI_MOVES:
        game.ai_rogue_seal_points = pick_fog_mask_fn(game.size, rng)
        return

    fog_pts: list[tuple[int, int]] = []
    for _ in range(gameplay_config.ROGUE_FOG_POST_MASK_POINTS):
        fog_pts.extend(pick_fog_point_fn(game, rng))
    seen: set[tuple[int, int]] = set()
    game.ai_rogue_seal_points = [point for point in fog_pts if not (point in seen or seen.add(point))]


def prepare_player_turn_modifiers(
    game: Any,
    *,
    refresh_ai_rogue_player_turn_fn: Callable[[Any], None] = refresh_ai_rogue_player_turn,
) -> None:
    if game.two_player or game.current_player != game.player_color:
        return
    refresh_ai_rogue_player_turn_fn(game)
    if game.rogue_card == "quickthink" and game.rogue_quickthink_stage == 0:
        game.rogue_quickthink_stage = 1
    if game.ultimate and game.ultimate_player_card == "quickthink" and not game.ultimate_quickthink_active:
        game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True


def finish_ultimate_ai_normal_turn(
    game: Any,
    *,
    prepare_player_turn_modifiers_fn: Callable[[Any], None] = prepare_player_turn_modifiers,
) -> None:
    game.ultimate_extra_turn = False
    game.current_player = game.player_color
    prepare_player_turn_modifiers_fn(game)
    game.push_history()


def clear_player_turn_modifiers(
    game: Any,
    *,
    finish_ultimate_quickthink_turn_fn: Callable[[Any], None] = finish_ultimate_quickthink_turn,
) -> None:
    game.rogue_quickthink_stage = 0
    finish_ultimate_quickthink_turn_fn(game)
