from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json
from types import SimpleNamespace

import server as s
from app.runtime.request_json import read_json_body


class FakeRequest:
    def __init__(self, body=None, *, raises: bool = False, host: str = "127.0.0.1") -> None:
        self.body = body
        self.raises = raises
        self.client = SimpleNamespace(host=host)

    async def json(self):
        if self.raises:
            raise ValueError("bad json")
        return self.body


def response_payload(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def endpoint_for(path: str, method: str):
    for route in s.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


async def smoke_read_json_body_preserves_body_and_invalid_json_error() -> None:
    ok = await read_json_body(FakeRequest({"values": {"x": 1}}))
    assert ok.ok is True
    assert ok.body == {"values": {"x": 1}}
    assert ok.error_response is None

    failed = await read_json_body(FakeRequest(raises=True))
    assert failed.ok is False
    assert failed.error_response.status_code == 400
    assert response_payload(failed.error_response) == {
        "ok": False,
        "errors": ["request body must be JSON"],
    }


async def smoke_card_config_route_uses_shared_json_reader() -> None:
    calls = []

    class FakeCardConfigService:
        def save_payload(self, config):
            calls.append(config)
            return {"ok": True, "saved": config}

    original_service = s.card_config_service
    try:
        s.card_config_service = FakeCardConfigService()
        save_card_config = endpoint_for("/api/card-config", "POST")

        saved = await save_card_config(FakeRequest({"config": {"cards": {}}}))
        assert saved == {"ok": True, "saved": {"cards": {}}}
        assert calls == [{"cards": {}}]

        saved_from_list = await save_card_config(FakeRequest(["not", "an", "object"]))
        assert saved_from_list == {"ok": True, "saved": None}
        assert calls[-1] is None

        saved_from_null = await save_card_config(FakeRequest(None))
        assert saved_from_null == {"ok": True, "saved": None}
        assert calls[-1] is None

        invalid = await save_card_config(FakeRequest(raises=True))
        assert invalid.status_code == 400
        assert response_payload(invalid) == {
            "ok": False,
            "errors": ["request body must be JSON"],
        }
    finally:
        s.card_config_service = original_service


async def smoke_balance_route_preserves_non_object_body_behavior() -> None:
    calls = []

    def fake_save_balance(values):
        calls.append(values)
        return {"ok": True, "values": values}

    original_save = s.save_balance_overrides
    try:
        s.save_balance_overrides = fake_save_balance
        save_balance = endpoint_for("/api/balance", "POST")

        saved = await save_balance(FakeRequest({"values": {"ROGUE_DICE_PASS_CHANCE": 1.0}}))
        assert saved == {"ok": True, "values": {"ROGUE_DICE_PASS_CHANCE": 1.0}}
        assert calls[-1] == {"ROGUE_DICE_PASS_CHANCE": 1.0}

        saved_from_list = await save_balance(FakeRequest(["not", "an", "object"]))
        assert saved_from_list == {"ok": True, "values": {}}
        assert calls[-1] == {}

        invalid = await save_balance(FakeRequest(raises=True))
        assert invalid.status_code == 400
        assert response_payload(invalid) == {
            "ok": False,
            "errors": ["request body must be JSON"],
        }
    finally:
        s.save_balance_overrides = original_save


async def main() -> None:
    await smoke_read_json_body_preserves_body_and_invalid_json_error()
    await smoke_card_config_route_uses_shared_json_reader()
    await smoke_balance_route_preserves_non_object_body_behavior()
    print("request json smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
