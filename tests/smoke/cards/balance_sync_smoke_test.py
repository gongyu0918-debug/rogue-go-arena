from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

from types import SimpleNamespace

import server as s
from app.services.balance_sync import sync_live_balance_globals


def smoke_balance_sync_updates_existing_server_globals_and_ws_keys() -> None:
    target_globals = {
        "ROGUE_COACH_BASE_TURNS": 30,
        "UNCHANGED": "keep",
    }
    config = SimpleNamespace(
        BALANCE_DEFAULTS={
            "ROGUE_COACH_BASE_TURNS": 30,
            "ROGUE_SEAL_POINT_COUNT": 4,
            "ROGUE_QUICKTHINK_SECOND_SECONDS": 1,
            "ROGUE_QUICKTHINK_FIRST_SECONDS": 2,
            "ULTIMATE_CHAIN_EXTRA_TURN_CHANCE": 0.75,
        },
        ROGUE_COACH_BASE_TURNS=12,
        ROGUE_SEAL_POINT_COUNT=6,
        ROGUE_QUICKTHINK_SECOND_SECONDS=9,
        ROGUE_QUICKTHINK_FIRST_SECONDS=4,
        ULTIMATE_CHAIN_EXTRA_TURN_CHANCE=0.25,
        ULTIMATE_JOSEKI_TARGET_COUNT=9,
        EXTRA_WS_BALANCE=99,
    )
    ws_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ULTIMATE_JOSEKI_TARGET_COUNT=7,
        ROGUE_QUICKTHINK_SECOND_SECONDS=1,
        EXTRA_WS_BALANCE=1,
    )
    ws_rogue_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ROGUE_SEAL_POINT_COUNT=4,
    )
    ws_ultimate_actions = SimpleNamespace(
        ULTIMATE_CHAIN_EXTRA_TURN_CHANCE=0.75,
        ULTIMATE_JOSEKI_TARGET_COUNT=7,
    )
    game_state = SimpleNamespace(
        ROGUE_QUICKTHINK_FIRST_SECONDS=2,
        ULTIMATE_CHAIN_EXTRA_TURN_CHANCE=0.75,
    )

    sync_live_balance_globals(
        target_globals=target_globals,
        gameplay_config=config,
        ws_actions_module=ws_actions,
        ws_action_modules=(ws_rogue_actions, ws_ultimate_actions),
        state_modules=(game_state,),
    )

    assert target_globals == {
        "ROGUE_COACH_BASE_TURNS": 12,
        "UNCHANGED": "keep",
    }
    assert not hasattr(ws_actions, "ROGUE_SEAL_POINT_COUNT")
    assert ws_actions.ROGUE_COACH_BASE_TURNS == 12
    assert ws_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 9
    assert ws_actions.ROGUE_QUICKTHINK_SECOND_SECONDS == 9
    assert ws_actions.EXTRA_WS_BALANCE == 1
    assert ws_rogue_actions.ROGUE_COACH_BASE_TURNS == 12
    assert ws_rogue_actions.ROGUE_SEAL_POINT_COUNT == 6
    assert ws_ultimate_actions.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE == 0.25
    assert ws_ultimate_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 9
    assert game_state.ROGUE_QUICKTHINK_FIRST_SECONDS == 4
    assert game_state.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE == 0.25


def smoke_server_balance_sync_wrapper_resolves_runtime_modules_late() -> None:
    config = SimpleNamespace(
        BALANCE_DEFAULTS={
            "ROGUE_COACH_BASE_TURNS": 30,
            "ROGUE_SEAL_POINT_COUNT": 4,
            "ROGUE_QUICKTHINK_SECOND_SECONDS": 1,
            "ULTIMATE_CHAIN_EXTRA_TURN_CHANCE": 0.8,
            "ULTIMATE_JOSEKI_TARGET_COUNT": 7,
        },
        ROGUE_COACH_BASE_TURNS=3,
        ROGUE_SEAL_POINT_COUNT=2,
        ROGUE_QUICKTHINK_SECOND_SECONDS=8,
        ULTIMATE_CHAIN_EXTRA_TURN_CHANCE=0.2,
        ULTIMATE_JOSEKI_TARGET_COUNT=5,
    )
    ws_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ROGUE_SEAL_POINT_COUNT=4,
        ULTIMATE_JOSEKI_TARGET_COUNT=7,
    )
    ws_rogue_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ROGUE_SEAL_POINT_COUNT=4,
    )
    ws_turn_actions = SimpleNamespace(
        ROGUE_HANDICAP_REQUIRED_PASSES=1,
    )
    ws_play_actions = SimpleNamespace(
        ROGUE_QUICKTHINK_SECOND_SECONDS=1,
    )
    ws_ultimate_actions = SimpleNamespace(
        ULTIMATE_CHAIN_EXTRA_TURN_CHANCE=0.8,
        ULTIMATE_JOSEKI_TARGET_COUNT=7,
    )
    originals = {
        "gameplay_config": s.gameplay_config,
        "ws_actions_module": s.ws_actions_module,
        "ws_play_actions_module": s.ws_play_actions_module,
        "ws_rogue_actions_module": s.ws_rogue_actions_module,
        "ws_turn_actions_module": s.ws_turn_actions_module,
        "ws_ultimate_actions_module": s.ws_ultimate_actions_module,
        "ROGUE_COACH_BASE_TURNS": s.ROGUE_COACH_BASE_TURNS,
        "ROGUE_SEAL_POINT_COUNT": s.ROGUE_SEAL_POINT_COUNT,
        "ULTIMATE_CHAIN_EXTRA_TURN_CHANCE": s.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
    }
    try:
        s.gameplay_config = config
        s.ws_actions_module = ws_actions
        s.ws_play_actions_module = ws_play_actions
        s.ws_rogue_actions_module = ws_rogue_actions
        s.ws_turn_actions_module = ws_turn_actions
        s.ws_ultimate_actions_module = ws_ultimate_actions
        s.ROGUE_COACH_BASE_TURNS = 30
        s.ROGUE_SEAL_POINT_COUNT = 4
        s.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE = 0.8

        s._sync_balance_globals()

        assert s.ROGUE_COACH_BASE_TURNS == 3
        assert s.ROGUE_SEAL_POINT_COUNT == 2
        assert s.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE == 0.2
        assert not hasattr(s, "ULTIMATE_JOSEKI_TARGET_COUNT")
        assert ws_actions.ROGUE_COACH_BASE_TURNS == 3
        assert ws_actions.ROGUE_SEAL_POINT_COUNT == 2
        assert ws_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 5
        assert ws_play_actions.ROGUE_QUICKTHINK_SECOND_SECONDS == 8
        assert ws_rogue_actions.ROGUE_COACH_BASE_TURNS == 3
        assert ws_rogue_actions.ROGUE_SEAL_POINT_COUNT == 2
        assert ws_ultimate_actions.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE == 0.2
        assert ws_ultimate_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 5
    finally:
        for name, value in originals.items():
            setattr(s, name, value)


def main() -> None:
    smoke_balance_sync_updates_existing_server_globals_and_ws_keys()
    smoke_server_balance_sync_wrapper_resolves_runtime_modules_late()
    print("balance sync smoke test: OK")


if __name__ == "__main__":
    main()
