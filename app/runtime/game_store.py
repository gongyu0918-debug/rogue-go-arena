from __future__ import annotations

import threading
import time
from typing import Generic, Optional, TypeVar


T = TypeVar("T")


class ActiveGameStore(Generic[T]):
    def __init__(self, retention_seconds: float):
        self.retention_seconds = retention_seconds
        self._games: dict[str, T] = {}
        self._lock = threading.RLock()

    def _touch_value(self, game: Optional[T]):
        if game is None:
            return
        touch = getattr(game, "touch", None)
        if callable(touch):
            touch()
            return
        setattr(game, "updated_at", time.time())

    def set(self, game_id: str, game: T):
        with self._lock:
            self._games[game_id] = game
            self._touch_value(game)

    def get(self, game_id: str, *, touch: bool = False) -> Optional[T]:
        with self._lock:
            game = self._games.get(game_id)
            if touch:
                self._touch_value(game)
            return game

    def touch(self, game_id: str) -> Optional[T]:
        with self._lock:
            game = self._games.get(game_id)
            self._touch_value(game)
            return game

    def count(self) -> int:
        with self._lock:
            return len(self._games)

    def prune(self, now: Optional[float] = None):
        current = time.time() if now is None else now
        expired_ids = []
        with self._lock:
            for game_id, game in list(self._games.items()):
                updated_at = getattr(game, "updated_at", getattr(game, "created_at", current))
                if current - updated_at > self.retention_seconds:
                    expired_ids.append(game_id)
            for game_id in expired_ids:
                self._games.pop(game_id, None)
