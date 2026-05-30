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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import uvicorn
import app.config.gameplay as gameplay_config
import app.runtime.ws_actions as ws_actions_module
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
from app.domain.game_state import GoGame
from app.domain.sgf import generate_sgf
from app.runtime.access_urls import get_access_urls as build_access_urls
from app.runtime.ai_style_adapters import (
    AiStyleMoveBinding,
    generate_ai_style_move as generate_ai_style_move_adapter,
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
from app.runtime.ai_turn_adapters import (
    AiTurnBinding,
    run_ai_turn as run_ai_turn_adapter,
)
from app.runtime.config_api import (
    balance_payload,
    card_config_payload as build_card_config_payload,
    card_config_schema as build_card_config_schema,
    reset_balance_request,
    reset_card_config_request,
    save_balance_request,
    save_card_config_request,
)
from app.runtime.capture_foul_adapters import (
    CaptureFoulBinding,
    check_capture_foul_violation as check_capture_foul_violation_adapter,
)
from app.runtime.challenge_adapters import (
    ChallengeFlowBinding,
    ChallengeLoadoutBinding,
    apply_challenge_loadout,
    apply_challenge_trap_bonus as apply_challenge_trap_bonus_adapter,
    emit_challenge_set_status,
    maybe_reduce_challenge_level,
)
from app.runtime.coach_adapters import (
    AiFinishMoveBinding,
    CoachMoveChoiceBinding,
    CoachTurnBinding,
    choose_coach_ai_move as choose_coach_ai_move_adapter,
    finish_ai_move as finish_ai_move_adapter,
    run_coach_turn_if_needed as run_coach_turn_if_needed_adapter,
)
from app.runtime.engine_control_api import restart_katago_request, stop_katago_request
from app.runtime.engine_gateway_adapters import (
    EngineGatewayRuntime,
    bind_engine_gateway as bind_engine_gateway_adapter,
    send_engine_command as send_engine_command_adapter,
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
from app.runtime.gpu_info import CachedGpuInfo, runtime_gpu_info_payload
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
from app.runtime.no_cache import apply_no_cache_headers_for_html
from app.runtime.observer_adapters import (
    AiObserverLoopBinding,
    ObserverDoublePassBinding,
    ObserverMovePlacementBinding,
    apply_observer_ai_move_to_board as apply_observer_ai_move_to_board_adapter,
    finish_observer_double_pass as finish_observer_double_pass_adapter,
    run_ai_observer_loop as run_ai_observer_loop_adapter,
)
from app.runtime.rank_api import build_rank_options
from app.runtime.rogue_activation_adapters import (
    AiRogueCardActivationBinding,
    RogueCardActivationBinding,
    activate_ai_rogue_card as activate_ai_rogue_card_adapter,
    activate_rogue_card as activate_rogue_card_adapter,
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
from app.runtime.rogue_move_effect_adapters import (
    AiRogueResponseEffectBinding,
    PlayerRogueMoveEffectBinding,
    apply_ai_rogue_response_effects as apply_ai_rogue_response_effects_adapter,
    apply_player_rogue_move_effects as apply_player_rogue_move_effects_adapter,
)
from app.runtime.service_bindings import (
    AiMoveServiceBinding,
    EngineGatewayBinding,
)
from app.runtime.sgf_export import build_sgf_export_response
from app.runtime.static_pages import (
    serve_balance_lab_page,
    serve_card_editor_page,
    serve_react_preview_page,
    serve_root_page,
)
from app.runtime.status_endpoint import build_runtime_status_payload
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
from app.runtime.ultimate_ai_adapters import (
    UltimateAiBonusTurnBinding,
    UltimateAiMoveSelectionBinding,
    UltimateAiTurnFinishBinding,
    finish_selected_ultimate_ai_move,
    run_ultimate_ai_bonus_turn_adapter,
    select_ultimate_ai_move,
)
from app.runtime.ws_context_adapters import (
    WebSocketContextBinding,
    build_websocket_action_context_from_binding,
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
    compute_game_visits,
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
from app.runtime.ws_session import run_websocket_game_session
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
SERVER_REV = "20260430-card-editor-shell"
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
    return compute_game_visits(
        level,
        move_count,
        mode,
        cpu_mode=engine_runtime.cpu_mode,
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


@app.on_event("startup")
async def startup():
    log("[Server] KataGo will start on first game request")


@app.on_event("shutdown")
async def shutdown():
    engine_runtime.handle_app_shutdown()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=False),
          name="static")
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets"), check_dir=False),
          name="assets")


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    return apply_no_cache_headers_for_html(response)


@app.get("/")
async def root():
    return serve_root_page(STATIC_DIR)


@app.get("/react-preview")
async def react_preview():
    return serve_react_preview_page(STATIC_DIR)


@app.get("/balance-lab")
async def balance_lab():
    return serve_balance_lab_page(STATIC_DIR)


@app.get("/card-editor")
async def card_editor():
    return serve_card_editor_page(STATIC_DIR)


@app.get("/api/card-config")
async def get_card_config_payload():
    return build_card_config_payload(card_config_service)


@app.get("/api/card-config/schema")
async def get_card_config_schema():
    return build_card_config_schema(card_config_service)


@app.post("/api/card-config")
async def save_card_config_payload(request: Request):
    return await save_card_config_request(request, card_config_service=card_config_service)


@app.post("/api/card-config/reset")
async def reset_card_config_payload():
    return reset_card_config_request(card_config_service)


@app.get("/api/balance")
async def get_balance_lab_payload():
    return balance_payload(get_balance_editor_payload)


@app.post("/api/balance")
async def save_balance_lab_payload(request: Request):
    return await save_balance_request(
        request,
        save_balance_overrides=save_balance_overrides,
    )


@app.post("/api/balance/reset")
async def reset_balance_lab_payload():
    return reset_balance_request(reset_balance_overrides)


@app.get("/ranks")
async def get_ranks():
    return build_rank_options(RANK_LABELS)


@app.post("/stop_katago")
async def stop_katago():
    """Stop the KataGo engine while keeping the server running."""
    return await stop_katago_request(
        engine_runtime=engine_runtime,
        run_in_executor=run_in_executor,
    )


@app.post("/restart_katago")
async def restart_katago():
    """Restart the KataGo engine."""
    return restart_katago_request(engine_runtime=engine_runtime)


@app.get("/status")
async def get_status():
    return build_runtime_status_payload(
        server_rev=SERVER_REV,
        host=SERVER_HOST,
        port=SERVER_PORT,
        get_access_urls=get_access_urls,
        engine=engine,
        engine_runtime=engine_runtime,
        engine_state_snapshot=_engine_state_snapshot,
        card_config_service=card_config_service,
        no_katago=NO_KATAGO,
        static_index_path=STATIC_DIR / "index.html",
    )


# ─── GPU detection ───────────────────────────────────────────────────────────
_gpu_detector = CachedGpuInfo()


@app.get("/gpu")
async def get_gpu_info():
    return await runtime_gpu_info_payload(
        detector=_gpu_detector,
        run_in_executor=run_in_executor,
        cpu_mode_fn=lambda: engine_runtime.cpu_mode,
        large_model_path=KATAGO_MODEL_LARGE,
    )


@app.get("/sgf/{game_id}")
async def export_sgf(game_id: str):
    return build_sgf_export_response(
        game_id=game_id,
        active_games=active_games,
        generate_sgf=generate_sgf,
    )


async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


engine_gateway = EngineRuntimeGateway(
    engine=engine,
    base_dir=BASE_DIR,
    get_game_visits=get_game_visits,
    gtp_to_coord=gtp_to_coord,
    run_in_executor=run_in_executor,
    log_fn=print,
    traceback_fn=traceback.print_exc,
)


def _engine_gateway_binding() -> EngineGatewayBinding:
    return EngineGatewayBinding(
        engine=engine,
        get_game_visits=get_game_visits,
        gtp_to_coord=gtp_to_coord,
        run_in_executor=run_in_executor,
        log_fn=print,
        traceback_fn=traceback.print_exc,
    )


def _engine_gateway_runtime() -> EngineGatewayRuntime:
    return EngineGatewayRuntime(
        gateway=engine_gateway,
        binding=_engine_gateway_binding(),
    )


def _bind_engine_gateway_runtime() -> None:
    bind_engine_gateway_adapter(_engine_gateway_runtime())


async def _send_engine_command(command: str) -> str:
    return await send_engine_command_adapter(_engine_gateway_runtime(), command)


async def _sync_engine_komi(game: GoGame) -> None:
    await sync_engine_komi_adapter(_engine_gateway_runtime(), game)


ai_move_service = AiMoveService(
    engine=engine,
    run_in_executor=run_in_executor,
    engine_log=_engine_log,
    coord_to_gtp=coord_to_gtp,
    gtp_to_coord=gtp_to_coord,
)


def _ai_move_service_binding() -> AiMoveServiceBinding:
    return AiMoveServiceBinding(
        engine=engine,
        run_in_executor=run_in_executor,
    )


def _ai_move_service_runtime() -> AiMoveServiceRuntime:
    return AiMoveServiceRuntime(
        service=ai_move_service,
        binding=_ai_move_service_binding(),
    )


def _bind_ai_move_service_runtime():
    bind_ai_move_service_adapter(_ai_move_service_runtime())


def _ws_context_binding() -> WebSocketContextBinding:
    return WebSocketContextBinding(
        active_games=active_games,
        engine=engine,
        run_in_executor=run_in_executor,
        GoGame=GoGame,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
        engine_state_snapshot=_engine_state_snapshot,
        start_engine_background=engine_runtime.start_background,
        reload_live_card_config=reload_live_card_config,
        get_game_visits=get_game_visits,
        pick_rogue_choices=pick_rogue_choices,
        pick_ultimate_choices=pick_ultimate_choices,
        pick_challenge_beta_choices=pick_challenge_beta_choices,
        pick_ai_rogue_card=pick_ai_rogue_card,
        pick_ai_ultimate_card=pick_ai_ultimate_card,
        apply_challenge_rogue_loadout=_apply_challenge_rogue_loadout,
        activate_rogue_card=_activate_rogue_card,
        activate_ai_rogue_card=_activate_ai_rogue_card,
        ai_move=_ai_move,
        ultimate_ai_move=_ultimate_ai_move,
        ultimate_force_score=_ultimate_force_score,
        run_coach_turn_if_needed=_run_coach_turn_if_needed,
        run_ai_observer_loop=_run_ai_observer_loop,
        sync_board_to_katago=_sync_board_to_katago,
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


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return build_websocket_action_context_from_binding(
            game_id=game_id,
            game=game,
            send=send,
            send_error=send_error,
            do_analysis=do_analysis,
            do_analysis_bg=do_analysis_bg,
            binding=_ws_context_binding(),
        )

    await run_websocket_game_session(
        websocket,
        game_id,
        active_games=active_games,
        action_handlers=WS_ACTION_HANDLERS,
        analyze_position=_analyze_current_position,
        make_context=make_context,
    )


def _record_ultimate_turn(game: GoGame) -> None:
    record_ultimate_turn_adapter(game)


def _record_ultimate_player_action(game: GoGame) -> None:
    record_ultimate_player_action_adapter(
        game,
        record_ultimate_turn_fn=_record_ultimate_turn,
    )


def _finish_ultimate_quickthink_turn(game: GoGame) -> None:
    finish_ultimate_quickthink_turn_adapter(game)


def _capture_foul_binding() -> CaptureFoulBinding:
    return CaptureFoulBinding(sync_komi=_sync_engine_komi)


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
    _bind_engine_gateway_runtime()
    return await engine_gateway.estimate_side_winrate(
        game,
        color,
        sync_board=_sync_board_to_katago,
    )


def _rogue_five_in_row_binding() -> RogueFiveInRowBinding:
    return RogueFiveInRowBinding(
        apply_five_in_row=apply_rogue_five_in_row,
        shuffle_points=random.shuffle,
        should_bonus_derivative=_challenge_should_bonus_derivative,
        support_stones=ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
        engine_ready=lambda: engine.ready,
        sync_board=_sync_board_to_katago,
    )


async def _trigger_rogue_five_in_row(game: GoGame, send_fn, color: str):
    await trigger_rogue_five_in_row_adapter(
        game,
        send_fn,
        color,
        _rogue_five_in_row_binding(),
    )


def _rogue_last_stand_binding() -> RogueLastStandBinding:
    return RogueLastStandBinding(
        apply_last_stand=apply_rogue_last_stand,
        estimate_side_winrate=_estimate_side_winrate,
        make_rng=lambda: random.Random(time.time_ns()),
        get_forbidden_points=_get_player_bonus_forbidden_points,
        clear_count=ROGUE_LAST_STAND_CLEAR_COUNT,
        spawn_count=ROGUE_LAST_STAND_SPAWN_COUNT,
        threshold=ROGUE_LAST_STAND_THRESHOLD,
        engine_ready=lambda: engine.ready,
        sync_board=_sync_board_to_katago,
    )


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
    return UltimateLastStandBinding(
        apply_last_stand=apply_ultimate_last_stand,
        estimate_side_winrate=_estimate_side_winrate,
        make_rng=lambda: random.Random(time.time_ns()),
        threshold=ULTIMATE_LAST_STAND_THRESHOLD,
    )


async def _trigger_ultimate_last_stand(game: GoGame, send_fn, color: str):
    return await trigger_ultimate_last_stand_adapter(
        game,
        send_fn,
        color,
        _ultimate_last_stand_binding(),
    )


def _ultimate_five_in_row_binding() -> UltimateFiveInRowBinding:
    return UltimateFiveInRowBinding(
        apply_five_in_row=apply_ultimate_five_in_row,
        make_rng=lambda: random.Random(time.time_ns()),
    )


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


def _challenge_flow_binding() -> ChallengeFlowBinding:
    return ChallengeFlowBinding(
        roll_random=random.random,
        trap_extra_turn_chance=CHALLENGE_TRAP_EXTRA_TURN_CHANCE,
        restriction_decay_chance=CHALLENGE_RESTRICTION_DECAY_CHANCE,
        weaken_rank_one_step=weaken_rank_one_step,
        rank_labels=RANK_LABELS,
        challenge_set_min_count=CHALLENGE_SET_MIN_COUNT,
        engine_ready=lambda: engine.ready,
        get_game_visits=get_game_visits,
        run_in_executor=run_in_executor,
        set_engine_visits=engine.set_visits,
    )


def _challenge_loadout_binding() -> ChallengeLoadoutBinding:
    return ChallengeLoadoutBinding(
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
        golden_corner_span=ROGUE_GOLDEN_CORNER_SPAN,
        joseki_target_count=ROGUE_JOSEKI_TARGET_COUNT,
        godhand_radius=ROGUE_GODHAND_RADIUS,
        sync_engine_komi=_sync_engine_komi,
        emit_set_bonus_status=_challenge_emit_set_bonus_status,
    )


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
    _bind_engine_gateway_runtime()
    return await engine_gateway.pick_analysis_point(game, color, start_index=start_index)


async def _pick_second_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=1)


async def _pick_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=0)


def _rogue_card_activation_binding() -> RogueCardActivationBinding:
    return RogueCardActivationBinding(
        get_card=get_rogue_card,
        apply_activation=apply_rogue_card_activation,
        coord_to_gtp=coord_to_gtp,
        choose_corner=lambda: random.randint(0, 3),
        make_rng=lambda: random.Random(time.time_ns()),
        get_blackhole_points=_get_blackhole_points,
        get_golden_corner_points=_get_golden_corner_points,
        pick_joseki_targets=_pick_joseki_targets,
        random_hidden_center=_random_hidden_center,
        diamond_points=_diamond_points,
        sync_engine_komi=_sync_engine_komi,
    )


def _ai_rogue_card_activation_binding() -> AiRogueCardActivationBinding:
    return AiRogueCardActivationBinding(
        get_card=get_rogue_card,
        apply_activation=apply_ai_rogue_card_activation,
        choose_corner=lambda: random.randint(0, 3),
        get_blackhole_points=_get_blackhole_points,
        get_golden_corner_points=_get_golden_corner_points,
        refresh_ai_rogue_player_turn=_refresh_ai_rogue_player_turn,
        golden_corner_span=ROGUE_GOLDEN_CORNER_SPAN,
    )


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


def _player_rogue_move_effect_binding() -> PlayerRogueMoveEffectBinding:
    return PlayerRogueMoveEffectBinding(
        has_rogue=_rogue_has,
        erosion_shift=ROGUE_EROSION_SHIFT,
        sync_engine_komi=_sync_engine_komi,
        apply_board_effects=apply_player_rogue_board_effects,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
        engine_ready=lambda: engine.ready,
        sync_board_to_katago=_sync_board_to_katago,
        challenge_apply_trap_bonus=_challenge_apply_trap_bonus,
        trigger_five_in_row=_trigger_rogue_five_in_row,
        trigger_last_stand=_trigger_rogue_last_stand,
        challenge_maybe_reduce_ai_level=_challenge_maybe_reduce_ai_level,
    )


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
    return AiRogueResponseEffectBinding(
        apply_board_effects=apply_ai_rogue_response_board_effects,
        coord_to_gtp=coord_to_gtp,
        shuffle_points=random.shuffle,
        engine_ready=lambda: engine.ready,
        sync_board_to_katago=_sync_board_to_katago,
    )


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
    _bind_engine_gateway_runtime()
    engine_gateway.sync_board_locked(game)


def _has_gtp_unsafe_whitespace(path: str) -> bool:
    return EngineRuntimeGateway.has_gtp_unsafe_whitespace(path)


def _gtp_safe_sync_sgf_path(game: GoGame) -> str:
    """Return a writable SGF path that KataGo GTP will not split on spaces."""
    _bind_engine_gateway_runtime()
    return engine_gateway.gtp_safe_sync_sgf_path(game)


async def _sync_board_to_katago(game: GoGame):
    """Reset KataGo board to match game.board (async wrapper)."""
    _bind_engine_gateway_runtime()
    await engine_gateway.sync_board(game)


def _empty_analysis_result() -> dict:
    return EngineRuntimeGateway.empty_analysis_result()


async def _analyze_current_position(game: GoGame, color: Optional[str] = None) -> dict:
    _bind_engine_gateway_runtime()
    return await engine_gateway.analyze_current_position(
        game,
        color=color,
        sync_board=_sync_board_to_katago,
    )


def _ultimate_get_territory_forbidden(game: GoGame, for_color_val: int) -> set:
    """Get forbidden points for a color due to opponent's 绝对领地 card.
    for_color_val: the color (1=B,2=W) that wants to PLACE a stone."""
    return get_ultimate_territory_forbidden_points(game, for_color_val)


def _ultimate_effect_binding() -> UltimateEffectBinding:
    return UltimateEffectBinding(
        apply_effect=apply_ultimate_card_effect_state,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
        trigger_five_in_row=_trigger_ultimate_five_in_row,
        trigger_last_stand=_trigger_ultimate_last_stand,
        apply_foolish_wisdom_wave=apply_ultimate_foolish_wisdom_wave,
        make_rng=lambda: random.Random(time.time_ns()),
        sleep=asyncio.sleep,
        foolish_chain_delay=ULTIMATE_FOOLISH_CHAIN_DELAY,
    )


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


async def _run_ultimate_ai_bonus_turn(game: GoGame, send_fn, color: str, bonus_turn) -> bool:
    async def run_next_ai_move(game_arg, send_arg, next_allow_double_bonus: bool) -> None:
        await _ultimate_ai_move(
            game_arg,
            send_arg,
            allow_double_bonus=next_allow_double_bonus,
        )

    return await run_ultimate_ai_bonus_turn_adapter(
        game,
        send_fn,
        color,
        bonus_turn,
        UltimateAiBonusTurnBinding(
            start_bonus_turn=start_ultimate_ai_bonus_turn_state,
            run_next_ai_move=run_next_ai_move,
        ),
    )


def _ultimate_ai_move_selection_binding() -> UltimateAiMoveSelectionBinding:
    return UltimateAiMoveSelectionBinding(
        engine_ready=lambda: engine.ready,
        sync_board_to_katago=_sync_board_to_katago,
        plan_search=lambda game: plan_ultimate_ai_search(
            game,
            get_territory_forbidden=_ultimate_get_territory_forbidden,
            get_game_visits=get_game_visits,
        ),
        engine=engine,
        run_in_executor=run_in_executor,
        get_game_visits=get_game_visits,
        no_resign_move=_ai_move_no_resign,
        pick_ranked_legal_move=_pick_ranked_legal_move,
        pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
        retry_avoiding_ko=_ai_retry_avoiding_ko,
        is_suspicious_ai_pass=_is_suspicious_ai_pass,
        resolve_occupied_ai_move=resolve_occupied_ai_move,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        log_fn=_engine_log,
    )


def _ultimate_ai_turn_finish_binding() -> UltimateAiTurnFinishBinding:
    return UltimateAiTurnFinishBinding(
        chain_chance=ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
        chain_random=random.random,
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
    )


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


def _generated_ai_move_candidate_binding() -> GeneratedMoveCandidateBinding:
    return GeneratedMoveCandidateBinding(
        choose_candidate=choose_ai_move_candidate,
        choose_avoid_move=_ai_move_avoid_points,
        analyze_position=_analyze_current_position,
        choose_style_move=choose_ai_style_move,
        generate_move=_ai_generate_move,
        gtp_to_coord=gtp_to_coord,
        log_error=print,
    )


def _generated_ai_move_preparation_binding() -> GeneratedMovePreparationBinding:
    return GeneratedMovePreparationBinding(
        prepare_move=prepare_generated_ai_move,
        apply_suspicious_pass_fallback_fn=apply_suspicious_pass_fallback,
        is_suspicious_pass=_is_suspicious_ai_pass,
        pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
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
    )


def _generated_ai_move_finish_binding(run_engine_command) -> GeneratedMoveFinishBinding:
    return GeneratedMoveFinishBinding(
        finish_move=finish_prepared_ai_move,
        apply_placement_effects=apply_ai_move_placement_effects,
        finish_turn_response=finish_ai_turn_response,
        gtp_to_coord=gtp_to_coord,
        sync_board_to_engine=_sync_board_to_katago,
        engine_is_ready=lambda: engine.ready,
        apply_move_to_board=apply_ai_move_to_board,
        apply_sansan_trap_counter=try_apply_sansan_trap_counter,
        try_no_regret_bonus=try_apply_no_regret_bonus,
        trap_stones=ROGUE_SANSAN_TRAP_STONES,
        get_sansan_points=_get_sansan_points,
        adjacent_points=_adjacent8_points,
        shuffle_points=random.shuffle,
        spawn_bonus_points=_spawn_bonus_points,
        coord_to_gtp=coord_to_gtp,
        apply_trap_bonus=_challenge_apply_trap_bonus,
        no_regret_chance=ROGUE_NO_REGRET_CHANCE,
        roll_random=random.random,
        has_rogue_card=_rogue_has,
        pick_best_point=_pick_best_point,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        apply_erosion_counter=apply_erosion_komi_counter,
        erosion_shift=ROGUE_EROSION_SHIFT,
        run_erosion_command=_send_engine_command,
        erosion_message=lambda capture_count, komi: f"蚕食反制：AI 提掉了 {capture_count} 子，当前贴目变为 {komi}",
        finalize_double_pass=try_finalize_double_pass,
        run_double_pass_command=run_engine_command,
        send_ai_move_response=send_ai_move_and_run_coach,
        run_coach_turn_if_needed=_run_coach_turn_if_needed,
    )


def _generated_ai_turn_binding() -> GeneratedAiTurnBinding:
    return GeneratedAiTurnBinding(
        rogue_forbidden_points=rogue_forbidden_points,
        challenge_zone_points=_challenge_zone_points,
        try_finish_generated_ai_move=try_finish_generated_ai_move,
        candidate_binding=_generated_ai_move_candidate_binding,
        preparation_binding=_generated_ai_move_preparation_binding,
        finish_binding=_generated_ai_move_finish_binding,
    )


def _forced_rogue_ai_turn_binding() -> ForcedRogueAiTurnBinding:
    return ForcedRogueAiTurnBinding(
        try_finish_forced_rogue_ai_move=try_finish_forced_rogue_ai_move,
        roll_random=random.random,
        dice_pass_chance=ROGUE_DICE_PASS_CHANCE,
        mirror_chance=ROGUE_MIRROR_CHANCE,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        mirror_coord=_mirror_coord,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        finalize_forced_pass=finalize_forced_ai_pass,
        finalize_forced_stone=try_finalize_forced_ai_stone,
        apply_puppet_move=try_apply_puppet_ai_move,
        finish_ai_move=_finish_ai_move,
    )


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
    return RestrictionRogueAiTurnBinding(
        try_finish_rogue_restriction_ai_move=try_finish_rogue_restriction_ai_move,
        choose_tengen_target=choose_tengen_target,
        tengen_followup_points=tengen_followup_points,
        gravity_allowed_points=gravity_allowed_points,
        lowline_allowed_points=lowline_allowed_points,
        sansan_opening_restriction=sansan_opening_restriction,
        coord_to_gtp=coord_to_gtp,
        finalize_forced_stone=try_finalize_forced_ai_stone,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        choose_allowed_move=_ai_move_avoid_points_allow_only,
        choose_avoid_move=_ai_move_avoid_points,
        finish_ai_move=_finish_ai_move,
        finish_allowed_restriction_move=try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=try_finish_sansan_restriction_move,
    )


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
    return ShadowRogueAiTurnBinding(
        try_finish_shadow_restriction_move=try_finish_shadow_restriction_move,
        roll_random=random.random,
        choose_restriction=lambda game_arg, color_arg, ai_count: shadow_followup_points(
            game_arg,
            color_arg,
            ai_count,
            gtp_to_coord=gtp_to_coord,
        ),
        choose_allowed_move=_ai_move_avoid_points_allow_only,
        finish_ai_move=_finish_ai_move,
    )


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
    return SuboptimalRogueAiTurnBinding(
        try_finish_suboptimal_rogue_move=try_finish_suboptimal_rogue_move,
        roll_random=random.random,
        choose_suboptimal_move=_ai_move_suboptimal,
        finish_ai_move=_finish_ai_move,
    )


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


def _ai_turn_binding() -> AiTurnBinding:
    return AiTurnBinding(
        engine_ready=lambda: engine.ready,
        sync_board_to_katago=_sync_board_to_katago,
        snapshot_turn=lambda game: snapshot_ai_turn(game, _rogue_card_ids),
        try_finish_forced=lambda game, send_fn, turn: _try_finish_forced_rogue_ai_turn(
            game,
            send_fn,
            turn,
            _send_engine_command,
        ),
        plan_search=_plan_ai_turn_search,
        refresh_fog_restriction=_refresh_ai_turn_fog_restriction,
        try_finish_restriction=lambda game, send_fn, turn, plan: _try_finish_rogue_restriction_ai_turn(
            game,
            send_fn,
            turn,
            plan,
            _send_engine_command,
        ),
        try_finish_shadow=_try_finish_shadow_rogue_ai_turn,
        try_finish_suboptimal=_try_finish_suboptimal_rogue_ai_turn,
        try_finish_generated=lambda game, send_fn, turn, plan: _try_finish_generated_ai_turn(
            game,
            send_fn,
            turn,
            plan,
            _send_engine_command,
        ),
    )


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


def _ai_finish_move_binding() -> AiFinishMoveBinding:
    return AiFinishMoveBinding(
        finalize_ai_move=finalize_ai_move,
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_ai_move_no_resign,
        retry_avoiding_ko=_ai_retry_avoiding_ko,
        check_capture_foul=_check_capture_foul,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        run_engine_command=_send_engine_command,
        run_coach_turn_if_needed=_run_coach_turn_if_needed,
    )


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


def _ai_style_move_binding() -> AiStyleMoveBinding:
    return AiStyleMoveBinding(
        sync_board_to_katago=_sync_board_to_katago,
        choose_or_generate_style_move=choose_or_generate_ai_style_move,
        analyze_position=_analyze_current_position,
        choose_style_move=choose_ai_style_move,
        generate_move=_ai_generate_move,
        gtp_to_coord=gtp_to_coord,
        play_chosen_move=_send_engine_command,
    )


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
    return CoachMoveChoiceBinding(
        get_game_visits=get_game_visits,
        generate_ai_style_move=_generate_ai_style_move,
        gtp_to_coord=gtp_to_coord,
        retry_avoiding_ko=_ai_retry_avoiding_ko,
        coach_visits=ROGUE_COACH_VISITS,
        max_move_time=MAX_MOVE_TIME,
    )


async def _choose_coach_ai_move(game: GoGame, color: str) -> tuple[str, tuple[int, int] | None]:
    return await choose_coach_ai_move_adapter(
        game,
        color,
        _coach_move_choice_binding(),
    )


def _coach_turn_binding() -> CoachTurnBinding:
    return CoachTurnBinding(
        engine_ready=lambda: engine.ready,
        choose_coach_ai_move=_choose_coach_ai_move,
        place_auxiliary_move=_place_auxiliary_ai_move_on_board,
        check_capture_foul=_check_capture_foul,
        apply_player_rogue_move_effects=_apply_player_rogue_move_effects,
        apply_ai_rogue_response_effects=_apply_ai_rogue_response_effects,
        estimate_side_winrate=_estimate_side_winrate,
        ai_move=_ai_move,
        bonus_threshold=ROGUE_COACH_BONUS_THRESHOLD,
        bonus_turns=ROGUE_COACH_BONUS_TURNS,
    )


async def _run_coach_turn_if_needed(game: GoGame, send_fn):
    await run_coach_turn_if_needed_adapter(
        game,
        send_fn,
        _coach_turn_binding(),
    )


def _observer_double_pass_binding() -> ObserverDoublePassBinding:
    return ObserverDoublePassBinding(
        run_engine_command=_send_engine_command,
    )


async def _finish_observer_double_pass(game: GoGame, send_fn) -> bool:
    return await finish_observer_double_pass_adapter(
        game,
        send_fn,
        _observer_double_pass_binding(),
    )


def _observer_move_placement_binding() -> ObserverMovePlacementBinding:
    return ObserverMovePlacementBinding(
        gtp_to_coord=gtp_to_coord,
        place_auxiliary_move=_place_auxiliary_ai_move_on_board,
    )


def _apply_observer_ai_move_to_board(game: GoGame, color: str, gtp_move: str) -> AiMovePlacement:
    return apply_observer_ai_move_to_board_adapter(
        game,
        color,
        gtp_move,
        _observer_move_placement_binding(),
    )


def _ai_observer_loop_binding() -> AiObserverLoopBinding:
    return AiObserverLoopBinding(
        engine_ready=lambda: engine.ready,
        sync_board=_sync_board_to_katago,
        get_game_visits=get_game_visits,
        generate_ai_style_move=_generate_ai_style_move,
        is_suspicious_ai_pass=_is_suspicious_ai_pass,
        pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
        place_ai_move_on_board=_apply_observer_ai_move_to_board,
        finish_double_pass=_finish_observer_double_pass,
        sleep=asyncio.sleep,
        opening_move_threshold=OPENING_MOVE_THRESHOLD,
    )


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
