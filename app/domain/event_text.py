"""Player-visible messages with a language-neutral key.

Server messages used to be Chinese strings that the client translated with
regex tables. An ``EventText`` is still that Chinese string (so existing code,
logs and older clients keep working), but it also carries a stable ``key`` and
JSON-safe ``params``. The websocket layer sends both side by side; the client
renders ``key`` with its locale pack and falls back to the old text.

Param conventions (the client formats these by type, see static/js/event_text.js):
card ids, colors as "B"/"W", corners as "tl"/"tr"/"bl"/"br", rank ids such as
"a3d", board points as GTP strings, lists as JSON lists, numbers as numbers.
"""
from __future__ import annotations

from typing import Any, Mapping

CORNER_IDS = ("tl", "tr", "bl", "br")


class EventText(str):
    key: str
    params: dict[str, Any]

    def __new__(cls, key: str, text: str, params: Mapping[str, Any] | None = None) -> "EventText":
        obj = super().__new__(cls, text)
        obj.key = key
        obj.params = dict(params or {})
        return obj

    def __reduce__(self):
        return (EventText, (self.key, str(self), self.params))

    def __deepcopy__(self, memo):
        return EventText(self.key, str(self), {k: _copy(v) for k, v in self.params.items()})


def _copy(value: Any) -> Any:
    if isinstance(value, list):
        return [_copy(v) for v in value]
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    return value


def event_text(key: str, zh: str, **params: Any) -> EventText:
    """A message: ``key`` + ``params`` for the client, ``zh`` as the legacy text."""
    return EventText(key, zh, params)


def with_event_keys(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add ``key``/``params`` next to an EventText ``msg`` or ``message`` field."""
    if "key" in payload:
        return payload
    for field in ("msg", "message"):
        value = payload.get(field)
        if isinstance(value, EventText):
            return {**payload, "key": value.key, "params": _copy(value.params)}
    return payload
