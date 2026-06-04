"""
rogue-go-arena server - KataGo-powered board game with FastAPI WebSocket backend
"""
import argparse
import asyncio
import random
import traceback
import time
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocketDisconnect
import uvicorn
import app.config.gameplay as gameplay_config
import app.runtime.ws_actions as ws_actions_module
import app.runtime.ws_rogue_actions as ws_rogue_actions_module
import app.runtime.ws_ultimate_actions as ws_ultimate_actions_module
from app.config.gameplay import (
    CHALLENGE_RESTRICTION_DECAY_CHANCE,
    CHALLENGE_SET_MIN_COUNT,
    CHALLENGE_TRAP_EXTRA_TURN_CHANCE,
    MAX_MOVE_TIME,
    OPENING_MOVE_THRESHOLD,
    RANK_LABELS,
    ROGUE_COACH_BASE_TURNS,
    ROGUE_COACH_BONUS_THRESHOLD,
    ROGUE_COACH_BONUS_TURNS,
    ROGUE_COACH_VISITS,
    ROGUE_CORNER_HELPER_STONES,
    ROGUE_CORNER_HELPER_TRIGGER_STONES,
    ROGUE_DICE_PASS_CHANCE,
    ROGUE_EROSION_SHIFT,
    ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
    ROGUE_FOG_AI_MOVES,
    ROGUE_FOG_MASK_RADIUS,
    ROGUE_FOG_POST_MASK_POINTS,
    ROGUE_FOOLISH_FILL_COUNT,
    ROGUE_GODHAND_FILL_COUNT,
    ROGUE_GODHAND_RADIUS,
    ROGUE_GOLDEN_CORNER_SPAN,
    ROGUE_HANDICAP_BONUS_INTERVAL,
    ROGUE_HANDICAP_MAX_BONUSES,
    ROGUE_HANDICAP_REQUIRED_PASSES,
    ROGUE_JOSEKI_REQUIRED_HITS,
    ROGUE_JOSEKI_TARGET_COUNT,
    ROGUE_LAST_STAND_CLEAR_COUNT,
    ROGUE_LAST_STAND_SPAWN_COUNT,
    ROGUE_LAST_STAND_THRESHOLD,
    ROGUE_METHODICAL_BONUS_INTERVAL,
    ROGUE_METHODICAL_BONUS_PLAYS,
    ROGUE_METHODICAL_BASE_PLAYS,
    ROGUE_MIRROR_CHANCE,
    ROGUE_NO_REGRET_CHANCE,
    ROGUE_QUICKTHINK_FIRST_SECONDS,
    ROGUE_QUICKTHINK_SECOND_SECONDS,
    ROGUE_SANSAN_TRAP_STONES,
    ROGUE_SANRENSEI_BONUS_STONES,
    ROGUE_SANRENSEI_OPENING_MOVES,
    ROGUE_SANRENSEI_REQUIRED_STARS,
    ROGUE_SANRENSEI_SUPPORT_STONES,
    ROGUE_SEAL_POINT_COUNT,
    ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
    ULTIMATE_FOOLISH_CHAIN_DELAY,
    ULTIMATE_JOSEKI_BONUS_STONES,
    ULTIMATE_JOSEKI_REQUIRED_HITS,
    ULTIMATE_LAST_STAND_THRESHOLD,
    ULTIMATE_QUICKTHINK_SECONDS,
    get_balance_editor_payload,
    reset_balance_overrides,
    save_balance_overrides,
)
from app.data.cards import (
    get_gameplay_tuning_specs,
    get_gameplay_tuning_values,
    get_rogue_card,
    rogue_card_ids,
)
from app.domain.coordinates import coord_to_gtp, gtp_to_coord
import app.domain.game_state as game_state_module
from app.domain.game_state import GoGame
from app.domain.sgf import generate_sgf
from app.runtime.access_urls import get_access_urls as build_access_urls
from app.runtime.ai_style_adapters import (
    AiStyleMoveBinding,
    generate_ai_style_move as generate_ai_style_move_adapter,
)
from app.runtime.ai_style_runtime import (
    AiStyleMoveDependencies,
    AiStyleMoveRuntimeFns,
    build_ai_style_move_binding,
)
from app.runtime.ai_move_service_adapters import (
    AiMoveServiceRuntime,
    allow_only_points as ai_service_allow_only_points,
    avoid_points as ai_service_avoid_points,
    bind_ai_move_service as bind_ai_move_service_adapter,
    generate_move as ai_service_generate_move,
    no_resign_move as ai_service_no_resign_move,
    pick_nonpass_fallback_move as ai_service_pick_nonpass_fallback_move,
    pick_ranked_legal_move as ai_service_pick_ranked_legal_move,
    retry_avoiding_ko as ai_service_retry_avoiding_ko,
    suboptimal_move as ai_service_suboptimal_move,
)
from app.runtime.app_shell import AppShellBinding, configure_app_shell
from app.runtime.ai_turn_adapters import (
    AiTurnBinding,
    run_ai_turn as run_ai_turn_adapter,
)
from app.runtime.ai_turn_runtime import (
    AiTurnDependencies,
    AiTurnRuntimeFns,
    AiTurnStepFns,
    build_ai_turn_binding,
)
from app.runtime.config_routes import (
    ConfigRoutesBinding,
    build_config_router,
)
from app.runtime.control_routes import (
    RuntimeControlRoutesBinding,
    build_runtime_control_router,
)
from app.runtime.capture_foul_adapters import (
    CaptureFoulBinding,
    check_capture_foul_violation as check_capture_foul_violation_adapter,
)
from app.runtime.capture_foul_runtime import (
    CaptureFoulDependencies,
    CaptureFoulRuntimeFns,
    build_capture_foul_binding,
)
from app.runtime.challenge_adapters import (
    ChallengeFlowBinding,
    ChallengeLoadoutBinding,
    apply_challenge_loadout,
    apply_challenge_trap_bonus as apply_challenge_trap_bonus_adapter,
    emit_challenge_set_status,
    maybe_reduce_challenge_level,
)
from app.runtime.challenge_runtime import (
    ChallengeFlowRuntimeFns,
    ChallengeFlowTuning,
    ChallengeLoadoutRuntimeFns,
    ChallengeLoadoutTuning,
    ChallengeRuntimeDependencies,
    build_challenge_flow_binding,
    build_challenge_loadout_binding,
)
from app.runtime.coach_adapters import (
    AiFinishMoveBinding,
    CoachMoveChoiceBinding,
    CoachTurnBinding,
    choose_coach_ai_move as choose_coach_ai_move_adapter,
    finish_ai_move as finish_ai_move_adapter,
    run_coach_turn_if_needed as run_coach_turn_if_needed_adapter,
)
from app.runtime.coach_runtime import (
    AiFinishMoveRuntimeFns,
    CoachDependencies,
    CoachMoveChoiceRuntimeFns,
    CoachTuning,
    CoachTurnRuntimeFns,
    build_ai_finish_move_binding,
    build_coach_move_choice_binding,
    build_coach_turn_binding,
)
from app.runtime.engine_gateway_adapters import (
    EngineGatewayRuntime,
    analyze_current_position as engine_gateway_analyze_current_position,
    bind_engine_gateway as bind_engine_gateway_adapter,
    empty_analysis_result as engine_gateway_empty_analysis_result,
    estimate_side_winrate as engine_gateway_estimate_side_winrate,
    gtp_safe_sync_sgf_path as engine_gateway_gtp_safe_sync_sgf_path,
    pick_analysis_point as engine_gateway_pick_analysis_point,
    send_engine_command as send_engine_command_adapter,
    sync_board as engine_gateway_sync_board,
    sync_board_locked as engine_gateway_sync_board_locked,
    sync_engine_komi as sync_engine_komi_adapter,
)
from app.runtime.engine_gateway import EngineRuntimeGateway
from app.runtime.generated_ai_adapters import (
    GeneratedAiTurnBinding,
    GeneratedMoveCandidateBinding,
    GeneratedMoveFinishBinding,
    GeneratedMovePreparationBinding,
    try_finish_generated_ai_turn as try_finish_generated_ai_turn_adapter,
)
from app.runtime.generated_ai_runtime import (
    GeneratedAiRuntimeDependencies,
    GeneratedAiTurnFns,
    GeneratedMoveCandidateFns,
    GeneratedMoveFinishFns,
    GeneratedMoveFinishTuning,
    GeneratedMovePreparationFns,
    build_generated_ai_turn_binding,
    build_generated_move_candidate_binding,
    build_generated_move_finish_binding,
    build_generated_move_preparation_binding,
)
from app.runtime.gpu_info import CachedGpuInfo
from app.runtime.http_routes_runtime import (
    AppShellDependencies,
    ConfigRoutesDependencies,
    RuntimeControlRoutesDependencies,
    RuntimeInfoRoutesDependencies,
    StaticPageRoutesDependencies,
    build_app_shell_binding,
    build_config_routes_binding,
    build_runtime_control_routes_binding,
    build_runtime_info_routes_binding,
    build_static_page_routes_binding,
)
from app.runtime.info_routes import (
    RuntimeInfoRoutesBinding,
    build_runtime_info_router,
)
from app.runtime.katago_paths import (
    UserKataGoPaths,
    ensure_user_katago_dirs,
    write_runtime_katago_config,
)
from app.runtime.line_trigger_adapters import (
    RogueFiveInRowBinding,
    RogueLastStandBinding,
    UltimateFiveInRowBinding,
    UltimateLastStandBinding,
    trigger_rogue_five_in_row as trigger_rogue_five_in_row_adapter,
    trigger_rogue_last_stand as trigger_rogue_last_stand_adapter,
    trigger_ultimate_five_in_row as trigger_ultimate_five_in_row_adapter,
    trigger_ultimate_last_stand as trigger_ultimate_last_stand_adapter,
)
from app.runtime.line_trigger_runtime import (
    LineTriggerDependencies,
    LineTriggerEffectFns,
    LineTriggerRuntimeFns,
    LineTriggerTuning,
    build_rogue_five_in_row_binding,
    build_rogue_last_stand_binding,
    build_ultimate_five_in_row_binding,
    build_ultimate_last_stand_binding,
)
from app.runtime.observer_adapters import (
    AiObserverLoopBinding,
    ObserverDoublePassBinding,
    ObserverMovePlacementBinding,
    apply_observer_ai_move_to_board as apply_observer_ai_move_to_board_adapter,
    finish_observer_double_pass as finish_observer_double_pass_adapter,
    run_ai_observer_loop as run_ai_observer_loop_adapter,
)
from app.runtime.observer_runtime import (
    ObserverDependencies,
    ObserverMoveFns,
    ObserverRuntimeFns,
    ObserverTuning,
    build_ai_observer_loop_binding,
    build_observer_double_pass_binding,
    build_observer_move_placement_binding,
)
from app.runtime.rogue_activation_adapters import (
    AiRogueCardActivationBinding,
    RogueCardActivationBinding,
    activate_ai_rogue_card as activate_ai_rogue_card_adapter,
    activate_rogue_card as activate_rogue_card_adapter,
)
from app.runtime.rogue_activation_runtime import (
    RogueActivationDependencies,
    RogueActivationEffectFns,
    RogueActivationRuntimeFns,
    RogueActivationTuning,
    build_ai_rogue_card_activation_binding,
    build_rogue_card_activation_binding,
)
from app.runtime.rogue_ai_turn_adapters import (
    ForcedRogueAiTurnBinding,
    RestrictionRogueAiTurnBinding,
    ShadowRogueAiTurnBinding,
    SuboptimalRogueAiTurnBinding,
    try_finish_forced_rogue_ai_turn as try_finish_forced_rogue_ai_turn_adapter,
    try_finish_restriction_rogue_ai_turn as try_finish_restriction_rogue_ai_turn_adapter,
    try_finish_shadow_rogue_ai_turn as try_finish_shadow_rogue_ai_turn_adapter,
    try_finish_suboptimal_rogue_ai_turn as try_finish_suboptimal_rogue_ai_turn_adapter,
)
from app.runtime.rogue_ai_turn_runtime import (
    ForcedRogueAiTurnFns,
    RestrictionRogueAiTurnFns,
    RogueAiTurnDependencies,
    RogueAiTurnSharedFns,
    RogueAiTurnTuning,
    ShadowRogueAiTurnFns,
    SuboptimalRogueAiTurnFns,
    build_forced_rogue_ai_turn_binding,
    build_restriction_rogue_ai_turn_binding,
    build_shadow_rogue_ai_turn_binding,
    build_suboptimal_rogue_ai_turn_binding,
)
from app.runtime.rogue_move_effect_adapters import (
    AiRogueResponseEffectBinding,
    PlayerRogueMoveEffectBinding,
    apply_ai_rogue_response_effects as apply_ai_rogue_response_effects_adapter,
    apply_player_rogue_move_effects as apply_player_rogue_move_effects_adapter,
)
from app.runtime.rogue_move_effect_runtime import (
    RogueMoveEffectDependencies,
    RogueMoveEffectFns,
    RogueMoveEffectRuntimeFns,
    RogueMoveEffectTuning,
    build_ai_rogue_response_effect_binding,
    build_player_rogue_move_effect_binding,
)
from app.runtime.service_bindings import (
    AiMoveServiceBinding,
    EngineGatewayBinding,
)
from app.runtime.service_runtime import (
    AiMoveServiceDependencies,
    EngineGatewayDependencies,
    build_ai_move_service,
    build_ai_move_service_binding,
    build_ai_move_service_runtime,
    build_engine_gateway,
    build_engine_gateway_binding,
    build_engine_gateway_runtime,
)
from app.runtime.static_page_routes import (
    StaticPageRoutesBinding,
    build_static_page_router,
)
from app.runtime.turn_modifier_adapters import (
    clear_player_turn_modifiers as clear_player_turn_modifiers_adapter,
    finish_ultimate_quickthink_turn as finish_ultimate_quickthink_turn_adapter,
    get_ai_rogue_forbidden_points as get_ai_rogue_forbidden_points_adapter,
    get_player_bonus_forbidden_points as get_player_bonus_forbidden_points_adapter,
    pick_fog_mask as pick_fog_mask_adapter,
    pick_fog_point as pick_fog_point_adapter,
    player_non_pass_coords as player_non_pass_coords_adapter,
    prepare_player_turn_modifiers as prepare_player_turn_modifiers_adapter,
    record_ultimate_player_action as record_ultimate_player_action_adapter,
    record_ultimate_turn as record_ultimate_turn_adapter,
    refresh_ai_rogue_player_turn as refresh_ai_rogue_player_turn_adapter,
)
from app.runtime.ultimate_effect_adapters import (
    UltimateEffectBinding,
    apply_ultimate_effect as apply_ultimate_effect_adapter,
)
from app.runtime.ultimate_effect_runtime import (
    UltimateEffectDependencies,
    UltimateEffectFns,
    UltimateEffectRuntimeFns,
    UltimateEffectTuning,
    build_ultimate_effect_binding,
)
from app.runtime.ultimate_ai_adapters import (
    UltimateAiBonusTurnBinding,
    UltimateAiMoveSelectionBinding,
    UltimateAiTurnFinishBinding,
    finish_selected_ultimate_ai_move,
    run_ultimate_ai_bonus_turn_adapter,
    select_ultimate_ai_move,
)
from app.runtime.ultimate_ai_runtime import (
    UltimateAiBonusFns,
    UltimateAiDependencies,
    UltimateAiFinishFns,
    UltimateAiSelectionMoveFns,
    UltimateAiSelectionRuntimeFns,
    UltimateAiTuning,
    build_ultimate_ai_bonus_turn_binding,
    build_ultimate_ai_move_selection_binding,
    build_ultimate_ai_turn_finish_binding,
)
from app.runtime.ws_context_adapters import (
    WebSocketContextBinding,
    build_websocket_context_binding,
)
from app.runtime.ws_context import (
    WebSocketCardSelectionDeps,
    WebSocketContextDeps,
    WebSocketEngineDeps,
    WebSocketModeFlowDeps,
    WebSocketRuleEffectDeps,
    WebSocketRuntimeDeps,
)
from app.runtime.ws_routes import WebSocketRoutesBinding, build_websocket_router
from app.runtime.ws_routes_runtime import (
    WebSocketRoutesDependencies,
    WebSocketRoutesRuntimeFns,
    build_websocket_routes_binding,
)
from app.gameplay.card_selection import (
    pick_ai_rogue_card,
    pick_ai_ultimate_card,
    pick_challenge_beta_choices,
    pick_rogue_choices,
    pick_ultimate_choices,
)
from app.gameplay.ai_moves import (
    AiMoveService,
    AiMovePlan,
    AiTurnSnapshot,
    choose_ai_style_move,
    choose_tengen_target,
    gravity_allowed_points,
    is_suspicious_ai_pass as is_suspicious_ai_pass_state,
    lowline_allowed_points,
    plan_ultimate_ai_search,
    plan_rogue_ai_search,
    resolve_occupied_ai_move,
    rogue_forbidden_points,
    sansan_opening_restriction,
    shadow_followup_points,
    snapshot_ai_turn,
    tengen_followup_points,
    weaken_rank,
    weaken_rank_one_step,
)
from app.runtime.game_visits import runtime_game_visits
from app.gameplay.ai_move_flow import (
    apply_ai_move_to_board,
    apply_ai_move_placement_effects,
    apply_erosion_komi_counter,
    apply_slip_ai_move,
    apply_suspicious_pass_fallback,
    AiMovePlacement,
    choose_ai_move_candidate,
    choose_or_generate_ai_style_move,
    finalize_ai_move,
    finalize_forced_ai_pass,
    finish_ai_turn_response,
    finish_prepared_ai_move,
    refresh_fog_restriction_points,
    resolve_ai_resign_move,
    prepare_generated_ai_move,
    retry_ai_move_avoiding_ko,
    send_ai_move_and_run_coach,
    try_apply_no_regret_bonus,
    try_apply_puppet_ai_move,
    try_apply_sansan_trap_counter,
    try_finish_forced_rogue_ai_move,
    try_finish_allowed_restriction_move,
    try_finish_rogue_restriction_ai_move,
    try_finish_sansan_restriction_move,
    try_finalize_double_pass,
    try_finalize_forced_ai_stone,
    try_finish_generated_ai_move,
    try_finish_shadow_restriction_move,
    try_finish_suboptimal_rogue_move,
)
from app.gameplay.move_placement import (
    place_auxiliary_ai_move_on_board as place_auxiliary_ai_move_on_board_state,
)
from app.gameplay.turn_modifiers import (
    apply_ultimate_ai_move_result as apply_ultimate_ai_move_result_state,
    choose_ultimate_ai_bonus_turn as choose_ultimate_ai_bonus_turn_state,
    finish_ultimate_ai_normal_turn as finish_ultimate_ai_normal_turn_state,
    start_ultimate_ai_bonus_turn as start_ultimate_ai_bonus_turn_state,
)
from app.gameplay.effect_utils import (
    adjacent8_points as _adjacent8_points,
    adjacent_points as _adjacent_points,
    count_stones as _count_stones,
    diamond_points as _diamond_points,
    find_corner_with_min_stones as _find_corner_with_min_stones,
    get_blackhole_points as _get_blackhole_points,
    get_corner_helper_spawn_points as _get_corner_helper_spawn_points,
    get_golden_corner_points as _get_golden_corner_points,
    get_sansan_points as _get_sansan_points,
    get_star_points as _get_star_points,
    line_key as _line_key,
    line_points_between as _line_points_between,
    mirror_coord as _mirror_coord,
    pick_joseki_targets as _pick_joseki_targets,
    random_hidden_center as _random_hidden_center,
    set_points_to_color as _set_points_to_color,
    shape_center as _shape_center,
    spawn_bonus_points as _spawn_bonus_points,
    try_spawn_bonus_stone as _try_spawn_bonus_stone,
)
from app.gameplay.rogue_effects import (
    challenge_active_use_bonus as _challenge_active_use_bonus,
    challenge_remaining as _challenge_remaining,
    challenge_should_bonus_derivative as _challenge_should_bonus_derivative,
    challenge_zone_points as _challenge_zone_points,
    apply_challenge_rogue_loadout as apply_challenge_rogue_loadout_state,
    apply_ai_rogue_card_activation,
    apply_rogue_five_in_row,
    apply_rogue_last_stand,
    apply_rogue_card_activation,
    apply_ai_rogue_response_board_effects,
    apply_player_rogue_board_effects,
    rogue_card_ids as _rogue_card_ids,
    rogue_has as _rogue_has,
)
from app.services.card_config_service import CardConfigService
from app.services.balance_sync import sync_live_balance_globals
from app.gameplay.ultimate_effects import (
    apply_ultimate_card_effect as apply_ultimate_card_effect_state,
    apply_ultimate_foolish_wisdom_wave,
    apply_ultimate_five_in_row,
    apply_ultimate_last_stand,
    get_ultimate_territory_forbidden_points,
    resolve_pending_shadow_links,
)
from app.gameplay.ultimate_ai_flow import apply_ultimate_ai_post_move_effects
from app.gameplay.ultimate_scoring import finalize_ultimate_score
from app.runtime.engine import KataGoEngine
from app.runtime.game_store import ActiveGameStore
from app.runtime.startup import EnginePaths, EngineStartupManager
from app.runtime.ws_actions import WS_ACTION_HANDLERS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# ─── CLI flags ───────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--no-katago", action="store_true",
                    help="Disable KataGo (free-play / two-player only)")
parser.add_argument("--host", default="127.0.0.1",
                    help="Host interface to bind the HTTP/WebSocket server to")
parser.add_argument("--port", default=8000, type=int,
                    help="Port to bind the HTTP/WebSocket server to")
args, _ = parser.parse_known_args()
NO_KATAGO = args.no_katago

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.parent
else:
    BASE_DIR = Path(__file__).parent
USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(BASE_DIR))) / "rogue-go-arena"
USER_KATAGO_DIR = USER_DATA_DIR / "katago"
USER_KATAGO_HOME = USER_KATAGO_DIR / "KataGoData"
USER_RUNTIME_CONFIG_DIR = USER_KATAGO_DIR / "runtime"
USER_KATAGO_PATHS = UserKataGoPaths(
    data_dir=USER_DATA_DIR,
    katago_dir=USER_KATAGO_DIR,
    home_dir=USER_KATAGO_HOME,
    runtime_config_dir=USER_RUNTIME_CONFIG_DIR,
)
SERVER_REV = "20260601-runtime-hardening"
KATAGO_EXE = BASE_DIR / "katago" / "katago.exe"             # CUDA build (legacy/optional)
KATAGO_CUDA_EXE = BASE_DIR / "katago" / "katago_cuda.exe"   # CUDA (downloaded upgrade)
KATAGO_OPENCL_EXE = BASE_DIR / "katago" / "katago_opencl.exe"  # OpenCL (any GPU)
KATAGO_CPU_EXE = BASE_DIR / "katago" / "katago_cpu.exe"      # CPU (no GPU needed)
KATAGO_MODEL_LARGE = BASE_DIR / "katago" / "model_large.bin.gz"  # Upgraded large model (b28/b40)
KATAGO_MODEL = BASE_DIR / "katago" / "model.bin.gz"             # Default bundled model
KATAGO_MODEL_SMALL = BASE_DIR / "katago" / "model_b18.bin.gz"   # Compact model (b18)
USER_KATAGO_MODEL_LARGE = USER_KATAGO_DIR / "model_large.bin.gz"
KATAGO_CONFIG = BASE_DIR / "katago" / "config.cfg"
KATAGO_CPU_CONFIG = BASE_DIR / "katago" / "config_cpu.cfg"
STATIC_DIR = BASE_DIR / "static"
SERVER_HOST = args.host
SERVER_PORT = args.port


def log(message: str):
    print(message, flush=True)


def _sync_balance_globals() -> None:
    sync_live_balance_globals(
        target_globals=globals(),
        gameplay_config=gameplay_config,
        ws_actions_module=ws_actions_module,
        ws_action_modules=(ws_rogue_actions_module, ws_ultimate_actions_module),
        state_modules=(game_state_module,),
    )


card_config_service = CardConfigService(
    get_tuning_values=get_gameplay_tuning_values,
    get_tuning_specs=get_gameplay_tuning_specs,
    apply_balance_values=gameplay_config.apply_balance_values,
    sync_balance_globals=_sync_balance_globals,
)


def reload_live_card_config() -> list[str]:
    return card_config_service.reload_live_config()


CARD_CONFIG_STARTUP_ERRORS = reload_live_card_config()
if CARD_CONFIG_STARTUP_ERRORS:
    log("[CardConfig] " + " | ".join(CARD_CONFIG_STARTUP_ERRORS[:5]))


def _ensure_user_katago_dirs():
    ensure_user_katago_dirs(USER_KATAGO_PATHS)


def _runtime_config_path(source_config: Path) -> Path:
    return write_runtime_katago_config(source_config, USER_KATAGO_PATHS)


def get_game_visits(level: str, move_count: int = -1,
                    mode: str = "normal") -> int:
    return runtime_game_visits(
        level,
        move_count,
        mode,
        cpu_mode_fn=lambda: engine_runtime.cpu_mode,
    )


def get_access_urls(host: str = SERVER_HOST, port: int = SERVER_PORT) -> dict[str, list[str]]:
    return build_access_urls(host, port)


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI()
engine = KataGoEngine(
    default_exe=KATAGO_EXE,
    default_config=KATAGO_CONFIG,
    default_model=KATAGO_MODEL,
    log_fn=log,
    ensure_dirs_fn=_ensure_user_katago_dirs,
    coord_parser=gtp_to_coord,
)
ACTIVE_GAME_RETENTION_SECONDS = 24 * 60 * 60
active_games: ActiveGameStore[GoGame] = ActiveGameStore(
    retention_seconds=ACTIVE_GAME_RETENTION_SECONDS
)
engine_runtime = EngineStartupManager(
    engine,
    paths=EnginePaths(
        base_dir=BASE_DIR,
        cuda_exe=KATAGO_CUDA_EXE,
        legacy_exe=KATAGO_EXE,
        opencl_exe=KATAGO_OPENCL_EXE,
        cpu_exe=KATAGO_CPU_EXE,
        config=KATAGO_CONFIG,
        cpu_config=KATAGO_CPU_CONFIG,
        model_large=KATAGO_MODEL_LARGE,
        model_default=KATAGO_MODEL,
        model_small=KATAGO_MODEL_SMALL,
        user_model_large=USER_KATAGO_MODEL_LARGE,
    ),
    no_katago=NO_KATAGO,
    log_fn=log,
)
_engine_log = engine_runtime.log_event
_engine_state_snapshot = engine_runtime.snapshot


def _app_shell_dependencies() -> AppShellDependencies:
    return AppShellDependencies(
        static_dir=STATIC_DIR,
        engine_runtime=engine_runtime,
        log_fn=log,
    )


def _app_shell_binding() -> AppShellBinding:
    return build_app_shell_binding(_app_shell_dependencies())


configure_app_shell(app, _app_shell_binding)


def _static_page_routes_dependencies() -> StaticPageRoutesDependencies:
    return StaticPageRoutesDependencies(static_dir=STATIC_DIR)


def _static_page_routes_binding() -> StaticPageRoutesBinding:
    return build_static_page_routes_binding(_static_page_routes_dependencies())


app.include_router(build_static_page_router(_static_page_routes_binding))


def _config_routes_dependencies() -> ConfigRoutesDependencies:
    return ConfigRoutesDependencies(
        card_config_service=card_config_service,
        get_balance_editor_payload=get_balance_editor_payload,
        save_balance_overrides=save_balance_overrides,
        reset_balance_overrides=reset_balance_overrides,
    )


def _config_routes_binding() -> ConfigRoutesBinding:
    return build_config_routes_binding(_config_routes_dependencies())


app.include_router(build_config_router(_config_routes_binding))


def _runtime_control_routes_dependencies() -> RuntimeControlRoutesDependencies:
    return RuntimeControlRoutesDependencies(
        rank_labels=RANK_LABELS,
        engine_runtime=engine_runtime,
        run_in_executor=run_in_executor,
    )


def _runtime_control_routes_binding() -> RuntimeControlRoutesBinding:
    return build_runtime_control_routes_binding(_runtime_control_routes_dependencies())


app.include_router(build_runtime_control_router(_runtime_control_routes_binding))


_gpu_detector = CachedGpuInfo()


def _runtime_info_routes_dependencies() -> RuntimeInfoRoutesDependencies:
    return RuntimeInfoRoutesDependencies(
        server_rev=SERVER_REV,
        host=SERVER_HOST,
        port=SERVER_PORT,
        get_access_urls=get_access_urls,
        engine=engine,
        engine_runtime=engine_runtime,
        engine_state_snapshot=_engine_state_snapshot,
        card_config_service=card_config_service,
        no_katago=NO_KATAGO,
        static_dir=STATIC_DIR,
        gpu_detector=_gpu_detector,
        run_in_executor=run_in_executor,
        large_model_path=KATAGO_MODEL_LARGE,
        active_games=active_games,
        generate_sgf=generate_sgf,
    )


def _runtime_info_routes_binding() -> RuntimeInfoRoutesBinding:
    return build_runtime_info_routes_binding(_runtime_info_routes_dependencies())


app.include_router(build_runtime_info_router(_runtime_info_routes_binding))


async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


def _engine_gateway_dependencies() -> EngineGatewayDependencies:
    return EngineGatewayDependencies(
        engine=engine,
        base_dir=BASE_DIR,
        get_game_visits=get_game_visits,
        gtp_to_coord=gtp_to_coord,
        run_in_executor=run_in_executor,
        log_fn=print,
        traceback_fn=traceback.print_exc,
    )


engine_gateway = build_engine_gateway(
    _engine_gateway_dependencies(),
    EngineRuntimeGateway,
)


def _engine_gateway_binding() -> EngineGatewayBinding:
    return build_engine_gateway_binding(_engine_gateway_dependencies())


def _engine_gateway_runtime() -> EngineGatewayRuntime:
    return build_engine_gateway_runtime(engine_gateway, _engine_gateway_dependencies())


def _bind_engine_gateway_runtime() -> None:
    bind_engine_gateway_adapter(_engine_gateway_runtime())


async def _send_engine_command(command: str) -> str:
    return await send_engine_command_adapter(_engine_gateway_runtime(), command)


def _undo_engine_move_locked() -> None:
    with engine.command_lock:
        engine._send_command_locked("undo")


async def _sync_engine_komi(game: GoGame) -> None:
    await sync_engine_komi_adapter(_engine_gateway_runtime(), game)


def _ai_move_service_dependencies() -> AiMoveServiceDependencies:
    return AiMoveServiceDependencies(
        engine=engine,
        run_in_executor=run_in_executor,
        engine_log=_engine_log,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )


ai_move_service = build_ai_move_service(
    _ai_move_service_dependencies(),
    AiMoveService,
)


def _ai_move_service_binding() -> AiMoveServiceBinding:
    return build_ai_move_service_binding(_ai_move_service_dependencies())


def _ai_move_service_runtime() -> AiMoveServiceRuntime:
    return build_ai_move_service_runtime(ai_move_service, _ai_move_service_dependencies())


def _bind_ai_move_service_runtime():
    bind_ai_move_service_adapter(_ai_move_service_runtime())


def _ws_runtime_deps() -> WebSocketRuntimeDeps:
    return WebSocketRuntimeDeps(
        active_games=active_games,
        engine=engine,
        run_in_executor=run_in_executor,
        GoGame=GoGame,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )


def _ws_engine_deps() -> WebSocketEngineDeps:
    return WebSocketEngineDeps(
        engine_state_snapshot=_engine_state_snapshot,
        start_engine_background=engine_runtime.start_background,
        get_game_visits=get_game_visits,
        sync_board_to_katago=_sync_board_to_katago,
    )


def _ws_card_selection_deps() -> WebSocketCardSelectionDeps:
    return WebSocketCardSelectionDeps(
        reload_live_card_config=reload_live_card_config,
        pick_rogue_choices=pick_rogue_choices,
        pick_ultimate_choices=pick_ultimate_choices,
        pick_challenge_beta_choices=pick_challenge_beta_choices,
        pick_ai_rogue_card=pick_ai_rogue_card,
        pick_ai_ultimate_card=pick_ai_ultimate_card,
    )


def _ws_mode_flow_deps() -> WebSocketModeFlowDeps:
    return WebSocketModeFlowDeps(
        apply_challenge_rogue_loadout=_apply_challenge_rogue_loadout,
        activate_rogue_card=_activate_rogue_card,
        activate_ai_rogue_card=_activate_ai_rogue_card,
        ai_move=_ai_move,
        ultimate_ai_move=_ultimate_ai_move,
        ultimate_force_score=_ultimate_force_score,
        run_coach_turn_if_needed=_run_coach_turn_if_needed,
        run_ai_observer_loop=_run_ai_observer_loop,
    )


def _ws_rule_effect_deps() -> WebSocketRuleEffectDeps:
    return WebSocketRuleEffectDeps(
        challenge_remaining=_challenge_remaining,
        challenge_zone_points=_challenge_zone_points,
        rogue_has=_rogue_has,
        get_ai_rogue_forbidden_points=_get_ai_rogue_forbidden_points,
        ultimate_get_territory_forbidden=_ultimate_get_territory_forbidden,
        record_ultimate_player_action=_record_ultimate_player_action,
        check_capture_foul=_check_capture_foul,
        count_stones=_count_stones,
        apply_ultimate_effect=_apply_ultimate_effect,
        resolve_pending_ultimate_shadow_links=_resolve_pending_ultimate_shadow_links,
        apply_player_rogue_move_effects=_apply_player_rogue_move_effects,
        apply_ai_rogue_response_effects=_apply_ai_rogue_response_effects,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        finish_ultimate_quickthink_turn=_finish_ultimate_quickthink_turn,
        pick_joseki_targets=_pick_joseki_targets,
        random_hidden_center=_random_hidden_center,
        diamond_points=_diamond_points,
    )


def _ws_context_deps() -> WebSocketContextDeps:
    return WebSocketContextDeps(
        runtime=_ws_runtime_deps(),
        engine_control=_ws_engine_deps(),
        card_selection=_ws_card_selection_deps(),
        mode_flow=_ws_mode_flow_deps(),
        rule_effects=_ws_rule_effect_deps(),
    )


def _ws_context_binding() -> WebSocketContextBinding:
    return build_websocket_context_binding(_ws_context_deps())


def _websocket_routes_dependencies() -> WebSocketRoutesDependencies:
    return WebSocketRoutesDependencies(
        runtime=WebSocketRoutesRuntimeFns(
            active_games=active_games,
            action_handlers=WS_ACTION_HANDLERS,
            analyze_position=_analyze_current_position,
            websocket_context_binding=_ws_context_binding,
        ),
    )


def _websocket_routes_binding() -> WebSocketRoutesBinding:
    return build_websocket_routes_binding(_websocket_routes_dependencies())


app.include_router(build_websocket_router(_websocket_routes_binding))


def _record_ultimate_turn(game: GoGame) -> None:
    record_ultimate_turn_adapter(game)


def _record_ultimate_player_action(game: GoGame) -> None:
    record_ultimate_player_action_adapter(
        game,
        record_ultimate_turn_fn=_record_ultimate_turn,
    )


def _finish_ultimate_quickthink_turn(game: GoGame) -> None:
    finish_ultimate_quickthink_turn_adapter(game)


def _capture_foul_dependencies() -> CaptureFoulDependencies:
    return CaptureFoulDependencies(
        runtime=CaptureFoulRuntimeFns(
            sync_komi=_sync_engine_komi,
            sync_board=_sync_board_to_katago,
            pick_best_point=_pick_best_point,
            spawn_bonus_points=_spawn_bonus_points,
            coord_to_gtp=coord_to_gtp,
        ),
    )


def _capture_foul_binding() -> CaptureFoulBinding:
    return build_capture_foul_binding(_capture_foul_dependencies())


async def _check_capture_foul(game: GoGame, send_fn, offender: str, captured: int, *, ultimate: bool) -> None:
    """Track capture-foul progress and penalise when threshold is met.

    The card only punishes the *opponent* of the card holder:
      - Rogue: player picks the card → only the AI is punished.
      - Ultimate: whoever picked the card → only the other side is punished.
    ``offender`` is the colour that just captured stones.
    """
    await check_capture_foul_violation_adapter(
        game,
        send_fn,
        offender,
        captured,
        ultimate=ultimate,
        binding=_capture_foul_binding(),
    )


def _pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_mask_adapter(size, rng)


def _pick_fog_point(game, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_point_adapter(game, rng)


def _get_player_bonus_forbidden_points(game: GoGame, color: str) -> set[tuple[int, int]]:
    return get_player_bonus_forbidden_points_adapter(game, color)


async def _estimate_side_winrate(game: GoGame, color: str) -> float:
    return await engine_gateway_estimate_side_winrate(
        _engine_gateway_runtime(),
        game,
        color,
        sync_board=_sync_board_to_katago,
    )


def _line_trigger_dependencies() -> LineTriggerDependencies:
    return LineTriggerDependencies(
        effects=LineTriggerEffectFns(
            apply_rogue_five_in_row=apply_rogue_five_in_row,
            apply_rogue_last_stand=apply_rogue_last_stand,
            apply_ultimate_last_stand=apply_ultimate_last_stand,
            apply_ultimate_five_in_row=apply_ultimate_five_in_row,
        ),
        runtime=LineTriggerRuntimeFns(
            shuffle_points=random.shuffle,
            should_bonus_derivative=_challenge_should_bonus_derivative,
            engine_ready=lambda: engine.ready,
            sync_board=_sync_board_to_katago,
            estimate_side_winrate=_estimate_side_winrate,
            make_rng=lambda: random.Random(time.time_ns()),
            get_forbidden_points=_get_player_bonus_forbidden_points,
        ),
        tuning=LineTriggerTuning(
            rogue_five_in_row_support_stones=ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
            rogue_last_stand_clear_count=ROGUE_LAST_STAND_CLEAR_COUNT,
            rogue_last_stand_spawn_count=ROGUE_LAST_STAND_SPAWN_COUNT,
            rogue_last_stand_threshold=ROGUE_LAST_STAND_THRESHOLD,
            ultimate_last_stand_threshold=ULTIMATE_LAST_STAND_THRESHOLD,
        ),
    )


def _rogue_five_in_row_binding() -> RogueFiveInRowBinding:
    return build_rogue_five_in_row_binding(_line_trigger_dependencies())


async def _trigger_rogue_five_in_row(game: GoGame, send_fn, color: str):
    await trigger_rogue_five_in_row_adapter(
        game,
        send_fn,
        color,
        _rogue_five_in_row_binding(),
    )


def _rogue_last_stand_binding() -> RogueLastStandBinding:
    return build_rogue_last_stand_binding(_line_trigger_dependencies())


async def _trigger_rogue_last_stand(
    game: GoGame,
    send_fn,
    color: str,
    center: tuple[int, int],
):
    await trigger_rogue_last_stand_adapter(
        game,
        send_fn,
        color,
        center,
        _rogue_last_stand_binding(),
    )


def _ultimate_last_stand_binding() -> UltimateLastStandBinding:
    return build_ultimate_last_stand_binding(_line_trigger_dependencies())


async def _trigger_ultimate_last_stand(game: GoGame, send_fn, color: str):
    return await trigger_ultimate_last_stand_adapter(
        game,
        send_fn,
        color,
        _ultimate_last_stand_binding(),
    )


def _ultimate_five_in_row_binding() -> UltimateFiveInRowBinding:
    return build_ultimate_five_in_row_binding(_line_trigger_dependencies())


async def _trigger_ultimate_five_in_row(game: GoGame, send_fn, color: str):
    return await trigger_ultimate_five_in_row_adapter(
        game,
        send_fn,
        color,
        _ultimate_five_in_row_binding(),
    )


def _player_non_pass_coords(game: GoGame, color: str, limit: Optional[int] = None) -> list[tuple[int, int]]:
    return player_non_pass_coords_adapter(game, color, gtp_to_coord, limit=limit)


async def _resolve_pending_ultimate_shadow_links(game: GoGame, send_fn) -> bool:
    result = resolve_pending_shadow_links(
        game,
        coord_to_gtp=coord_to_gtp,
        line_points_between=_line_points_between,
    )
    for message in result.messages:
        await send_fn({"type": "rogue_event", "msg": message})
    return result.modified


def _get_ai_rogue_forbidden_points(game: GoGame) -> list[tuple[int, int]]:
    return get_ai_rogue_forbidden_points_adapter(game)


def _challenge_runtime_dependencies() -> ChallengeRuntimeDependencies:
    return ChallengeRuntimeDependencies(
        flow_runtime=ChallengeFlowRuntimeFns(
            roll_random=random.random,
            weaken_rank_one_step=weaken_rank_one_step,
            engine_ready=lambda: engine.ready,
            get_game_visits=get_game_visits,
            run_in_executor=run_in_executor,
            set_engine_visits=engine.set_visits,
        ),
        flow_tuning=ChallengeFlowTuning(
            trap_extra_turn_chance=CHALLENGE_TRAP_EXTRA_TURN_CHANCE,
            restriction_decay_chance=CHALLENGE_RESTRICTION_DECAY_CHANCE,
            rank_labels=RANK_LABELS,
            challenge_set_min_count=CHALLENGE_SET_MIN_COUNT,
        ),
        loadout_runtime=ChallengeLoadoutRuntimeFns(
            apply_loadout=apply_challenge_rogue_loadout_state,
            card_ids_fn=rogue_card_ids,
            get_rogue_card_fn=get_rogue_card,
            active_use_bonus_fn=_challenge_active_use_bonus,
            challenge_zone_points_fn=_challenge_zone_points,
            choose_corner=lambda: random.randint(0, 3),
            make_rng=lambda: random.Random(time.time_ns()),
            get_blackhole_points_fn=_get_blackhole_points,
            get_golden_corner_points_fn=_get_golden_corner_points,
            pick_joseki_targets_fn=_pick_joseki_targets,
            random_hidden_center_fn=_random_hidden_center,
            diamond_points_fn=_diamond_points,
            sync_engine_komi=_sync_engine_komi,
            emit_set_bonus_status=_challenge_emit_set_bonus_status,
        ),
        loadout_tuning=ChallengeLoadoutTuning(
            golden_corner_span=ROGUE_GOLDEN_CORNER_SPAN,
            joseki_target_count=ROGUE_JOSEKI_TARGET_COUNT,
            godhand_radius=ROGUE_GODHAND_RADIUS,
        ),
    )


def _challenge_flow_binding() -> ChallengeFlowBinding:
    return build_challenge_flow_binding(_challenge_runtime_dependencies())


def _challenge_loadout_binding() -> ChallengeLoadoutBinding:
    return build_challenge_loadout_binding(_challenge_runtime_dependencies())


async def _challenge_apply_trap_bonus(game: GoGame, send_fn, source_name: str) -> None:
    await apply_challenge_trap_bonus_adapter(
        game,
        send_fn,
        source_name,
        _challenge_flow_binding(),
    )


async def _challenge_maybe_reduce_ai_level(game: GoGame, send_fn) -> None:
    await maybe_reduce_challenge_level(
        game,
        send_fn,
        _challenge_flow_binding(),
    )


async def _challenge_emit_set_bonus_status(game: GoGame, send_fn) -> None:
    await emit_challenge_set_status(
        game,
        send_fn,
        _challenge_flow_binding(),
    )


def _refresh_ai_rogue_player_turn(game: GoGame):
    refresh_ai_rogue_player_turn_adapter(
        game,
        pick_fog_mask_fn=_pick_fog_mask,
        pick_fog_point_fn=_pick_fog_point,
    )


def _prepare_player_turn_modifiers(game: GoGame):
    prepare_player_turn_modifiers_adapter(
        game,
        refresh_ai_rogue_player_turn_fn=_refresh_ai_rogue_player_turn,
    )


def _clear_player_turn_modifiers(game: GoGame):
    clear_player_turn_modifiers_adapter(
        game,
        finish_ultimate_quickthink_turn_fn=_finish_ultimate_quickthink_turn,
    )


async def _pick_analysis_point(game: GoGame, color: str, *, start_index: int = 0) -> Optional[tuple[int, int]]:
    return await engine_gateway_pick_analysis_point(
        _engine_gateway_runtime(),
        game,
        color,
        start_index=start_index,
    )


async def _pick_second_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=1)


async def _pick_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=0)


def _rogue_activation_dependencies() -> RogueActivationDependencies:
    return RogueActivationDependencies(
        effects=RogueActivationEffectFns(
            get_card=get_rogue_card,
            apply_player_activation=apply_rogue_card_activation,
            apply_ai_activation=apply_ai_rogue_card_activation,
        ),
        runtime=RogueActivationRuntimeFns(
            coord_to_gtp=coord_to_gtp,
            choose_corner=lambda: random.randint(0, 3),
            make_rng=lambda: random.Random(time.time_ns()),
            get_blackhole_points=_get_blackhole_points,
            get_golden_corner_points=_get_golden_corner_points,
            pick_joseki_targets=_pick_joseki_targets,
            random_hidden_center=_random_hidden_center,
            diamond_points=_diamond_points,
            sync_engine_komi=_sync_engine_komi,
            refresh_ai_rogue_player_turn=_refresh_ai_rogue_player_turn,
        ),
        tuning=RogueActivationTuning(
            golden_corner_span=ROGUE_GOLDEN_CORNER_SPAN,
        ),
    )


def _rogue_card_activation_binding() -> RogueCardActivationBinding:
    return build_rogue_card_activation_binding(_rogue_activation_dependencies())


def _ai_rogue_card_activation_binding() -> AiRogueCardActivationBinding:
    return build_ai_rogue_card_activation_binding(_rogue_activation_dependencies())


async def _activate_rogue_card(game: GoGame, send_fn, card_id: str):
    """Apply immediate effects when the player picks a rogue card."""
    await activate_rogue_card_adapter(
        game,
        send_fn,
        card_id,
        _rogue_card_activation_binding(),
    )


async def _activate_ai_rogue_card(game: GoGame, send_fn, card_id: str):
    await activate_ai_rogue_card_adapter(
        game,
        send_fn,
        card_id,
        _ai_rogue_card_activation_binding(),
    )


async def _apply_challenge_rogue_loadout(game: GoGame, send_fn):
    await apply_challenge_loadout(
        game,
        send_fn,
        _challenge_loadout_binding(),
    )


def _rogue_move_effect_dependencies() -> RogueMoveEffectDependencies:
    return RogueMoveEffectDependencies(
        effects=RogueMoveEffectFns(
            has_rogue=_rogue_has,
            apply_player_board_effects=apply_player_rogue_board_effects,
            apply_ai_response_board_effects=apply_ai_rogue_response_board_effects,
        ),
        runtime=RogueMoveEffectRuntimeFns(
            sync_engine_komi=_sync_engine_komi,
            coord_to_gtp=coord_to_gtp,
            gtp_to_coord=gtp_to_coord,
            engine_ready=lambda: engine.ready,
            sync_board_to_katago=_sync_board_to_katago,
            challenge_apply_trap_bonus=_challenge_apply_trap_bonus,
            trigger_five_in_row=_trigger_rogue_five_in_row,
            trigger_last_stand=_trigger_rogue_last_stand,
            challenge_maybe_reduce_ai_level=_challenge_maybe_reduce_ai_level,
            shuffle_points=random.shuffle,
        ),
        tuning=RogueMoveEffectTuning(
            erosion_shift=ROGUE_EROSION_SHIFT,
        ),
    )


def _player_rogue_move_effect_binding() -> PlayerRogueMoveEffectBinding:
    return build_player_rogue_move_effect_binding(_rogue_move_effect_dependencies())


async def _apply_player_rogue_move_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str, captured: int):
    """Apply player-side rogue effects after a successful move."""
    await apply_player_rogue_move_effects_adapter(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        captured=captured,
        binding=_player_rogue_move_effect_binding(),
    )


def _ai_rogue_response_effect_binding() -> AiRogueResponseEffectBinding:
    return build_ai_rogue_response_effect_binding(_rogue_move_effect_dependencies())


async def _apply_ai_rogue_response_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str):
    await apply_ai_rogue_response_effects_adapter(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        binding=_ai_rogue_response_effect_binding(),
    )


def _sync_board_to_katago_locked(game: GoGame):
    """Reset KataGo board to match game.board using SGF loadsgf.
    Must be called while holding engine.command_lock."""
    engine_gateway_sync_board_locked(_engine_gateway_runtime(), game)


def _has_gtp_unsafe_whitespace(path: str) -> bool:
    return EngineRuntimeGateway.has_gtp_unsafe_whitespace(path)


def _gtp_safe_sync_sgf_path(game: GoGame) -> str:
    """Return a writable SGF path that KataGo GTP will not split on spaces."""
    return engine_gateway_gtp_safe_sync_sgf_path(_engine_gateway_runtime(), game)


async def _sync_board_to_katago(game: GoGame):
    """Reset KataGo board to match game.board (async wrapper)."""
    await engine_gateway_sync_board(_engine_gateway_runtime(), game)


def _empty_analysis_result() -> dict:
    return engine_gateway_empty_analysis_result(_engine_gateway_runtime())


async def _analyze_current_position(game: GoGame, color: Optional[str] = None) -> dict:
    return await engine_gateway_analyze_current_position(
        _engine_gateway_runtime(),
        game,
        color=color,
        sync_board=_sync_board_to_katago,
    )


def _ultimate_get_territory_forbidden(game: GoGame, for_color_val: int) -> set:
    """Get forbidden points for a color due to opponent's 绝对领地 card.
    for_color_val: the color (1=B,2=W) that wants to PLACE a stone."""
    return get_ultimate_territory_forbidden_points(game, for_color_val)


def _ultimate_effect_dependencies() -> UltimateEffectDependencies:
    return UltimateEffectDependencies(
        effects=UltimateEffectFns(
            apply_effect=apply_ultimate_card_effect_state,
            apply_foolish_wisdom_wave=apply_ultimate_foolish_wisdom_wave,
        ),
        runtime=UltimateEffectRuntimeFns(
            coord_to_gtp=coord_to_gtp,
            gtp_to_coord=gtp_to_coord,
            trigger_five_in_row=_trigger_ultimate_five_in_row,
            trigger_last_stand=_trigger_ultimate_last_stand,
            make_rng=lambda: random.Random(time.time_ns()),
            sleep=asyncio.sleep,
        ),
        tuning=UltimateEffectTuning(
            foolish_chain_delay=ULTIMATE_FOOLISH_CHAIN_DELAY,
        ),
    )


def _ultimate_effect_binding() -> UltimateEffectBinding:
    return build_ultimate_effect_binding(_ultimate_effect_dependencies())


async def _apply_ultimate_effect(game: GoGame, send_fn, x: int, y: int,
                                  color: str, card: str):
    """Apply a single ultimate card effect after a stone is placed at (x,y).
    Returns True if board was modified (needs KataGo sync)."""
    return await apply_ultimate_effect_adapter(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        card=card,
        binding=_ultimate_effect_binding(),
    )


async def _ultimate_force_score(game: GoGame, send_fn):
    """Force game end in ultimate mode — count stones for scoring."""
    await finalize_ultimate_score(game, send_fn)


def _is_suspicious_ai_pass(game: GoGame, gtp_move: str, color: str) -> bool:
    return is_suspicious_ai_pass_state(game, gtp_move, color)


async def _pick_nonpass_fallback_move(
    game: GoGame,
    color: str,
    visits: int,
    forbidden: Optional[set[tuple[int, int]]] = None,
) -> Optional[str]:
    return await ai_service_pick_nonpass_fallback_move(
        _ai_move_service_runtime(),
        game,
        color,
        visits,
        forbidden,
    )


async def _pick_ranked_legal_move(
    game: GoGame,
    color: str,
    visits: int,
    forbidden: Optional[set[tuple[int, int]]] = None,
    *,
    time_limit: float = 1.5,
) -> Optional[str]:
    return await ai_service_pick_ranked_legal_move(
        _ai_move_service_runtime(),
        game,
        color,
        visits,
        forbidden,
        time_limit=time_limit,
    )


def _plan_ultimate_ai_search(game: GoGame):
    return plan_ultimate_ai_search(
        game,
        get_territory_forbidden=_ultimate_get_territory_forbidden,
        get_game_visits=get_game_visits,
    )


async def _run_next_ultimate_ai_move(game: GoGame, send_fn, next_allow_double_bonus: bool) -> None:
    await _ultimate_ai_move(
        game,
        send_fn,
        allow_double_bonus=next_allow_double_bonus,
    )


def _ultimate_ai_dependencies() -> UltimateAiDependencies:
    return UltimateAiDependencies(
        selection_runtime=UltimateAiSelectionRuntimeFns(
            engine_ready=lambda: engine.ready,
            sync_board_to_katago=_sync_board_to_katago,
            plan_search=_plan_ultimate_ai_search,
            engine=engine,
            run_in_executor=run_in_executor,
            get_game_visits=get_game_visits,
            log_fn=_engine_log,
        ),
        selection_moves=UltimateAiSelectionMoveFns(
            no_resign_move=_ai_move_no_resign,
            pick_ranked_legal_move=_pick_ranked_legal_move,
            pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
            retry_avoiding_ko=_ai_retry_avoiding_ko,
            is_suspicious_ai_pass=_is_suspicious_ai_pass,
            resolve_occupied_ai_move=resolve_occupied_ai_move,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
        ),
        finish=UltimateAiFinishFns(
            apply_ai_move_result=apply_ultimate_ai_move_result_state,
            record_ultimate_turn=_record_ultimate_turn,
            check_capture_foul=_check_capture_foul,
            post_move_effects=apply_ultimate_ai_post_move_effects,
            count_stones=_count_stones,
            apply_ultimate_effect=_apply_ultimate_effect,
            resolve_pending_ultimate_shadow_links=_resolve_pending_ultimate_shadow_links,
            sync_board_to_katago=_sync_board_to_katago,
            choose_bonus_turn=choose_ultimate_ai_bonus_turn_state,
            run_bonus_turn=_run_ultimate_ai_bonus_turn,
            finish_normal_turn=finish_ultimate_ai_normal_turn_state,
            prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
            force_score=_ultimate_force_score,
        ),
        bonus=UltimateAiBonusFns(
            start_bonus_turn=start_ultimate_ai_bonus_turn_state,
            run_next_ai_move=_run_next_ultimate_ai_move,
        ),
        tuning=UltimateAiTuning(
            chain_chance=ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
            chain_random=random.random,
        ),
    )


def _ultimate_ai_bonus_turn_binding() -> UltimateAiBonusTurnBinding:
    return build_ultimate_ai_bonus_turn_binding(_ultimate_ai_dependencies())


async def _run_ultimate_ai_bonus_turn(game: GoGame, send_fn, color: str, bonus_turn) -> bool:
    return await run_ultimate_ai_bonus_turn_adapter(
        game,
        send_fn,
        color,
        bonus_turn,
        _ultimate_ai_bonus_turn_binding(),
    )


def _ultimate_ai_move_selection_binding() -> UltimateAiMoveSelectionBinding:
    return build_ultimate_ai_move_selection_binding(_ultimate_ai_dependencies())


def _ultimate_ai_turn_finish_binding() -> UltimateAiTurnFinishBinding:
    return build_ultimate_ai_turn_finish_binding(_ultimate_ai_dependencies())


async def _ultimate_ai_move(game: GoGame, send_fn,
                            allow_double_bonus: bool = True):
    """AI move in ultimate mode - generates move, applies AI's card effect."""
    selection = await select_ultimate_ai_move(
        game,
        _ultimate_ai_move_selection_binding(),
    )
    if selection is None:
        return

    await finish_selected_ultimate_ai_move(
        game,
        send_fn,
        selection,
        allow_double_bonus=allow_double_bonus,
        binding=_ultimate_ai_turn_finish_binding(),
    )


def _generated_ai_runtime_dependencies() -> GeneratedAiRuntimeDependencies:
    return GeneratedAiRuntimeDependencies(
        candidate=GeneratedMoveCandidateFns(
            choose_candidate=choose_ai_move_candidate,
            choose_avoid_move=_ai_move_avoid_points,
            analyze_position=_analyze_current_position,
            choose_style_move=choose_ai_style_move,
            generate_move=_ai_generate_move,
            gtp_to_coord=gtp_to_coord,
            log_error=print,
        ),
        preparation=GeneratedMovePreparationFns(
            prepare_move=prepare_generated_ai_move,
            apply_suspicious_pass_fallback_fn=apply_suspicious_pass_fallback,
            is_suspicious_pass=_is_suspicious_ai_pass,
            pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
            undo_engine_move=_undo_engine_move_locked,
            run_engine_command=_send_engine_command,
            log_event=_engine_log,
            resolve_resign_move=resolve_ai_resign_move,
            no_resign_move=_ai_move_no_resign,
            apply_slip_move=apply_slip_ai_move,
            roll_random=random.random,
            choose_point=random.choice,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
            adjacent_points=_adjacent_points,
            retry_ko_move=retry_ai_move_avoiding_ko,
            retry_avoiding_ko=_ai_retry_avoiding_ko,
        ),
        finish=GeneratedMoveFinishFns(
            finish_move=finish_prepared_ai_move,
            apply_placement_effects=apply_ai_move_placement_effects,
            finish_turn_response=finish_ai_turn_response,
            gtp_to_coord=gtp_to_coord,
            sync_board_to_engine=_sync_board_to_katago,
            engine_is_ready=lambda: engine.ready,
            apply_move_to_board=apply_ai_move_to_board,
            apply_sansan_trap_counter=try_apply_sansan_trap_counter,
            try_no_regret_bonus=try_apply_no_regret_bonus,
            get_sansan_points=_get_sansan_points,
            adjacent_points=_adjacent8_points,
            shuffle_points=random.shuffle,
            spawn_bonus_points=_spawn_bonus_points,
            coord_to_gtp=coord_to_gtp,
            apply_trap_bonus=_challenge_apply_trap_bonus,
            roll_random=random.random,
            has_rogue_card=_rogue_has,
            pick_best_point=_pick_best_point,
            check_capture_foul=_check_capture_foul,
            prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
            apply_erosion_counter=apply_erosion_komi_counter,
            run_erosion_command=_send_engine_command,
            erosion_message=lambda capture_count, komi: f"蚕食反制：AI 提掉了 {capture_count} 子，当前贴目变为 {komi}",
            finalize_double_pass=try_finalize_double_pass,
            send_ai_move_response=send_ai_move_and_run_coach,
            run_coach_turn_if_needed=_run_coach_turn_if_needed,
        ),
        finish_tuning=GeneratedMoveFinishTuning(
            trap_stones=ROGUE_SANSAN_TRAP_STONES,
            no_regret_chance=ROGUE_NO_REGRET_CHANCE,
            erosion_shift=ROGUE_EROSION_SHIFT,
        ),
        turn=GeneratedAiTurnFns(
            rogue_forbidden_points=rogue_forbidden_points,
            challenge_zone_points=_challenge_zone_points,
            try_finish_generated_ai_move=try_finish_generated_ai_move,
        ),
    )


def _generated_ai_move_candidate_binding() -> GeneratedMoveCandidateBinding:
    return build_generated_move_candidate_binding(_generated_ai_runtime_dependencies())


def _generated_ai_move_preparation_binding() -> GeneratedMovePreparationBinding:
    return build_generated_move_preparation_binding(_generated_ai_runtime_dependencies())


def _generated_ai_move_finish_binding(run_engine_command) -> GeneratedMoveFinishBinding:
    return build_generated_move_finish_binding(
        _generated_ai_runtime_dependencies(),
        run_engine_command,
    )


def _generated_ai_turn_binding() -> GeneratedAiTurnBinding:
    return build_generated_ai_turn_binding(
        _generated_ai_runtime_dependencies(),
        candidate_binding=_generated_ai_move_candidate_binding,
        preparation_binding=_generated_ai_move_preparation_binding,
        finish_binding=_generated_ai_move_finish_binding,
    )


def _choose_shadow_restriction(game_arg, color_arg: str, ai_count: int):
    return shadow_followup_points(
        game_arg,
        color_arg,
        ai_count,
        gtp_to_coord=gtp_to_coord,
    )


def _rogue_ai_turn_dependencies() -> RogueAiTurnDependencies:
    return RogueAiTurnDependencies(
        shared=RogueAiTurnSharedFns(
            roll_random=random.random,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
            prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
            check_capture_foul=_check_capture_foul,
            finish_ai_move=_finish_ai_move,
        ),
        forced=ForcedRogueAiTurnFns(
            try_finish_forced_rogue_ai_move=try_finish_forced_rogue_ai_move,
            mirror_coord=_mirror_coord,
            finalize_forced_pass=finalize_forced_ai_pass,
            finalize_forced_stone=try_finalize_forced_ai_stone,
            apply_puppet_move=try_apply_puppet_ai_move,
        ),
        restriction=RestrictionRogueAiTurnFns(
            try_finish_rogue_restriction_ai_move=try_finish_rogue_restriction_ai_move,
            choose_tengen_target=choose_tengen_target,
            tengen_followup_points=tengen_followup_points,
            gravity_allowed_points=gravity_allowed_points,
            lowline_allowed_points=lowline_allowed_points,
            sansan_opening_restriction=sansan_opening_restriction,
            choose_allowed_move=_ai_move_avoid_points_allow_only,
            choose_avoid_move=_ai_move_avoid_points,
            finish_allowed_restriction_move=try_finish_allowed_restriction_move,
            finish_sansan_restriction_move=try_finish_sansan_restriction_move,
        ),
        shadow=ShadowRogueAiTurnFns(
            try_finish_shadow_restriction_move=try_finish_shadow_restriction_move,
            choose_restriction=_choose_shadow_restriction,
            choose_allowed_move=_ai_move_avoid_points_allow_only,
        ),
        suboptimal=SuboptimalRogueAiTurnFns(
            try_finish_suboptimal_rogue_move=try_finish_suboptimal_rogue_move,
            choose_suboptimal_move=_ai_move_suboptimal,
        ),
        tuning=RogueAiTurnTuning(
            dice_pass_chance=ROGUE_DICE_PASS_CHANCE,
            mirror_chance=ROGUE_MIRROR_CHANCE,
        ),
    )


def _forced_rogue_ai_turn_binding() -> ForcedRogueAiTurnBinding:
    return build_forced_rogue_ai_turn_binding(_rogue_ai_turn_dependencies())


async def _try_finish_forced_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    run_engine_command,
) -> bool:
    return await try_finish_forced_rogue_ai_turn_adapter(
        game,
        send_fn,
        turn,
        run_engine_command,
        _forced_rogue_ai_turn_binding(),
    )


def _restriction_rogue_ai_turn_binding() -> RestrictionRogueAiTurnBinding:
    return build_restriction_rogue_ai_turn_binding(_rogue_ai_turn_dependencies())


async def _try_finish_rogue_restriction_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
    run_engine_command,
) -> bool:
    return await try_finish_restriction_rogue_ai_turn_adapter(
        game,
        send_fn,
        turn,
        ai_plan=ai_plan,
        run_engine_command=run_engine_command,
        binding=_restriction_rogue_ai_turn_binding(),
    )


def _shadow_rogue_ai_turn_binding() -> ShadowRogueAiTurnBinding:
    return build_shadow_rogue_ai_turn_binding(_rogue_ai_turn_dependencies())


async def _try_finish_shadow_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
) -> bool:
    return await try_finish_shadow_rogue_ai_turn_adapter(
        game,
        send_fn,
        turn,
        ai_plan,
        _shadow_rogue_ai_turn_binding(),
    )


def _suboptimal_rogue_ai_turn_binding() -> SuboptimalRogueAiTurnBinding:
    return build_suboptimal_rogue_ai_turn_binding(_rogue_ai_turn_dependencies())


async def _try_finish_suboptimal_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
) -> bool:
    return await try_finish_suboptimal_rogue_ai_turn_adapter(
        game,
        send_fn,
        turn,
        ai_plan,
        _suboptimal_rogue_ai_turn_binding(),
    )


async def _try_finish_generated_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
    run_engine_command,
) -> bool:
    return await try_finish_generated_ai_turn_adapter(
        game,
        send_fn,
        turn,
        ai_plan,
        run_engine_command,
        _generated_ai_turn_binding(),
    )


def _plan_ai_turn_search(game: GoGame, turn: AiTurnSnapshot) -> AiMovePlan:
    return plan_rogue_ai_search(
        game,
        turn.rogue_cards,
        move_count=turn.move_count,
        ai_move_count=turn.ai_move_count,
        get_game_visits=get_game_visits,
        weaken_rank=weaken_rank,
    )


async def _refresh_ai_turn_fog_restriction(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    _ai_plan: AiMovePlan,
) -> None:
    await refresh_fog_restriction_points(
        game,
        send_fn,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        make_rng=lambda: random.Random(time.time_ns()),
        challenge_zone_points=_challenge_zone_points,
        pick_fog_mask=_pick_fog_mask,
        pick_fog_point=_pick_fog_point,
    )


def _ai_turn_dependencies() -> AiTurnDependencies:
    def snapshot_current_turn(game, _rogue_card_ids_fn):
        return snapshot_ai_turn(game, _rogue_card_ids)

    async def finish_forced_with_current_engine(game, send_fn, turn, _run_engine_command):
        return await _try_finish_forced_rogue_ai_turn(
            game,
            send_fn,
            turn,
            _send_engine_command,
        )

    async def finish_restriction_with_current_engine(
        game,
        send_fn,
        turn,
        plan,
        _run_engine_command,
    ):
        return await _try_finish_rogue_restriction_ai_turn(
            game,
            send_fn,
            turn,
            plan,
            _send_engine_command,
        )

    async def finish_generated_with_current_engine(
        game,
        send_fn,
        turn,
        plan,
        _run_engine_command,
    ):
        return await _try_finish_generated_ai_turn(
            game,
            send_fn,
            turn,
            plan,
            _send_engine_command,
        )

    return AiTurnDependencies(
        runtime=AiTurnRuntimeFns(
            engine_ready=lambda: engine.ready,
            sync_board_to_katago=_sync_board_to_katago,
            snapshot_ai_turn=snapshot_current_turn,
            rogue_card_ids=lambda: _rogue_card_ids(),
            run_engine_command=lambda command: _send_engine_command(command),
        ),
        steps=AiTurnStepFns(
            try_finish_forced=finish_forced_with_current_engine,
            plan_search=_plan_ai_turn_search,
            refresh_fog_restriction=_refresh_ai_turn_fog_restriction,
            try_finish_restriction=finish_restriction_with_current_engine,
            try_finish_shadow=_try_finish_shadow_rogue_ai_turn,
            try_finish_suboptimal=_try_finish_suboptimal_rogue_ai_turn,
            try_finish_generated=finish_generated_with_current_engine,
        ),
    )


def _ai_turn_binding() -> AiTurnBinding:
    return build_ai_turn_binding(_ai_turn_dependencies())


async def _ai_move(game: GoGame, send_fn):
    await run_ai_turn_adapter(game, send_fn, _ai_turn_binding())


async def _ai_move_avoid_points(game, color, visits, time_limit, forbidden):
    return await ai_service_avoid_points(
        _ai_move_service_runtime(),
        game,
        color,
        visits,
        time_limit,
        forbidden,
    )


async def _ai_move_avoid_points_allow_only(game, color, visits, time_limit,
                                           allowed: list[tuple[int, int]]):
    return await ai_service_allow_only_points(
        _ai_move_service_runtime(),
        game,
        color,
        visits,
        time_limit,
        allowed,
    )


async def _ai_move_suboptimal(game, color, visits, time_limit, start_idx=2, end_idx=5):
    return await ai_service_suboptimal_move(
        _ai_move_service_runtime(),
        game,
        color,
        visits,
        time_limit,
        start_idx=start_idx,
        end_idx=end_idx,
    )


async def _ai_move_no_resign(game, color: str) -> str:
    return await ai_service_no_resign_move(_ai_move_service_runtime(), game, color)


async def _ai_retry_avoiding_ko(game, color):
    return await ai_service_retry_avoiding_ko(_ai_move_service_runtime(), game, color)


async def _ai_generate_move(color: str, visits: int, time_limit: float) -> str:
    return await ai_service_generate_move(_ai_move_service_runtime(), color, visits, time_limit)


def _coach_dependencies() -> CoachDependencies:
    return CoachDependencies(
        finish=AiFinishMoveRuntimeFns(
            finalize_ai_move=finalize_ai_move,
            gtp_to_coord=gtp_to_coord,
            no_resign_move=_ai_move_no_resign,
            retry_avoiding_ko=_ai_retry_avoiding_ko,
            check_capture_foul=_check_capture_foul,
            prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
            run_engine_command=_send_engine_command,
            run_coach_turn_if_needed=_run_coach_turn_if_needed,
        ),
        choice=CoachMoveChoiceRuntimeFns(
            get_game_visits=get_game_visits,
            generate_ai_style_move=_generate_ai_style_move,
            gtp_to_coord=gtp_to_coord,
            retry_avoiding_ko=_ai_retry_avoiding_ko,
        ),
        turn=CoachTurnRuntimeFns(
            engine_ready=lambda: engine.ready,
            choose_coach_ai_move=_choose_coach_ai_move,
            place_auxiliary_move=_place_auxiliary_ai_move_on_board,
            check_capture_foul=_check_capture_foul,
            apply_player_rogue_move_effects=_apply_player_rogue_move_effects,
            apply_ai_rogue_response_effects=_apply_ai_rogue_response_effects,
            estimate_side_winrate=_estimate_side_winrate,
            ai_move=_ai_move,
        ),
        tuning=CoachTuning(
            coach_visits=ROGUE_COACH_VISITS,
            max_move_time=MAX_MOVE_TIME,
            bonus_threshold=ROGUE_COACH_BONUS_THRESHOLD,
            bonus_turns=ROGUE_COACH_BONUS_TURNS,
        ),
    )


def _ai_finish_move_binding() -> AiFinishMoveBinding:
    return build_ai_finish_move_binding(_coach_dependencies())


async def _finish_ai_move(game, send_fn, color, card, gtp_move, rogue_msg=None):
    """Finalize a rogue-forced AI move: update game state and send messages."""
    await finish_ai_move_adapter(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=gtp_move,
        rogue_msg=rogue_msg,
        binding=_ai_finish_move_binding(),
    )


def _ai_style_move_dependencies() -> AiStyleMoveDependencies:
    return AiStyleMoveDependencies(
        runtime=AiStyleMoveRuntimeFns(
            sync_board_to_katago=_sync_board_to_katago,
            choose_or_generate_style_move=choose_or_generate_ai_style_move,
            analyze_position=_analyze_current_position,
            choose_style_move=choose_ai_style_move,
            generate_move=_ai_generate_move,
            gtp_to_coord=gtp_to_coord,
            play_chosen_move=_send_engine_command,
        ),
    )


def _ai_style_move_binding() -> AiStyleMoveBinding:
    return build_ai_style_move_binding(_ai_style_move_dependencies())


async def _generate_ai_style_move(game: GoGame, color: str, visits: int, time_limit: float) -> str:
    return await generate_ai_style_move_adapter(
        game,
        color=color,
        visits=visits,
        time_limit=time_limit,
        binding=_ai_style_move_binding(),
    )


def _place_auxiliary_ai_move_on_board(
    game: GoGame,
    color: str,
    gtp_move: str,
    coord: tuple[int, int] | None,
) -> AiMovePlacement:
    return place_auxiliary_ai_move_on_board_state(game, color, gtp_move, coord)


def _coach_move_choice_binding() -> CoachMoveChoiceBinding:
    return build_coach_move_choice_binding(_coach_dependencies())


async def _choose_coach_ai_move(game: GoGame, color: str) -> tuple[str, tuple[int, int] | None]:
    return await choose_coach_ai_move_adapter(
        game,
        color,
        _coach_move_choice_binding(),
    )


def _coach_turn_binding() -> CoachTurnBinding:
    return build_coach_turn_binding(_coach_dependencies())


async def _run_coach_turn_if_needed(game: GoGame, send_fn):
    await run_coach_turn_if_needed_adapter(
        game,
        send_fn,
        _coach_turn_binding(),
    )


def _observer_dependencies() -> ObserverDependencies:
    return ObserverDependencies(
        runtime=ObserverRuntimeFns(
            engine_ready=lambda: engine.ready,
            sync_board=_sync_board_to_katago,
            run_engine_command=_send_engine_command,
            gtp_to_coord=gtp_to_coord,
            sleep=asyncio.sleep,
        ),
        moves=ObserverMoveFns(
            get_game_visits=get_game_visits,
            generate_ai_style_move=_generate_ai_style_move,
            is_suspicious_ai_pass=_is_suspicious_ai_pass,
            pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
            place_auxiliary_move=_place_auxiliary_ai_move_on_board,
            place_ai_move_on_board=_apply_observer_ai_move_to_board,
            finish_double_pass=_finish_observer_double_pass,
        ),
        tuning=ObserverTuning(
            opening_move_threshold=OPENING_MOVE_THRESHOLD,
        ),
    )


def _observer_double_pass_binding() -> ObserverDoublePassBinding:
    return build_observer_double_pass_binding(_observer_dependencies())


async def _finish_observer_double_pass(game: GoGame, send_fn) -> bool:
    return await finish_observer_double_pass_adapter(
        game,
        send_fn,
        _observer_double_pass_binding(),
    )


def _observer_move_placement_binding() -> ObserverMovePlacementBinding:
    return build_observer_move_placement_binding(_observer_dependencies())


def _apply_observer_ai_move_to_board(game: GoGame, color: str, gtp_move: str) -> AiMovePlacement:
    return apply_observer_ai_move_to_board_adapter(
        game,
        color,
        gtp_move,
        _observer_move_placement_binding(),
    )


def _ai_observer_loop_binding() -> AiObserverLoopBinding:
    return build_ai_observer_loop_binding(_observer_dependencies())


async def _run_ai_observer_loop(game: GoGame, send_fn):
    try:
        await run_ai_observer_loop_adapter(
            game,
            send_fn,
            _ai_observer_loop_binding(),
        )
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
