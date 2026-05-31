from __future__ import annotations

import asyncio

import server as s
from app.runtime.control_routes import RuntimeControlRoutesBinding, build_runtime_control_router
from app.runtime.rank_api import build_rank_options


async def noop_executor(func, *args):
    return func(*args)


def endpoint_for(routes, path: str, method: str = "GET"):
    for route in routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def smoke_rank_options_preserve_mapping_order_and_shape() -> None:
    labels = {
        "18k": "18 level",
        "1k": "1 level",
        "a1d": "amateur 1 dan",
    }

    assert build_rank_options(labels) == [
        {"id": "18k", "label": "18 level"},
        {"id": "1k", "label": "1 level"},
        {"id": "a1d", "label": "amateur 1 dan"},
    ]


async def smoke_rank_router_resolves_labels_late() -> None:
    current = {
        "labels": {
            "test-low": "Test Low",
            "test-high": "Test High",
        }
    }

    def binding_provider():
        return RuntimeControlRoutesBinding(
            rank_labels=current["labels"],
            engine_runtime=object(),
            run_in_executor=noop_executor,
        )

    router = build_runtime_control_router(binding_provider)
    payload = await endpoint_for(router.routes, "/ranks")()
    assert payload == [
        {"id": "test-low", "label": "Test Low"},
        {"id": "test-high", "label": "Test High"},
    ]

    current["labels"] = {"patched": "Patched"}
    assert await endpoint_for(router.routes, "/ranks")() == [
        {"id": "patched", "label": "Patched"},
    ]


async def smoke_server_rank_route_resolves_runtime_labels_late() -> None:
    original_labels = s.RANK_LABELS
    try:
        s.RANK_LABELS = {
            "test-low": "Test Low",
            "test-high": "Test High",
        }
        assert s._runtime_control_routes_binding().rank_labels is s.RANK_LABELS
        payload = await endpoint_for(s.app.routes, "/ranks")()
    finally:
        s.RANK_LABELS = original_labels

    assert payload == [
        {"id": "test-low", "label": "Test Low"},
        {"id": "test-high", "label": "Test High"},
    ]


async def main() -> None:
    smoke_rank_options_preserve_mapping_order_and_shape()
    await smoke_rank_router_resolves_labels_late()
    await smoke_server_rank_route_resolves_runtime_labels_late()
    print("rank api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
