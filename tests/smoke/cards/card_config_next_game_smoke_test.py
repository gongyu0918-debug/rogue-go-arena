from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import copy
import tempfile
from pathlib import Path

import server as s
from app.config import gameplay as gameplay_config
from app.data import cards as card_data
from app.runtime.ws_new_game_actions import handle_new_game

KEY = "ROGUE_DICE_PASS_CHANCE"


def live_state() -> tuple[float, str, set[str]]:
    return (
        getattr(gameplay_config, KEY),
        card_data.ROGUE_CARDS["dice"]["name"],
        set(card_data.ROGUE_DISABLED_CARDS),
    )


def edited_config() -> dict:
    config = copy.deepcopy(s.card_config_service.get_payload()["config"])
    config["tuning"][KEY]["value"] = 0.5
    config["cards"]["rogue"]["dice"]["name"]["zh-CN"] = "下局生效的骰子"
    config["offers"]["rogue_disabled"] = []
    return config


def smoke_saved_edits_wait_for_the_next_game() -> None:
    service = s.card_config_service
    original_user_path = card_data.CARD_CONFIG_USER_PATH
    with tempfile.TemporaryDirectory() as tmp:
        card_data.CARD_CONFIG_USER_PATH = Path(tmp) / "cards.json"
        try:
            assert service.reload_live_config() == []
            before = live_state()

            result = service.save_payload(edited_config())
            assert result["ok"], result.get("errors")
            assert live_state() == before, "a game in progress must keep its rules"

            payload = service.get_payload()  # opening the editor must not apply either
            assert live_state() == before
            assert payload["pending_next_game"] is True
            assert payload["config"]["tuning"][KEY]["value"] == 0.5
            assert payload["source"] == "user"

            # handle_new_game reloads first, so the next game uses the edits.
            assert s.reload_live_card_config() == []
            assert live_state() == (0.5, "下局生效的骰子", set())
            assert service.get_payload()["pending_next_game"] is False

            # Restoring defaults is deferred the same way.
            assert service.reset_payload()["ok"]
            assert live_state() == (0.5, "下局生效的骰子", set())
            assert service.get_payload()["pending_next_game"] is True
            assert s.reload_live_card_config() == []
            assert live_state() == before
        finally:
            card_data.CARD_CONFIG_USER_PATH = original_user_path
            assert service.reload_live_config() == []


def smoke_balance_lab_also_waits_and_keeps_pending_edits() -> None:
    service = s.card_config_service
    original_user_path = card_data.CARD_CONFIG_USER_PATH
    with tempfile.TemporaryDirectory() as tmp:
        card_data.CARD_CONFIG_USER_PATH = Path(tmp) / "cards.json"
        try:
            assert service.reload_live_config() == []
            before = live_state()
            assert service.save_payload(edited_config())["ok"]
            result = gameplay_config.save_balance_overrides({KEY: 0.25})
            assert result["ok"], result.get("errors")
            assert live_state() == before
            saved = service.get_payload()["config"]
            assert saved["tuning"][KEY]["value"] == 0.25
            assert saved["cards"]["rogue"]["dice"]["name"]["zh-CN"] == "下局生效的骰子", "pending card edits kept"
            assert s.reload_live_card_config() == []
            assert live_state() == (0.25, "下局生效的骰子", set())
        finally:
            card_data.CARD_CONFIG_USER_PATH = original_user_path
            assert service.reload_live_config() == []


def smoke_invalid_save_changes_nothing() -> None:
    service = s.card_config_service
    before = live_state()
    bad = edited_config()
    bad["tuning"][KEY]["value"] = 5  # above the allowed maximum of 1
    result = service.save_payload(bad)
    assert result["ok"] is False and result["errors"]
    assert live_state() == before


class NewGameProbe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def reload_live_card_config(self) -> list[str]:
        self.calls.append("reload")
        return ["stop here"]

    async def send_error(self, message: str) -> None:
        self.calls.append("error")


def smoke_new_game_reloads_config_first() -> None:
    probe = NewGameProbe()
    asyncio.run(handle_new_game(probe, {"size": 9}))
    assert probe.calls == ["reload", "error"]


def main() -> None:
    smoke_saved_edits_wait_for_the_next_game()
    smoke_balance_lab_also_waits_and_keeps_pending_edits()
    smoke_invalid_save_changes_nothing()
    smoke_new_game_reloads_config_first()
    print("card config next-game smoke ok")


if __name__ == "__main__":
    main()
