from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from dataclasses import dataclass

from app.runtime.game_store import ActiveGameStore


@dataclass
class FakeGame:
    created_at: float
    updated_at: float
    touched: int = 0

    def touch(self) -> None:
        self.touched += 1
        self.updated_at += 1


def smoke_game_store_tracks_and_prunes_games() -> None:
    store = ActiveGameStore[FakeGame](retention_seconds=10)
    old_game = FakeGame(created_at=0, updated_at=0)
    fresh_game = FakeGame(created_at=100, updated_at=100)

    store.set("old", old_game)
    store.set("fresh", fresh_game)

    assert old_game.touched == 1
    assert store.count() == 2
    assert store.get("fresh", touch=True) is fresh_game
    assert fresh_game.touched == 2
    assert store.touch("old") is old_game
    assert old_game.touched == 2

    old_game.updated_at = 0
    fresh_game.updated_at = 105
    store.prune(now=111)

    assert store.count() == 1
    assert store.get("old") is None
    assert store.get("fresh") is fresh_game


if __name__ == "__main__":
    smoke_game_store_tracks_and_prunes_games()
    print("game store smoke test: OK")
