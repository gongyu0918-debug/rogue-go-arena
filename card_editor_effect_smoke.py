from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import websockets
from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = Path(
    os.environ.get(
        "GOAI_ARTIFACT_DIR",
        r"F:\Workspaces\Playground\artifacts\GoAI\card-editor-effect-smoke",
    )
)

TUNING_EDITS = {
    "ROGUE_DICE_PASS_CHANCE": 1.0,
    "ROGUE_SANSAN_TRAP_STONES": 5,
    "ROGUE_SEAL_POINT_COUNT": 2,
    "ROGUE_COACH_BASE_TURNS": 4,
    "ULTIMATE_METEOR_DESTROY_COUNT": 3,
    "ULTIMATE_QUANTUM_PLACE_COUNT": 4,
}

BASE_SMOKE_NAMES = [
    "smoke_activate_rogue_cards",
    "smoke_player_rogue_effects",
    "smoke_joseki_completion",
    "smoke_puppet_flow",
    "smoke_ai_rogue_cards",
    "smoke_slip_card",
    "smoke_new_rogue_cards",
    "smoke_sansan_trap",
    "smoke_seal_fallback",
    "smoke_ultimate_effects",
    "smoke_new_ultimate_cards",
    "smoke_ultimate_turn_flow",
    "smoke_ultimate_ai_effect_sync",
    "smoke_challenge_beta_set_bonuses",
    "smoke_corner_helper_can_trigger_per_corner",
    "smoke_quickthink_flow",
    "smoke_featured_pools",
    "smoke_suboptimal_extended",
    "smoke_fog_mask_refresh",
    "smoke_foolish_wisdom_rogue",
    "smoke_bonus_spawn_safety",
    "smoke_place_stone_does_not_overwrite",
    "smoke_ko_recapture_blocked",
    "smoke_suicide_illegal",
    "smoke_magic_effects_clear_ko",
    "smoke_batch_bonus_persists_after_followup_move",
    "smoke_undo_preserves_bonus_stones",
    "smoke_bonus_turn_does_not_grant_extra_ai_move",
    "smoke_foolish_wisdom_ultimate",
    "smoke_two_player_rogue_shared_cards",
    "smoke_ai_rogue_support",
    "smoke_five_in_row_and_last_stand_cards",
    "smoke_ultimate_joseki_and_wall_updates",
]


def marker(mode: str, card_id: str) -> str:
    return f"E2E-{mode}-{card_id}"


def desc_marker(mode: str, card_id: str) -> str:
    return f"E2E-desc-{mode}-{card_id}"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(base_url: str, path: str, *, timeout: int = 20) -> dict[str, Any]:
    with urllib.request.urlopen(base_url + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(base_url: str, path: str, body: dict[str, Any], *, timeout: int = 60) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base_url + path,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_server(proc: subprocess.Popen[str], base_url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"server exited early: {output}")
        try:
            http_json(base_url, "/api/card-config", timeout=3)
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise TimeoutError(f"server did not become ready: {last_error}")


async def edit_all_cards_with_form(base_url: str, screenshot_path: Path) -> dict[str, Any]:
    payload = http_json(base_url, "/api/card-config")
    config = payload["config"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        await page.goto(base_url + "/card-editor")
        await page.evaluate("localStorage.setItem('card_editor_lang', 'zh')")
        await page.reload()
        await page.wait_for_selector('.card-row[data-id="puppet"]')

        for mode in ("rogue", "ultimate"):
            await page.locator(f'[data-tab="{mode}"]').click()
            for card_id, card in config["cards"][mode].items():
                await page.locator("#searchBox").fill(card_id)
                row = page.locator(f'.card-row[data-id="{card_id}"]')
                await row.wait_for(state="visible", timeout=5000)
                await row.locator('[data-field="name"]').fill(marker(mode, card_id))
                await row.locator('[data-field="desc"]').fill(desc_marker(mode, card_id))
                if mode == "rogue" and "uses" in card:
                    await row.locator('[data-field="uses"]').fill("3")

        await page.locator('[data-tab="tuning"]').click()
        for key, value in TUNING_EDITS.items():
            await page.locator("#searchBox").fill(key)
            row = page.locator(f'.tune-row[data-key="{key}"]')
            await row.wait_for(state="visible", timeout=5000)
            await row.locator("[data-tune-number]").fill(str(value))

        await page.locator("#searchBox").fill("")
        async with page.expect_response(
            lambda response: response.url.endswith("/api/card-config")
            and response.request.method == "POST",
            timeout=15000,
        ) as response_info:
            await page.locator("#saveBtn").click()
        response = await response_info.value
        if not response.ok:
            raise AssertionError(f"editor save failed: HTTP {response.status}")
        await page.wait_for_timeout(500)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(screenshot_path), full_page=True)
        await browser.close()

    saved = http_json(base_url, "/api/card-config")
    for mode in ("rogue", "ultimate"):
        for card_id in config["cards"][mode]:
            card = saved["config"]["cards"][mode][card_id]
            assert card["name"]["zh-CN"] == marker(mode, card_id)
            assert card["desc"]["zh-CN"] == desc_marker(mode, card_id)
    for key, value in TUNING_EDITS.items():
        assert saved["config"]["tuning"][key]["value"] == value
    return saved["config"]


async def recv_until(ws, predicate, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for websocket message")
        msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        if predicate(msg):
            return msg


async def verify_every_rogue_offer(base_url: str, ws_base_url: str, config: dict[str, Any]) -> list[str]:
    checked: list[str] = []
    for card_id, card in config["cards"]["rogue"].items():
        fixture = copy.deepcopy(config)
        fixture["pools"]["two_player_rogue"] = [card_id]
        fixture["pools"]["rogue_featured"] = [card_id]
        result = post_json(base_url, "/api/card-config", {"config": fixture})
        assert result["ok"] is True

        game_id = "editor-e2e-" + card_id + "-" + uuid.uuid4().hex[:6]
        async with websockets.connect(f"{ws_base_url}/ws/{game_id}", max_size=10_000_000) as ws:
            await ws.send(
                json.dumps(
                    {
                        "action": "new_game",
                        "size": 9,
                        "komi": 7.5,
                        "handicap": 0,
                        "player_color": "B",
                        "level": "5k",
                        "two_player": True,
                        "ai_observer": False,
                        "rogue": True,
                        "ai_rogue": False,
                        "ultimate": False,
                        "challenge_beta": False,
                    }
                )
            )
            await recv_until(ws, lambda msg: msg.get("type") == "game_start")
            offer = await recv_until(ws, lambda msg: msg.get("type") == "rogue_offer")
            cards = offer.get("cards") or []
            assert [item.get("id") for item in cards] == [card_id]
            offered = cards[0]
            assert offered["name"] == marker("rogue", card_id)
            assert offered["desc"] == desc_marker("rogue", card_id)
            assert offered["i18n"]["name"]["zh-CN"] == marker("rogue", card_id)
            assert offered["i18n"]["desc"]["zh-CN"] == desc_marker("rogue", card_id)

            await ws.send(json.dumps({"action": "rogue_select_card", "card_id": card_id}))
            selected = await recv_until(ws, lambda msg: msg.get("type") == "rogue_card_selected")
            assert selected["name"] == marker("rogue", card_id)
            if "uses" in card:
                assert selected.get("rogue_uses", {}).get(card_id) == 3
        checked.append(card_id)
    post_json(base_url, "/api/card-config", {"config": config})
    return checked


async def verify_direct_configured_effects() -> dict[str, Any]:
    import card_smoke_test as base_smoke
    import server as s
    from app.data import cards as card_data
    from app.runtime.ws_actions import (
        handle_rogue_seal_point,
        handle_rogue_use_coach,
        handle_ultimate_select_card,
    )

    errors = s.reload_live_card_config()
    assert errors == []
    assert card_data.validate_card_catalog() == []

    for card_id in s.ROGUE_CARDS:
        summary = s.rogue_card_summary(card_id)
        assert summary["name"] == marker("rogue", card_id)
        assert summary["desc"] == desc_marker("rogue", card_id)
        assert summary["i18n"]["name"]["zh-CN"] == marker("rogue", card_id)

    for card_id in s.ULTIMATE_CARDS:
        summary = s.ultimate_card_summary(card_id)
        assert summary["name"] == marker("ultimate", card_id)
        assert summary["desc"] == desc_marker("ultimate", card_id)
        assert summary["i18n"]["name"]["zh-CN"] == marker("ultimate", card_id)

    for card_id, cdef in s.ROGUE_CARDS.items():
        game = base_smoke.make_game()
        base_smoke.seed_board(game)
        sent: list[dict[str, Any]] = []

        async def send(payload: dict[str, Any]) -> None:
            sent.append(copy.deepcopy(payload))

        await s._activate_rogue_card(game, send, card_id)
        selected = next(msg for msg in sent if msg.get("type") == "rogue_card_selected")
        assert selected["name"] == marker("rogue", card_id)
        if "uses" in cdef:
            assert game.rogue_uses[card_id] == 3

    for card_id in s.ULTIMATE_CARDS:
        game = base_smoke.make_game()
        game.ultimate = True
        sent: list[dict[str, Any]] = []
        ctx = base_smoke.make_ws_context(game, sent, engine=base_smoke.DummyEngine())
        await handle_ultimate_select_card(ctx, {"card_id": card_id})
        selected = next(msg for msg in sent if msg.get("type") == "ultimate_cards_selected")
        assert selected["player_name"] == marker("ultimate", card_id)

    old_engine = s.engine
    old_random = s.random.random
    try:
        s.engine = base_smoke.DummyEngine(["E5"])
        s.random.random = lambda: 0.99
        game = base_smoke.make_game()
        game.rogue_card = "dice"
        game.current_player = game.ai_color
        game.moves = [("B", "D4")]
        sent = []

        async def send_dice(payload: dict[str, Any]) -> None:
            sent.append(copy.deepcopy(payload))

        await s._ai_move(game, send_dice)
        assert any(msg.get("type") == "ai_move" and msg.get("gtp") == "pass" for msg in sent)
    finally:
        s.engine = old_engine
        s.random.random = old_random

    old_engine = s.engine
    try:
        s.engine = base_smoke.DummyEngine(["C7"])
        game = base_smoke.make_game()
        game.rogue_card = "sansan_trap"
        game.current_player = game.ai_color
        sent = []

        async def send_sansan(payload: dict[str, Any]) -> None:
            sent.append(copy.deepcopy(payload))

        await s._ai_move(game, send_sansan)
        spawned = sum(1 for row in game.board for cell in row if cell == 1)
        assert spawned == TUNING_EDITS["ROGUE_SANSAN_TRAP_STONES"]
    finally:
        s.engine = old_engine

    game = base_smoke.make_game()
    game.rogue_card = "seal"
    game.rogue_waiting_seal = True
    sent = []
    ctx = base_smoke.make_ws_context(game, sent, engine=base_smoke.DummyEngine())
    ctx.engine.ready = False
    await handle_rogue_seal_point(ctx, {"x": 0, "y": 0})
    assert game.rogue_waiting_seal is True
    await handle_rogue_seal_point(ctx, {"x": 1, "y": 0})
    assert game.rogue_waiting_seal is False
    assert any(msg.get("type") == "rogue_seal_done" for msg in sent)

    game = base_smoke.make_game()
    game.rogue_card = "coach_mode"
    game.rogue_uses["coach_mode"] = 3
    sent = []
    ctx = base_smoke.make_ws_context(game, sent, engine=base_smoke.DummyEngine())
    await handle_rogue_use_coach(ctx, {})
    assert game.rogue_uses["coach_mode"] == 2
    assert game.rogue_coach_moves_left == TUNING_EDITS["ROGUE_COACH_BASE_TURNS"]

    game = base_smoke.make_game()
    game.ultimate = True
    for index in range(6):
        game.board[index // 3][index % 3] = 2
    sent = []

    async def send_ultimate(payload: dict[str, Any]) -> None:
        sent.append(copy.deepcopy(payload))

    before = sum(1 for row in game.board for cell in row if cell == 2)
    await s._apply_ultimate_effect(game, send_ultimate, 4, 4, "B", "meteor")
    after = sum(1 for row in game.board for cell in row if cell == 2)
    assert before - after == TUNING_EDITS["ULTIMATE_METEOR_DESTROY_COUNT"]

    game = base_smoke.make_game()
    game.ultimate = True
    game.board[4][4] = 1
    before = sum(1 for row in game.board for cell in row if cell == 1)
    await s._apply_ultimate_effect(game, send_ultimate, 4, 4, "B", "quantum")
    after = sum(1 for row in game.board for cell in row if cell == 1)
    assert after - before == TUNING_EDITS["ULTIMATE_QUANTUM_PLACE_COUNT"]

    old_engine = s.engine
    try:
        s.engine = base_smoke.DummyEngine(["D4", "E5", "F6"])
        for name in BASE_SMOKE_NAMES:
            await getattr(base_smoke, name)()
    finally:
        s.engine = old_engine

    return {
        "rogue_cards": len(s.ROGUE_CARDS),
        "ultimate_cards": len(s.ULTIMATE_CARDS),
        "base_effect_smokes": len(BASE_SMOKE_NAMES),
    }


async def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rogue-go-card-editor-") as temp_dir:
        config_path = Path(temp_dir) / "cards.json"
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        ws_base_url = f"ws://127.0.0.1:{port}"
        env = os.environ.copy()
        env["ROGUE_GO_CARD_CONFIG"] = str(config_path)
        env["PYTHONIOENCODING"] = "utf-8"
        os.environ["ROGUE_GO_CARD_CONFIG"] = str(config_path)

        proc = subprocess.Popen(
            [
                sys.executable,
                "server.py",
                "--no-katago",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        try:
            wait_for_server(proc, base_url)
            screenshot = ARTIFACT_DIR / "card-editor-all-card-form-edits.png"
            config = await edit_all_cards_with_form(base_url, screenshot)
            direct = await verify_direct_configured_effects()
            offered = await verify_every_rogue_offer(base_url, ws_base_url, config)

            report = {
                "ok": True,
                "config_path": str(config_path),
                "screenshot": str(screenshot),
                "rogue_offers_checked": len(offered),
                **direct,
            }
            report_path = ARTIFACT_DIR / "card-editor-effect-smoke-report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=10)
            if proc.poll() is None:
                proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
