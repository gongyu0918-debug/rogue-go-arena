from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import random
import time
from typing import Any

import app.config.gameplay as gameplay_config
from app.gameplay.effect_utils import (
    adjacent8_points,
    adjacent_points,
    clear_random_enemy_stones,
    diamond_points,
    find_corner_with_min_stones,
    find_exact_five_lines,
    find_new_fool_shapes,
    get_blackhole_points,
    get_corner_helper_spawn_points,
    get_golden_corner_points,
    get_sansan_points,
    get_square_points,
    get_star_points,
    line_endpoints,
    player_non_pass_coords,
    pick_joseki_targets,
    random_hidden_center,
    set_points_to_color,
    shape_center,
    spawn_bonus_points,
    spawn_random_owned_stones,
)
from app.data.cards import challenge_card_category, challenge_category_counts


ShufflePointsFn = Callable[[list[tuple[int, int]]], None]
CoordFormatter = Callable[[int, int, int], str | None]
ChooseCornerFn = Callable[[], int]
RngFactory = Callable[[], random.Random]
PointListFn = Callable[[int], list[tuple[int, int]]]
GoldenCornerFn = Callable[[int, int, int], list[tuple[int, int]]]
JosekiTargetsFn = Callable[[int, int], list[tuple[int, int]]]
HiddenCenterFn = Callable[[int, int, random.Random], tuple[int, int]]
DiamondPointsFn = Callable[[int, int, int, int], list[tuple[int, int]]]
RefreshAiRogueTurnFn = Callable[[Any], None]
CardIdsFn = Callable[[list[str]], list[str]]
GetCardFn = Callable[[str], dict[str, Any]]
ActiveUseBonusFn = Callable[[Any, str], int]
ZonePointsFn = Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]


@dataclass
class RogueBoardEffectResult:
    modified: bool
    messages: list[str]
    trap_bonus_sources: list[str]


@dataclass
class RogueCardActivationResult:
    messages: list[str]
    sync_komi: bool = False


@dataclass
class ChallengeRogueLoadoutResult:
    cards: list[str]


def reset_rogue_effect_state(
    game: Any,
    *,
    reset_uses: bool = False,
    reset_handicap: bool = False,
) -> None:
    if reset_uses:
        game.rogue_uses = {}
    game.rogue_waiting_seal = False
    game.rogue_skip_ai = False
    game.rogue_joseki_targets = []
    game.rogue_joseki_hits = 0
    game.rogue_joseki_done = False
    game.rogue_godhand_center = None
    game.rogue_godhand_trigger = []
    game.rogue_godhand_done = False
    game.rogue_sansan_trap_done = False
    game.rogue_corner_helper_done = set()
    game.rogue_sanrensei_done = False
    game.rogue_puppet_target = None
    game.rogue_five_in_row_seen = set()
    game.rogue_last_stand_done = {"B": False, "W": False}
    game.rogue_capture_foul_progress = {"B": 0, "W": 0}
    game.rogue_defense_first_triggers = {"B": 0, "W": 0}
    game.rogue_attack_first_triggers = {"B": 0, "W": 0}
    game.rogue_defense_first_last_index = {"B": 0, "W": 0}
    game.rogue_attack_first_last_index = {"B": 0, "W": 0}
    game.rogue_methodical_turns = {"B": 0, "W": 0}
    game.rogue_methodical_remaining = 0
    game.rogue_coach_moves_left = 0
    game.rogue_coach_bonus_checked = False
    game.rogue_quickthink_stage = 0
    game.rogue_fool_shapes = set()
    game.rogue_seal_points = []
    if reset_handicap:
        game.rogue_handicap_passes = 0
        game.rogue_handicap_active = False
        game.rogue_handicap_bonuses = 0


def apply_rogue_card_uses(game: Any, card_id: str, card_def: dict[str, Any], *, bonus: int = 0) -> None:
    if "uses" in card_def:
        game.rogue_uses[card_id] = card_def["uses"] + bonus


def apply_rogue_card_activation(
    game: Any,
    card_id: str,
    card_def: dict[str, Any],
    *,
    coord_to_gtp: CoordFormatter,
    choose_corner: ChooseCornerFn = lambda: random.randint(0, 3),
    make_rng: RngFactory = random.Random,
    get_blackhole_points_fn: PointListFn = get_blackhole_points,
    get_golden_corner_points_fn: GoldenCornerFn = get_golden_corner_points,
    pick_joseki_targets_fn: JosekiTargetsFn = pick_joseki_targets,
    random_hidden_center_fn: HiddenCenterFn = random_hidden_center,
    diamond_points_fn: DiamondPointsFn = diamond_points,
) -> RogueCardActivationResult:
    game.rogue_card = card_id
    reset_rogue_effect_state(game)
    apply_rogue_card_uses(game, card_id, card_def)

    messages: list[str] = []
    sync_komi = False
    if card_id == "komi_relief":
        if game.player_color == "B":
            game.komi = max(0.5, game.komi - 7.0)
        else:
            game.komi = game.komi + 7.0
        sync_komi = True
    elif card_id == "seal":
        game.rogue_waiting_seal = True
    elif card_id == "blackhole":
        game.rogue_seal_points = get_blackhole_points_fn(game.size)
        messages.append("黑洞已锁定中央区域，整局都会限制 AI 进入")
    elif card_id == "golden_corner":
        corner = choose_corner()
        game.rogue_seal_points = get_golden_corner_points_fn(
            game.size,
            corner,
            gameplay_config.ROGUE_GOLDEN_CORNER_SPAN,
        )
        corner_names = ["左上角", "右上角", "左下角", "右下角"]
        messages.append(
            f"黄金角已封锁 {corner_names[corner]} 的 "
            f"{gameplay_config.ROGUE_GOLDEN_CORNER_SPAN}x"
            f"{gameplay_config.ROGUE_GOLDEN_CORNER_SPAN} 区域，整局都会限制 AI 进入"
        )
    elif card_id == "joseki_ocd":
        game.rogue_joseki_targets = pick_joseki_targets_fn(
            game.size,
            gameplay_config.ROGUE_JOSEKI_TARGET_COUNT,
        )
        pts_str = ", ".join(
            coord_to_gtp(px, py, game.size)
            for px, py in game.rogue_joseki_targets
        )
        messages.append(
            f"定式强迫症已点亮 {gameplay_config.ROGUE_JOSEKI_TARGET_COUNT} 个目标点：{pts_str}。"
            f"命中其中 {gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS} 个后会自动补上剩余 "
            f"{gameplay_config.ROGUE_JOSEKI_TARGET_COUNT - gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS} 个点位"
        )
    elif card_id == "handicap_quest":
        messages.append(
            f"让子任务开始：你需要先虚手 {gameplay_config.ROGUE_HANDICAP_REQUIRED_PASSES} 次，"
            f"之后每下满 {gameplay_config.ROGUE_HANDICAP_BONUS_INTERVAL} 手可再让 AI 虚手一次"
        )
    elif card_id == "god_hand":
        rng = make_rng()
        game.rogue_godhand_center = random_hidden_center_fn(game.size, 2, rng)
        game.rogue_godhand_trigger = diamond_points_fn(
            game.rogue_godhand_center[0],
            game.rogue_godhand_center[1],
            gameplay_config.ROGUE_GODHAND_RADIUS,
            game.size,
        )
    elif card_id == "quickthink" and game.current_player == game.player_color:
        game.rogue_quickthink_stage = 1
    elif card_id == "methodical" and game.current_player == game.player_color:
        game.rogue_methodical_turns[game.player_color] += 1
        turn_count = game.rogue_methodical_turns[game.player_color]
        game.rogue_methodical_remaining = (
            gameplay_config.ROGUE_METHODICAL_BONUS_PLAYS
            if turn_count % gameplay_config.ROGUE_METHODICAL_BONUS_INTERVAL == 0
            else gameplay_config.ROGUE_METHODICAL_BASE_PLAYS
        )
    elif card_id == "coach_mode":
        game.rogue_uses.setdefault("coach_mode", 1)

    return RogueCardActivationResult(messages=messages, sync_komi=sync_komi)


def apply_ai_rogue_card_activation(
    game: Any,
    card_id: str,
    *,
    choose_corner: ChooseCornerFn = lambda: random.randint(0, 3),
    get_blackhole_points_fn: PointListFn = get_blackhole_points,
    get_golden_corner_points_fn: GoldenCornerFn = get_golden_corner_points,
    refresh_ai_rogue_player_turn_fn: RefreshAiRogueTurnFn,
    golden_corner_span: int = gameplay_config.ROGUE_GOLDEN_CORNER_SPAN,
) -> None:
    game.ai_rogue_enabled = True
    game.ai_rogue_card = card_id
    game.ai_rogue_seal_points = []
    game.ai_rogue_sansan_trap_done = False

    if card_id == "blackhole":
        game.ai_rogue_seal_points = get_blackhole_points_fn(game.size)
    elif card_id == "golden_corner":
        corner = choose_corner()
        game.ai_rogue_seal_points = get_golden_corner_points_fn(
            game.size,
            corner,
            golden_corner_span,
        )
    elif card_id == "fog":
        refresh_ai_rogue_player_turn_fn(game)


def apply_challenge_rogue_loadout(
    game: Any,
    *,
    card_ids_fn: CardIdsFn,
    get_rogue_card_fn: GetCardFn,
    active_use_bonus_fn: ActiveUseBonusFn | None = None,
    challenge_zone_points_fn: ZonePointsFn | None = None,
    choose_corner: ChooseCornerFn = lambda: random.randint(0, 3),
    make_rng: RngFactory = random.Random,
    get_blackhole_points_fn: PointListFn = get_blackhole_points,
    get_golden_corner_points_fn: GoldenCornerFn = get_golden_corner_points,
    pick_joseki_targets_fn: JosekiTargetsFn = pick_joseki_targets,
    random_hidden_center_fn: HiddenCenterFn = random_hidden_center,
    diamond_points_fn: DiamondPointsFn = diamond_points,
    golden_corner_span: int = gameplay_config.ROGUE_GOLDEN_CORNER_SPAN,
    joseki_target_count: int = gameplay_config.ROGUE_JOSEKI_TARGET_COUNT,
    godhand_radius: int = gameplay_config.ROGUE_GODHAND_RADIUS,
) -> ChallengeRogueLoadoutResult:
    if active_use_bonus_fn is None:
        active_use_bonus_fn = challenge_active_use_bonus
    if challenge_zone_points_fn is None:
        challenge_zone_points_fn = challenge_zone_points

    cards = [
        card_id
        for card_id in card_ids_fn(game.challenge_cards)
        if card_id != "methodical"
    ]
    game.challenge_cards = cards
    game.rogue_card = cards[-1] if cards else None
    reset_rogue_effect_state(game, reset_uses=True, reset_handicap=True)
    game.rogue_enabled = bool(cards)

    for card_id in cards:
        card_def = get_rogue_card_fn(card_id)
        use_bonus = active_use_bonus_fn(game, card_id)
        apply_rogue_card_uses(game, card_id, card_def, bonus=use_bonus)

        if card_id == "komi_relief":
            if game.player_color == "B":
                game.komi = max(0.5, game.komi - 7.0)
            else:
                game.komi = game.komi + 7.0
        elif card_id == "blackhole":
            game.rogue_seal_points.extend(
                challenge_zone_points_fn(game, get_blackhole_points_fn(game.size))
            )
        elif card_id == "golden_corner":
            corner = choose_corner()
            game.rogue_seal_points.extend(
                challenge_zone_points_fn(
                    game,
                    get_golden_corner_points_fn(game.size, corner, golden_corner_span),
                )
            )
        elif card_id == "joseki_ocd" and not game.rogue_joseki_targets:
            game.rogue_joseki_targets = pick_joseki_targets_fn(game.size, joseki_target_count)
        elif card_id == "god_hand" and not game.rogue_godhand_trigger:
            rng = make_rng()
            game.rogue_godhand_center = random_hidden_center_fn(game.size, 2, rng)
            game.rogue_godhand_trigger = diamond_points_fn(
                game.rogue_godhand_center[0],
                game.rogue_godhand_center[1],
                godhand_radius,
                game.size,
            )
        elif card_id == "quickthink" and game.current_player == game.player_color:
            game.rogue_quickthink_stage = 1
        elif card_id == "coach_mode":
            game.rogue_uses.setdefault("coach_mode", 1 + use_bonus)

    return ChallengeRogueLoadoutResult(cards=cards)


def rogue_card_ids(game: Any) -> list[str]:
    cards: list[str] = []
    for card_id in list(getattr(game, "challenge_cards", [])) + [game.rogue_card]:
        if card_id and card_id not in cards:
            cards.append(card_id)
    return cards


def rogue_has(game: Any, card_id: str) -> bool:
    return card_id in rogue_card_ids(game)


def _color_value(color: str) -> int:
    return 1 if color == "B" else 2


def _enemy_value(color: str) -> int:
    return 2 if color == "B" else 1


def _recent_non_pass_move_entries(
    game: Any,
    color: str,
    gtp_to_coord: CoordFormatter,
    count: int,
) -> list[tuple[int, tuple[int, int]]]:
    entries: list[tuple[int, tuple[int, int]]] = []
    color_move_index = sum(
        1
        for move_color, gtp in game.moves
        if move_color == color and gtp.upper() != "PASS"
    )
    for move_color, gtp in reversed(game.moves):
        if move_color != color or gtp.upper() == "PASS":
            continue
        coord = gtp_to_coord(gtp, game.size)
        if coord:
            entries.append((color_move_index, coord))
        color_move_index -= 1
        if len(entries) >= count:
            break
    return list(reversed(entries))


def _has_stone_in_square(
    game: Any,
    center: tuple[int, int],
    color_value: int,
    radius: int,
) -> bool:
    return any(
        game.board[py][px] == color_value
        for px, py in get_square_points(center[0], center[1], radius, game.size)
    )


def _empty_points_around_stones(
    game: Any,
    anchor_value: int,
    radius: int,
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for sy in range(game.size):
        for sx in range(game.size):
            if game.board[sy][sx] != anchor_value:
                continue
            for point in get_square_points(sx, sy, radius, game.size):
                if point in seen:
                    continue
                seen.add(point)
                px, py = point
                if game.board[py][px] == 0:
                    candidates.append(point)
    random.shuffle(candidates)
    return candidates


def _apply_supremacy_card(
    game: Any,
    color: str,
    *,
    card_id: str,
    recent_entries: list[tuple[int, tuple[int, int]]],
    spawn_anchor_value: int,
    spawn_radius: int,
    trigger_counts: dict[str, int],
    last_trigger_indices: dict[str, int],
    message_name: str,
    coord_to_gtp: CoordFormatter,
) -> RogueBoardEffectResult:
    if trigger_counts.get(color, 0) >= gameplay_config.ROGUE_SUPREMACY_MAX_TRIGGERS:
        return RogueBoardEffectResult(False, [], [])
    if len(recent_entries) < gameplay_config.ROGUE_SUPREMACY_TRIGGER_WINDOW:
        return RogueBoardEffectResult(False, [], [])

    window_entries = recent_entries[-gameplay_config.ROGUE_SUPREMACY_TRIGGER_WINDOW:]
    last_trigger_index = last_trigger_indices.get(color, 0)
    if any(index <= last_trigger_index for index, _coord in window_entries):
        return RogueBoardEffectResult(False, [], [])

    candidates = _empty_points_around_stones(game, spawn_anchor_value, spawn_radius)
    changed = spawn_bonus_points(game, candidates[:1], color)
    if not changed:
        return RogueBoardEffectResult(False, [], [])

    trigger_counts[color] = trigger_counts.get(color, 0) + 1
    last_trigger_indices[color] = window_entries[-1][0]
    bx, by = changed[0]
    remaining = gameplay_config.ROGUE_SUPREMACY_MAX_TRIGGERS - trigger_counts[color]
    return RogueBoardEffectResult(
        True,
        [
            f"{message_name}触发：在 {coord_to_gtp(bx, by, game.size)} 赠送 1 颗己棋，"
            f"本局剩余 {remaining} 次"
        ],
        [],
    )


def _apply_defense_first(
    game: Any,
    color: str,
    *,
    gtp_to_coord: CoordFormatter,
    coord_to_gtp: CoordFormatter,
) -> RogueBoardEffectResult:
    recent = _recent_non_pass_move_entries(
        game,
        color,
        gtp_to_coord,
        gameplay_config.ROGUE_SUPREMACY_TRIGGER_WINDOW,
    )
    recent_coords = [coord for _index, coord in recent]
    enemy = _enemy_value(color)
    if any(
        _has_stone_in_square(game, coord, enemy, gameplay_config.ROGUE_DEFENSE_SAFE_RADIUS)
        for coord in recent_coords
    ):
        return RogueBoardEffectResult(False, [], [])
    return _apply_supremacy_card(
        game,
        color,
        card_id="defense_first",
        recent_entries=recent,
        spawn_anchor_value=_color_value(color),
        spawn_radius=gameplay_config.ROGUE_DEFENSE_SPAWN_RADIUS,
        trigger_counts=game.rogue_defense_first_triggers,
        last_trigger_indices=game.rogue_defense_first_last_index,
        message_name="🛡 防御至上",
        coord_to_gtp=coord_to_gtp,
    )


def _apply_attack_first(
    game: Any,
    color: str,
    *,
    gtp_to_coord: CoordFormatter,
    coord_to_gtp: CoordFormatter,
) -> RogueBoardEffectResult:
    recent = _recent_non_pass_move_entries(
        game,
        color,
        gtp_to_coord,
        gameplay_config.ROGUE_SUPREMACY_TRIGGER_WINDOW,
    )
    recent_coords = [coord for _index, coord in recent]
    enemy = _enemy_value(color)
    if not all(
        _has_stone_in_square(game, coord, enemy, gameplay_config.ROGUE_ATTACK_NEAR_RADIUS)
        for coord in recent_coords
    ):
        return RogueBoardEffectResult(False, [], [])
    return _apply_supremacy_card(
        game,
        color,
        card_id="attack_first",
        recent_entries=recent,
        spawn_anchor_value=enemy,
        spawn_radius=gameplay_config.ROGUE_ATTACK_SPAWN_RADIUS,
        trigger_counts=game.rogue_attack_first_triggers,
        last_trigger_indices=game.rogue_attack_first_last_index,
        message_name="⚔ 进攻至上",
        coord_to_gtp=coord_to_gtp,
    )


def challenge_remaining(game: Any, key: str) -> int:
    return max(0, game.challenge_limits.get(key, 0) - game.challenge_usage.get(key, 0))


def challenge_category_counts_for_game(game: Any) -> dict[str, int]:
    return challenge_category_counts(list(getattr(game, "challenge_cards", [])))


def challenge_has_set(
    game: Any,
    category: str,
    need: int | None = None,
) -> bool:
    if not getattr(game, "challenge_beta", False):
        return False
    if need is None:
        need = gameplay_config.CHALLENGE_SET_MIN_COUNT
    return challenge_category_counts_for_game(game).get(category, 0) >= need


def challenge_zone_points(game: Any, points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not challenge_has_set(game, "zone"):
        return list(points)
    expanded: set[tuple[int, int]] = set()
    for px, py in points:
        radius = gameplay_config.CHALLENGE_ZONE_EXPAND_RADIUS
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = px + dx, py + dy
                if 0 <= nx < game.size and 0 <= ny < game.size:
                    expanded.add((nx, ny))
    return sorted(expanded)


def challenge_active_use_bonus(game: Any, card_id: str) -> int:
    if not challenge_has_set(game, "active"):
        return 0
    if challenge_card_category(card_id) != "active":
        return 0
    return gameplay_config.CHALLENGE_ACTIVE_USE_BONUS


def challenge_should_bonus_derivative(game: Any) -> bool:
    return (
        challenge_has_set(game, "derivative")
        and random.random() < gameplay_config.CHALLENGE_DERIVATIVE_BONUS_CHANCE
    )


def apply_player_rogue_board_effects(
    game: Any,
    *,
    x: int,
    y: int,
    color: str,
    captured: int,
    coord_to_gtp: Any,
    gtp_to_coord: Any,
) -> RogueBoardEffectResult:
    messages: list[str] = []
    trap_bonus_sources: list[str] = []
    modified = False

    if rogue_has(game, "sprout") and captured > 0:
        sprout_area: list[tuple[int, int]] = []
        seen_sprout_points: set[tuple[int, int]] = set()
        captured_points = list(getattr(game, "last_captured_points", [])) or [(x, y)]
        for cx, cy in captured_points:
            for point in get_square_points(cx, cy, 1, game.size):
                if point in seen_sprout_points:
                    continue
                seen_sprout_points.add(point)
                px, py = point
                if game.board[py][px] == 0:
                    sprout_area.append(point)
        random.shuffle(sprout_area)
        changed = spawn_bonus_points(game, sprout_area[:1], color)
        if changed:
            bx, by = changed[0]
            modified = True
            messages.append(
                f"萌芽触发：在提子处 3×3 范围的 {coord_to_gtp(bx, by, game.size)} 额外长出一颗己方棋子"
            )

    if rogue_has(game, "joseki_ocd") and not game.rogue_joseki_done:
        if (x, y) in game.rogue_joseki_targets:
            game.rogue_joseki_hits += 1
            messages.append(
                f"定式命中 ({game.rogue_joseki_hits}/{gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS})"
            )
        if game.rogue_joseki_hits >= gameplay_config.ROGUE_JOSEKI_REQUIRED_HITS:
            game.rogue_joseki_done = True
            color_val = 1 if color == "B" else 2
            remaining_targets = [
                (tx, ty)
                for tx, ty in game.rogue_joseki_targets
                if game.board[ty][tx] != color_val
            ]
            changed = set_points_to_color(game, remaining_targets, color)
            if changed:
                modified = True
            messages.append(f"定式强迫症完成，自动补上 {len(changed)} 颗同色棋")

    if (
        rogue_has(game, "god_hand")
        and not game.rogue_godhand_done
        and (x, y) in game.rogue_godhand_trigger
    ):
        game.rogue_godhand_done = True
        center = game.rogue_godhand_center or (x, y)
        area = get_square_points(
            center[0],
            center[1],
            gameplay_config.ROGUE_GODHAND_RADIUS,
            game.size,
        )
        random.shuffle(area)
        targets = [
            (px, py)
            for px, py in area
            if game.board[py][px] == 0
        ][:gameplay_config.ROGUE_GODHAND_FILL_COUNT]
        changed = set_points_to_color(game, targets, color)
        if changed:
            modified = True
        messages.append(f"✨ 神之一手发动，在暗点周围爆发 {len(changed)} 颗同色棋")
        trap_bonus_sources.append("神之一手")

    if (
        game.two_player
        and rogue_has(game, "sansan_trap")
        and (x, y) in get_sansan_points(game.size)
    ):
        trigger_color = "W" if color == "B" else "B"
        nearby = [
            (nx, ny)
            for nx, ny in adjacent8_points(x, y, game.size)
            if game.board[ny][nx] == 0
        ]
        random.shuffle(nearby)
        changed = spawn_bonus_points(
            game,
            nearby[:gameplay_config.ROGUE_SANSAN_TRAP_STONES],
            trigger_color,
        ) if nearby else []
        if changed:
            modified = True
            messages.append(
                f"△ 三三陷阱发动，在 {coord_to_gtp(x, y, game.size)} 相邻点反打 {len(changed)} 子"
            )

    if rogue_has(game, "corner_helper"):
        corner = find_corner_with_min_stones(
            game,
            color,
            5,
            gameplay_config.ROGUE_CORNER_HELPER_TRIGGER_STONES,
            exclude=list(game.rogue_corner_helper_done),
        )
        if corner is not None:
            candidates = [
                (px, py)
                for px, py in get_corner_helper_spawn_points(game.size, corner, 5)
                if game.board[py][px] == 0
            ]
            random.shuffle(candidates)
            changed = spawn_bonus_points(
                game,
                candidates[:gameplay_config.ROGUE_CORNER_HELPER_STONES],
                color,
            )
            if changed:
                game.rogue_corner_helper_done.add(corner)
                modified = True
                messages.append(f"🏯 守角辅助补强了 {len(changed)} 颗角部援军")

    if rogue_has(game, "sanrensei") and not game.rogue_sanrensei_done:
        player_moves = player_non_pass_coords(
            game,
            color,
            gtp_to_coord,
            limit=gameplay_config.ROGUE_SANRENSEI_OPENING_MOVES,
        )
        star_set = set(get_star_points(game.size))
        first_moves = player_moves[:gameplay_config.ROGUE_SANRENSEI_REQUIRED_STARS]
        if (
            len(first_moves) >= gameplay_config.ROGUE_SANRENSEI_REQUIRED_STARS
            and all(pt in star_set for pt in first_moves)
        ):
            choices = [
                pt
                for pt in star_set
                if game.board[pt[1]][pt[0]] == 0
            ]
            random.shuffle(choices)
            changed = spawn_bonus_points(
                game,
                choices[:gameplay_config.ROGUE_SANRENSEI_BONUS_STONES],
                color,
            )
            support_pool = []
            if gameplay_config.ROGUE_SANRENSEI_SUPPORT_STONES > 0:
                for sx, sy in (first_moves + changed):
                    for px, py in adjacent8_points(sx, sy, game.size):
                        if game.board[py][px] == 0 and (px, py) not in support_pool:
                            support_pool.append((px, py))
                random.shuffle(support_pool)
                changed.extend(spawn_bonus_points(
                    game,
                    support_pool[:gameplay_config.ROGUE_SANRENSEI_SUPPORT_STONES],
                    color,
                ))
            if changed and challenge_should_bonus_derivative(game):
                extra_pool = [
                    pt
                    for pt in star_set
                    if game.board[pt[1]][pt[0]] == 0 and pt not in changed
                ]
                random.shuffle(extra_pool)
                changed.extend(spawn_bonus_points(game, extra_pool[:1], color))
            game.rogue_sanrensei_done = True
            if changed:
                modified = True
            messages.append(f"✦ 三连星发动，自动补出 {len(changed)} 颗星位棋")

    if rogue_has(game, "foolish_wisdom"):
        new_shapes = find_new_fool_shapes(game, color, game.rogue_fool_shapes)
        changed = []
        for shape in new_shapes:
            game.rogue_fool_shapes.add(shape)
            cx, cy = shape_center(shape)
            area = [
                (px, py)
                for px, py in get_square_points(cx, cy, 2, game.size)
                if game.board[py][px] == 0
            ]
            random.shuffle(area)
            changed.extend(spawn_bonus_points(
                game,
                area[:gameplay_config.ROGUE_FOOLISH_FILL_COUNT],
                color,
            ))
            if challenge_should_bonus_derivative(game):
                extra_area = [
                    (px, py)
                    for px, py in get_square_points(cx, cy, 2, game.size)
                    if game.board[py][px] == 0
                ]
                random.shuffle(extra_area)
                changed.extend(spawn_bonus_points(game, extra_area[:1], color))
        if changed:
            modified = True
        if new_shapes:
            messages.append(
                f"🪤 大智若愚发动，识别到 {len(new_shapes)} 个愚形，额外长出 {len(changed)} 颗己方棋子"
            )

    if rogue_has(game, "defense_first"):
        result = _apply_defense_first(
            game,
            color,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
        )
        if result.modified:
            modified = True
        messages.extend(result.messages)

    if rogue_has(game, "attack_first"):
        result = _apply_attack_first(
            game,
            color,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
        )
        if result.modified:
            modified = True
        messages.extend(result.messages)

    if (
        rogue_has(game, "handicap_quest")
        and game.rogue_handicap_active
        and game.rogue_handicap_bonuses < gameplay_config.ROGUE_HANDICAP_MAX_BONUSES
        and not game.two_player
    ):
        player_moves = sum(
            1
            for move_color, gtp in game.moves
            if move_color == game.player_color and gtp.upper() != "PASS"
        )
        if (
            player_moves > 0
            and player_moves % gameplay_config.ROGUE_HANDICAP_BONUS_INTERVAL == 0
        ):
            game.rogue_skip_ai = True
            game.rogue_handicap_bonuses += 1
            messages.append(
                f"让子任务奖励触发：每满 {gameplay_config.ROGUE_HANDICAP_BONUS_INTERVAL} 手获得一次奖励，"
                f"当前进度 {game.rogue_handicap_bonuses}/{gameplay_config.ROGUE_HANDICAP_MAX_BONUSES}，AI 将虚手一次"
            )

    return RogueBoardEffectResult(
        modified=modified,
        messages=messages,
        trap_bonus_sources=trap_bonus_sources,
    )


def apply_rogue_five_in_row(
    game: Any,
    color: str,
    *,
    shuffle_points: ShufflePointsFn = random.shuffle,
    should_bonus_derivative_fn: Callable[[Any], bool] = challenge_should_bonus_derivative,
    support_stones: int = gameplay_config.ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
) -> RogueBoardEffectResult:
    del should_bonus_derivative_fn, support_stones

    current_lines = set(find_exact_five_lines(game, color))
    game.rogue_five_in_row_seen.intersection_update(current_lines)
    new_lines = [
        line
        for line in current_lines
        if line not in game.rogue_five_in_row_seen
    ]
    if not new_lines:
        return RogueBoardEffectResult(False, [], [])

    targets: list[tuple[int, int]] = []
    planned: set[tuple[int, int]] = set()
    for line in new_lines:
        game.rogue_five_in_row_seen.add(line)
        sorted_line = sorted(line)
        start, end = line_endpoints(line)
        for point, anchor in ((start, sorted_line[0]), (end, sorted_line[-1])):
            center = point if point and 0 <= point[0] < game.size and 0 <= point[1] < game.size else anchor
            region = [
                (px, py)
                for px, py in get_square_points(center[0], center[1], 1, game.size)
                if game.board[py][px] == 0 and (px, py) not in planned
            ]
            shuffle_points(region)
            if region:
                targets.append(region[0])
                planned.add(region[0])

    changed = spawn_bonus_points(game, targets, color)

    if not changed:
        return RogueBoardEffectResult(False, [], [])

    return RogueBoardEffectResult(
        True,
        [
            f"🎯 五子连珠发动，正好连成 5 子，在首尾 3×3 区域补下 {len(changed)} 颗己方棋子"
        ],
        [],
    )


def apply_rogue_last_stand(
    game: Any,
    color: str,
    center: tuple[int, int],
    *,
    rng: random.Random | None = None,
    forbidden_points: set[tuple[int, int]] | None = None,
    clear_count: int = gameplay_config.ROGUE_LAST_STAND_CLEAR_COUNT,
    spawn_count: int = gameplay_config.ROGUE_LAST_STAND_SPAWN_COUNT,
) -> RogueBoardEffectResult:
    if game.rogue_last_stand_done.get(color):
        return RogueBoardEffectResult(False, [], [])

    rng = random.Random(time.time_ns()) if rng is None else rng
    area = get_square_points(center[0], center[1], 1, game.size)
    cleared = clear_random_enemy_stones(game, color, clear_count, rng, area=area)
    changed = spawn_random_owned_stones(
        game,
        color,
        spawn_count,
        rng,
        area=area,
        forbidden=forbidden_points,
    )
    if not cleared and not changed:
        return RogueBoardEffectResult(False, [], [])

    game.rogue_last_stand_done[color] = True
    return RogueBoardEffectResult(
        True,
        [
            f"🫀 起死回生发动，在上一手周围扭转局面：清掉 {len(cleared)} 颗敌子，补下 {len(changed)} 颗己棋"
        ],
        [],
    )


def apply_ai_rogue_response_board_effects(
    game: Any,
    *,
    x: int,
    y: int,
    coord_to_gtp: Any,
    shuffle_points: ShufflePointsFn = random.shuffle,
) -> RogueBoardEffectResult:
    if game.two_player or not game.ai_rogue_enabled:
        return RogueBoardEffectResult(False, [], [])
    if game.ai_rogue_card != "sansan_trap":
        return RogueBoardEffectResult(False, [], [])

    coord = (x, y)
    if coord not in get_sansan_points(game.size):
        return RogueBoardEffectResult(False, [], [])

    nearby = [
        (nx, ny)
        for nx, ny in adjacent8_points(coord[0], coord[1], game.size)
        if game.board[ny][nx] == 0
    ]
    shuffle_points(nearby)
    changed = spawn_bonus_points(
        game,
        nearby[:gameplay_config.ROGUE_SANSAN_TRAP_STONES],
        game.ai_color,
    )
    if not changed:
        return RogueBoardEffectResult(False, [], [])

    message = (
        f"三三陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} "
        f"相邻点反打 {len(changed)} 子"
    )
    return RogueBoardEffectResult(True, [message], [])
