from __future__ import annotations

import random
import time
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from typing import Any, Callable, Optional

import app.config.gameplay as gameplay_config
from app.gameplay.effect_utils import (
    adjacent_points,
    diamond_points,
    get_blackhole_points,
    get_star_points,
    is_lowline,
)


KATAGO_UNLIMITED_MAX_TIME = "1e20"
RANK_ORDER = tuple(gameplay_config.RANK_VISITS.keys())


@dataclass(frozen=True)
class AiMovePlan:
    mode: str
    effective_level: str
    visits: int
    time_limit: float
    move_count: int
    ai_move_count: int


@dataclass(frozen=True)
class AiTurnSnapshot:
    color: str
    card: str | None
    rogue_cards: set[str]
    move_count: int
    ai_move_count: int


@dataclass(frozen=True)
class AiTargetPlan:
    coord: tuple[int, int]
    message: str


@dataclass(frozen=True)
class AiPointRestriction:
    kind: str
    points: list[tuple[int, int]]
    message: str


@dataclass(frozen=True)
class UltimateAiSearchPlan:
    color: str
    ai_card: str | None
    color_value: int
    forbidden: set[tuple[int, int]]
    visits: int


def compute_game_visits(
    level: str,
    move_count: int = -1,
    mode: str = "normal",
    *,
    cpu_mode: bool = False,
) -> int:
    raw = gameplay_config.RANK_VISITS.get(level, 800)
    visits = gameplay_config.MAX_GAME_VISITS if raw == 0 else min(raw, gameplay_config.MAX_GAME_VISITS)
    if mode == "rogue":
        visits = min(visits, gameplay_config.ROGUE_MAX_VISITS)
    elif mode == "ultimate":
        visits = min(visits, gameplay_config.ULTIMATE_MAX_VISITS)
    if cpu_mode:
        visits = min(visits, gameplay_config.CPU_MAX_VISITS)
    if (
        0 <= move_count < gameplay_config.OPENING_MOVE_THRESHOLD
        and visits > gameplay_config.OPENING_MAX_VISITS
    ):
        visits = gameplay_config.OPENING_MAX_VISITS
    return visits


def snapshot_ai_turn(
    game: Any,
    rogue_card_ids: Callable[[Any], Iterable[str]],
) -> AiTurnSnapshot:
    color = game.ai_color
    return AiTurnSnapshot(
        color=color,
        card=game.rogue_card,
        rogue_cards=set(rogue_card_ids(game)),
        move_count=len(game.moves),
        ai_move_count=sum(1 for move_color, _move in game.moves if move_color == color),
    )


def weaken_rank(level: str, steps: int = 1) -> str:
    try:
        idx = RANK_ORDER.index(level)
    except ValueError:
        return level
    return RANK_ORDER[max(0, idx - steps)]


def weaken_rank_one_step(level: str) -> str:
    return weaken_rank(level, 1)


def is_suspicious_ai_pass(game: Any, gtp_move: str, color: str) -> bool:
    if gtp_move.upper() != "PASS":
        return False
    non_pass_moves = sum(
        1
        for move_color, move in game.moves
        if move_color == color and move.upper() != "PASS"
    )
    empty_points = sum(1 for row in game.board for cell in row if cell == 0)
    return non_pass_moves < 3 and empty_points > max(20, game.size * 2)


def plan_rogue_ai_search(
    game: Any,
    rogue_cards: set[str],
    *,
    move_count: int,
    ai_move_count: int,
    get_game_visits: Callable[[str, int, str], int],
    weaken_rank: Callable[[str, int], str],
) -> AiMovePlan:
    mode = "rogue" if rogue_cards else "normal"
    effective_level = game.level
    if "nerf" in rogue_cards:
        effective_level = weaken_rank(effective_level, 8)
    if "time_press" in rogue_cards:
        effective_level = weaken_rank(effective_level, 5)
    visits = get_game_visits(effective_level, move_count, mode)

    if "nerf" in rogue_cards:
        visits = max(30, int(visits * gameplay_config.ROGUE_NERF_FACTOR))

    if move_count < gameplay_config.OPENING_MOVE_THRESHOLD:
        time_limit = min(3.0, gameplay_config.MAX_MOVE_TIME)
    elif visits > 5000:
        time_limit = gameplay_config.MAX_MOVE_TIME
    else:
        time_limit = 8.0

    if "time_press" in rogue_cards:
        time_limit = min(gameplay_config.ROGUE_TIME_PRESS_MAX_TIME, time_limit)
        visits = min(visits, gameplay_config.ROGUE_TIME_PRESS_MAX_VISITS)

    return AiMovePlan(
        mode=mode,
        effective_level=effective_level,
        visits=visits,
        time_limit=time_limit,
        move_count=move_count,
        ai_move_count=ai_move_count,
    )


def plan_ultimate_ai_search(
    game: Any,
    *,
    get_territory_forbidden: Callable[[Any, int], set[tuple[int, int]]],
    get_game_visits: Callable[[str, int, str], int],
) -> UltimateAiSearchPlan:
    color = game.ai_color
    color_value = 1 if color == "B" else 2
    forbidden: set[tuple[int, int]] = set()
    if game.ultimate_player_card == "territory":
        forbidden = set(get_territory_forbidden(game, color_value))
    return UltimateAiSearchPlan(
        color=color,
        ai_card=game.ultimate_ai_card,
        color_value=color_value,
        forbidden=forbidden,
        visits=get_game_visits(game.level, len(game.moves), "ultimate"),
    )


def resolve_occupied_ai_move(
    game: Any,
    color: str,
    gtp_move: str,
    coord: Optional[tuple[int, int]],
    *,
    coord_to_gtp: Callable[[int, int, int], str],
    rng: random.Random | None = None,
) -> tuple[str, Optional[tuple[int, int]]]:
    if gtp_move.upper() == "PASS" or coord is None:
        return gtp_move, coord

    x, y = coord
    if game.board[y][x] == 0:
        return gtp_move, coord

    rng = random.Random(time.time_ns()) if rng is None else rng
    empties = [
        (sx, sy)
        for sy in range(game.size)
        for sx in range(game.size)
        if game.board[sy][sx] == 0 and game.is_legal_move(sx, sy, color)
    ]
    if not empties:
        return "pass", None

    x, y = rng.choice(empties)
    return coord_to_gtp(x, y, game.size), (x, y)


def choose_tengen_target(game: Any, ai_move_count: int) -> Optional[AiTargetPlan]:
    if ai_move_count >= gameplay_config.ROGUE_TENGEN_AI_MOVES:
        return None
    if ai_move_count == 0:
        c = game.size // 2
        return AiTargetPlan((c, c), "天元触发，AI 优先抢下天元")
    return None


def tengen_followup_points(game: Any, ai_move_count: int) -> Optional[AiPointRestriction]:
    if not (0 < ai_move_count < gameplay_config.ROGUE_TENGEN_AI_MOVES):
        return None
    c = game.size // 2
    available = [
        (x, y)
        for x, y in diamond_points(c, c, 2, game.size)
        if game.board[y][x] == 0
    ]
    if not available:
        return None
    return AiPointRestriction("allow_only", available, "天元牵引：AI 被限制在天元 5x5 菱形区域内落子")


def gravity_allowed_points(game: Any, ai_move_count: int) -> Optional[AiPointRestriction]:
    if ai_move_count >= gameplay_config.ROGUE_GRAVITY_AI_MOVES:
        return None
    available = [(x, y) for x, y in get_star_points(game.size) if game.board[y][x] == 0]
    if not available:
        return None
    return AiPointRestriction("allow_only", available, "引力触发，AI 被限制在星位附近落子")


def lowline_allowed_points(game: Any, ai_move_count: int) -> Optional[AiPointRestriction]:
    if ai_move_count >= gameplay_config.ROGUE_LOWLINE_AI_MOVES:
        return None
    allowed = [
        (x, y)
        for x in range(game.size)
        for y in range(game.size)
        if is_lowline(x, y, game.size) and game.board[y][x] == 0
    ]
    if not allowed:
        return None
    return AiPointRestriction("allow_only", allowed, "低空飞行触发，AI 继续在低线路落子")


def sansan_opening_restriction(game: Any, ai_move_count: int) -> Optional[AiPointRestriction]:
    if ai_move_count >= 3:
        return None

    points = []
    for base_x in (0, game.size - 3):
        for base_y in (0, game.size - 3):
            for dy in range(3):
                for dx in range(3):
                    x, y = base_x + dx, base_y + dy
                    if game.board[y][x] == 0:
                        points.append((x, y))
    if not points:
        return None
    return AiPointRestriction("allow_only", points, "三三开局触发，AI 前 3 手必须落在角部 3x3 区域")


def shadow_followup_points(
    game: Any,
    color: str,
    ai_move_count: int,
    *,
    gtp_to_coord: Callable[[str, int], Optional[tuple[int, int]]],
) -> Optional[AiPointRestriction]:
    prev_ai_gtp = None
    for move_color, move_gtp in reversed(game.moves):
        if move_color == color and move_gtp.upper() != "PASS":
            prev_ai_gtp = move_gtp
            break
    if not prev_ai_gtp:
        return None

    coord = gtp_to_coord(prev_ai_gtp, game.size)
    if not coord:
        return None
    available = [
        (x, y)
        for x, y in adjacent_points(coord[0], coord[1], game.size)
        if game.board[y][x] == 0
    ]
    if not available:
        return None
    return AiPointRestriction("allow_only", available, "影子触发，AI 贴着自己的上一手继续下")


def rogue_forbidden_points(
    game: Any,
    rogue_cards: set[str],
    ai_move_count: int,
    *,
    challenge_zone_points: Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]],
) -> list[tuple[int, int]]:
    if "seal" in rogue_cards and game.rogue_seal_points:
        return list(game.rogue_seal_points)
    if "fog" in rogue_cards and game.rogue_seal_points:
        return list(game.rogue_seal_points)
    if (
        "blackhole" in rogue_cards
    ):
        return challenge_zone_points(game, get_blackhole_points(game.size))
    if (
        "golden_corner" in rogue_cards
        and game.rogue_seal_points
    ):
        return list(game.rogue_seal_points)
    return []


def choose_ai_style_move(
    game: Any,
    color: str,
    top_moves: list[dict],
    style: str,
    *,
    gtp_to_coord: Callable[[str, int], Optional[tuple[int, int]]],
) -> Optional[str]:
    if style not in gameplay_config.AI_STYLE_OPTIONS or style == "balanced":
        return None
    best_move = None
    best_score = None
    for item in top_moves[:8]:
        gtp = (item.get("move") or "").strip()
        coord = gtp_to_coord(gtp, game.size)
        if not coord:
            continue
        x, y = coord
        if game.board[y][x] != 0:
            continue
        score = _ai_style_target_score(game, color, coord, style)
        if best_score is None or score > best_score:
            best_score = score
            best_move = gtp
    return best_move


def _ai_style_target_score(game: Any, color: str, coord: tuple[int, int], style: str) -> float:
    x, y = coord
    center = (game.size - 1) / 2.0
    edge_dist = min(x, y, game.size - 1 - x, game.size - 1 - y)
    center_dist = abs(x - center) + abs(y - center)
    own = 1 if color == "B" else 2
    opp = 3 - own
    own_adj = 0
    opp_adj = 0
    for nx, ny in game.neighbors(x, y):
        cell = game.board[ny][nx]
        if cell == own:
            own_adj += 1
        elif cell == opp:
            opp_adj += 1
    if style == "territory":
        return -edge_dist * 3 + own_adj - opp_adj * 0.25
    if style == "influence":
        return -center_dist * 2 + opp_adj * 0.4
    if style == "attack":
        return opp_adj * 4 + own_adj * 0.5 - edge_dist * 0.3
    if style == "defense":
        return own_adj * 4 + opp_adj * 0.2 - center_dist * 0.2
    return 0.0


class AiMoveService:
    def __init__(
        self,
        *,
        engine: Any,
        run_in_executor: Callable[..., Awaitable[Any]],
        engine_log: Callable[[str], None],
        coord_to_gtp: Callable[[int, int, int], str],
        gtp_to_coord: Callable[[str, int], Optional[tuple[int, int]]],
    ) -> None:
        self._engine = engine
        self._run_in_executor = run_in_executor
        self._engine_log = engine_log
        self._coord_to_gtp = coord_to_gtp
        self._gtp_to_coord = gtp_to_coord

    def bind_runtime(
        self,
        *,
        engine: Any,
        run_in_executor: Callable[..., Awaitable[Any]],
    ) -> None:
        self._engine = engine
        self._run_in_executor = run_in_executor

    def _clear_max_time_locked(self) -> None:
        self._engine._send_command_locked(
            f"kata-set-param maxTime {KATAGO_UNLIMITED_MAX_TIME}"
        )

    async def pick_nonpass_fallback_move(
        self,
        game: Any,
        color: str,
        visits: int,
        forbidden: Optional[set[tuple[int, int]]] = None,
    ) -> Optional[str]:
        forbidden = forbidden or set()
        try:
            lines, _ = self._engine.analyze(
                color,
                visits=max(100, min(visits, 1200)),
                interval=50,
                duration=1.5,
                extra_args=["rootInfo", "true"],
            )
            result = self._engine.parse_analysis(lines, [], game.size, to_move_color=color)
            for item in result.get("top_moves", []):
                gtp = (item.get("move") or item.get("gtp") or "").strip()
                if not gtp or gtp.upper() in {"PASS", "RESIGN"}:
                    continue
                coord = self._gtp_to_coord(gtp, game.size)
                if not coord or game.board[coord[1]][coord[0]] != 0:
                    continue
                if coord in forbidden or not game.is_legal_move(coord[0], coord[1], color):
                    continue
                with self._engine.command_lock:
                    resp = self._engine._send_command_locked(f"play {color} {gtp}")
                    if "?" not in resp:
                        return gtp
        except Exception as exc:
            self._engine_log(f"non-pass fallback failed: {exc}")
        return None

    async def pick_ranked_legal_move(
        self,
        game: Any,
        color: str,
        visits: int,
        forbidden: Optional[set[tuple[int, int]]] = None,
        *,
        time_limit: float = 1.5,
    ) -> Optional[str]:
        forbidden = forbidden or set()
        try:
            lines, _ = await self._run_in_executor(
                self._engine.analyze,
                color,
                max(120, min(visits, 1400)),
                50,
                time_limit,
                ["rootInfo", "true"],
            )
            result = self._engine.parse_analysis(lines, [], game.size, to_move_color=color)
            candidates = []
            for item in result.get("top_moves", []):
                gtp = (item.get("move") or item.get("gtp") or "").strip()
                if not gtp or gtp.upper() in {"PASS", "RESIGN"}:
                    continue
                coord = self._gtp_to_coord(gtp, game.size)
                if (
                    coord
                    and coord not in forbidden
                    and game.board[coord[1]][coord[0]] == 0
                    and game.is_legal_move(coord[0], coord[1], color)
                ):
                    candidates.append(gtp)
            for gtp in candidates:
                with self._engine.command_lock:
                    resp = self._engine._send_command_locked(f"play {color} {gtp}")
                    if "?" not in resp:
                        return gtp
        except Exception as exc:
            self._engine_log(f"ranked legal fallback failed: {exc}")
        return None

    async def avoid_points(
        self,
        game: Any,
        color: str,
        visits: int,
        time_limit: float,
        forbidden: list[tuple[int, int]] | set[tuple[int, int]],
    ) -> str:
        forbidden_gtp = {
            self._coord_to_gtp(x, y, game.size)
            for x, y in forbidden
        }
        forbidden_gtp_upper = {s.upper() for s in forbidden_gtp}
        forbidden_coords = set(forbidden)

        def _analyze_and_pick():
            with self._engine.command_lock:
                mv = 10000000 if visits == 0 else visits
                self._engine._send_command_locked(f"kata-set-param maxVisits {mv}")
                self._engine.current_visits = visits
                self._engine._send_command_locked(f"kata-set-param maxTime {time_limit}")
                resp = self._engine._send_command_locked(
                    f"genmove {color}",
                    timeout=max(60, time_limit + 15),
                )
                self._clear_max_time_locked()

                gtp_move = resp.replace("=", "").strip()
                if (
                    gtp_move.upper() not in ("PASS", "RESIGN")
                    and gtp_move.upper() not in forbidden_gtp_upper
                ):
                    return gtp_move

                if gtp_move.upper() not in ("PASS", "RESIGN"):
                    self._engine._send_command_locked("undo")
                for attempt in range(5):
                    v = max(50, visits // (2 + attempt))
                    self._engine._send_command_locked(f"kata-set-param maxVisits {v}")
                    resp2 = self._engine._send_command_locked(f"genmove {color}", timeout=20)
                    m = resp2.replace("=", "").strip()
                    if (
                        m.upper() not in ("PASS", "RESIGN")
                        and m.upper() not in forbidden_gtp_upper
                    ):
                        return m
                    if m.upper() not in ("PASS", "RESIGN"):
                        self._engine._send_command_locked("undo")
                return None

        picked = await self._run_in_executor(_analyze_and_pick)
        if picked:
            return picked

        ranked = await self.pick_ranked_legal_move(
            game,
            color,
            visits,
            forbidden_coords,
            time_limit=1.3,
        )
        if ranked:
            return ranked

        def _last_resort():
            with self._engine.command_lock:
                allowed = [
                    (x, y)
                    for y in range(game.size) for x in range(game.size)
                    if game.board[y][x] == 0
                    and (x, y) not in forbidden_coords
                    and game.is_legal_move(x, y, color)
                ]
                random.shuffle(allowed)
                for ax, ay in allowed:
                    gtp = self._coord_to_gtp(ax, ay, game.size)
                    r = self._engine._send_command_locked(f"play {color} {gtp}")
                    if "?" not in r:
                        return gtp
                self._engine._send_command_locked(f"play {color} pass")
                return "pass"

        return await self._run_in_executor(_last_resort)

    async def allow_only_points(
        self,
        game: Any,
        color: str,
        visits: int,
        time_limit: float,
        allowed: list[tuple[int, int]],
    ) -> str:
        allowed_gtp = {self._coord_to_gtp(x, y, game.size).upper() for x, y in allowed}

        def _pick():
            with self._engine.command_lock:
                mv = max(50, min(visits, 2000))
                self._engine._send_command_locked(f"kata-set-param maxVisits {mv}")
                self._engine.current_visits = mv
                self._engine._send_command_locked(
                    f"kata-set-param maxTime {min(time_limit, 3.0)}"
                )

                for attempt in range(6):
                    v = max(50, mv // (1 + attempt))
                    self._engine._send_command_locked(f"kata-set-param maxVisits {v}")
                    resp = self._engine._send_command_locked(f"genmove {color}", timeout=15)
                    m = resp.replace("=", "").strip()
                    if m.upper() in ("PASS", "RESIGN"):
                        self._clear_max_time_locked()
                        return m
                    if m.upper() in allowed_gtp:
                        self._clear_max_time_locked()
                        return m
                    self._engine._send_command_locked("undo")

                self._clear_max_time_locked()
                random.shuffle(allowed)
                for ax, ay in allowed:
                    if game.board[ay][ax] == 0:
                        gtp = self._coord_to_gtp(ax, ay, game.size)
                        r = self._engine._send_command_locked(f"play {color} {gtp}")
                        if "?" not in r:
                            return gtp
                resp = self._engine._send_command_locked(f"genmove {color}", timeout=15)
                return resp.replace("=", "").strip()

        return await self._run_in_executor(_pick)

    async def suboptimal_move(
        self,
        game: Any,
        color: str,
        visits: int,
        time_limit: float,
        start_idx: int = 2,
        end_idx: int = 5,
    ) -> Optional[str]:
        del time_limit

        def _analyze_pick():
            mv = max(200, min(visits, 3000))
            lines, _ = self._engine.analyze(
                color,
                visits=mv,
                interval=50,
                duration=2.0,
                extra_args=["rootInfo", "true"],
            )
            result = self._engine.parse_analysis(lines, [], game.size, to_move_color=color)

            top = result.get("top_moves", [])
            if len(top) < end_idx:
                return None

            pick = random.choice(top[start_idx:end_idx])
            gtp = pick.get("move") or pick.get("gtp")
            if not gtp:
                return None

            with self._engine.command_lock:
                resp = self._engine._send_command_locked(f"play {color} {gtp}")
                if "?" in resp:
                    return None
            return gtp

        return await self._run_in_executor(_analyze_pick)

    async def generate_move(self, color: str, visits: int, time_limit: float) -> str:
        def _genmove_atomic():
            with self._engine.command_lock:
                mv = 10000000 if visits == 0 else visits
                self._engine._send_command_locked(f"kata-set-param maxVisits {mv}")
                self._engine.current_visits = visits
                self._engine._send_command_locked(f"kata-set-param maxTime {time_limit}")
                resp = self._engine._send_command_locked(
                    f"genmove {color}",
                    timeout=max(60, time_limit + 15),
                )
                self._clear_max_time_locked()
                return resp

        return await self._run_in_executor(_genmove_atomic)

    async def no_resign_move(self, game: Any, color: str) -> str:
        del game

        def _retry():
            with self._engine.command_lock:
                for v in (100, 30, 10):
                    self._engine._send_command_locked(f"kata-set-param maxVisits {v}")
                    self._engine._send_command_locked("kata-set-param maxTime 2")
                    resp = self._engine._send_command_locked(f"genmove {color}", timeout=10)
                    self._clear_max_time_locked()
                    m = resp.replace("=", "").strip()
                    if m.upper() != "RESIGN":
                        return m
                    self._engine._send_command_locked("undo")
                self._engine._send_command_locked(f"play {color} pass")
                return "pass"

        return await self._run_in_executor(_retry)

    async def retry_avoiding_ko(self, game: Any, color: str) -> str:
        def _retry():
            with self._engine.command_lock:
                self._engine._send_command_locked("undo")

                for attempt in range(5):
                    v = max(50, 800 // (2 + attempt))
                    self._engine._send_command_locked(f"kata-set-param maxVisits {v}")
                    self._engine._send_command_locked("kata-set-param maxTime 3")
                    resp = self._engine._send_command_locked(f"genmove {color}", timeout=10)
                    self._clear_max_time_locked()
                    m = resp.replace("=", "").strip()
                    if m.upper() in ("PASS", "RESIGN"):
                        return m
                    coord = self._gtp_to_coord(m, game.size)
                    if not coord or not game.is_ko(coord[0], coord[1], color):
                        return m
                    self._engine._send_command_locked("undo")

                empties = [
                    (x, y)
                    for y in range(game.size) for x in range(game.size)
                    if game.board[y][x] == 0
                    and game.is_legal_move(x, y, color)
                ]
                random.shuffle(empties)
                for ax, ay in empties:
                    gtp = self._coord_to_gtp(ax, ay, game.size)
                    r = self._engine._send_command_locked(f"play {color} {gtp}")
                    if "?" not in r:
                        return gtp

                self._engine._send_command_locked(f"play {color} pass")
                return "pass"

        return await self._run_in_executor(_retry)
