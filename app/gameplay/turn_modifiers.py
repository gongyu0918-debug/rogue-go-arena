from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import app.config.gameplay as gameplay_config
from app.domain.coordinates import gtp_to_coord
from app.gameplay.effect_utils import diamond_points, get_square_points


@dataclass(frozen=True)
class UltimateAiBonusTurn:
    kind: str
    message: str
    next_allow_double_bonus: bool


def pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    cx = rng.randint(0, size - 1)
    cy = rng.randint(0, size - 1)
    return get_square_points(cx, cy, gameplay_config.ROGUE_FOG_MASK_RADIUS, size)


def pick_fog_point(game: Any, rng: random.Random) -> list[tuple[int, int]]:
    last_ai_coord = None
    for move_color, move in reversed(game.moves):
        if move_color != game.ai_color or move.upper() == "PASS":
            continue
        last_ai_coord = gtp_to_coord(move, game.size)
        break
    if last_ai_coord:
        candidates = [
            (x, y)
            for x, y in diamond_points(last_ai_coord[0], last_ai_coord[1], 1, game.size)
            if game.board[y][x] == 0
        ]
        if candidates:
            return [rng.choice(candidates)]
        return []

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


def has_methodical_card(game: Any) -> bool:
    return game.rogue_card == "methodical"


def prepare_methodical_turn(game: Any) -> None:
    if game.two_player or not has_methodical_card(game):
        return
    if game.current_player != game.player_color:
        return
    if game.rogue_methodical_remaining > 0:
        return

    game.rogue_methodical_turns[game.player_color] += 1
    turn_count = game.rogue_methodical_turns[game.player_color]
    game.rogue_methodical_remaining = (
        gameplay_config.ROGUE_METHODICAL_BONUS_PLAYS
        if turn_count % gameplay_config.ROGUE_METHODICAL_BONUS_INTERVAL == 0
        else gameplay_config.ROGUE_METHODICAL_BASE_PLAYS
    )


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
    prepare_methodical_turn(game)
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


def choose_ultimate_ai_bonus_turn(
    game: Any,
    *,
    ai_card: str | None,
    gtp_move: str,
    allow_double_bonus: bool,
    chain_random: Callable[[], float],
    chain_chance: float,
) -> UltimateAiBonusTurn | None:
    if game.game_over or gtp_move.upper() == "PASS":
        return None
    if ai_card == "chain" and chain_random() < chain_chance:
        return UltimateAiBonusTurn(
            kind="chain",
            message="AI 的连珠棋触发，AI 将继续落子",
            next_allow_double_bonus=True,
        )
    if ai_card == "double" and allow_double_bonus:
        return UltimateAiBonusTurn(
            kind="double",
            message="AI 的双刀流触发，AI 将继续落子",
            next_allow_double_bonus=False,
        )
    return None


def start_ultimate_ai_bonus_turn(game: Any, color: str) -> None:
    game.ultimate_extra_turn = True
    game.current_player = color


def clear_player_turn_modifiers(
    game: Any,
    *,
    finish_ultimate_quickthink_turn_fn: Callable[[Any], None] = finish_ultimate_quickthink_turn,
) -> None:
    game.rogue_quickthink_stage = 0
    finish_ultimate_quickthink_turn_fn(game)
