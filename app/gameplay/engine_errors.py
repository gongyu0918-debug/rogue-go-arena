from __future__ import annotations

from app.domain.event_text import EventText, event_text


def is_engine_error_response(value: str | None) -> bool:
    return bool(value and value.lstrip().startswith("?"))


def engine_error_message(value: str) -> str:
    """Keep the key of a keyed engine reason (e.g. an occupied point)."""
    if isinstance(value, EventText):
        return event_text(value.key, f"AI 引擎落子失败：{value}", **value.params)
    return event_text("error.engine.move_failed", f"AI 引擎落子失败：{value}", detail=str(value).strip())
