from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import copy
import json
import pickle

from app.domain.event_text import EventText, event_text, with_event_keys
from app.runtime.ws_session import run_websocket_game_session
from ws_session_smoke_test import FakeActiveGames, FakeContext, FakeWebSocket


def smoke_event_text_is_still_the_chinese_string() -> None:
    msg = event_text("card.sprout.gift", "萌芽触发：在 D4 额外长出一颗己方棋子", card="sprout", point="D4")
    assert isinstance(msg, str) and msg == "萌芽触发：在 D4 额外长出一颗己方棋子"
    assert "萌芽" in msg and msg.startswith("萌芽")
    assert json.dumps({"msg": msg}, ensure_ascii=False) == '{"msg": "萌芽触发：在 D4 额外长出一颗己方棋子"}'
    for clone in (copy.deepcopy(msg), pickle.loads(pickle.dumps(msg))):
        assert isinstance(clone, EventText) and clone == msg
        assert clone.key == "card.sprout.gift" and clone.params == {"card": "sprout", "point": "D4"}
    # Building a longer string from an EventText gives a plain str (it needs its own key).
    assert type(msg + "!") is str


def smoke_with_event_keys_adds_key_and_params() -> None:
    msg = event_text("card.joseki_ocd.targets", "中文", points=["D4", "Q16"], count=7)
    payload = with_event_keys({"type": "rogue_event", "msg": msg})
    assert payload == {"type": "rogue_event", "msg": "中文", "key": "card.joseki_ocd.targets",
                       "params": {"points": ["D4", "Q16"], "count": 7}}
    payload["params"]["points"].append("K10")
    assert msg.params["points"] == ["D4", "Q16"], "params are copied, not shared"
    error = with_event_keys({"type": "error", "message": event_text("error.x", "错误")})
    assert error["key"] == "error.x" and error["params"] == {}
    plain = {"type": "rogue_event", "msg": "普通字符串"}
    assert with_event_keys(plain) is plain
    explicit = {"type": "rogue_event", "msg": msg, "key": "already.set"}
    assert with_event_keys(explicit) is explicit


async def smoke_websocket_sends_key_next_to_legacy_text() -> None:
    active_games = FakeActiveGames()
    websocket = FakeWebSocket([json.dumps({"action": "ping"})])

    async def analyze_position(game):
        raise AssertionError("analysis is not used here")

    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return FakeContext("session-1", game, send, do_analysis_bg)

    async def handle_ping(ctx, data):
        await ctx.send({"type": "rogue_event", "msg": event_text("card.god_hand.burst", "✨ 神之一手发动", card="god_hand", count=3)})
        await ctx.send({"type": "rogue_event", "msg": "旧消息"})

    await run_websocket_game_session(
        websocket,
        "session-1",
        active_games=active_games,
        action_handlers={"ping": handle_ping},
        analyze_position=analyze_position,
        make_context=make_context,
        log_fn=lambda message: None,
        traceback_fn=lambda: None,
    )
    assert websocket.sent == [
        {"type": "rogue_event", "msg": "✨ 神之一手发动", "key": "card.god_hand.burst",
         "params": {"card": "god_hand", "count": 3}},
        {"type": "rogue_event", "msg": "旧消息"},
    ]


def main() -> None:
    smoke_event_text_is_still_the_chinese_string()
    smoke_with_event_keys_adds_key_and_params()
    asyncio.run(smoke_websocket_sends_key_next_to_legacy_text())
    print("event text smoke test: OK")


if __name__ == "__main__":
    main()
