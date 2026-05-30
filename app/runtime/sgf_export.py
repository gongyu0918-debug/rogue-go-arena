from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.responses import Response


SgfGenerator = Callable[[Any], str]


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
        headers={"Content-Disposition": f'attachment; filename="rogue-go-arena_{game_id}.sgf"'},
    )
