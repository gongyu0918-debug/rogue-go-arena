from __future__ import annotations


def is_engine_error_response(value: str | None) -> bool:
    return bool(value and value.lstrip().startswith("?"))


def engine_error_message(value: str) -> str:
    return f"AI 引擎落子失败：{value}"
