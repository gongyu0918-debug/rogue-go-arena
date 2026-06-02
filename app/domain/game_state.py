from __future__ import annotations

import copy
import time
from typing import Optional

from app.config.gameplay import (
    ROGUE_QUICKTHINK_FIRST_SECONDS,
    ROGUE_QUICKTHINK_SECOND_SECONDS,
    ULTIMATE_QUICKTHINK_SECONDS,
)
from app.domain.coordinates import gtp_to_coord

# ─── Game state ──────────────────────────────────────────────────────────────
class GoGame:
    def __init__(self, size: int = 19, komi: float = 7.5, handicap: int = 0,
                 player_color: str = "B", level: str = "a3d",
                 two_player: bool = False):
        now = time.time()
        self.size = size
        self.komi = komi
        self.handicap = handicap
        self.player_color = player_color
        self.ai_color = "W" if player_color == "B" else "B"
        self.level = level
        self.two_player = two_player
        self.moves = []
        self.current_player = "B"
        self.board = [[0] * size for _ in range(size)]
        self.captures = {"B": 0, "W": 0}
        self.game_over = False
        self.winner = None
        self.passed = {"B": False, "W": False}
        self.territory = None
        # Rogue mode
        self.rogue_enabled: bool = False
        self.rogue_card: Optional[str] = None
        self.rogue_uses: dict[str, int] = {}     # card_id → remaining uses
        self.rogue_seal_points: list[tuple] = []  # forbidden (x,y) for AI
        self.rogue_waiting_seal: bool = False      # waiting for seal point input
        self.rogue_skip_ai: bool = False           # twin star: skip next AI turn
        self.rogue_puppet_target: Optional[tuple[int, int]] = None
        self.ai_rogue_enabled: bool = False
        self.ai_rogue_card: Optional[str] = None
        self.ai_rogue_seal_points: list[tuple] = []
        # 定式强迫症: 7 random target points, player must hit 4 of them
        self.rogue_joseki_targets: list[tuple] = []
        self.rogue_joseki_hits: int = 0
        self.rogue_joseki_done: bool = False
        self.rogue_godhand_center: Optional[tuple[int, int]] = None
        self.rogue_godhand_trigger: list[tuple] = []
        self.rogue_godhand_done: bool = False
        self.rogue_sansan_trap_done: bool = False
        self.ai_rogue_sansan_trap_done: bool = False
        self.rogue_corner_helper_done: set[int] = set()
        self.rogue_sanrensei_done: bool = False
        self.rogue_five_in_row_seen: set[tuple[tuple[int, int], ...]] = set()
        self.rogue_last_stand_done: dict[str, bool] = {"B": False, "W": False}
        self.rogue_capture_foul_progress: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_defense_first_triggers: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_attack_first_triggers: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_defense_first_last_index: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_attack_first_last_index: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_methodical_turns: dict[str, int] = {"B": 0, "W": 0}
        self.rogue_methodical_remaining: int = 0
        self.rogue_coach_moves_left: int = 0
        self.rogue_coach_bonus_checked: bool = False
        self.rogue_quickthink_stage: int = 0
        self.rogue_fool_shapes: set[tuple[tuple[int, int], ...]] = set()
        # 让子棋任务: player passes 2 turns, then gets bonus turns
        self.rogue_handicap_passes: int = 0       # passes completed
        self.rogue_handicap_active: bool = False   # task completed, bonus active
        self.rogue_handicap_bonuses: int = 0       # bonus turns used (max 3)
        self.challenge_beta: bool = False
        self.challenge_stage: int = 0
        self.challenge_cards: list[str] = []
        self.challenge_offer_cards: list[str] = []
        self.challenge_refreshes: int = 0
        self.challenge_limits: dict[str, int] = {
            "undo": 0,
            "hint": 0,
            "coach": 0,
        }
        self.challenge_usage: dict[str, int] = {
            "undo": 0,
            "hint": 0,
            "coach": 0,
        }
        # Ultimate rogue mode (大招模式)
        self.ultimate: bool = False
        self.ultimate_player_card: Optional[str] = None
        self.ultimate_ai_card: Optional[str] = None
        self.ultimate_move_count: int = 0          # total moves (both sides)
        self.ultimate_extra_turn: bool = False     # chain/double: extra turn flag
        self.ultimate_double_pending: bool = False # double: waiting for 2nd stone
        self.ultimate_territory_pts: list[tuple] = []  # cached forbidden points
        self.ultimate_joseki_targets: list[tuple] = []
        self.ultimate_joseki_hits: int = 0
        self.ultimate_joseki_done: bool = False
        self.ultimate_godhand_center: Optional[tuple[int, int]] = None
        self.ultimate_godhand_trigger: list[tuple] = []
        self.ultimate_godhand_done: bool = False
        self.ultimate_corner_helper_done: set[int] = set()
        self.ultimate_sanrensei_done: bool = False
        self.ultimate_five_in_row_seen: set[tuple[tuple[int, int], ...]] = set()
        self.ultimate_last_stand_done: dict[str, bool] = {"B": False, "W": False}
        self.ultimate_capture_foul_progress: dict[str, int] = {"B": 0, "W": 0}
        self.ultimate_quickthink_active: bool = False
        self.ultimate_quickthink_token: int = 0
        self.ultimate_quickthink_turn_counted: bool = False
        self.ultimate_fool_shapes: set[tuple[tuple[int, int], ...]] = set()
        self.ultimate_shadow_clone_links: list[dict] = []
        self.ai_observer: bool = False
        self.ai_style: str = "balanced"
        self.ai_level_black: str = level
        self.ai_level_white: str = level
        self.ai_style_black: str = "balanced"
        self.ai_style_white: str = "balanced"
        self.last_analysis: dict = {"winrate": 0.5, "score": 0.0, "top_moves": [], "ownership": []}
        self.last_captured_points: list[tuple[int, int]] = []
        # Ko rule: (x, y, color_value) that is forbidden on the NEXT move
        self.ko_point: Optional[tuple[int, int, int]] = None
        self.created_at: float = now
        self.updated_at: float = now
        self._history: list[dict] = []
        self.reset_history()

    def touch(self):
        self.updated_at = time.time()

    # ─── Board logic ─────────────────────────────────────────────────────────
    def neighbors(self, x, y):
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                yield nx, ny

    def get_group(self, x, y):
        color = self.board[y][x]
        if color == 0:
            return set()
        group, stack = set(), [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in group:
                continue
            group.add((cx, cy))
            for nx, ny in self.neighbors(cx, cy):
                if self.board[ny][nx] == color and (nx, ny) not in group:
                    stack.append((nx, ny))
        return group

    def has_liberty(self, group):
        for x, y in group:
            for nx, ny in self.neighbors(x, y):
                if self.board[ny][nx] == 0:
                    return True
        return False

    def is_ko(self, x, y, color) -> bool:
        """Return True if placing *color* at (x, y) would violate the ko rule."""
        if self.ko_point is None:
            return False
        cv = 1 if color == "B" else 2
        return self.ko_point == (x, y, cv)

    def is_legal_move(self, x, y, color, *, skip_ko=False) -> bool:
        """Check whether a move is legal without mutating persistent state."""
        if not (0 <= x < self.size and 0 <= y < self.size):
            return False
        board_before = [row[:] for row in self.board]
        captures_before = dict(self.captures)
        ko_before = self.ko_point
        captured_before = list(self.last_captured_points)
        result = self.place_stone(x, y, color, skip_ko=skip_ko)
        self.board = board_before
        self.captures = captures_before
        self.ko_point = ko_before
        self.last_captured_points = captured_before
        return result >= 0

    def place_stone(self, x, y, color, *, skip_ko=False):
        cv = 1 if color == "B" else 2
        ov = 3 - cv
        if self.board[y][x] != 0:
            return 0
        if not skip_ko and self.is_ko(x, y, color):
            return -1  # ko violation
        prev_captures = dict(self.captures)
        prev_ko_point = self.ko_point
        prev_captured_points = list(self.last_captured_points)
        self.board[y][x] = cv
        captured = 0
        captured_single: Optional[tuple[int, int]] = None
        captured_points: list[tuple[int, int]] = []
        for nx, ny in self.neighbors(x, y):
            if self.board[ny][nx] == ov:
                grp = self.get_group(nx, ny)
                if not self.has_liberty(grp):
                    for gx, gy in grp:
                        self.board[gy][gx] = 0
                        captured_points.append((gx, gy))
                    if len(grp) == 1 and captured == 0:
                        captured_single = next(iter(grp))
                    captured += len(grp)
        self.captures[color] = self.captures.get(color, 0) + captured
        own_grp = self.get_group(x, y)
        if not own_grp or not self.has_liberty(own_grp):
            self.board[y][x] = 0
            self.captures = prev_captures
            self.ko_point = prev_ko_point
            self.last_captured_points = prev_captured_points
            return -2  # suicide / self-capture
        # Update ko point: if exactly 1 stone was captured and the
        # capturing stone itself has exactly 1 liberty (the captured
        # position), then the opponent cannot immediately recapture.
        if captured == 1 and captured_single is not None:
            if len(own_grp) == 1:
                liberties = [
                    (lx, ly) for lx, ly in self.neighbors(x, y)
                    if self.board[ly][lx] == 0
                ]
                if len(liberties) == 1 and liberties[0] == captured_single:
                    self.ko_point = (captured_single[0], captured_single[1], ov)
                else:
                    self.ko_point = None
            else:
                self.ko_point = None
        else:
            self.ko_point = None
        self.last_captured_points = captured_points
        return captured

    def _snapshot_state(self) -> dict:
        return copy.deepcopy({
            k: v for k, v in self.__dict__.items()
            if k not in {"_history", "created_at", "updated_at"}
        })

    def reset_history(self):
        self._history = [self._snapshot_state()]

    def push_history(self):
        self._history.append(self._snapshot_state())

    def undo_history(self, steps: int) -> bool:
        if steps <= 0 or len(self._history) <= 1:
            return False
        history = self._history
        while steps > 0 and len(history) > 1:
            history.pop()
            steps -= 1
        state = copy.deepcopy(history[-1])
        created_at = getattr(self, "created_at", time.time())
        self.__dict__.clear()
        self.__dict__.update(state)
        self.created_at = created_at
        self.updated_at = time.time()
        self._history = history
        return True

    def rebuild_board(self):
        self.board = [[0] * self.size for _ in range(self.size)]
        self.captures = {"B": 0, "W": 0}
        for color, gtp in self.moves:
            if gtp.upper() == "PASS":
                continue
            coord = gtp_to_coord(gtp, self.size)
            if coord:
                self.place_stone(coord[0], coord[1], color, skip_ko=True)

    def to_state(self) -> dict:
        return {
            "board": self.board,
            "size": self.size,
            "komi": self.komi,
            "handicap": self.handicap,
            "current_player": self.current_player,
            "player_color": self.player_color,
            "ai_color": self.ai_color,
            "captures": self.captures,
            "ko_point": [self.ko_point[0], self.ko_point[1]] if self.ko_point else None,
            "move_number": len(self.moves),
            "game_over": self.game_over,
            "winner": self.winner,
            "last_move": self.moves[-1] if self.moves else None,
            "moves_list": [[c, g] for c, g in self.moves],
            "level": self.level,
            "two_player": self.two_player,
            "ai_observer": self.ai_observer,
            "ai_style": self.ai_style,
            "ai_level_black": self.ai_level_black,
            "ai_level_white": self.ai_level_white,
            "ai_style_black": self.ai_style_black,
            "ai_style_white": self.ai_style_white,
            "rogue_enabled": self.rogue_enabled,
            "rogue_card": self.rogue_card,
            "rogue_uses": self.rogue_uses,
            "rogue_seal_points": [[x, y] for x, y in self.rogue_seal_points],
            "rogue_puppet_target": list(self.rogue_puppet_target) if self.rogue_puppet_target else None,
            "ai_rogue_enabled": self.ai_rogue_enabled,
            "ai_rogue_card": self.ai_rogue_card,
            "ai_rogue_seal_points": [[x, y] for x, y in self.ai_rogue_seal_points],
            "rogue_joseki_targets": [[x, y] for x, y in self.rogue_joseki_targets],
            "rogue_joseki_done": self.rogue_joseki_done,
            "rogue_undo_disabled": self.rogue_card in {"no_regret", "quickthink"},
            "rogue_coach_moves_left": self.rogue_coach_moves_left,
            "rogue_quickthink_stage": self.rogue_quickthink_stage,
            "rogue_methodical_remaining": self.rogue_methodical_remaining,
            "rogue_quickthink_seconds": (
                ROGUE_QUICKTHINK_FIRST_SECONDS
                if self.rogue_quickthink_stage == 1
                else ROGUE_QUICKTHINK_SECOND_SECONDS
                if self.rogue_quickthink_stage == 2
                else 0
            ),
            "rogue_handicap_active": self.rogue_handicap_active,
            "rogue_handicap_passes": self.rogue_handicap_passes,
            "challenge_beta": self.challenge_beta,
            "challenge_stage": self.challenge_stage,
            "challenge_cards": list(self.challenge_cards),
            "challenge_refreshes": self.challenge_refreshes,
            "challenge_limits": dict(self.challenge_limits),
            "challenge_usage": dict(self.challenge_usage),
            "challenge_remaining": {
                key: max(0, self.challenge_limits.get(key, 0) - self.challenge_usage.get(key, 0))
                for key in {"undo", "hint", "coach"}
            },
            "ultimate": self.ultimate,
            "ultimate_player_card": self.ultimate_player_card,
            "ultimate_ai_card": self.ultimate_ai_card,
            "ultimate_move_count": self.ultimate_move_count,
            "ultimate_max_moves": 20,
            "ultimate_extra_turn": self.ultimate_extra_turn,
            "ultimate_double_pending": self.ultimate_double_pending,
            "ultimate_joseki_targets": [[x, y] for x, y in self.ultimate_joseki_targets],
            "ultimate_joseki_hits": self.ultimate_joseki_hits,
            "ultimate_joseki_done": self.ultimate_joseki_done,
            "ultimate_quickthink_active": self.ultimate_quickthink_active,
            "ultimate_quickthink_token": self.ultimate_quickthink_token,
            "ultimate_quickthink_seconds": (
                ULTIMATE_QUICKTHINK_SECONDS if self.ultimate_quickthink_active else 0
            ),
        }
