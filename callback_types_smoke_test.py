from __future__ import annotations

from collections.abc import Callable
from typing import get_args, get_origin

from app.runtime.callback_types import DepsFactory, EngineCommandFn, FinishDepsFactory, SendFn


def smoke_shared_runtime_callback_aliases() -> None:
    assert get_origin(SendFn) is Callable
    assert get_origin(EngineCommandFn) is Callable
    assert get_origin(DepsFactory) is Callable
    assert get_origin(FinishDepsFactory) is Callable
    assert get_args(FinishDepsFactory)[0][0] is EngineCommandFn


def main() -> None:
    smoke_shared_runtime_callback_aliases()
    print("callback types smoke test: OK")


if __name__ == "__main__":
    main()
