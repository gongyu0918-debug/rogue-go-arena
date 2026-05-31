from __future__ import annotations

import asyncio

import server as s
from app.runtime.sgf_export import build_sgf_export_response


class FakeGameStore:
    def __init__(self, games=None) -> None:
        self.games = games or {}
        self.calls = []

    def prune(self) -> None:
        self.calls.append(("prune",))

    def get(self, game_id: str, *, touch: bool = False):
        self.calls.append(("get", game_id, touch))
        return self.games.get(game_id)


def body_text(response) -> str:
    return response.body.decode("utf-8")


def endpoint_for(path: str, method: str = "GET"):
    for route in s.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def smoke_sgf_export_helper_preserves_found_response() -> None:
    game = object()
    store = FakeGameStore({"abc": game})
    generator_calls = []

    def generate(game_arg) -> str:
        generator_calls.append(game_arg is game)
        return "(;GM[1]SZ[9])"

    response = build_sgf_export_response(
        game_id="abc",
        active_games=store,
        generate_sgf=generate,
    )

    assert store.calls == [("prune",), ("get", "abc", True)]
    assert generator_calls == [True]
    assert response.status_code == 200
    assert response.media_type == "application/x-go-sgf"
    assert response.headers["content-disposition"] == 'attachment; filename="rogue-go-arena_abc.sgf"'
    assert body_text(response) == "(;GM[1]SZ[9])"


def smoke_sgf_export_helper_preserves_missing_response() -> None:
    store = FakeGameStore()

    def generate(_game) -> str:
        raise AssertionError("missing game must not generate SGF")

    response = build_sgf_export_response(
        game_id="missing",
        active_games=store,
        generate_sgf=generate,
    )

    assert store.calls == [("prune",), ("get", "missing", True)]
    assert response.status_code == 404
    assert body_text(response) == "Game not found"


async def smoke_server_sgf_route_uses_shared_helper() -> None:
    game = object()
    store = FakeGameStore({"server-game": game})
    generator_calls = []

    def generate(game_arg) -> str:
        generator_calls.append(game_arg is game)
        return "(;GM[1]PB[server])"

    original_store = s.active_games
    original_generator = s.generate_sgf
    try:
        s.active_games = store
        s.generate_sgf = generate
        binding = s._runtime_info_routes_binding()
        assert binding.active_games is store
        assert binding.generate_sgf is generate
        export_sgf = endpoint_for("/sgf/{game_id}")
        response = await export_sgf("server-game")
        missing = await export_sgf("unknown")
    finally:
        s.active_games = original_store
        s.generate_sgf = original_generator

    assert store.calls == [
        ("prune",),
        ("get", "server-game", True),
        ("prune",),
        ("get", "unknown", True),
    ]
    assert generator_calls == [True]
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="rogue-go-arena_server-game.sgf"'
    )
    assert body_text(response) == "(;GM[1]PB[server])"
    assert missing.status_code == 404
    assert body_text(missing) == "Game not found"


async def main() -> None:
    smoke_sgf_export_helper_preserves_found_response()
    smoke_sgf_export_helper_preserves_missing_response()
    await smoke_server_sgf_route_uses_shared_helper()
    print("sgf export smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
