from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.responses import JSONResponse

from app.runtime.request_json import read_json_body


JsonReader = Callable[[Any], Awaitable[Any]]
PayloadProvider = Callable[[], dict[str, Any]]
ResetFn = Callable[[], dict[str, Any]]
SaveBalanceFn = Callable[[dict[str, Any]], dict[str, Any]]


def result_or_bad_request(result: dict[str, Any]) -> dict[str, Any] | JSONResponse:
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result


def card_config_payload(card_config_service: Any) -> dict[str, Any]:
    return card_config_service.get_payload()


def card_config_schema(card_config_service: Any) -> dict[str, Any]:
    return card_config_service.get_schema()


async def save_card_config_request(
    request: Any,
    *,
    card_config_service: Any,
    read_json_body_fn: JsonReader = read_json_body,
) -> dict[str, Any] | JSONResponse:
    json_body = await read_json_body_fn(request)
    if not json_body.ok:
        return json_body.error_response
    body = json_body.body
    config = body.get("config") if isinstance(body, dict) else None
    return result_or_bad_request(card_config_service.save_payload(config))


def reset_card_config_request(card_config_service: Any) -> dict[str, Any] | JSONResponse:
    return result_or_bad_request(card_config_service.reset_payload())


def balance_payload(get_balance_editor_payload: PayloadProvider) -> dict[str, Any]:
    return get_balance_editor_payload()


async def save_balance_request(
    request: Any,
    *,
    save_balance_overrides: SaveBalanceFn,
    read_json_body_fn: JsonReader = read_json_body,
) -> dict[str, Any] | JSONResponse:
    json_body = await read_json_body_fn(request)
    if not json_body.ok:
        return json_body.error_response
    body = json_body.body
    values = body.get("values", {}) if isinstance(body, dict) else {}
    return result_or_bad_request(save_balance_overrides(values))


def reset_balance_request(reset_balance_overrides: ResetFn) -> dict[str, Any]:
    return reset_balance_overrides()
