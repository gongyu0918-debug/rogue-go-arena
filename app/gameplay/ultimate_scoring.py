from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


AsyncSend = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class UltimateScoreResult:
    winner: str
    score: str
    reason: str
    black_score: float
    white_score: float


def compute_ultimate_area_score(
    game: Any,
    *,
    reason: str = "ultimate_20moves",
) -> UltimateScoreResult:
    b_score = 0
    w_score = 0
    size = game.size
    visited = [[False] * size for _ in range(size)]

    for y in range(size):
        for x in range(size):
            if game.board[y][x] == 1:
                b_score += 1
            elif game.board[y][x] == 2:
                w_score += 1

    for y in range(size):
        for x in range(size):
            if game.board[y][x] != 0 or visited[y][x]:
                continue
            region = []
            stack = [(x, y)]
            borders = set()
            while stack:
                cx, cy = stack.pop()
                if visited[cy][cx]:
                    continue
                visited[cy][cx] = True
                region.append((cx, cy))
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < size and 0 <= ny < size:
                        if game.board[ny][nx] == 0 and not visited[ny][nx]:
                            stack.append((nx, ny))
                        elif game.board[ny][nx] != 0:
                            borders.add(game.board[ny][nx])
            if len(borders) != 1:
                continue
            owner = borders.pop()
            if owner == 1:
                b_score += len(region)
            else:
                w_score += len(region)

    b_score_final = float(b_score)
    w_score_final = float(w_score + game.komi)
    if b_score_final > w_score_final:
        winner = "B"
        score_str = f"B+{b_score_final - w_score_final:.1f}"
    else:
        winner = "W"
        score_str = f"W+{w_score_final - b_score_final:.1f}"

    return UltimateScoreResult(
        winner=winner,
        score=score_str,
        reason=reason,
        black_score=b_score_final,
        white_score=w_score_final,
    )


async def finalize_ultimate_score(
    game: Any,
    send_fn: AsyncSend,
    *,
    reason: str = "ultimate_20moves",
) -> UltimateScoreResult:
    result = compute_ultimate_area_score(game, reason=reason)
    game.game_over = True
    game.winner = result.winner
    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})
    await send_fn({
        "type": "game_over",
        "winner": result.winner,
        "score": result.score,
        "reason": result.reason,
    })
    return result
