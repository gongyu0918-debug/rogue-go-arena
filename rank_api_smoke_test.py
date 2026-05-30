from __future__ import annotations

import asyncio

import server as s
from app.runtime.rank_api import build_rank_options


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


async def smoke_server_rank_wrapper_resolves_runtime_labels_late() -> None:
    original_labels = s.RANK_LABELS
    try:
        s.RANK_LABELS = {
            "test-low": "Test Low",
            "test-high": "Test High",
        }
        payload = await s.get_ranks()
    finally:
        s.RANK_LABELS = original_labels

    assert payload == [
        {"id": "test-low", "label": "Test Low"},
        {"id": "test-high", "label": "Test High"},
    ]


async def main() -> None:
    smoke_rank_options_preserve_mapping_order_and_shape()
    await smoke_server_rank_wrapper_resolves_runtime_labels_late()
    print("rank api smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
