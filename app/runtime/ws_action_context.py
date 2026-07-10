from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional


@dataclass
class WebSocketActionContext:
    game_id: str
    game: Optional[Any]
    active_games: Any
    engine: Any
    send: Callable[[dict], Awaitable[None]]
    send_error: Callable[[str], Awaitable[None]]
    do_analysis: Callable[[Any], Awaitable[dict]]
    do_analysis_bg: Callable[[Any], Awaitable[None]]
    run_in_executor: Callable[..., Awaitable[Any]]
    GoGame: type
    coord_to_gtp: Callable[[int, int, int], Optional[str]]
    gtp_to_coord: Callable[[str, int], Optional[tuple[int, int]]]
    engine_state_snapshot: Callable[[], dict]
    start_engine_background: Callable[[str], None]
    get_game_visits: Callable[[str, int, str], int]
    sync_board_to_katago: Callable[..., Awaitable[None]]
    reload_live_card_config: Callable[[], list[str]]
    pick_rogue_choices: Callable[..., list[str]]
    pick_ultimate_choices: Callable[..., list[str]]
    pick_challenge_beta_choices: Callable[..., list[str]]
    pick_ai_rogue_card: Callable[..., str]
    pick_ai_ultimate_card: Callable[..., str]
    apply_challenge_rogue_loadout: Callable[..., Awaitable[None]]
    activate_rogue_card: Callable[..., Awaitable[None]]
    activate_ai_rogue_card: Callable[..., Awaitable[None]]
    ai_move: Callable[..., Awaitable[None]]
    ultimate_ai_move: Callable[..., Awaitable[None]]
    ultimate_force_score: Callable[..., Awaitable[None]]
    run_coach_turn_if_needed: Callable[..., Awaitable[None]]
    run_ai_observer_loop: Callable[..., Awaitable[None]]
    challenge_remaining: Callable[[Any, str], int]
    challenge_zone_points: Callable[[Any, list[tuple[int, int]]], list[tuple[int, int]]]
    rogue_has: Callable[[Any, str], bool]
    get_ai_rogue_forbidden_points: Callable[[Any], set[tuple[int, int]]]
    ultimate_get_territory_forbidden: Callable[[Any, int], set]
    record_ultimate_player_action: Callable[[Any], None]
    check_capture_foul: Callable[..., Awaitable[None]]
    count_stones: Callable[[Any, int], int]
    apply_ultimate_effect: Callable[..., Awaitable[bool]]
    resolve_pending_ultimate_shadow_links: Callable[..., Awaitable[bool]]
    apply_player_rogue_move_effects: Callable[..., Awaitable[None]]
    apply_ai_rogue_response_effects: Callable[..., Awaitable[None]]
    prepare_player_turn_modifiers: Callable[[Any], None]
    finish_ultimate_quickthink_turn: Callable[[Any], None]
    pick_joseki_targets: Callable[[int, int], list[tuple[int, int]]]
    random_hidden_center: Callable[[int, int, random.Random], tuple[int, int]]
    diamond_points: Callable[..., list[tuple[int, int]]]

    def restore_game(self) -> Any:
        if self.active_games is None:
            return self.game
        stored_game = self.active_games.get(self.game_id, touch=True)
        if stored_game is not None:
            self.game = stored_game
        return self.game
