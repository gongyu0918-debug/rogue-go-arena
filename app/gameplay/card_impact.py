"""Card impact read-out and card evolution for player Rogue cards.

After a player's own Rogue card changes the board or komi, the engine's raw
network value is read for the position just before and just after the card
fired, so the UI can show how much the card swung the game. Each impactful
trigger also charges the card; enough charge evolves it, and evolved cards
echo a small, bounded bonus on later triggers.
"""
from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

from app.callback_types import SendFn
from app.gameplay.effect_utils import is_safe_bonus_point

# Charges needed to reach level 2 and level 3.
EVOLUTION_THRESHOLDS = (3, 6)
MAX_EVOLUTION_LEVEL = len(EVOLUTION_THRESHOLDS) + 1
# Komi-only cards (Erosion, Komi Cut) echo this much extra komi per level above 1.
ECHO_KOMI_PER_LEVEL = 1.0

RawEval = tuple[float, float]  # (white win probability, white score lead)
MeasureFn = Callable[[Any, Any], Awaitable[Optional[tuple[RawEval, RawEval]]]]


@dataclass(frozen=True)
class ImpactSnapshot:
    board: list[list[int]]
    komi: float


def take_snapshot(game: Any) -> ImpactSnapshot:
    return ImpactSnapshot(board=[row[:] for row in game.board], komi=float(game.komi))


def snapshot_game(game: Any, snapshot: ImpactSnapshot) -> Any:
    """Lightweight stand-in for *game* positioned at *snapshot* (for engine sync)."""
    clone = object.__new__(type(game))
    clone.__dict__.update(game.__dict__)
    clone.board = [row[:] for row in snapshot.board]
    clone.komi = snapshot.komi
    return clone


def parse_raw_nn(response: str) -> Optional[RawEval]:
    """Parse ``kata-raw-nn 0`` output into (whiteWin, whiteLead)."""
    values: dict[str, float] = {}
    for line in response.splitlines():
        parts = line.strip().lstrip("=").split()
        if len(parts) == 2 and parts[0] in {"whiteWin", "whiteLead"}:
            try:
                values[parts[0]] = float(parts[1])
            except ValueError:
                return None
    if "whiteWin" not in values or "whiteLead" not in values:
        return None
    return values["whiteWin"], values["whiteLead"]


def _for_color(raw: RawEval, color: str) -> tuple[float, float]:
    white_win, white_lead = raw
    return (white_win, white_lead) if color == "W" else (1.0 - white_win, -white_lead)


def stone_changes(before: list[list[int]], after: list[list[int]], color: str) -> tuple[int, int]:
    """Return (friendly stones gained, enemy stones lost) between two boards."""
    own = 1 if color == "B" else 2
    gained = lost = 0
    for row_before, row_after in zip(before, after):
        for was, now in zip(row_before, row_after):
            if was != own and now == own:
                gained += 1
            if was == 3 - own and now != 3 - own:
                lost += 1
    return gained, lost


def new_friendly_points(before: list[list[int]], after: list[list[int]], color: str) -> list[tuple[int, int]]:
    own = 1 if color == "B" else 2
    return [
        (x, y)
        for y, (row_before, row_after) in enumerate(zip(before, after))
        for x, (was, now) in enumerate(zip(row_before, row_after))
        if was != own and now == own
    ]


def evolution_state(game: Any) -> dict[str, Any]:
    level = int(getattr(game, "rogue_evolution_level", 1))
    charge = int(getattr(game, "rogue_evolution_charge", 0))
    next_at = EVOLUTION_THRESHOLDS[level - 1] if level < MAX_EVOLUTION_LEVEL else None
    floor = EVOLUTION_THRESHOLDS[level - 2] if level > 1 else 0
    return {"level": level, "charge": charge, "floor": floor, "next": next_at, "max_level": MAX_EVOLUTION_LEVEL}


def add_evolution_charge(game: Any) -> bool:
    """Charge the player's card once; return True when it levels up."""
    game.rogue_evolution_charge = int(getattr(game, "rogue_evolution_charge", 0)) + 1
    level = int(getattr(game, "rogue_evolution_level", 1))
    if level < MAX_EVOLUTION_LEVEL and game.rogue_evolution_charge >= EVOLUTION_THRESHOLDS[level - 1]:
        game.rogue_evolution_level = level + 1
        return True
    return False


def place_echo_stones(
    game: Any,
    color: str,
    anchors: list[tuple[int, int]],
    count: int,
    forbidden: set[tuple[int, int]],
    rng: random.Random,
) -> list[tuple[int, int]]:
    """Place up to *count* friendly stones next to *anchors*; return placed points."""
    placed: list[tuple[int, int]] = []
    frontier = list(anchors)
    while len(placed) < count and frontier:
        candidates = sorted({
            (nx, ny)
            for ax, ay in frontier
            for nx, ny in game.neighbors(ax, ay)
            if is_safe_bonus_point(game, nx, ny, color, forbidden)
        })
        if not candidates:
            break
        point = rng.choice(candidates)
        game.place_stone(point[0], point[1], color)
        placed.append(point)
        frontier.append(point)
    return placed


def impact_payload(
    *,
    card_id: Optional[str],
    color: str,
    before: ImpactSnapshot,
    game: Any,
    evals: Optional[tuple[RawEval, RawEval]],
    echo_points: list[tuple[int, int]],
    echo_komi: float,
) -> dict[str, Any]:
    gained, lost = stone_changes(before.board, game.board, color)
    komi_gain = (before.komi - game.komi) if color == "B" else (game.komi - before.komi)
    payload: dict[str, Any] = {
        "type": "card_impact",
        "card_id": card_id,
        "stones_gained": gained,
        "enemy_stones_lost": lost,
        "komi_gain": round(komi_gain, 2),
        "echo_points": [[x, y] for x, y in echo_points],
        "echo_komi": echo_komi,
        "evolution": evolution_state(game),
        "measured": evals is not None,
    }
    if evals is not None:
        win_before, lead_before = _for_color(evals[0], color)
        win_after, lead_after = _for_color(evals[1], color)
        payload.update({
            "winrate_before": round(win_before, 4),
            "winrate_after": round(win_after, 4),
            "winrate_delta": round(win_after - win_before, 4),
            "lead_before": round(lead_before, 2),
            "lead_after": round(lead_after, 2),
            "lead_delta": round(lead_after - lead_before, 2),
        })
    return payload


async def resolve_card_impact(
    game: Any,
    send_fn: SendFn,
    before: ImpactSnapshot,
    color: str,
    *,
    card_id: Optional[str],
    forbidden: set[tuple[int, int]],
    measure: Optional[MeasureFn],
    ultimate_twins: set[str],
    rng: Optional[random.Random] = None,
) -> Optional[dict[str, Any]]:
    """Echo, charge, measure and announce a player card trigger.

    Does nothing unless the player's card changed the board or komi.
    """
    if game.board == before.board and float(game.komi) == before.komi:
        return None
    rng = rng or random.Random()

    level = int(getattr(game, "rogue_evolution_level", 1))
    echo_points: list[tuple[int, int]] = []
    echo_komi = 0.0
    if level > 1:
        anchors = new_friendly_points(before.board, game.board, color)
        if anchors:
            echo_points = place_echo_stones(game, color, anchors, level - 1, forbidden, rng)
        else:
            echo_komi = ECHO_KOMI_PER_LEVEL * (level - 1)
            game.komi += -echo_komi if color == "B" else echo_komi

    leveled_up = add_evolution_charge(game)
    evals = await measure(game, before) if measure is not None else None
    payload = impact_payload(
        card_id=card_id,
        color=color,
        before=before,
        game=game,
        evals=evals,
        echo_points=echo_points,
        echo_komi=echo_komi,
    )
    await send_fn(payload)
    if leveled_up:
        await send_fn({
            "type": "card_evolved",
            "card_id": card_id,
            "ultimate_twin": card_id if card_id in ultimate_twins else None,
            **evolution_state(game),
        })
    return payload
