from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request
import uuid
from urllib.parse import urlparse

import websockets


ROGUE_SMOKE_DIRECT_AI_CARDS = {
    "tengen",
    "dice",
    "erosion",
    "nerf",
    "komi_relief",
    "time_press",
    "lowline",
    "suboptimal",
    "mirror",
    "slip",
    "blackhole",
    "fog",
    "gravity",
    "golden_corner",
    "sansan",
    "shadow",
    "sprout",
    "god_hand",
    "corner_helper",
    "no_regret",
    "foolish_wisdom",
    "capture_foul",
    "last_stand",
}


def coord_to_gtp(x: int, y: int, size: int) -> str:
    cols = "ABCDEFGHJKLMNOPQRST"
    return f"{cols[x]}{size - y}"


def gtp_to_sgf(gtp: str, size: int) -> str:
    cols = "ABCDEFGHJKLMNOPQRST"
    col = cols.index(gtp[0].upper())
    row = size - int(gtp[1:])
    return chr(ord("a") + col) + chr(ord("a") + row)


def http_text(base_url: str, path: str) -> str:
    with urllib.request.urlopen(base_url + path, timeout=20) as resp:
        return resp.read().decode("utf-8")


def http_json(base_url: str, path: str) -> dict:
    return json.loads(http_text(base_url, path))


async def recv_until(ws, predicate, *, timeout: float, transcript: list[dict]) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for websocket message")
        msg = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        transcript.append(msg)
        if predicate(msg):
            return msg


async def normal_smoke(base_http: str, base_ws: str) -> dict:
    game_id = "runtime-normal-" + uuid.uuid4().hex[:8]
    transcript: list[dict] = []
    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            "action": "new_game",
            "size": 9,
            "komi": 7.5,
            "handicap": 0,
            "player_color": "B",
            "level": "5k",
            "two_player": False,
            "ai_observer": False,
            "rogue": False,
            "ai_rogue": False,
            "ultimate": False,
            "challenge_beta": False,
        }))
        await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=20, transcript=transcript)
        await ws.send(json.dumps({"action": "play", "x": 4, "y": 4}))
        ai_move = await recv_until(ws, lambda m: m.get("type") == "ai_move", timeout=30, transcript=transcript)
        await ws.send(json.dumps({"action": "request_hint"}))
        analysis = await recv_until(
            ws,
            lambda m: (
                m.get("type") == "analysis"
                and len(m.get("top_moves") or []) > 0
                and len(m.get("ownership") or []) > 0
            ),
            timeout=30,
            transcript=transcript,
        )

    sgf = http_text(base_http, f"/sgf/{game_id}")
    player_gtp = coord_to_gtp(4, 4, 9)
    ai_gtp = ai_move.get("gtp") or ""
    return {
        "game_id": game_id,
        "player_move": player_gtp,
        "ai_move": ai_gtp,
        "analysis_top_moves": len(analysis.get("top_moves") or []),
        "analysis_ownership": len(analysis.get("ownership") or []),
        "sgf_has_player": f";B[{gtp_to_sgf(player_gtp, 9)}]" in sgf,
        "sgf_has_ai": f";W[{gtp_to_sgf(ai_gtp, 9)}]" in sgf if ai_gtp else False,
        "status": "passed",
    }


async def rogue_smoke(base_ws: str) -> dict:
    skipped_offers: list[list[str]] = []
    for _attempt in range(8):
        game_id = "runtime-rogue-" + uuid.uuid4().hex[:8]
        transcript: list[dict] = []
        async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
            await ws.send(json.dumps({
                "action": "new_game",
                "size": 9,
                "komi": 7.5,
                "handicap": 0,
                "player_color": "B",
                "level": "5k",
                "two_player": False,
                "ai_observer": False,
                "rogue": True,
                "ai_rogue": False,
                "ultimate": False,
                "challenge_beta": False,
            }))
            await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=20, transcript=transcript)
            offer = await recv_until(ws, lambda m: m.get("type") == "rogue_offer", timeout=20, transcript=transcript)
            cards = offer.get("cards") or []
            chosen = next((card for card in cards if card.get("id") in ROGUE_SMOKE_DIRECT_AI_CARDS), None)
            if not chosen:
                skipped_offers.append([card.get("id") for card in cards])
                continue
            await ws.send(json.dumps({"action": "rogue_select_card", "card_id": chosen["id"]}))
            await recv_until(ws, lambda m: m.get("type") == "rogue_card_selected", timeout=20, transcript=transcript)

            accepted = False
            last_error = None
            saw_ai_move = None
            for y in range(9):
                for x in range(9):
                    await ws.send(json.dumps({"action": "play", "x": x, "y": y}))
                    msg = await recv_until(
                        ws,
                        lambda m: m.get("type") in {"error", "game_state", "ai_move"},
                        timeout=30,
                        transcript=transcript,
                    )
                    if msg.get("type") == "error":
                        last_error = msg.get("message")
                        continue
                    accepted = True
                    if msg.get("type") == "ai_move":
                        saw_ai_move = msg
                    break
                if accepted:
                    break

            if not accepted:
                raise RuntimeError(f"rogue player move was never accepted: {last_error}")
            ai_move = saw_ai_move or await recv_until(ws, lambda m: m.get("type") == "ai_move", timeout=30, transcript=transcript)
            return {
                "game_id": game_id,
                "offer_ids": [card.get("id") for card in cards],
                "skipped_offers": skipped_offers,
                "selected_card": chosen["id"],
                "ai_move": ai_move.get("gtp"),
                "status": "passed",
            }

    raise RuntimeError(f"no direct-AI rogue smoke card was offered: {skipped_offers}")


async def ultimate_smoke(base_ws: str) -> dict:
    game_id = "runtime-ultimate-" + uuid.uuid4().hex[:8]
    transcript: list[dict] = []
    avoid = {"quickthink", "chain", "double"}
    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            "action": "new_game",
            "size": 9,
            "komi": 7.5,
            "handicap": 0,
            "player_color": "B",
            "level": "5k",
            "two_player": False,
            "ai_observer": False,
            "rogue": False,
            "ai_rogue": False,
            "ultimate": True,
            "challenge_beta": False,
        }))
        await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=20, transcript=transcript)
        offer = await recv_until(ws, lambda m: m.get("type") == "ultimate_offer", timeout=20, transcript=transcript)
        cards = offer.get("cards") or []
        chosen = next((card for card in cards if card.get("id") not in avoid), cards[0])
        await ws.send(json.dumps({"action": "ultimate_select_card", "card_id": chosen["id"]}))
        await recv_until(
            ws,
            lambda m: m.get("type") == "ultimate_cards_selected",
            timeout=20,
            transcript=transcript,
        )

        accepted = False
        last_error = None
        for y in range(9):
            for x in range(9):
                await ws.send(json.dumps({"action": "play", "x": x, "y": y}))
                msg = await recv_until(
                    ws,
                    lambda m: m.get("type") in {"error", "game_state", "ai_move", "rogue_event"},
                    timeout=30,
                    transcript=transcript,
                )
                if msg.get("type") == "error":
                    last_error = msg.get("message")
                    continue
                accepted = True
                break
            if accepted:
                break

        if chosen["id"] == "quickthink":
            await ws.send(json.dumps({"action": "ultimate_quickthink_end"}))
        ai_move = await recv_until(ws, lambda m: m.get("type") == "ai_move", timeout=30, transcript=transcript)

    if not accepted:
        raise RuntimeError(f"ultimate player move was never accepted: {last_error}")
    return {
        "game_id": game_id,
        "offer_ids": [card.get("id") for card in cards],
        "selected_card": chosen["id"],
        "ai_move": ai_move.get("gtp"),
        "status": "passed",
    }


async def capture_smoke(base_ws: str) -> dict:
    game_id = "runtime-capture-" + uuid.uuid4().hex[:8]
    transcript: list[dict] = []
    sequence = [
        (0, 1),
        (1, 1),
        (1, 0),
        (4, 4),
        (2, 1),
        (4, 3),
        (1, 2),
    ]
    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            "action": "new_game",
            "size": 5,
            "komi": 7.5,
            "handicap": 0,
            "player_color": "B",
            "level": "5k",
            "two_player": True,
            "ai_observer": False,
            "rogue": False,
            "ai_rogue": False,
            "ultimate": False,
            "challenge_beta": False,
        }))
        await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=20, transcript=transcript)
        last_state = None
        for x, y in sequence:
            await ws.send(json.dumps({"action": "play", "x": x, "y": y}))
            last_state = await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10, transcript=transcript)

    captures = last_state.get("captures") or {}
    board = last_state.get("board") or []
    passed = captures.get("B") == 1 and board[1][1] == 0
    return {
        "game_id": game_id,
        "captures_B": captures.get("B"),
        "center_removed": board[1][1] == 0,
        "status": "passed" if passed else "failed",
    }


async def ko_smoke(base_ws: str) -> dict:
    game_id = "runtime-ko-" + uuid.uuid4().hex[:8]
    transcript: list[dict] = []
    setup_moves = [
        (0, 1),
        (1, 1),
        (2, 1),
        (0, 2),
        (1, 0),
        (2, 2),
        (4, 4),
        (1, 3),
        (1, 2),
    ]
    async with websockets.connect(f"{base_ws}/ws/{game_id}", max_size=10_000_000) as ws:
        await ws.send(json.dumps({
            "action": "new_game",
            "size": 5,
            "komi": 7.5,
            "handicap": 0,
            "player_color": "B",
            "level": "5k",
            "two_player": True,
            "ai_observer": False,
            "rogue": False,
            "ai_rogue": False,
            "ultimate": False,
            "challenge_beta": False,
        }))
        await recv_until(ws, lambda m: m.get("type") == "game_start", timeout=20, transcript=transcript)
        for x, y in setup_moves:
            await ws.send(json.dumps({"action": "play", "x": x, "y": y}))
            await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10, transcript=transcript)

        await ws.send(json.dumps({"action": "play", "x": 1, "y": 1}))
        ko_error = await recv_until(ws, lambda m: m.get("type") == "error", timeout=10, transcript=transcript)

        await ws.send(json.dumps({"action": "play", "x": 4, "y": 0}))
        await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10, transcript=transcript)
        await ws.send(json.dumps({"action": "play", "x": 4, "y": 1}))
        await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10, transcript=transcript)
        await ws.send(json.dumps({"action": "play", "x": 1, "y": 1}))
        final_state = await recv_until(ws, lambda m: m.get("type") == "game_state", timeout=10, transcript=transcript)

    captures = final_state.get("captures") or {}
    board = final_state.get("board") or []
    passed = (
        "打劫禁着" in (ko_error.get("message") or "")
        and captures.get("W") == 1
        and board[1][1] == 2
        and board[2][1] == 0
    )
    return {
        "game_id": game_id,
        "immediate_recapture_error": ko_error.get("message"),
        "captures_W": captures.get("W"),
        "recapture_succeeded": board[1][1] == 2 and board[2][1] == 0,
        "status": "passed" if passed else "failed",
    }


async def run_smoke(base_url: str) -> dict:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    ws_base = f"{scheme}://{parsed.netloc}"

    results = {
        "status": http_json(base_url, "/status"),
        "gpu": http_json(base_url, "/gpu"),
        "normal": await normal_smoke(base_url, ws_base),
        "rogue": await rogue_smoke(ws_base),
        "ultimate": await ultimate_smoke(ws_base),
        "capture_rule": await capture_smoke(ws_base),
        "ko_rule": await ko_smoke(ws_base),
    }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GoAI runtime smoke tests.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    results = asyncio.run(run_smoke(args.base_url.rstrip("/")))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2))

    failures = [
        key for key in ("normal", "rogue", "ultimate", "capture_rule", "ko_rule")
        if results.get(key, {}).get("status") != "passed"
    ]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
