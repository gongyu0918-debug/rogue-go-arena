"""
rogue-go-arena server - KataGo-powered board game with FastAPI WebSocket backend
"""
import argparse
import asyncio
import random
import re
import traceback
import time
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
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
from app.runtime.engine_gateway import EngineRuntimeGateway
from app.runtime.gpu_info import apply_runtime_gpu_overrides, detect_gpu_info
from app.runtime.status_payload import build_status_payload
from app.gameplay.card_selection import (
    pick_ai_rogue_card,
    pick_ai_ultimate_card,
    pick_challenge_beta_choices,
    pick_rogue_choices,
    pick_ultimate_choices,
)
from app.gameplay.challenge_flow import (
    ChallengeFlowDeps,
    ChallengeLoadoutFlowDeps,
    apply_challenge_rogue_loadout_event,
    apply_challenge_trap_bonus_event,
    emit_challenge_set_bonus_status,
    maybe_reduce_challenge_ai_level,
)
from app.gameplay.line_trigger_flow import (
    RogueFiveInRowDeps,
    RogueLastStandDeps,
    UltimateFiveInRowDeps,
    UltimateLastStandDeps,
    trigger_rogue_five_in_row as trigger_rogue_five_in_row_state,
    trigger_rogue_last_stand as trigger_rogue_last_stand_state,
    trigger_ultimate_five_in_row as trigger_ultimate_five_in_row_state,
    trigger_ultimate_last_stand as trigger_ultimate_last_stand_state,
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
    GeneratedMoveCandidateDeps,
    GeneratedMoveFinishDeps,
    GeneratedMovePreparationDeps,
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
from app.gameplay.ai_turn_flow import AiTurnFlowDeps, run_ai_turn
from app.gameplay.ai_observer import (
    AiObserverLoopDeps,
    apply_observer_ai_move_to_board as apply_observer_ai_move_to_board_state,
    finish_observer_double_pass as finish_observer_double_pass_state,
    run_ai_observer_loop as run_ai_observer_loop_state,
)
from app.gameplay.coach_mode import (
    CoachMoveChoiceDeps,
    CoachTurnDeps,
    choose_coach_ai_move as choose_coach_ai_move_state,
    run_coach_turn_if_needed as run_coach_turn_if_needed_state,
)
from app.gameplay.capture_foul_flow import check_capture_foul_event
from app.gameplay.rogue_card_flow import (
    AiRogueCardActivationFlowDeps,
    RogueCardActivationFlowDeps,
    activate_ai_rogue_card_event,
    activate_rogue_card_event,
)
from app.gameplay.rogue_move_effect_flow import (
    AiRogueResponseEffectDeps,
    PlayerRogueMoveEffectDeps,
    apply_ai_rogue_response_effects_event,
    apply_player_rogue_move_effects_event,
)
from app.gameplay.ultimate_effect_flow import (
    UltimateEffectFlowDeps,
    apply_ultimate_effect_event,
)
from app.gameplay.turn_modifiers import (
    apply_ultimate_ai_move_result as apply_ultimate_ai_move_result_state,
    choose_ultimate_ai_bonus_turn as choose_ultimate_ai_bonus_turn_state,
    clear_player_turn_modifiers as clear_player_turn_modifiers_state,
    finish_ultimate_quickthink_turn as finish_ultimate_quickthink_turn_state,
    finish_ultimate_ai_normal_turn as finish_ultimate_ai_normal_turn_state,
    get_ai_rogue_forbidden_points as get_ai_rogue_forbidden_points_state,
    get_player_bonus_forbidden_points as get_player_bonus_forbidden_points_state,
    pick_fog_mask as pick_fog_mask_state,
    pick_fog_point as pick_fog_point_state,
    prepare_player_turn_modifiers as prepare_player_turn_modifiers_state,
    record_ultimate_player_action as record_ultimate_player_action_state,
    record_ultimate_turn as record_ultimate_turn_state,
    refresh_ai_rogue_player_turn as refresh_ai_rogue_player_turn_state,
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
    player_non_pass_coords as player_non_pass_coords_state,
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
from app.gameplay.ultimate_effects import (
    apply_ultimate_card_effect as apply_ultimate_card_effect_state,
    apply_ultimate_foolish_wisdom_wave,
    apply_ultimate_five_in_row,
    apply_ultimate_last_stand,
    get_ultimate_territory_forbidden_points,
    resolve_pending_shadow_links,
)
from app.gameplay.ultimate_ai_flow import (
    apply_ultimate_ai_post_move_effects,
    choose_ultimate_ai_move,
    finish_ultimate_ai_turn,
)
from app.gameplay.ultimate_scoring import finalize_ultimate_score
from app.runtime.engine import KataGoEngine
from app.runtime.game_store import ActiveGameStore
from app.runtime.startup import EnginePaths, EngineStartupManager
from app.runtime.ws_session import run_websocket_game_session
from app.runtime.ws_actions import WS_ACTION_HANDLERS, WebSocketActionContext

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
    for key in gameplay_config.BALANCE_DEFAULTS:
        if key in globals():
            globals()[key] = getattr(gameplay_config, key)
    for key in ("ROGUE_COACH_BASE_TURNS", "ROGUE_SEAL_POINT_COUNT", "ULTIMATE_JOSEKI_TARGET_COUNT"):
        if hasattr(ws_actions_module, key):
            setattr(ws_actions_module, key, getattr(gameplay_config, key))


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
    for path in (USER_DATA_DIR, USER_KATAGO_DIR, USER_KATAGO_HOME, USER_RUNTIME_CONFIG_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _runtime_config_path(source_config: Path) -> Path:
    _ensure_user_katago_dirs()
    runtime_path = USER_RUNTIME_CONFIG_DIR / f"{source_config.stem}_runtime.cfg"
    content = source_config.read_text(encoding="utf-8", errors="ignore")
    home_dir = USER_KATAGO_HOME.as_posix()
    if re.search(r"(?m)^\s*#?\s*homeDataDir\s*=", content):
        content = re.sub(
            r"(?m)^\s*#?\s*homeDataDir\s*=.*$",
            f"homeDataDir = {home_dir}",
            content,
            count=1,
        )
    else:
        content = content.rstrip() + f"\n\nhomeDataDir = {home_dir}\n"
    runtime_path.write_text(content, encoding="utf-8")
    return runtime_path


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
    # Prevent browser from caching HTML / API responses
    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
async def root():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return Response(
            content="static/index.html not found",
            media_type="text/plain; charset=utf-8",
            status_code=500,
        )
    return FileResponse(str(index_path))


@app.get("/react-preview")
async def react_preview():
    preview_path = STATIC_DIR / "react" / "index.html"
    if not preview_path.exists():
        return Response(
            content="static/react/index.html not found. Run npm run build --prefix frontend.",
            media_type="text/plain; charset=utf-8",
            status_code=404,
        )
    return FileResponse(str(preview_path))


@app.get("/balance-lab")
async def balance_lab():
    lab_path = STATIC_DIR / "card_editor.html"
    if not lab_path.exists():
        return Response(
            content="static/card_editor.html not found",
            media_type="text/plain; charset=utf-8",
            status_code=500,
        )
    return FileResponse(str(lab_path))


@app.get("/card-editor")
async def card_editor():
    return await balance_lab()


@app.get("/api/card-config")
async def get_card_config_payload():
    return card_config_service.get_payload()


@app.get("/api/card-config/schema")
async def get_card_config_schema():
    return card_config_service.get_schema()


@app.post("/api/card-config")
async def save_card_config_payload(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "errors": ["request body must be JSON"]},
            status_code=400,
        )
    config = body.get("config") if isinstance(body, dict) else None
    result = card_config_service.save_payload(config)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result


@app.post("/api/card-config/reset")
async def reset_card_config_payload():
    result = card_config_service.reset_payload()
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result


@app.get("/api/balance")
async def get_balance_lab_payload():
    return get_balance_editor_payload()


@app.post("/api/balance")
async def save_balance_lab_payload(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"ok": False, "errors": ["request body must be JSON"]},
            status_code=400,
        )
    values = body.get("values", {}) if isinstance(body, dict) else {}
    result = save_balance_overrides(values)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result


@app.post("/api/balance/reset")
async def reset_balance_lab_payload():
    return reset_balance_overrides()


@app.get("/ranks")
async def get_ranks():
    return [{"id": k, "label": v} for k, v in RANK_LABELS.items()]


@app.post("/stop_katago")
async def stop_katago():
    """Stop the KataGo engine while keeping the server running."""
    return await run_in_executor(engine_runtime.stop_via_api)


@app.post("/restart_katago")
async def restart_katago():
    """Restart the KataGo engine."""
    return engine_runtime.restart_via_api()


@app.get("/status")
async def get_status():
    snapshot = _engine_state_snapshot()
    model_exists = engine_runtime.has_model_files()
    exe_exists = engine_runtime.has_engine_binaries()
    selected_model = engine_runtime.select_model()
    card_config_payload = card_config_service.get_payload()
    return build_status_payload(
        server_rev=SERVER_REV,
        host=SERVER_HOST,
        port=SERVER_PORT,
        access_urls=get_access_urls(SERVER_HOST, SERVER_PORT),
        engine_ready=engine.ready,
        engine_snapshot=snapshot,
        exe_exists=exe_exists,
        model_exists=model_exists,
        selected_model_name=selected_model.name if selected_model else None,
        no_katago=NO_KATAGO,
        cpu_mode=engine_runtime.cpu_mode,
        static_ready=(STATIC_DIR / "index.html").exists(),
        card_config_payload=card_config_payload,
    )


# ─── GPU detection ───────────────────────────────────────────────────────────
_gpu_cache: dict = {}


def _detect_gpu() -> dict:
    """Detect NVIDIA GPU using nvidia-smi. Returns gpu info dict."""
    if _gpu_cache:
        return _gpu_cache
    result = detect_gpu_info()
    _gpu_cache.update(result)
    return result


@app.get("/gpu")
async def get_gpu_info():
    info = await run_in_executor(_detect_gpu)
    return apply_runtime_gpu_overrides(
        info,
        cpu_mode=engine_runtime.cpu_mode,
        large_model_path=KATAGO_MODEL_LARGE,
    )


@app.get("/sgf/{game_id}")
async def export_sgf(game_id: str):
    active_games.prune()
    game = active_games.get(game_id, touch=True)
    if not game:
        return Response(content="Game not found", status_code=404)
    sgf = generate_sgf(game)
    return Response(
        content=sgf,
        media_type="application/x-go-sgf",
        headers={"Content-Disposition": f'attachment; filename="rogue-go-arena_{game_id}.sgf"'},
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


def _bind_engine_gateway_runtime() -> None:
    engine_gateway.bind_runtime(
        engine=engine,
        get_game_visits=get_game_visits,
        gtp_to_coord=gtp_to_coord,
        run_in_executor=run_in_executor,
        log_fn=print,
        traceback_fn=traceback.print_exc,
    )


async def _send_engine_command(command: str) -> str:
    _bind_engine_gateway_runtime()
    return await engine_gateway.send_command(command)


async def _sync_engine_komi(game: GoGame) -> None:
    _bind_engine_gateway_runtime()
    await engine_gateway.sync_komi(game)


ai_move_service = AiMoveService(
    engine=engine,
    run_in_executor=run_in_executor,
    engine_log=_engine_log,
    coord_to_gtp=coord_to_gtp,
    gtp_to_coord=gtp_to_coord,
)


def _bind_ai_move_service_runtime():
    ai_move_service.bind_runtime(engine=engine, run_in_executor=run_in_executor)


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    def make_context(game, send, send_error, do_analysis, do_analysis_bg):
        return WebSocketActionContext(
            game_id=game_id,
            game=game,
            active_games=active_games,
            engine=engine,
            send=send,
            send_error=send_error,
            do_analysis=do_analysis,
            do_analysis_bg=do_analysis_bg,
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

    await run_websocket_game_session(
        websocket,
        game_id,
        active_games=active_games,
        action_handlers=WS_ACTION_HANDLERS,
        analyze_position=_analyze_current_position,
        make_context=make_context,
    )


def _record_ultimate_turn(game: GoGame) -> None:
    record_ultimate_turn_state(game)


def _record_ultimate_player_action(game: GoGame) -> None:
    record_ultimate_player_action_state(
        game,
        record_ultimate_turn_fn=_record_ultimate_turn,
    )


def _finish_ultimate_quickthink_turn(game: GoGame) -> None:
    finish_ultimate_quickthink_turn_state(game)


async def _check_capture_foul(game: GoGame, send_fn, offender: str, captured: int, *, ultimate: bool) -> None:
    """Track capture-foul progress and penalise when threshold is met.

    The card only punishes the *opponent* of the card holder:
      - Rogue: player picks the card → only the AI is punished.
      - Ultimate: whoever picked the card → only the other side is punished.
    ``offender`` is the colour that just captured stones.
    """
    await check_capture_foul_event(
        game,
        send_fn,
        offender,
        captured,
        ultimate=ultimate,
        sync_komi=_sync_engine_komi,
    )


def _pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_mask_state(size, rng)


def _pick_fog_point(game, rng: random.Random) -> list[tuple[int, int]]:
    return pick_fog_point_state(game, rng)


def _get_player_bonus_forbidden_points(game: GoGame, color: str) -> set[tuple[int, int]]:
    return get_player_bonus_forbidden_points_state(game, color)


async def _estimate_side_winrate(game: GoGame, color: str) -> float:
    _bind_engine_gateway_runtime()
    return await engine_gateway.estimate_side_winrate(
        game,
        color,
        sync_board=_sync_board_to_katago,
    )


async def _trigger_rogue_five_in_row(game: GoGame, send_fn, color: str):
    await trigger_rogue_five_in_row_state(
        game,
        send_fn,
        color,
        RogueFiveInRowDeps(
            apply_five_in_row=apply_rogue_five_in_row,
            shuffle_points=random.shuffle,
            should_bonus_derivative=_challenge_should_bonus_derivative,
            support_stones=ROGUE_FIVE_IN_ROW_SUPPORT_STONES,
            engine_ready=lambda: engine.ready,
            sync_board=_sync_board_to_katago,
        ),
    )


async def _trigger_rogue_last_stand(
    game: GoGame,
    send_fn,
    color: str,
    center: tuple[int, int],
):
    await trigger_rogue_last_stand_state(
        game,
        send_fn,
        color,
        center,
        RogueLastStandDeps(
            apply_last_stand=apply_rogue_last_stand,
            estimate_side_winrate=_estimate_side_winrate,
            make_rng=lambda: random.Random(time.time_ns()),
            get_forbidden_points=_get_player_bonus_forbidden_points,
            clear_count=ROGUE_LAST_STAND_CLEAR_COUNT,
            spawn_count=ROGUE_LAST_STAND_SPAWN_COUNT,
            threshold=ROGUE_LAST_STAND_THRESHOLD,
            engine_ready=lambda: engine.ready,
            sync_board=_sync_board_to_katago,
        ),
    )


async def _trigger_ultimate_last_stand(game: GoGame, send_fn, color: str):
    return await trigger_ultimate_last_stand_state(
        game,
        send_fn,
        color,
        UltimateLastStandDeps(
            apply_last_stand=apply_ultimate_last_stand,
            estimate_side_winrate=_estimate_side_winrate,
            make_rng=lambda: random.Random(time.time_ns()),
            threshold=ULTIMATE_LAST_STAND_THRESHOLD,
        ),
    )


async def _trigger_ultimate_five_in_row(game: GoGame, send_fn, color: str):
    return await trigger_ultimate_five_in_row_state(
        game,
        send_fn,
        color,
        UltimateFiveInRowDeps(
            apply_five_in_row=apply_ultimate_five_in_row,
            make_rng=lambda: random.Random(time.time_ns()),
        ),
    )


def _player_non_pass_coords(game: GoGame, color: str, limit: Optional[int] = None) -> list[tuple[int, int]]:
    return player_non_pass_coords_state(game, color, gtp_to_coord, limit=limit)


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
    return get_ai_rogue_forbidden_points_state(game)


def _challenge_flow_deps() -> ChallengeFlowDeps:
    return ChallengeFlowDeps(
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


def _challenge_loadout_flow_deps() -> ChallengeLoadoutFlowDeps:
    return ChallengeLoadoutFlowDeps(
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
    await apply_challenge_trap_bonus_event(
        game,
        send_fn,
        source_name,
        _challenge_flow_deps(),
    )


async def _challenge_maybe_reduce_ai_level(game: GoGame, send_fn) -> None:
    await maybe_reduce_challenge_ai_level(
        game,
        send_fn,
        _challenge_flow_deps(),
    )


async def _challenge_emit_set_bonus_status(game: GoGame, send_fn) -> None:
    await emit_challenge_set_bonus_status(
        game,
        send_fn,
        _challenge_flow_deps(),
    )


def _refresh_ai_rogue_player_turn(game: GoGame):
    refresh_ai_rogue_player_turn_state(
        game,
        pick_fog_mask_fn=_pick_fog_mask,
        pick_fog_point_fn=_pick_fog_point,
    )


def _prepare_player_turn_modifiers(game: GoGame):
    prepare_player_turn_modifiers_state(
        game,
        refresh_ai_rogue_player_turn_fn=_refresh_ai_rogue_player_turn,
    )


def _clear_player_turn_modifiers(game: GoGame):
    clear_player_turn_modifiers_state(
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


def _rogue_card_activation_flow_deps() -> RogueCardActivationFlowDeps:
    return RogueCardActivationFlowDeps(
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


def _ai_rogue_card_activation_flow_deps() -> AiRogueCardActivationFlowDeps:
    return AiRogueCardActivationFlowDeps(
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
    await activate_rogue_card_event(
        game,
        send_fn,
        card_id,
        _rogue_card_activation_flow_deps(),
    )


async def _activate_ai_rogue_card(game: GoGame, send_fn, card_id: str):
    await activate_ai_rogue_card_event(
        game,
        send_fn,
        card_id,
        _ai_rogue_card_activation_flow_deps(),
    )


async def _apply_challenge_rogue_loadout(game: GoGame, send_fn):
    await apply_challenge_rogue_loadout_event(
        game,
        send_fn,
        _challenge_loadout_flow_deps(),
    )


def _player_rogue_move_effect_deps() -> PlayerRogueMoveEffectDeps:
    return PlayerRogueMoveEffectDeps(
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
    await apply_player_rogue_move_effects_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        captured=captured,
        deps=_player_rogue_move_effect_deps(),
    )


def _ai_rogue_response_effect_deps() -> AiRogueResponseEffectDeps:
    return AiRogueResponseEffectDeps(
        apply_board_effects=apply_ai_rogue_response_board_effects,
        coord_to_gtp=coord_to_gtp,
        shuffle_points=random.shuffle,
        engine_ready=lambda: engine.ready,
        sync_board_to_katago=_sync_board_to_katago,
    )


async def _apply_ai_rogue_response_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str):
    await apply_ai_rogue_response_effects_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        deps=_ai_rogue_response_effect_deps(),
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


def _ultimate_effect_flow_deps() -> UltimateEffectFlowDeps:
    return UltimateEffectFlowDeps(
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
    return await apply_ultimate_effect_event(
        game,
        send_fn,
        x=x,
        y=y,
        color=color,
        card=card,
        deps=_ultimate_effect_flow_deps(),
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
    return await ai_move_service.pick_nonpass_fallback_move(game, color, visits, forbidden)


async def _pick_ranked_legal_move(
    game: GoGame,
    color: str,
    visits: int,
    forbidden: Optional[set[tuple[int, int]]] = None,
    *,
    time_limit: float = 1.5,
) -> Optional[str]:
    return await ai_move_service.pick_ranked_legal_move(
        game,
        color,
        visits,
        forbidden,
        time_limit=time_limit,
    )


async def _run_ultimate_ai_bonus_turn(game: GoGame, send_fn, color: str, bonus_turn) -> bool:
    start_ultimate_ai_bonus_turn_state(game, color)
    await send_fn({"type": "rogue_event", "msg": bonus_turn.message})
    await send_fn({"type": "game_state", **game.to_state()})
    if game.ultimate_move_count < 20:
        await _ultimate_ai_move(
            game,
            send_fn,
            allow_double_bonus=bonus_turn.next_allow_double_bonus,
        )
        return True
    return False


async def _ultimate_ai_move(game: GoGame, send_fn,
                            allow_double_bonus: bool = True):
    """AI move in ultimate mode - generates move, applies AI's card effect."""
    if game.game_over or not engine.ready:
        return

    game.ultimate_extra_turn = False

    await _sync_board_to_katago(game)
    search_plan = plan_ultimate_ai_search(
        game,
        get_territory_forbidden=_ultimate_get_territory_forbidden,
        get_game_visits=get_game_visits,
    )
    color = search_plan.color
    ai_card = search_plan.ai_card
    forbidden = search_plan.forbidden

    visits = search_plan.visits

    def _gen():
        with engine.command_lock:
            engine._send_command_locked(f"kata-set-param maxVisits {visits}")
            resp = engine._send_command_locked(f"genmove {color}", timeout=30)
            engine._send_command_locked(
                f"kata-set-param maxVisits {get_game_visits(game.level, 0, mode='ultimate')}")
            return resp.replace("=", "").strip()

    def _undo_engine_move() -> None:
        with engine.command_lock:
            engine._send_command_locked("undo")

    choice = await choose_ultimate_ai_move(
        game,
        color=color,
        visits=visits,
        forbidden=forbidden,
        generate_move=lambda: run_in_executor(_gen),
        no_resign_move=_ai_move_no_resign,
        undo_engine_move=_undo_engine_move,
        pick_ranked_legal_move=_pick_ranked_legal_move,
        pick_nonpass_fallback_move=_pick_nonpass_fallback_move,
        retry_avoiding_ko=_ai_retry_avoiding_ko,
        is_suspicious_ai_pass=_is_suspicious_ai_pass,
        resolve_occupied_ai_move=resolve_occupied_ai_move,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        log_fn=_engine_log,
    )
    gtp_move = choice.gtp_move
    coord = choice.coord

    await finish_ultimate_ai_turn(
        game,
        send_fn,
        color=color,
        ai_card=ai_card,
        gtp_move=gtp_move,
        coord=coord,
        allow_double_bonus=allow_double_bonus,
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


def _generated_ai_move_candidate_deps() -> GeneratedMoveCandidateDeps:
    return GeneratedMoveCandidateDeps(
        choose_candidate=choose_ai_move_candidate,
        choose_avoid_move=_ai_move_avoid_points,
        analyze_position=_analyze_current_position,
        choose_style_move=choose_ai_style_move,
        generate_move=_ai_generate_move,
        gtp_to_coord=gtp_to_coord,
        log_error=print,
    )


def _generated_ai_move_preparation_deps() -> GeneratedMovePreparationDeps:
    return GeneratedMovePreparationDeps(
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


def _generated_ai_move_finish_deps(run_engine_command) -> GeneratedMoveFinishDeps:
    return GeneratedMoveFinishDeps(
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


async def _try_finish_forced_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    run_engine_command,
) -> bool:
    return await try_finish_forced_rogue_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        roll_random=random.random,
        dice_pass_chance=ROGUE_DICE_PASS_CHANCE,
        mirror_chance=ROGUE_MIRROR_CHANCE,
        gtp_to_coord=gtp_to_coord,
        coord_to_gtp=coord_to_gtp,
        mirror_coord=_mirror_coord,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        run_engine_command=run_engine_command,
        finalize_forced_pass=finalize_forced_ai_pass,
        finalize_forced_stone=try_finalize_forced_ai_stone,
        apply_puppet_move=try_apply_puppet_ai_move,
        finish_ai_move=_finish_ai_move,
    )


async def _try_finish_rogue_restriction_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
    run_engine_command,
) -> bool:
    return await try_finish_rogue_restriction_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        choose_tengen_target=choose_tengen_target,
        tengen_followup_points=tengen_followup_points,
        gravity_allowed_points=gravity_allowed_points,
        lowline_allowed_points=lowline_allowed_points,
        sansan_opening_restriction=sansan_opening_restriction,
        coord_to_gtp=coord_to_gtp,
        finalize_forced_stone=try_finalize_forced_ai_stone,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        run_engine_command=run_engine_command,
        choose_allowed_move=_ai_move_avoid_points_allow_only,
        choose_avoid_move=_ai_move_avoid_points,
        finish_ai_move=_finish_ai_move,
        finish_allowed_restriction_move=try_finish_allowed_restriction_move,
        finish_sansan_restriction_move=try_finish_sansan_restriction_move,
    )


async def _try_finish_shadow_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
) -> bool:
    return await try_finish_shadow_restriction_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
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


async def _try_finish_suboptimal_rogue_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
) -> bool:
    return await try_finish_suboptimal_rogue_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        ai_move_count=turn.ai_move_count,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        roll_random=random.random,
        choose_suboptimal_move=_ai_move_suboptimal,
        finish_ai_move=_finish_ai_move,
    )


async def _try_finish_generated_ai_turn(
    game: GoGame,
    send_fn,
    turn: AiTurnSnapshot,
    ai_plan: AiMovePlan,
    run_engine_command,
) -> bool:
    forbidden = rogue_forbidden_points(
        game,
        turn.rogue_cards,
        turn.ai_move_count,
        challenge_zone_points=_challenge_zone_points,
    )

    return await try_finish_generated_ai_move(
        game,
        send_fn,
        color=turn.color,
        card=turn.card,
        rogue_cards=turn.rogue_cards,
        forbidden=forbidden,
        visits=ai_plan.visits,
        time_limit=ai_plan.time_limit,
        candidate_deps=_generated_ai_move_candidate_deps(),
        preparation_deps=_generated_ai_move_preparation_deps(),
        finish_deps=_generated_ai_move_finish_deps(run_engine_command),
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


def _ai_turn_flow_deps() -> AiTurnFlowDeps:
    return AiTurnFlowDeps(
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
    await run_ai_turn(game, send_fn, _ai_turn_flow_deps())


async def _ai_move_avoid_points(game, color, visits, time_limit, forbidden):
    _bind_ai_move_service_runtime()
    return await ai_move_service.avoid_points(game, color, visits, time_limit, forbidden)


async def _ai_move_avoid_points_allow_only(game, color, visits, time_limit,
                                           allowed: list[tuple[int, int]]):
    _bind_ai_move_service_runtime()
    return await ai_move_service.allow_only_points(game, color, visits, time_limit, allowed)


async def _ai_move_suboptimal(game, color, visits, time_limit, start_idx=2, end_idx=5):
    _bind_ai_move_service_runtime()
    return await ai_move_service.suboptimal_move(
        game,
        color,
        visits,
        time_limit,
        start_idx=start_idx,
        end_idx=end_idx,
    )


async def _ai_move_no_resign(game, color: str) -> str:
    _bind_ai_move_service_runtime()
    return await ai_move_service.no_resign_move(game, color)


async def _ai_retry_avoiding_ko(game, color):
    _bind_ai_move_service_runtime()
    return await ai_move_service.retry_avoiding_ko(game, color)


async def _ai_generate_move(color: str, visits: int, time_limit: float) -> str:
    _bind_ai_move_service_runtime()
    return await ai_move_service.generate_move(color, visits, time_limit)


async def _finish_ai_move(game, send_fn, color, card, gtp_move, rogue_msg=None):
    """Finalize a rogue-forced AI move: update game state and send messages."""
    await finalize_ai_move(
        game,
        send_fn,
        color=color,
        card=card,
        gtp_move=gtp_move,
        rogue_msg=rogue_msg,
        gtp_to_coord=gtp_to_coord,
        no_resign_move=_ai_move_no_resign,
        retry_avoiding_ko=_ai_retry_avoiding_ko,
        check_capture_foul=_check_capture_foul,
        prepare_player_turn_modifiers=_prepare_player_turn_modifiers,
        run_engine_command=_send_engine_command,
        run_coach_turn_if_needed=_run_coach_turn_if_needed,
    )


async def _generate_ai_style_move(game: GoGame, color: str, visits: int, time_limit: float) -> str:
    await _sync_board_to_katago(game)
    style = game.ai_style
    if game.ai_observer:
        style = game.ai_style_black if color == "B" else game.ai_style_white
    return await choose_or_generate_ai_style_move(
        game,
        color=color,
        visits=visits,
        time_limit=time_limit,
        style=style,
        analyze_position=_analyze_current_position,
        choose_style_move=choose_ai_style_move,
        generate_move=_ai_generate_move,
        gtp_to_coord=gtp_to_coord,
        play_chosen_move=_send_engine_command,
    )


def _place_auxiliary_ai_move_on_board(
    game: GoGame,
    color: str,
    gtp_move: str,
    coord: tuple[int, int] | None,
) -> AiMovePlacement:
    captured = 0
    game.moves.append((color, gtp_move))
    if gtp_move.upper() != "PASS" and coord:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    return AiMovePlacement(coord=coord, captured=captured)


async def _choose_coach_ai_move(game: GoGame, color: str) -> tuple[str, tuple[int, int] | None]:
    return await choose_coach_ai_move_state(
        game,
        color,
        CoachMoveChoiceDeps(
            get_game_visits=get_game_visits,
            generate_ai_style_move=_generate_ai_style_move,
            gtp_to_coord=gtp_to_coord,
            retry_avoiding_ko=_ai_retry_avoiding_ko,
            coach_visits=ROGUE_COACH_VISITS,
            max_move_time=MAX_MOVE_TIME,
        ),
    )


async def _run_coach_turn_if_needed(game: GoGame, send_fn):
    await run_coach_turn_if_needed_state(
        game,
        send_fn,
        CoachTurnDeps(
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
        ),
    )


async def _finish_observer_double_pass(game: GoGame, send_fn) -> bool:
    return await finish_observer_double_pass_state(
        game,
        send_fn,
        run_engine_command=_send_engine_command,
    )


def _apply_observer_ai_move_to_board(game: GoGame, color: str, gtp_move: str) -> AiMovePlacement:
    return apply_observer_ai_move_to_board_state(
        game,
        color,
        gtp_move,
        gtp_to_coord=gtp_to_coord,
        place_auxiliary_move=_place_auxiliary_ai_move_on_board,
    )


async def _run_ai_observer_loop(game: GoGame, send_fn):
    try:
        await run_ai_observer_loop_state(
            game,
            send_fn,
            AiObserverLoopDeps(
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
            ),
        )
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
