from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, Optional


def player_non_pass_coords(
    game: Any,
    color: str,
    gtp_to_coord: Callable[[str, int], tuple[int, int] | None],
    *,
    limit: int | None = None,
) -> list[tuple[int, int]]:
    coords = []
    for move_color, gtp in game.moves:
        if move_color != color or gtp.upper() == "PASS":
            continue
        coord = gtp_to_coord(gtp, game.size)
        if coord:
            coords.append(coord)
        if limit is not None and len(coords) >= limit:
            break
    return coords


def get_star_points(size: int) -> list[tuple[int, int]]:
    if size == 19:
        return [
            (3, 3), (9, 3), (15, 3), (3, 9), (9, 9), (15, 9),
            (3, 15), (9, 15), (15, 15),
        ]
    if size == 13:
        return [
            (3, 3), (6, 3), (9, 3), (3, 6), (6, 6), (9, 6),
            (3, 9), (6, 9), (9, 9),
        ]
    if size == 9:
        return [
            (2, 2), (4, 2), (6, 2), (2, 4), (4, 4), (6, 4),
            (2, 6), (4, 6), (6, 6),
        ]
    c = size // 2
    return [(c, c)]


def get_blackhole_points(size: int) -> list[tuple[int, int]]:
    c = size // 2
    pts = []
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if abs(dx) + abs(dy) <= 2:
                nx, ny = c + dx, c + dy
                if 0 <= nx < size and 0 <= ny < size:
                    pts.append((nx, ny))
    return pts


def get_golden_corner_points(size: int, corner: int, span: int = 5) -> list[tuple[int, int]]:
    pts = []
    for dy in range(span):
        for dx in range(span):
            if corner == 0:
                pts.append((dx, dy))
            elif corner == 1:
                pts.append((size - 1 - dx, dy))
            elif corner == 2:
                pts.append((dx, size - 1 - dy))
            else:
                pts.append((size - 1 - dx, size - 1 - dy))
    return pts


def get_sansan_points(size: int) -> list[tuple[int, int]]:
    return [(2, 2), (size - 3, 2), (2, size - 3), (size - 3, size - 3)]


def pick_joseki_targets(size: int, n: int = 8) -> list[tuple[int, int]]:
    rng = random.Random(time.time_ns())
    offsets = [(2, 2), (2, 3), (3, 2), (3, 3), (2, 4), (4, 2), (3, 4), (4, 3)]
    candidates = []
    for bx in (0, size - 1):
        for by in (0, size - 1):
            for ox, oy in offsets:
                x = ox if bx == 0 else size - 1 - ox
                y = oy if by == 0 else size - 1 - oy
                if 0 <= x < size and 0 <= y < size:
                    candidates.append((x, y))
    candidates = list(dict.fromkeys(candidates))
    rng.shuffle(candidates)
    return candidates[:n]


def is_lowline(x: int, y: int, size: int) -> bool:
    return x <= 2 or x >= size - 3 or y <= 2 or y >= size - 3


def mirror_coord(x: int, y: int, size: int) -> tuple[int, int]:
    return size - 1 - x, size - 1 - y


def adjacent_points(x: int, y: int, size: int) -> list[tuple[int, int]]:
    pts = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size:
            pts.append((nx, ny))
    return pts


def adjacent8_points(x: int, y: int, size: int) -> list[tuple[int, int]]:
    pts = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def diamond_points(
    cx: int,
    cy: int,
    radius: int,
    size: int,
    *,
    boundary_only: bool = False,
    include_center: bool = True,
) -> list[tuple[int, int]]:
    pts = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            dist = abs(dx) + abs(dy)
            if dist > radius:
                continue
            if boundary_only and dist != radius:
                continue
            if not include_center and dist == 0:
                continue
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def get_square_points(cx: int, cy: int, radius: int, size: int) -> list[tuple[int, int]]:
    pts = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < size and 0 <= ny < size:
                pts.append((nx, ny))
    return pts


def random_hidden_center(size: int, radius: int, rng: random.Random) -> tuple[int, int]:
    low = max(radius, 0)
    high = max(low, size - radius - 1)
    return rng.randint(low, high), rng.randint(low, high)


def line_key(points: list[tuple[int, int]] | tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(points))


def shape_center(shape: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    xs = [x for x, _ in shape]
    ys = [y for _, y in shape]
    return ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)


def find_new_fool_shapes(
    game: Any,
    color: str,
    seen_shapes: set[tuple[tuple[int, int], ...]],
) -> list[tuple[tuple[int, int], ...]]:
    cv = 1 if color == "B" else 2
    found = []
    found_keys = set()
    orientations = [
        ((1, 0), (0, 1)),
        ((-1, 0), (0, 1)),
        ((1, 0), (0, -1)),
        ((-1, 0), (0, -1)),
    ]

    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] != cv:
                continue
            for (ax, ay), (bx, by) in orientations:
                p1 = (x + ax, y + ay)
                p2 = (x + bx, y + by)
                if not (0 <= p1[0] < game.size and 0 <= p1[1] < game.size):
                    continue
                if not (0 <= p2[0] < game.size and 0 <= p2[1] < game.size):
                    continue
                if game.board[p1[1]][p1[0]] != cv or game.board[p2[1]][p2[0]] != cv:
                    continue
                diag = (x + ax + bx, y + ay + by)
                if 0 <= diag[0] < game.size and 0 <= diag[1] < game.size:
                    if game.board[diag[1]][diag[0]] == cv:
                        continue
                shape = line_key([(x, y), p1, p2])
                if shape in seen_shapes or shape in found_keys:
                    continue
                loosely_isolated = True
                shape_set = set(shape)
                for sx, sy in shape:
                    for nx, ny in adjacent_points(sx, sy, game.size):
                        if (nx, ny) in shape_set:
                            continue
                        if game.board[ny][nx] == cv:
                            loosely_isolated = False
                            break
                    if not loosely_isolated:
                        break
                if not loosely_isolated:
                    continue
                found.append(shape)
                found_keys.add(shape)

    return found


def find_exact_five_lines(game: Any, color: str) -> list[tuple[tuple[int, int], ...]]:
    cv = 1 if color == "B" else 2
    lines = []
    seen = set()
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] != cv:
                continue
            for dx, dy in directions:
                px, py = x - dx, y - dy
                if 0 <= px < game.size and 0 <= py < game.size and game.board[py][px] == cv:
                    continue
                run = []
                cx, cy = x, y
                while 0 <= cx < game.size and 0 <= cy < game.size and game.board[cy][cx] == cv:
                    run.append((cx, cy))
                    cx += dx
                    cy += dy
                if len(run) != 5:
                    continue
                key = line_key(run)
                if key in seen:
                    continue
                seen.add(key)
                lines.append(key)
    return lines


def line_endpoints(
    line: tuple[tuple[int, int], ...],
) -> tuple[Optional[tuple[int, int]], Optional[tuple[int, int]]]:
    if len(line) != 5:
        return None, None
    sorted_line = sorted(line)
    x1, y1 = sorted_line[0]
    x2, y2 = sorted_line[1]
    dx, dy = x2 - x1, y2 - y1
    return (x1 - dx, y1 - dy), (sorted_line[-1][0] + dx, sorted_line[-1][1] + dy)


def line_points_between(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy
    x, y = x1, y1
    while True:
        pts.append((x, y))
        if x == x2 and y == y2:
            break
        e2 = err * 2
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return pts


def count_stones(game: Any, color_val: int) -> int:
    return sum(cell == color_val for row in game.board for cell in row)


def set_points_to_color(game: Any, points: list[tuple[int, int]], color: str) -> list[tuple[int, int]]:
    return apply_magic_points(game, points, color, overwrite_enemy=True)


def apply_magic_points(
    game: Any,
    points: list[tuple[int, int]],
    color: str,
    *,
    overwrite_enemy: bool,
) -> list[tuple[int, int]]:
    cv = 1 if color == "B" else 2
    ov = 3 - cv
    touched = []
    seen = set()
    for x, y in points:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if not (0 <= x < game.size and 0 <= y < game.size):
            continue
        cell = game.board[y][x]
        if cell == cv:
            continue
        if cell == ov and not overwrite_enemy:
            continue
        if cell not in (0, ov):
            continue
        game.board[y][x] = cv
        touched.append((x, y))

    if not touched:
        return []

    frontier = set(touched)
    for x, y in touched:
        frontier.update(game.neighbors(x, y))
    frontier_list = list(frontier)
    _remove_dead_groups(game, frontier_list, ov)
    _remove_dead_groups(game, frontier_list, cv)
    game.ko_point = None
    return [(x, y) for x, y in touched if game.board[y][x] == cv]


def try_spawn_bonus_stone(game: Any, x: int, y: int, color: str) -> bool:
    if not (0 <= x < game.size and 0 <= y < game.size):
        return False
    if game.board[y][x] != 0:
        return False

    cv = 1 if color == "B" else 2
    ov = 3 - cv
    game.board[y][x] = cv

    for nx, ny in game.neighbors(x, y):
        if game.board[ny][nx] != ov:
            continue
        grp = game.get_group(nx, ny)
        if not game.has_liberty(grp):
            for gx, gy in grp:
                game.board[gy][gx] = 0

    own_group = game.get_group(x, y)
    if not own_group or not game.has_liberty(own_group):
        game.board[y][x] = 0
        game.ko_point = None
        return False
    game.ko_point = None
    return True


def spawn_bonus_points(game: Any, points: list[tuple[int, int]], color: str) -> list[tuple[int, int]]:
    return apply_magic_points(game, points, color, overwrite_enemy=False)


def spawn_random_owned_stones(
    game: Any,
    color: str,
    count: int,
    rng: random.Random,
    *,
    area: Optional[list[tuple[int, int]]] = None,
    forbidden: Optional[set[tuple[int, int]]] = None,
) -> list[tuple[int, int]]:
    forbidden = forbidden or set()
    candidates = list(area) if area is not None else [
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
    ]
    unique = []
    seen = set()
    for point in candidates:
        if point in seen or point in forbidden:
            continue
        seen.add(point)
        x, y = point
        if game.board[y][x] == 0:
            unique.append(point)
    rng.shuffle(unique)
    return spawn_bonus_points(game, unique[:count], color)


def clear_random_enemy_stones(
    game: Any,
    color: str,
    count: int,
    rng: random.Random,
    *,
    area: Optional[list[tuple[int, int]]] = None,
) -> list[tuple[int, int]]:
    ov = 2 if color == "B" else 1
    candidates = list(area) if area is not None else [
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
    ]
    enemies = []
    seen = set()
    for point in candidates:
        if point in seen:
            continue
        seen.add(point)
        x, y = point
        if game.board[y][x] == ov:
            enemies.append(point)
    rng.shuffle(enemies)
    cleared = enemies[:count]
    for x, y in cleared:
        game.board[y][x] = 0
    if cleared:
        game.ko_point = None
    return cleared


def get_corner_square_points(size: int, corner: int, span: int) -> list[tuple[int, int]]:
    pts = []
    for dy in range(span):
        for dx in range(span):
            if corner == 0:
                pts.append((dx, dy))
            elif corner == 1:
                pts.append((size - span + dx, dy))
            elif corner == 2:
                pts.append((dx, size - span + dy))
            else:
                pts.append((size - span + dx, size - span + dy))
    return pts


def get_corner_helper_spawn_points(size: int, corner: int, span: int = 5) -> list[tuple[int, int]]:
    inner = span - 1
    min_line = 2
    pts = []
    if corner == 0:
        pts.extend((x, inner) for x in range(min_line, span))
        pts.extend((inner, y) for y in range(min_line, span - 1))
    elif corner == 1:
        pts.extend((x, inner) for x in range(size - span, size - min_line))
        pts.extend((size - span, y) for y in range(min_line, span - 1))
    elif corner == 2:
        pts.extend((x, size - span) for x in range(min_line, span))
        pts.extend((inner, y) for y in range(size - span + 1, size - min_line))
    else:
        pts.extend((x, size - span) for x in range(size - span, size - min_line))
        pts.extend((size - span, y) for y in range(size - span + 1, size - min_line))
    return list(dict.fromkeys(pts))


def get_corner_boundary_points(size: int, corner: int, span: int) -> list[tuple[int, int]]:
    pts = []
    for x, y in get_corner_square_points(size, corner, span):
        min_x = 0 if corner in (0, 2) else size - span
        max_x = span - 1 if corner in (0, 2) else size - 1
        min_y = 0 if corner in (0, 1) else size - span
        max_y = span - 1 if corner in (0, 1) else size - 1
        if x in (min_x, max_x) or y in (min_y, max_y):
            pts.append((x, y))
    return pts


def find_corner_with_min_stones(
    game: Any,
    color: str,
    span: int,
    count: int,
    exclude: Optional[list[int]] = None,
) -> Optional[int]:
    cv = 1 if color == "B" else 2
    excluded = set(exclude or [])
    for corner in range(4):
        if corner in excluded:
            continue
        own = sum(
            1
            for x, y in get_corner_square_points(game.size, corner, span)
            if game.board[y][x] == cv
        )
        if own >= count:
            return corner
    return None


def collect_joseki_burst_points(
    game: Any,
    anchors: list[tuple[int, int]],
    color: str,
    count: int,
    rng: random.Random,
) -> list[tuple[int, int]]:
    cv = 1 if color == "B" else 2
    nearby = []
    seen = set()
    for ax, ay in anchors:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = ax + dx, ay + dy
                if 0 <= nx < game.size and 0 <= ny < game.size:
                    if (nx, ny) in seen or game.board[ny][nx] == cv:
                        continue
                    seen.add((nx, ny))
                    nearby.append((nx, ny))
    rng.shuffle(nearby)
    chosen = nearby[:count]
    if len(chosen) < count:
        leftovers = [
            (x, y)
            for y in range(game.size)
            for x in range(game.size)
            if game.board[y][x] != cv and (x, y) not in seen
        ]
        rng.shuffle(leftovers)
        chosen.extend(leftovers[: count - len(chosen)])
    return chosen


def _remove_dead_groups(game: Any, seeds: list[tuple[int, int]], color_value: int) -> list[tuple[int, int]]:
    removed = []
    seen = set()
    for x, y in seeds:
        if not (0 <= x < game.size and 0 <= y < game.size):
            continue
        if game.board[y][x] != color_value or (x, y) in seen:
            continue
        grp = game.get_group(x, y)
        seen.update(grp)
        if grp and not game.has_liberty(grp):
            for gx, gy in grp:
                game.board[gy][gx] = 0
                removed.append((gx, gy))
    return removed
