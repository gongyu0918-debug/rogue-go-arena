from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import random
import time
from typing import Any

import app.config.gameplay as gameplay_config
from app.gameplay.effect_utils import (
    collect_joseki_burst_points,
    diamond_points,
    get_corner_boundary_points,
    get_corner_square_points,
    get_star_points,
    pick_joseki_targets,
    player_non_pass_coords,
    random_hidden_center,
    set_points_to_color,
    spawn_bonus_points,
)


@dataclass
class BoardEffectResult:
    modified: bool
    messages: list[str]


def get_ultimate_territory_forbidden_points(
    game: Any,
    for_color_val: int,
    *,
    radius: int | None = None,
    search_span: int = 2,
) -> set[tuple[int, int]]:
    """Return points blocked by territory while preserving the legacy 5x5 scan."""
    territory_radius = gameplay_config.ULTIMATE_TERRITORY_RADIUS if radius is None else radius
    forbidden = set()
    owner_val = 3 - for_color_val
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] != owner_val:
                continue
            for dy in range(-search_span, search_span + 1):
                for dx in range(-search_span, search_span + 1):
                    if abs(dx) + abs(dy) > territory_radius:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < game.size and 0 <= ny < game.size:
                        forbidden.add((nx, ny))
    return forbidden


def resolve_pending_shadow_links(
    game: Any,
    *,
    coord_to_gtp: Callable[[int, int, int], str],
    line_points_between: Callable[[int, int, int, int], list[tuple[int, int]]],
) -> BoardEffectResult:
    if not game.ultimate_shadow_clone_links:
        return BoardEffectResult(modified=False, messages=[])

    pending = []
    messages: list[str] = []
    modified = False
    for link in game.ultimate_shadow_clone_links:
        if game.ultimate_move_count < link["trigger_move"]:
            pending.append(link)
            continue
        changed = 0
        for px, py in line_points_between(*link["from"], *link["to"]):
            if game.board[py][px] != link["color"]:
                game.board[py][px] = link["color"]
                changed += 1
        if changed:
            modified = True
            messages.append(
                f"👥 影分身连线完成："
                f"{coord_to_gtp(link['from'][0], link['from'][1], game.size)}"
                f" 连到 "
                f"{coord_to_gtp(link['to'][0], link['to'][1], game.size)}"
                f"，铺开 {changed} 颗同色棋"
            )

    game.ultimate_shadow_clone_links = pending
    if modified:
        game.ko_point = None
    return BoardEffectResult(modified=modified, messages=messages)


def reset_ultimate_effect_state(game: Any) -> None:
    game.ultimate_joseki_targets = []
    game.ultimate_joseki_hits = 0
    game.ultimate_joseki_done = False
    game.ultimate_godhand_center = None
    game.ultimate_godhand_trigger = []
    game.ultimate_godhand_done = False
    game.ultimate_corner_helper_done = set()
    game.ultimate_sanrensei_done = False
    game.ultimate_five_in_row_seen = set()
    game.ultimate_last_stand_done = {"B": False, "W": False}
    game.ultimate_quickthink_active = False
    game.ultimate_quickthink_turn_counted = False
    game.ultimate_fool_shapes = set()
    game.ultimate_shadow_clone_links = []


def apply_ultimate_board_effect(
    game: Any,
    *,
    x: int,
    y: int,
    color: str,
    card: str,
) -> BoardEffectResult | None:
    rng = random.Random(time.time_ns())
    size = game.size
    color_val = 1 if color == "B" else 2
    opponent_val = 3 - color_val
    messages: list[str] = []
    modified = False

    if card == "proliferate":
        candidates = [
            (nx, ny)
            for ny in range(max(0, y - 2), min(size, y + 3))
            for nx in range(max(0, x - 2), min(size, x + 3))
            if game.board[ny][nx] == 0
        ]
        rng.shuffle(candidates)
        placed = len(spawn_bonus_points(game, candidates[:5], color))
        if placed > 0:
            modified = True
            messages.append(f"🦠 无限增生！生成 {placed} 颗棋子")

    elif card == "wildgrow":
        own_stones = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == color_val
        ]
        rng.shuffle(own_stones)
        growth_targets = []
        for sx, sy in own_stones:
            if len(growth_targets) >= gameplay_config.ULTIMATE_WILDGROW_MAX_GROWTH:
                break
            adjacent_empty = [
                (nx, ny)
                for ny in range(max(0, sy - 1), min(size, sy + 2))
                for nx in range(max(0, sx - 1), min(size, sx + 2))
                if game.board[ny][nx] == 0
            ]
            if adjacent_empty:
                growth_targets.append(rng.choice(adjacent_empty))
        grown = len(spawn_bonus_points(game, growth_targets, color))
        if grown > 0:
            modified = True
            messages.append(f"🌿 狂野生长！{grown} 颗棋子生长出新子")

    elif card == "rejection":
        pushed = 0
        destroyed = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < size and 0 <= ny < size):
                    continue
                if game.board[ny][nx] != opponent_val:
                    continue
                push_x, push_y = nx + dx, ny + dy
                game.board[ny][nx] = 0
                if (
                    0 <= push_x < size
                    and 0 <= push_y < size
                    and game.board[push_y][push_x] == 0
                ):
                    game.board[push_y][push_x] = opponent_val
                    pushed += 1
                else:
                    destroyed += 1
                modified = True
        if pushed + destroyed > 0:
            msg = "💥 排异反应！"
            if pushed:
                msg += f"挤走 {pushed} 子"
            if destroyed:
                msg += f"{'，' if pushed else ''}摧毁 {destroyed} 子"
            messages.append(msg)

    elif card == "plague":
        targets = [
            (nx, ny)
            for ny in range(max(0, y - 2), min(size, y + 3))
            for nx in range(max(0, x - 2), min(size, x + 3))
            if game.board[ny][nx] == opponent_val
        ]
        converted = len(set_points_to_color(game, targets, color))
        if converted > 0:
            modified = True
            messages.append(f"☠️ 瘟疫蔓延！感染 {converted} 颗敌子")

    elif card == "meteor":
        enemies = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == opponent_val
        ]
        rng.shuffle(enemies)
        destroyed = 0
        for ex, ey in enemies[:gameplay_config.ULTIMATE_METEOR_DESTROY_COUNT]:
            game.board[ey][ex] = 0
            destroyed += 1
        if destroyed > 0:
            modified = True
            messages.append(f"☄️ 陨石雨！摧毁 {destroyed} 颗对方棋子")

    elif card == "quantum":
        empties = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == 0
        ]
        rng.shuffle(empties)
        placed = len(spawn_bonus_points(
            game,
            empties[:gameplay_config.ULTIMATE_QUANTUM_PLACE_COUNT],
            color,
        ))
        if placed > 0:
            modified = True
            messages.append(f"⚛️ 量子纠缠！在 {placed} 个位置出现棋子")

    elif card == "devour":
        eaten = 0
        for ny in range(max(0, y - 2), min(size, y + 3)):
            for nx in range(max(0, x - 2), min(size, x + 3)):
                if game.board[ny][nx] == opponent_val:
                    game.board[ny][nx] = 0
                    eaten += 1
        if eaten > 0:
            modified = True
            messages.append(f"👹 吞噬之口！吃掉 {eaten} 颗对方棋子")

    elif card == "blackout":
        destroyed = 0
        for d in range(-2, 3):
            for nx, ny in ((x + d, y), (x, y + d)):
                if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == opponent_val:
                    game.board[ny][nx] = 0
                    destroyed += 1
                    modified = True
        if destroyed > 0:
            messages.append(f"🌋 天崩地裂！十字清除 {destroyed} 颗敌子")

    elif card == "magnet":
        own_stones = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == color_val and (sx, sy) != (x, y)
        ]
        own_stones.sort(key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        moved = 0
        crushed = 0
        for sx, sy in own_stones:
            cx, cy = sx, sy
            for _ in range(3):
                dx_dir = 0 if cx == x else (1 if cx < x else -1)
                dy_dir = 0 if cy == y else (1 if cy < y else -1)
                if dx_dir == 0 and dy_dir == 0:
                    break
                nx, ny = cx + dx_dir, cy + dy_dir
                if not (0 <= nx < size and 0 <= ny < size):
                    break
                if game.board[ny][nx] == opponent_val:
                    game.board[ny][nx] = 0
                    crushed += 1
                if game.board[ny][nx] == 0:
                    game.board[cy][cx] = 0
                    game.board[ny][nx] = color_val
                    cx, cy = nx, ny
                    modified = True
                else:
                    break
            if (cx, cy) != (sx, sy):
                moved += 1
        if moved + crushed > 0:
            msg = f"🧲 磁力吸附！{moved} 子飞奔"
            if crushed:
                msg += f"，碾碎 {crushed} 颗敌子"
            messages.append(msg)

    elif card == "necro":
        empties = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == 0
        ]
        rng.shuffle(empties)
        spawned = len(spawn_bonus_points(game, empties[:3], color))
        enemies = [
            (sx, sy)
            for sy in range(size)
            for sx in range(size)
            if game.board[sy][sx] == opponent_val
        ]
        rng.shuffle(enemies)
        converted = len(set_points_to_color(game, enemies[:2], color))
        if spawned + converted > 0:
            modified = True
            messages.append(f"💀 亡灵召唤！召唤 {spawned} 子，转化 {converted} 子")

    elif card == "wall":
        if random.random() < gameplay_config.ULTIMATE_WALL_TRIGGER_CHANCE:
            row_slots = sum(1 for fx in range(size) if game.board[y][fx] == 0)
            col_slots = sum(1 for fy in range(size) if game.board[fy][x] == 0)
            if row_slots >= col_slots:
                placed = len(spawn_bonus_points(
                    game,
                    [(fx, y) for fx in range(size) if game.board[y][fx] == 0],
                    color,
                ))
                if placed > 0:
                    modified = True
                    messages.append(f"🧱 万里长城发动！第 {size - y} 行筑起 {placed} 子")
            else:
                placed = len(spawn_bonus_points(
                    game,
                    [(x, fy) for fy in range(size) if game.board[fy][x] == 0],
                    color,
                ))
                if placed > 0:
                    modified = True
                    cols = "ABCDEFGHJKLMNOPQRST"
                    messages.append(f"🧱 万里长城发动！{cols[x]} 列筑起 {placed} 子")
        else:
            messages.append("🧱 万里长城未能成型，这次没有筑起城墙")

    else:
        return None

    return BoardEffectResult(modified=modified, messages=messages)


def apply_ultimate_state_effect(
    game: Any,
    *,
    x: int,
    y: int,
    color: str,
    card: str,
    coord_to_gtp: Any,
    gtp_to_coord: Any,
) -> BoardEffectResult | None:
    rng = random.Random(time.time_ns())
    size = game.size
    color_val = 1 if color == "B" else 2
    opponent_val = 3 - color_val
    messages: list[str] = []
    modified = False

    if card == "shadow_clone":
        mx, my = size - 1 - x, size - 1 - y
        clone_target = None
        if game.board[my][mx] == 0:
            clone_target = (mx, my)
        else:
            nearby = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = mx + dx, my + dy
                    if 0 <= nx < size and 0 <= ny < size and game.board[ny][nx] == 0:
                        nearby.append((nx, ny))
            if nearby:
                nearby.sort(key=lambda p: abs(p[0] - mx) + abs(p[1] - my))
                clone_target = nearby[0]
        if clone_target:
            tx, ty = clone_target
            placed = spawn_bonus_points(game, [(tx, ty)], color)
            if placed:
                modified = True
                game.ultimate_shadow_clone_links.append({
                    "trigger_move": game.ultimate_move_count + 1,
                    "color": color_val,
                    "from": (x, y),
                    "to": (tx, ty),
                })
                messages.append(
                    f"👥 影分身！在 {coord_to_gtp(tx, ty, size)} 出现分身，下一回合会连成镜像线"
                )

    elif card == "timewarp":
        if rng.random() < gameplay_config.ULTIMATE_TIMEWARP_TRIGGER_CHANCE:
            opponent_color = "W" if color == "B" else "B"
            erased = 0
            for move_color, gtp in reversed(game.moves):
                if erased >= 2:
                    break
                if move_color != opponent_color or gtp.upper() == "PASS":
                    continue
                coord = gtp_to_coord(gtp, size)
                if not coord:
                    continue
                ox, oy = coord
                if game.board[oy][ox] == (1 if move_color == "B" else 2):
                    game.board[oy][ox] = 0
                    erased += 1
                    modified = True
            if erased > 0:
                messages.append(f"⏳ 时空裂缝！抹去对方 {erased} 手棋")

    elif card == "joseki_burst":
        if not game.ultimate_joseki_targets:
            game.ultimate_joseki_targets = pick_joseki_targets(
                game.size,
                gameplay_config.ULTIMATE_JOSEKI_TARGET_COUNT,
            )
        if not game.ultimate_joseki_done and (x, y) in game.ultimate_joseki_targets:
            game.ultimate_joseki_hits += 1
            messages.append(
                f"定式爆发命中 ({game.ultimate_joseki_hits}/{gameplay_config.ULTIMATE_JOSEKI_REQUIRED_HITS})"
            )
        if (
            not game.ultimate_joseki_done
            and game.ultimate_joseki_hits >= gameplay_config.ULTIMATE_JOSEKI_REQUIRED_HITS
        ):
            game.ultimate_joseki_done = True
            remaining_targets = [
                (tx, ty)
                for tx, ty in game.ultimate_joseki_targets
                if game.board[ty][tx] != color_val
            ]
            changed = set_points_to_color(game, remaining_targets, color)
            burst_points = collect_joseki_burst_points(
                game,
                game.ultimate_joseki_targets,
                color,
                gameplay_config.ULTIMATE_JOSEKI_BONUS_STONES,
                rng,
            )
            changed.extend(spawn_bonus_points(game, burst_points, color))
            if changed:
                modified = True
                messages.append(
                    f"定式爆发完成：补满 {len(remaining_targets)} 个目标点，并额外爆发 {len(changed) - len(remaining_targets)} 颗棋子"
                )

    elif card == "god_hand":
        if not game.ultimate_godhand_trigger:
            game.ultimate_godhand_center = random_hidden_center(game.size, 2, rng)
            game.ultimate_godhand_trigger = diamond_points(
                game.ultimate_godhand_center[0],
                game.ultimate_godhand_center[1],
                2,
                game.size,
            )
        if not game.ultimate_godhand_done and (x, y) in game.ultimate_godhand_trigger:
            game.ultimate_godhand_done = True
            cleared = 0
            for sy in range(size):
                for sx in range(size):
                    if game.board[sy][sx] == opponent_val:
                        game.board[sy][sx] = 0
                        cleared += 1
                        modified = True
            empties = [
                (sx, sy)
                for sy in range(size)
                for sx in range(size)
                if game.board[sy][sx] == 0
            ]
            rng.shuffle(empties)
            filled = len(spawn_bonus_points(
                game,
                empties[:gameplay_config.ULTIMATE_GODHAND_FILL_COUNT],
                color,
            ))
            if filled > 0:
                modified = True
            messages.append(f"✨ 神之一手发动，清空 {cleared} 颗敌子并洒下 {filled} 颗同色棋")

    elif card == "corner_helper":
        corner = None
        for candidate in range(4):
            if candidate in game.ultimate_corner_helper_done:
                continue
            own = sum(
                1
                for px, py in get_corner_square_points(size, candidate, 5)
                if game.board[py][px] == color_val
            )
            if own >= 2:
                corner = candidate
                break
        if corner is not None:
            cleared = 0
            for px, py in get_corner_square_points(size, corner, 8):
                if game.board[py][px] == opponent_val:
                    game.board[py][px] = 0
                    cleared += 1
                    modified = True
            placed = spawn_bonus_points(
                game,
                get_corner_boundary_points(size, corner, 8),
                color,
            )
            if placed:
                modified = True
            if cleared or placed:
                game.ultimate_corner_helper_done.add(corner)
                messages.append(f"🏯 守角要塞封锁角部，清空 {cleared} 子并筑边 {len(placed)} 子")

    elif card == "sanrensei":
        if not game.ultimate_sanrensei_done:
            first_three = player_non_pass_coords(game, color, gtp_to_coord, limit=3)
            star_set = set(get_star_points(size))
            if len(first_three) >= 3 and all(pt in star_set for pt in first_three[:3]):
                changed = []
                cleared = 0
                seen = set()
                for sx, sy in star_set:
                    for px, py in diamond_points(sx, sy, 2, size):
                        if (px, py) in seen:
                            continue
                        seen.add((px, py))
                        if game.board[py][px] == opponent_val:
                            game.board[py][px] = 0
                            cleared += 1
                            modified = True
                    changed.extend(spawn_bonus_points(
                        game,
                        diamond_points(sx, sy, 2, size, boundary_only=True) + [(sx, sy)],
                        color,
                    ))
                if changed:
                    modified = True
                game.ultimate_sanrensei_done = True
                messages.append(f"✦ 三连星爆发，清空 {cleared} 子并扩张 {len(changed)} 颗星位势力")

    else:
        return None

    return BoardEffectResult(modified=modified, messages=messages)
