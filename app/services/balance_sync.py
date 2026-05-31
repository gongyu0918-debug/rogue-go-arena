from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from typing import Any


DEFAULT_WS_ACTION_BALANCE_KEYS = (
    "ROGUE_COACH_BASE_TURNS",
    "ROGUE_SEAL_POINT_COUNT",
    "ULTIMATE_CHAIN_EXTRA_TURN_CHANCE",
    "ULTIMATE_JOSEKI_TARGET_COUNT",
)


def sync_live_balance_globals(
    *,
    target_globals: MutableMapping[str, Any],
    gameplay_config: Any,
    ws_actions_module: Any,
    ws_action_modules: Iterable[Any] = (),
    ws_action_keys: Iterable[str] = DEFAULT_WS_ACTION_BALANCE_KEYS,
) -> None:
    for key in gameplay_config.BALANCE_DEFAULTS:
        if key in target_globals:
            target_globals[key] = getattr(gameplay_config, key)

    for module in (ws_actions_module, *ws_action_modules):
        for key in ws_action_keys:
            if hasattr(module, key):
                setattr(module, key, getattr(gameplay_config, key))
