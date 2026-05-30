from __future__ import annotations

from collections.abc import Mapping


def build_rank_options(rank_labels: Mapping[str, str]) -> list[dict[str, str]]:
    return [{"id": rank_id, "label": label} for rank_id, label in rank_labels.items()]
