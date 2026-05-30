from __future__ import annotations

import random
from typing import Any, Callable, Optional

from app.gameplay.effect_utils import player_non_pass_coords as player_non_pass_coords_state
from app.gameplay.turn_modifiers import (
    clear_player_turn_modifiers as clear_player_turn_modifiers_state,
    finish_ultimate_quickthink_turn as finish_ultimate_quickthink_turn_state,
    get_ai_rogue_forbidden_points as get_ai_rogue_forbidden_points_state,
    get_player_bonus_forbidden_points as get_player_bonus_forbidden_points_state,
    pick_fog_mask as pick_fog_mask_state,
    pick_fog_point as pick_fog_point_state,
    prepare_player_turn_modifiers as prepare_player_turn_modifiers_state,
    record_ultimate_player_action as record_ultimate_player_action_state,
    record_ultimate_turn as record_ultimate_turn_state,
    refresh_ai_rogue_player_turn as refresh_ai_rogue_player_turn_state,
)


def record_ultimate_turn(game: Any) -> None:
    record_ultimate_turn_state(game)


def record_ultimate_player_action(
    game: Any,
    *,
    record_ultimate_turn_fn: Callable[[Any], None] = record_ultimate_turn,
) -> None:
    record_ultimate_player_action_state(
        game,
        record_ultimate_turn_fn=record_ultimate_turn_fn,
    )


def finish_ultimate_quickthink_turn(game: Any) -> None:
    finish_ultimate_quickthink_turn_state(game)


def pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_mask_state(size, rng)


def pick_fog_point(game: Any, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_point_state(game, rng)


def get_player_bonus_forbidden_points(game: Any, color: str) -> set[tuple[int, int]]:
    return get_player_bonus_forbidden_points_state(game, color)


def player_non_pass_coords(
    game: Any,
    color: str,
    gtp_to_coord: Callable[[str, int], Optional[tuple[int, int]]],
    *,
    limit: Optional[int] = None,
) -> list[tuple[int, int]]:
    return player_non_pass_coords_state(game, color, gtp_to_coord, limit=limit)


def get_ai_rogue_forbidden_points(game: Any) -> list[tuple[int, int]]:
    return get_ai_rogue_forbidden_points_state(game)


def refresh_ai_rogue_player_turn(
    game: Any,
    *,
    pick_fog_mask_fn: Callable[[int, random.Random], list[tuple[int, int]]] = pick_fog_mask,
    pick_fog_point_fn: Callable[[Any, random.Random], list[tuple[int, int]]] = pick_fog_point,
) -> None:
    refresh_ai_rogue_player_turn_state(
        game,
        pick_fog_mask_fn=pick_fog_mask_fn,
        pick_fog_point_fn=pick_fog_point_fn,
    )


def prepare_player_turn_modifiers(
    game: Any,
    *,
    refresh_ai_rogue_player_turn_fn: Callable[[Any], None] = refresh_ai_rogue_player_turn,
) -> None:
    prepare_player_turn_modifiers_state(
        game,
        refresh_ai_rogue_player_turn_fn=refresh_ai_rogue_player_turn_fn,
    )


def clear_player_turn_modifiers(
    game: Any,
    *,
    finish_ultimate_quickthink_turn_fn: Callable[[Any], None] = finish_ultimate_quickthink_turn,
) -> None:
    clear_player_turn_modifiers_state(
        game,
        finish_ultimate_quickthink_turn_fn=finish_ultimate_quickthink_turn_fn,
    )
