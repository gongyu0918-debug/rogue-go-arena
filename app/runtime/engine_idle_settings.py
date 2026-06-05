from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
ENV_IDLE_TIMEOUT_SECONDS = "ROGUE_GO_ENGINE_IDLE_TIMEOUT_SECONDS"
SETTINGS_KEY = "engine_idle_timeout_seconds"


def normalize_idle_timeout_seconds(value: Any) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return DEFAULT_IDLE_TIMEOUT_SECONDS
    if seconds <= 0:
        return 0.0
    return min(24 * 60 * 60, max(1.0, seconds))


def load_idle_timeout_seconds(settings_path: Path) -> float:
    env_value = os.environ.get(ENV_IDLE_TIMEOUT_SECONDS)
    if env_value is not None:
        return normalize_idle_timeout_seconds(env_value)
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_IDLE_TIMEOUT_SECONDS
    return normalize_idle_timeout_seconds(payload.get(SETTINGS_KEY))


def save_idle_timeout_seconds(settings_path: Path, value: Any) -> float:
    seconds = normalize_idle_timeout_seconds(value)
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    payload[SETTINGS_KEY] = seconds
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return seconds
