from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import json
from types import SimpleNamespace

from fastapi import HTTPException
import server as s
from app.runtime.config_api import (
    balance_payload,
    card_config_payload,
    card_config_schema,
    reset_balance_request,
    reset_card_config_request,
    save_balance_request,
    save_card_config_request,
)
from app.runtime.config_routes import ConfigRoutesBinding, build_config_router


class FakeRequest:
    def __init__(self, body=None, *, raises: bool = False, host: str = "127.0.0.1") -> None:
        self.body = body
        self.raises = raises
        self.client = SimpleNamespace(host=host)

    async def json(self):
        if self.raises:
            raise ValueError("bad json")
        return self.body


class FakeCardConfigService:
    def __init__(self) -> None:
        self.calls = []
        self.save_result = {"ok": True, "saved": True}
        self.reset_result = {"ok": True, "reset": True}

    def get_payload(self):
        self.calls.append(("get_payload",))
        return {"payload": True}

    def get_schema(self):
        self.calls.append(("get_schema",))
        return {"schema": True}

    def save_payload(self, config):
        self.calls.append(("save", config))
        return dict(self.save_result)

    def reset_payload(self):
        self.calls.append(("reset",))
        return dict(self.reset_result)


def response_payload(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def endpoint_for(routes, path: str, method: str):
    for route in routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


async def smoke_card_config_api_helpers_preserve_payloads_and_errors() -> None:
    service = FakeCardConfigService()

    assert card_config_payload(service) == {"payload": True}
    assert card_config_schema(service) == {"schema": True}

    saved = await save_card_config_request(
        FakeRequest({"config": {"cards": {}}}),
        card_config_service=service,
    )
    assert saved == {"ok": True, "saved": True}
    assert service.calls[-1] == ("save", {"cards": {}})

    saved_from_list = await save_card_config_request(
        FakeRequest(["not", "a", "dict"]),
        card_config_service=service,
    )
    assert saved_from_list == {"ok": True, "saved": True}
    assert service.calls[-1] == ("save", None)

    invalid_json = await save_card_config_request(FakeRequest(raises=True), card_config_service=service)
    assert invalid_json.status_code == 400
    assert response_payload(invalid_json) == {
        "ok": False,
        "errors": ["request body must be JSON"],
    }

    service.save_result = {"ok": False, "errors": ["bad config"]}
    failed_save = await save_card_config_request(
        FakeRequest({"config": {"bad": True}}),
        card_config_service=service,
    )
    assert failed_save.status_code == 400
    assert response_payload(failed_save) == {"ok": False, "errors": ["bad config"]}

    service.reset_result = {"ok": False, "errors": ["reset failed"]}
    failed_reset = reset_card_config_request(service)
    assert failed_reset.status_code == 400
    assert response_payload(failed_reset) == {"ok": False, "errors": ["reset failed"]}


async def smoke_balance_api_helpers_preserve_values_and_errors() -> None:
    save_calls = []
    reset_calls = []

    def get_payload():
        return {"balance": True}

    def save(values):
        save_calls.append(values)
        if values.get("bad"):
            return {"ok": False, "errors": ["bad value"]}
        return {"ok": True, "values": values}

    def reset():
        reset_calls.append("reset")
        return {"ok": True, "reset": True}

    assert balance_payload(get_payload) == {"balance": True}

    saved = await save_balance_request(
        FakeRequest({"values": {"ROGUE_DICE_PASS_CHANCE": 1.0}}),
        save_balance_overrides=save,
    )
    assert saved == {"ok": True, "values": {"ROGUE_DICE_PASS_CHANCE": 1.0}}
    assert save_calls[-1] == {"ROGUE_DICE_PASS_CHANCE": 1.0}

    saved_from_list = await save_balance_request(
        FakeRequest(["not", "a", "dict"]),
        save_balance_overrides=save,
    )
    assert saved_from_list == {"ok": True, "values": {}}
    assert save_calls[-1] == {}

    invalid_json = await save_balance_request(FakeRequest(raises=True), save_balance_overrides=save)
    assert invalid_json.status_code == 400
    assert response_payload(invalid_json) == {
        "ok": False,
        "errors": ["request body must be JSON"],
    }

    failed_save = await save_balance_request(FakeRequest({"values": {"bad": True}}), save_balance_overrides=save)
    assert failed_save.status_code == 400
    assert response_payload(failed_save) == {"ok": False, "errors": ["bad value"]}

    assert reset_balance_request(reset) == {"ok": True, "reset": True}
    assert reset_calls == ["reset"]


async def smoke_config_router_preserves_paths_and_resolves_deps_late() -> None:
    service = FakeCardConfigService()
    balance_calls = []

    def get_balance_payload():
        balance_calls.append("get")
        return {"balance": "server"}

    def save_balance(values):
        balance_calls.append(("save", values))
        return {"ok": True, "values": values}

    def reset_balance():
        balance_calls.append("reset")
        return {"ok": True, "reset": "server"}

    current = {"service": service, "get_payload": get_balance_payload}

    def binding_provider():
        return ConfigRoutesBinding(
            card_config_service=current["service"],
            get_balance_editor_payload=current["get_payload"],
            save_balance_overrides=save_balance,
            reset_balance_overrides=reset_balance,
        )

    router = build_config_router(binding_provider)

    assert await endpoint_for(router.routes, "/api/card-config", "GET")() == {"payload": True}
    assert await endpoint_for(router.routes, "/api/card-config/schema", "GET")() == {"schema": True}
    assert await endpoint_for(router.routes, "/api/card-config", "POST")(
        FakeRequest({"config": {"cards": {}}})
    ) == {"ok": True, "saved": True}
    assert await endpoint_for(router.routes, "/api/card-config/reset", "POST")(FakeRequest()) == {
        "ok": True,
        "reset": True,
    }
    assert await endpoint_for(router.routes, "/api/balance", "GET")() == {"balance": "server"}
    assert await endpoint_for(router.routes, "/api/balance", "POST")(
        FakeRequest({"values": {"x": 2}})
    ) == {"ok": True, "values": {"x": 2}}
    assert await endpoint_for(router.routes, "/api/balance/reset", "POST")(FakeRequest()) == {
        "ok": True,
        "reset": "server",
    }
    try:
        await endpoint_for(router.routes, "/api/balance", "POST")(
            FakeRequest({"values": {"x": 3}}, host="192.168.1.30")
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("non-loopback config writes must be rejected")

    assert service.calls == [
        ("get_payload",),
        ("get_schema",),
        ("save", {"cards": {}}),
        ("reset",),
    ]
    assert balance_calls == ["get", ("save", {"x": 2}), "reset"]


async def smoke_server_config_router_resolves_runtime_deps_late() -> None:
    service = FakeCardConfigService()
    balance_calls = []

    def get_balance_payload():
        balance_calls.append("get")
        return {"balance": "patched"}

    def save_balance(values):
        balance_calls.append(("save", values))
        return {"ok": True, "values": values}

    def reset_balance():
        balance_calls.append("reset")
        return {"ok": True, "reset": "patched"}

    originals = {
        "card_config_service": s.card_config_service,
        "get_balance_editor_payload": s.get_balance_editor_payload,
        "save_balance_overrides": s.save_balance_overrides,
        "reset_balance_overrides": s.reset_balance_overrides,
    }
    try:
        s.card_config_service = service
        s.get_balance_editor_payload = get_balance_payload
        s.save_balance_overrides = save_balance
        s.reset_balance_overrides = reset_balance

        assert s._config_routes_binding().card_config_service is service
        assert await endpoint_for(s.app.routes, "/api/card-config", "GET")() == {"payload": True}
        assert await endpoint_for(s.app.routes, "/api/card-config/schema", "GET")() == {"schema": True}
        assert await endpoint_for(s.app.routes, "/api/card-config", "POST")(
            FakeRequest({"config": {"cards": {}}})
        ) == {"ok": True, "saved": True}
        assert await endpoint_for(s.app.routes, "/api/card-config/reset", "POST")(FakeRequest()) == {
            "ok": True,
            "reset": True,
        }
        assert await endpoint_for(s.app.routes, "/api/balance", "GET")() == {"balance": "patched"}
        assert await endpoint_for(s.app.routes, "/api/balance", "POST")(
            FakeRequest({"values": {"y": 3}})
        ) == {"ok": True, "values": {"y": 3}}
        assert await endpoint_for(s.app.routes, "/api/balance/reset", "POST")(FakeRequest()) == {
            "ok": True,
            "reset": "patched",
        }
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert service.calls == [
        ("get_payload",),
        ("get_schema",),
        ("save", {"cards": {}}),
        ("reset",),
    ]
    assert balance_calls == ["get", ("save", {"y": 3}), "reset"]


async def main() -> None:
    await smoke_card_config_api_helpers_preserve_payloads_and_errors()
    await smoke_balance_api_helpers_preserve_values_and_errors()
    await smoke_config_router_preserves_paths_and_resolves_deps_late()
    await smoke_server_config_router_resolves_runtime_deps_late()
    print("config api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
