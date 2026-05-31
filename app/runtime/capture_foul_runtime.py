from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.runtime.capture_foul_adapters import CaptureFoulBinding


@dataclass(frozen=True)
class CaptureFoulRuntimeFns:
    sync_komi: Callable[[Any], Awaitable[None]]


@dataclass(frozen=True)
class CaptureFoulDependencies:
    runtime: CaptureFoulRuntimeFns


def build_capture_foul_binding(
    dependencies: CaptureFoulDependencies,
) -> CaptureFoulBinding:
    return CaptureFoulBinding(
        sync_komi=dependencies.runtime.sync_komi,
    )
