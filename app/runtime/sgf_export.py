from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from fastapi.responses import Response


SgfGenerator = Callable[[Any], str]


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_-]+")


def safe_sgf_filename_id(game_id: str) -> str:
    safe_id = _SAFE_FILENAME_RE.sub("_", str(game_id)).strip("_-")
    return (safe_id[:80] or "game")


def build_sgf_export_response(
    *,
    game_id: str,
    active_games: Any,
    generate_sgf: SgfGenerator,
) -> Response:
    active_games.prune()
    game = active_games.get(game_id, touch=True)
    if not game:
        return Response(content="Game not found", status_code=404)

    sgf = generate_sgf(game)
    return Response(
        content=sgf,
        media_type="application/x-go-sgf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="rogue-go-arena_{safe_sgf_filename_id(game_id)}.sgf"'
            )
        },
    )
