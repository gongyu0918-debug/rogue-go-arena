from __future__ import annotations

from typing import Awaitable, Callable

from app.runtime.ws_action_context import WebSocketActionContext
from app.runtime.ws_new_game_actions import handle_new_game
from app.runtime.ws_play_actions import handle_play
from app.runtime.ws_rogue_actions import (
    handle_challenge_refresh_offer,
    handle_rogue_seal_point,
    handle_rogue_select_card,
    handle_rogue_use_coach,
    handle_rogue_use_exchange,
    handle_rogue_use_puppet,
    handle_rogue_use_twin,
)
from app.runtime.ws_session_actions import (
    handle_load_position,
    handle_reconnect,
    handle_request_hint,
    handle_resign,
    handle_set_level,
    handle_time_expired,
)
from app.runtime.ws_turn_actions import (
    handle_pass,
    handle_score,
    handle_undo,
)
from app.runtime.ws_ultimate_actions import (
    handle_ultimate_quickthink_end,
    handle_ultimate_select_card,
)


WS_ACTION_HANDLERS: dict[str, Callable[[WebSocketActionContext, dict], Awaitable[None]]] = {
    "new_game": handle_new_game,
    "play": handle_play,
    "pass": handle_pass,
    "undo": handle_undo,
    "reconnect": handle_reconnect,
    "resign": handle_resign,
    "request_hint": handle_request_hint,
    "set_level": handle_set_level,
    "load_position": handle_load_position,
    "time_expired": handle_time_expired,
    "rogue_select_card": handle_rogue_select_card,
    "challenge_refresh_offer": handle_challenge_refresh_offer,
    "rogue_seal_point": handle_rogue_seal_point,
    "rogue_use_puppet": handle_rogue_use_puppet,
    "rogue_use_twin": handle_rogue_use_twin,
    "rogue_use_exchange": handle_rogue_use_exchange,
    "rogue_use_coach": handle_rogue_use_coach,
    "ultimate_select_card": handle_ultimate_select_card,
    "ultimate_quickthink_end": handle_ultimate_quickthink_end,
    "score": handle_score,
}
