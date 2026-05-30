from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.runtime.ws_actions import WebSocketActionContext


@dataclass(frozen=True)
class WebSocketContextDeps:
    active_games: Any
    engine: Any
    run_in_executor: Any
    GoGame: Any
    coord_to_gtp: Any
    gtp_to_coord: Any
    engine_state_snapshot: Any
    start_engine_background: Any
    reload_live_card_config: Any
    get_game_visits: Any
    pick_rogue_choices: Any
    pick_ultimate_choices: Any
    pick_challenge_beta_choices: Any
    pick_ai_rogue_card: Any
    pick_ai_ultimate_card: Any
    apply_challenge_rogue_loadout: Any
    activate_rogue_card: Any
    activate_ai_rogue_card: Any
    ai_move: Any
    ultimate_ai_move: Any
    ultimate_force_score: Any
    run_coach_turn_if_needed: Any
    run_ai_observer_loop: Any
    sync_board_to_katago: Any
    challenge_remaining: Any
    challenge_zone_points: Any
    rogue_has: Any
    get_ai_rogue_forbidden_points: Any
    ultimate_get_territory_forbidden: Any
    record_ultimate_player_action: Any
    check_capture_foul: Any
    count_stones: Any
    apply_ultimate_effect: Any
    resolve_pending_ultimate_shadow_links: Any
    apply_player_rogue_move_effects: Any
    apply_ai_rogue_response_effects: Any
    prepare_player_turn_modifiers: Any
    finish_ultimate_quickthink_turn: Any
    pick_joseki_targets: Any
    random_hidden_center: Any
    diamond_points: Any


def build_websocket_action_context(
    *,
    game_id: str,
    game: Any,
    send: Any,
    send_error: Any,
    do_analysis: Any,
    do_analysis_bg: Any,
    deps: WebSocketContextDeps,
) -> WebSocketActionContext:
    return WebSocketActionContext(
        game_id=game_id,
        game=game,
        active_games=deps.active_games,
        engine=deps.engine,
        send=send,
        send_error=send_error,
        do_analysis=do_analysis,
        do_analysis_bg=do_analysis_bg,
        run_in_executor=deps.run_in_executor,
        GoGame=deps.GoGame,
        coord_to_gtp=deps.coord_to_gtp,
        gtp_to_coord=deps.gtp_to_coord,
        engine_state_snapshot=deps.engine_state_snapshot,
        start_engine_background=deps.start_engine_background,
        reload_live_card_config=deps.reload_live_card_config,
        get_game_visits=deps.get_game_visits,
        pick_rogue_choices=deps.pick_rogue_choices,
        pick_ultimate_choices=deps.pick_ultimate_choices,
        pick_challenge_beta_choices=deps.pick_challenge_beta_choices,
        pick_ai_rogue_card=deps.pick_ai_rogue_card,
        pick_ai_ultimate_card=deps.pick_ai_ultimate_card,
        apply_challenge_rogue_loadout=deps.apply_challenge_rogue_loadout,
        activate_rogue_card=deps.activate_rogue_card,
        activate_ai_rogue_card=deps.activate_ai_rogue_card,
        ai_move=deps.ai_move,
        ultimate_ai_move=deps.ultimate_ai_move,
        ultimate_force_score=deps.ultimate_force_score,
        run_coach_turn_if_needed=deps.run_coach_turn_if_needed,
        run_ai_observer_loop=deps.run_ai_observer_loop,
        sync_board_to_katago=deps.sync_board_to_katago,
        challenge_remaining=deps.challenge_remaining,
        challenge_zone_points=deps.challenge_zone_points,
        rogue_has=deps.rogue_has,
        get_ai_rogue_forbidden_points=deps.get_ai_rogue_forbidden_points,
        ultimate_get_territory_forbidden=deps.ultimate_get_territory_forbidden,
        record_ultimate_player_action=deps.record_ultimate_player_action,
        check_capture_foul=deps.check_capture_foul,
        count_stones=deps.count_stones,
        apply_ultimate_effect=deps.apply_ultimate_effect,
        resolve_pending_ultimate_shadow_links=deps.resolve_pending_ultimate_shadow_links,
        apply_player_rogue_move_effects=deps.apply_player_rogue_move_effects,
        apply_ai_rogue_response_effects=deps.apply_ai_rogue_response_effects,
        prepare_player_turn_modifiers=deps.prepare_player_turn_modifiers,
        finish_ultimate_quickthink_turn=deps.finish_ultimate_quickthink_turn,
        pick_joseki_targets=deps.pick_joseki_targets,
        random_hidden_center=deps.random_hidden_center,
        diamond_points=deps.diamond_points,
    )
