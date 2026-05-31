from __future__ import annotations

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
        },
        ROGUE_COACH_BASE_TURNS=12,
        ROGUE_SEAL_POINT_COUNT=6,
        ULTIMATE_JOSEKI_TARGET_COUNT=9,
        EXTRA_WS_BALANCE=99,
    )
    ws_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ULTIMATE_JOSEKI_TARGET_COUNT=7,
        EXTRA_WS_BALANCE=1,
    )
    ws_rogue_actions = SimpleNamespace(
        ROGUE_COACH_BASE_TURNS=30,
        ROGUE_SEAL_POINT_COUNT=4,
    )

    sync_live_balance_globals(
        target_globals=target_globals,
        gameplay_config=config,
        ws_actions_module=ws_actions,
        ws_action_modules=(ws_rogue_actions,),
    )

    assert target_globals == {
        "ROGUE_COACH_BASE_TURNS": 12,
        "UNCHANGED": "keep",
    }
    assert not hasattr(ws_actions, "ROGUE_SEAL_POINT_COUNT")
    assert ws_actions.ROGUE_COACH_BASE_TURNS == 12
    assert ws_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 9
    assert ws_actions.EXTRA_WS_BALANCE == 1
    assert ws_rogue_actions.ROGUE_COACH_BASE_TURNS == 12
    assert ws_rogue_actions.ROGUE_SEAL_POINT_COUNT == 6


def smoke_server_balance_sync_wrapper_resolves_runtime_modules_late() -> None:
    config = SimpleNamespace(
        BALANCE_DEFAULTS={
            "ROGUE_COACH_BASE_TURNS": 30,
            "ROGUE_SEAL_POINT_COUNT": 4,
            "ULTIMATE_JOSEKI_TARGET_COUNT": 7,
        },
        ROGUE_COACH_BASE_TURNS=3,
        ROGUE_SEAL_POINT_COUNT=2,
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
    originals = {
        "gameplay_config": s.gameplay_config,
        "ws_actions_module": s.ws_actions_module,
        "ws_rogue_actions_module": s.ws_rogue_actions_module,
        "ROGUE_COACH_BASE_TURNS": s.ROGUE_COACH_BASE_TURNS,
        "ROGUE_SEAL_POINT_COUNT": s.ROGUE_SEAL_POINT_COUNT,
    }
    try:
        s.gameplay_config = config
        s.ws_actions_module = ws_actions
        s.ws_rogue_actions_module = ws_rogue_actions
        s.ROGUE_COACH_BASE_TURNS = 30
        s.ROGUE_SEAL_POINT_COUNT = 4

        s._sync_balance_globals()

        assert s.ROGUE_COACH_BASE_TURNS == 3
        assert s.ROGUE_SEAL_POINT_COUNT == 2
        assert not hasattr(s, "ULTIMATE_JOSEKI_TARGET_COUNT")
        assert ws_actions.ROGUE_COACH_BASE_TURNS == 3
        assert ws_actions.ROGUE_SEAL_POINT_COUNT == 2
        assert ws_actions.ULTIMATE_JOSEKI_TARGET_COUNT == 5
        assert ws_rogue_actions.ROGUE_COACH_BASE_TURNS == 3
        assert ws_rogue_actions.ROGUE_SEAL_POINT_COUNT == 2
    finally:
        for name, value in originals.items():
            setattr(s, name, value)


def main() -> None:
    smoke_balance_sync_updates_existing_server_globals_and_ws_keys()
    smoke_server_balance_sync_wrapper_resolves_runtime_modules_late()
    print("balance sync smoke test: OK")


if __name__ == "__main__":
    main()
