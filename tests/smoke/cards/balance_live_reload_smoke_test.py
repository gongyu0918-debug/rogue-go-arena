from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.config import gameplay as gameplay_config
from app.domain.game_state import GoGame
from app.gameplay import card_selection
from app.gameplay.rogue_card_flow import RogueCardActivationFlowDeps, activate_rogue_card_event


def _apply_live(values: dict) -> None:
    errors = gameplay_config.apply_balance_values(values)
    assert not errors, errors
    s._sync_balance_globals()


def _restore(keys: list[str]) -> None:
    _apply_live({key: gameplay_config.BALANCE_DEFAULTS[key] for key in keys})


def smoke_seal_count_edit_reaches_card_selected_payload() -> None:
    sent: list[dict] = []

    async def send(payload: dict) -> None:
        sent.append(payload)

    async def sync_komi(_game) -> None:
        return None

    deps = RogueCardActivationFlowDeps(
        get_card=lambda card_id: {"name": card_id, "icon": "*"},
        apply_activation=lambda *args, **kwargs: SimpleNamespace(messages=[], sync_komi=False),
        coord_to_gtp=lambda *args: "",
        choose_corner=lambda: 0,
        make_rng=lambda: None,
        get_blackhole_points=lambda *args: [],
        get_golden_corner_points=lambda *args: [],
        pick_joseki_targets=lambda *args: [],
        random_hidden_center=lambda *args: None,
        diamond_points=lambda *args: [],
        sync_engine_komi=sync_komi,
    )
    try:
        _apply_live({"ROGUE_SEAL_POINT_COUNT": 6})
        asyncio.run(activate_rogue_card_event(GoGame(), send, "seal", deps))
    finally:
        _restore(["ROGUE_SEAL_POINT_COUNT"])
    selected = [msg for msg in sent if msg.get("type") == "rogue_card_selected"][-1]
    assert selected["rogue_seal_required"] == 6, selected["rogue_seal_required"]


def smoke_challenge_stage_weight_edit_reaches_card_selection() -> None:
    captured: dict = {}
    original_sample = card_selection._weighted_unique_sample

    def capture(pool, n, weights, rng):
        captured.update(weights)
        return original_sample(pool, n, weights, rng)

    card_selection._weighted_unique_sample = capture
    try:
        _apply_live({"CHALLENGE_STAGE_BIAS_WEIGHT": 7.5})
        card_selection.pick_challenge_beta_choices(["dice"])
    finally:
        card_selection._weighted_unique_sample = original_sample
        _restore(["CHALLENGE_STAGE_BIAS_WEIGHT"])
    # "nerf" shares the "restriction" category with the one selected card.
    assert captured["nerf"] == 1.0 + 7.5, captured["nerf"]


def main() -> None:
    smoke_seal_count_edit_reaches_card_selected_payload()
    smoke_challenge_stage_weight_edit_reaches_card_selection()
    print("balance live reload smoke ok")


if __name__ == "__main__":
    main()
