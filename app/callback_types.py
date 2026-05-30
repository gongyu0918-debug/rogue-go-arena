from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


SendFn = Callable[[dict[str, Any]], Awaitable[None]]
EngineCommandFn = Callable[[str], Awaitable[str]]
DepsFactory = Callable[[], Any]
FinishDepsFactory = Callable[[EngineCommandFn], Any]
