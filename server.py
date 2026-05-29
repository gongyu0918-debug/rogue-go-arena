"""
rogue-go-arena server - KataGo-powered board game with FastAPI WebSocket backend
"""
import argparse
import asyncio
import copy
import json
import random
import re
import time
import os
import sys
import tempfile
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
    RANK_VISITS,
    ROGUE_CAPTURE_FOUL_BASE,
    ROGUE_CAPTURE_FOUL_KOMI_PENALTY,
    ROGUE_CAPTURE_FOUL_STEP,
    ROGUE_CAPTURE_FOUL_THRESHOLD,
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
    ROGUE_NERF_BACKUP_AI_MOVES,
    ROGUE_NERF_BACKUP_CHANCE,
    ROGUE_NERF_FACTOR,
    ROGUE_NO_REGRET_CHANCE,
    ROGUE_QUICKTHINK_FIRST_SECONDS,
    ROGUE_QUICKTHINK_SECOND_SECONDS,
    ROGUE_SANSAN_TRAP_STONES,
    ROGUE_SANRENSEI_BONUS_STONES,
    ROGUE_SANRENSEI_OPENING_MOVES,
    ROGUE_SANRENSEI_REQUIRED_STARS,
    ROGUE_SANRENSEI_SUPPORT_STONES,
    ROGUE_SEAL_POINT_COUNT,
    ROGUE_SHADOW_CHANCE,
    ROGUE_SLIP_CHANCE,
    ROGUE_SUBOPTIMAL_AI_MOVES,
    ROGUE_TIME_PRESS_BACKUP_AI_MOVES,
    ROGUE_TIME_PRESS_BACKUP_CHANCE,
    ROGUE_TIME_PRESS_MAX_TIME,
    ROGUE_TIME_PRESS_MAX_VISITS,
    ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY,
    ULTIMATE_CAPTURE_FOUL_THRESHOLD,
    ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
    ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT,
    ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT,
    ULTIMATE_FOOLISH_CHAIN_DELAY,
    ULTIMATE_FOOLISH_FILL_COUNT,
    ULTIMATE_JOSEKI_BONUS_STONES,
    ULTIMATE_JOSEKI_REQUIRED_HITS,
    ULTIMATE_LAST_STAND_CLEAR_COUNT,
    ULTIMATE_LAST_STAND_SPAWN_COUNT,
    ULTIMATE_LAST_STAND_THRESHOLD,
    ULTIMATE_QUICKTHINK_SECONDS,
    ULTIMATE_TERRITORY_RADIUS,
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
from app.runtime.gpu_info import apply_runtime_gpu_overrides, detect_gpu_info
from app.runtime.status_payload import build_status_payload
from app.gameplay.card_selection import (
    pick_ai_rogue_card,
    pick_ai_ultimate_card,
    pick_challenge_beta_choices,
    pick_rogue_choices,
    pick_ultimate_choices,
)
from app.gameplay.ai_moves import (
    AiMoveService,
    compute_game_visits,
    choose_ai_style_move,
    choose_tengen_target,
    gravity_allowed_points,
    lowline_allowed_points,
    plan_rogue_ai_search,
    rogue_forbidden_points,
    sansan_opening_restriction,
    shadow_followup_points,
    tengen_followup_points,
)
from app.gameplay.effect_utils import (
    adjacent8_points as _adjacent8_points,
    adjacent_points as _adjacent_points,
    clear_random_enemy_stones as _clear_random_enemy_stones,
    count_stones as _count_stones,
    diamond_points as _diamond_points,
    find_exact_five_lines as _find_exact_five_lines,
    find_corner_with_min_stones as _find_corner_with_min_stones,
    find_new_fool_shapes as _find_new_fool_shapes,
    get_blackhole_points as _get_blackhole_points,
    get_corner_helper_spawn_points as _get_corner_helper_spawn_points,
    get_golden_corner_points as _get_golden_corner_points,
    get_sansan_points as _get_sansan_points,
    get_square_points as _get_square_points,
    get_star_points as _get_star_points,
    line_endpoints as _line_endpoints,
    line_key as _line_key,
    line_points_between as _line_points_between,
    mirror_coord as _mirror_coord,
    pick_joseki_targets as _pick_joseki_targets,
    random_hidden_center as _random_hidden_center,
    set_points_to_color as _set_points_to_color,
    shape_center as _shape_center,
    spawn_bonus_points as _spawn_bonus_points,
    spawn_random_owned_stones as _spawn_random_owned_stones,
    try_spawn_bonus_stone as _try_spawn_bonus_stone,
)
from app.gameplay.rogue_effects import (
    apply_rogue_card_uses,
    challenge_active_use_bonus as _challenge_active_use_bonus,
    challenge_category_counts_for_game as _challenge_category_counts,
    challenge_has_set as _challenge_has_set,
    challenge_remaining as _challenge_remaining,
    challenge_should_bonus_derivative as _challenge_should_bonus_derivative,
    challenge_zone_points as _challenge_zone_points,
    apply_player_rogue_board_effects,
    reset_rogue_effect_state,
    rogue_card_ids as _rogue_card_ids,
    rogue_has as _rogue_has,
)
from app.services.card_config_service import CardConfigService
from app.gameplay.ultimate_effects import apply_ultimate_board_effect, apply_ultimate_state_effect
from app.runtime.engine import KataGoEngine
from app.runtime.game_store import ActiveGameStore
from app.runtime.startup import EnginePaths, EngineStartupManager
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


# Rank ordering for slow-from comparison
_RANK_ORDER = list(RANK_VISITS.keys())


@app.get("/gpu")
async def get_gpu_info():
    info = await run_in_executor(_detect_gpu)
    return apply_runtime_gpu_overrides(
        info,
        cpu_mode=engine_runtime.cpu_mode,
        large_model_path=KATAGO_MODEL_LARGE,
    )


def _board_point_from_data(data: dict, size: int) -> Optional[tuple[int, int]]:
    try:
        x = int(data["x"])
        y = int(data["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= x < size and 0 <= y < size):
        return None
    return x, y


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
    await websocket.accept()
    websocket_closed = False

    # Restore existing game if this gameId is already known
    active_games.prune()
    game: Optional[GoGame] = active_games.get(game_id, touch=True)

    async def send(data: dict):
        nonlocal websocket_closed
        if websocket_closed:
            raise WebSocketDisconnect(code=1006)
        try:
            await websocket.send_text(json.dumps(data))
            active_games.touch(game_id)
        except WebSocketDisconnect:
            websocket_closed = True
            raise
        except RuntimeError as exc:
            message = str(exc)
            if (
                "websocket.close" in message
                or "WebSocket is not connected" in message
                or "response already completed" in message
            ):
                websocket_closed = True
                raise WebSocketDisconnect(code=1006) from exc
            raise

    async def send_error(msg: str):
        await send({"type": "error", "message": msg})

    async def do_analysis(g: GoGame) -> dict:
        if not engine.ready:
            result = {"winrate": 0.5, "score": 0.0, "top_moves": [],
                      "ownership": [], "analysis_ready": False}
            g.last_analysis = copy.deepcopy(result)
            return result
        await _sync_board_to_katago(g)
        color = g.current_player
        analysis_visits = max(80, min(get_game_visits(g.level, len(g.moves)) // 2, 1000))

        def _analyze():
            try:
                lines, ownership = engine.analyze(
                    color,
                    visits=analysis_visits,
                    interval=50,
                    duration=1.0,
                    extra_args=["rootInfo", "true", "ownership", "true"],
                )
                result = engine.parse_analysis(
                    lines,
                    ownership,
                    g.size,
                    to_move_color=color,
                )
                print(f"[Analysis] top_moves={len(result.get('top_moves',[]))} winrate={result.get('winrate')}")
                return result
            except Exception as ex:
                import traceback
                print(f"[Analysis] error: {ex}")
                traceback.print_exc()
                return {"winrate": 0.5, "score": 0.0, "top_moves": [],
                        "ownership": [], "analysis_ready": False}

        result = await run_in_executor(_analyze)
        g.last_analysis = copy.deepcopy(result)
        return result

    async def do_analysis_bg(g: GoGame):
        """Run analysis in background so the AI move is shown immediately."""
        try:
            move_count_before = len(g.moves)
            result = await do_analysis(g)
            # Skip sending if game state changed during analysis (stale)
            if g.game_over or len(g.moves) != move_count_before:
                return
            await send({"type": "analysis", **result})
        except WebSocketDisconnect:
            return
        except Exception as ex:
            print(f"[Analysis-bg] error: {ex}")

    ws_action_context = WebSocketActionContext(
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

    try:
        while True:
            data = json.loads(await websocket.receive_text())
            action = data.get("action")
            try:
                ws_action_context.game = game
                handler = WS_ACTION_HANDLERS.get(action)
                if handler is not None:
                    await handler(ws_action_context, data)
                    game = ws_action_context.game
                    continue

                continue

            except WebSocketDisconnect:
                raise
            except Exception as e:
                import traceback
                print(f"[WS {game_id}] Action error ({action}): {e}")
                traceback.print_exc()
                try:
                    await send_error(f"处理出错: {e}")
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass  # Keep game state for reconnection
    except Exception as e:
        print(f"[WS {game_id}] Fatal error: {e}")
        try:
            await send({"type": "error", "message": f"服务器错误: {e}"})
        except Exception:
            pass


def _record_ultimate_turn(game: GoGame) -> None:
    game.ultimate_move_count += 1


def _record_ultimate_player_action(game: GoGame) -> None:
    if game.ultimate_player_card == "quickthink" and game.ultimate_quickthink_active:
        if not game.ultimate_quickthink_turn_counted:
            _record_ultimate_turn(game)
            game.ultimate_quickthink_turn_counted = True
        return
    if not game.ultimate_double_pending:
        _record_ultimate_turn(game)


def _finish_ultimate_quickthink_turn(game: GoGame) -> None:
    game.ultimate_quickthink_active = False
    game.ultimate_quickthink_turn_counted = False


def _apply_score_penalty(game: GoGame, offender: str, amount: float) -> None:
    if offender == "B":
        game.komi += amount
    else:
        game.komi -= amount


async def _check_capture_foul(game: GoGame, send_fn, offender: str, captured: int, *, ultimate: bool) -> None:
    """Track capture-foul progress and penalise when threshold is met.

    The card only punishes the *opponent* of the card holder:
      - Rogue: player picks the card → only the AI is punished.
      - Ultimate: whoever picked the card → only the other side is punished.
    ``offender`` is the colour that just captured stones.
    """
    if captured <= 0:
        return
    if ultimate:
        # Determine which side(s) are protected by this card
        player_has = game.ultimate and game.ultimate_player_card == "capture_foul"
        ai_has = game.ultimate and game.ultimate_ai_card == "capture_foul"
        if not (player_has or ai_has):
            return
        # Only punish the opponent of the card holder
        if player_has and offender != game.ai_color:
            return  # player holds card → only AI gets punished
        if ai_has and offender != game.player_color:
            return  # AI holds card → only player gets punished
        progress = game.ultimate_capture_foul_progress
        progress[offender] += captured
        if progress[offender] < ULTIMATE_CAPTURE_FOUL_THRESHOLD:
            return
        _apply_score_penalty(game, offender, ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY)
        progress[offender] = 0
        await send_fn({
            "type": "rogue_event",
            "msg": f"🧺 提子犯规触发！{('黑棋' if offender == 'B' else '白棋')} 被罚 {ULTIMATE_CAPTURE_FOUL_SCORE_PENALTY:.0f} 目",
        })
        if engine.ready:
            await run_in_executor(engine.send_command, f"komi {game.komi}")
        return

    if game.rogue_card != "capture_foul":
        return
    # Rogue: player picks the card → only AI (opponent) is punished
    if offender != game.ai_color:
        return
    progress = game.rogue_capture_foul_progress
    progress[offender] += captured
    if progress[offender] < ROGUE_CAPTURE_FOUL_THRESHOLD:
        return
    chance = min(1.0, ROGUE_CAPTURE_FOUL_BASE + max(0, progress[offender] - ROGUE_CAPTURE_FOUL_THRESHOLD) * ROGUE_CAPTURE_FOUL_STEP)
    if random.random() > chance:
        return
    _apply_score_penalty(game, offender, ROGUE_CAPTURE_FOUL_KOMI_PENALTY)
    progress[offender] = 0
    await send_fn({
        "type": "rogue_event",
        "msg": f"🧺 提子犯规！{('黑棋' if offender == 'B' else '白棋')} 被罚 {ROGUE_CAPTURE_FOUL_KOMI_PENALTY:.1f} 目",
    })
    if engine.ready:
        await run_in_executor(engine.send_command, f"komi {game.komi}")


def _pick_fog_mask(size: int, rng: random.Random) -> list[tuple[int, int]]:
    cx = rng.randint(0, size - 1)
    cy = rng.randint(0, size - 1)
    return _get_square_points(cx, cy, ROGUE_FOG_MASK_RADIUS, size)


def _pick_fog_point(game, rng: random.Random) -> list[tuple[int, int]]:
    candidates = [
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
        if game.board[y][x] == 0
    ]
    if not candidates:
        return []
    return [rng.choice(candidates)]


def _get_player_bonus_forbidden_points(game: GoGame, color: str) -> set[tuple[int, int]]:
    if game.two_player:
        return set()
    if color != game.player_color:
        return set()
    return set(_get_ai_rogue_forbidden_points(game))


async def _estimate_side_winrate(game: GoGame, color: str) -> float:
    if not engine.ready:
        return 0.5
    await _sync_board_to_katago(game)

    def _analyze():
        try:
            lines, ownership = engine.analyze(
                game.current_player,
                visits=120,
                interval=50,
                duration=0.7,
                extra_args=["rootInfo", "true", "ownership", "false"],
            )
            result = engine.parse_analysis(
                lines,
                ownership,
                game.size,
                to_move_color=game.current_player,
            )
            black_wr = float(result.get("winrate", 0.5))
            return black_wr if color == "B" else 1.0 - black_wr
        except Exception:
            return 0.5

    try:
        return max(0.0, min(1.0, float(await run_in_executor(_analyze))))
    except Exception:
        return 0.5


async def _trigger_rogue_five_in_row(game: GoGame, send_fn, color: str):
    current_lines = set(_find_exact_five_lines(game, color))
    game.rogue_five_in_row_seen.intersection_update(current_lines)
    new_lines = [
        line
        for line in current_lines
        if line not in game.rogue_five_in_row_seen
    ]
    if not new_lines:
        return
    endpoints = []
    for line in new_lines:
        game.rogue_five_in_row_seen.add(line)
        sorted_line = sorted(line)
        x1, y1 = sorted_line[0]
        x2, y2 = sorted_line[1]
        dx, dy = x2 - x1, y2 - y1
        perp = (-dy, dx)
        start, end = _line_endpoints(line)
        for point, anchor in ((start, sorted_line[0]), (end, sorted_line[-1])):
            if not point:
                continue
            x, y = point
            if 0 <= x < game.size and 0 <= y < game.size and game.board[y][x] == 0:
                endpoints.append(point)
                continue
            ax, ay = anchor
            for px, py in ((ax + perp[0], ay + perp[1]), (ax - perp[0], ay - perp[1])):
                if 0 <= px < game.size and 0 <= py < game.size and game.board[py][px] == 0:
                    endpoints.append((px, py))
                    break
    changed = _spawn_bonus_points(game, endpoints, color)
    if changed:
        support_pool = []
        for line in new_lines:
            for px, py in line:
                for nx, ny in _adjacent8_points(px, py, game.size):
                    if game.board[ny][nx] == 0 and (nx, ny) not in support_pool:
                        support_pool.append((nx, ny))
        random.shuffle(support_pool)
        changed.extend(_spawn_bonus_points(game, support_pool[:ROGUE_FIVE_IN_ROW_SUPPORT_STONES], color))
    if changed and _challenge_should_bonus_derivative(game):
        extra_endpoints = [point for point in endpoints if point not in changed and game.board[point[1]][point[0]] == 0]
        random.shuffle(extra_endpoints)
        changed.extend(_spawn_bonus_points(game, extra_endpoints[:1], color))
    if changed:
        if engine.ready:
            await _sync_board_to_katago(game)
        await send_fn({
            "type": "rogue_event",
            "msg": f"🎯 五子连珠发动，正好连成 5 子，首尾额外补下 {len(changed)} 颗棋子",
        })


async def _trigger_rogue_last_stand(
    game: GoGame,
    send_fn,
    color: str,
    center: tuple[int, int],
):
    if game.rogue_last_stand_done.get(color):
        return
    if await _estimate_side_winrate(game, color) >= ROGUE_LAST_STAND_THRESHOLD:
        return
    area = _get_square_points(center[0], center[1], 1, game.size)
    rng = random.Random(time.time_ns())
    cleared = _clear_random_enemy_stones(game, color, ROGUE_LAST_STAND_CLEAR_COUNT, rng, area=area)
    forbidden = _get_player_bonus_forbidden_points(game, color)
    changed = _spawn_random_owned_stones(
        game,
        color,
        ROGUE_LAST_STAND_SPAWN_COUNT,
        rng,
        area=area,
        forbidden=forbidden,
    )
    if not cleared and not changed:
        return
    game.rogue_last_stand_done[color] = True
    if engine.ready:
        await _sync_board_to_katago(game)
    await send_fn({
        "type": "rogue_event",
        "msg": f"🫀 起死回生发动，在上一手周围扭转局面：清掉 {len(cleared)} 颗敌子，补下 {len(changed)} 颗己棋",
    })


async def _trigger_ultimate_last_stand(game: GoGame, send_fn, color: str):
    if game.ultimate_last_stand_done.get(color):
        return False
    if await _estimate_side_winrate(game, color) >= ULTIMATE_LAST_STAND_THRESHOLD:
        return False
    rng = random.Random(time.time_ns())
    cleared = _clear_random_enemy_stones(game, color, ULTIMATE_LAST_STAND_CLEAR_COUNT, rng)
    changed = _spawn_random_owned_stones(game, color, ULTIMATE_LAST_STAND_SPAWN_COUNT, rng)
    if not cleared and not changed:
        return False
    game.ultimate_last_stand_done[color] = True
    await send_fn({
        "type": "rogue_event",
        "msg": f"🫀 起死回生发动，绝境反扑：清掉 {len(cleared)} 颗敌子，并补下 {len(changed)} 颗己棋",
    })
    return bool(cleared or changed)


async def _trigger_ultimate_five_in_row(game: GoGame, send_fn, color: str):
    rng = random.Random(time.time_ns())
    total_cleared = 0
    total_spawned = 0
    chain_count = 0
    while True:
        new_lines = [
            line
            for line in _find_exact_five_lines(game, color)
            if line not in game.ultimate_five_in_row_seen
        ]
        if not new_lines:
            break
        for line in new_lines:
            game.ultimate_five_in_row_seen.add(line)
            cleared = _clear_random_enemy_stones(
                game, color, ULTIMATE_FIVE_IN_ROW_CLEAR_COUNT, rng
            )
            spawned = _spawn_random_owned_stones(
                game, color, ULTIMATE_FIVE_IN_ROW_SPAWN_COUNT, rng
            )
            if not cleared and not spawned:
                continue
            chain_count += 1
            total_cleared += len(cleared)
            total_spawned += len(spawned)
        if chain_count == 0:
            break
    if chain_count > 0:
        await send_fn({
            "type": "rogue_event",
            "msg": f"🎯 五子连珠爆发连锁 {chain_count} 次：随机清除 {total_cleared} 颗敌子，并补下 {total_spawned} 颗己棋",
        })
    return chain_count > 0


def _player_non_pass_coords(game: GoGame, color: str, limit: Optional[int] = None) -> list[tuple[int, int]]:
    coords = []
    for move_color, gtp in game.moves:
        if move_color != color or gtp.upper() == "PASS":
            continue
        coord = gtp_to_coord(gtp, game.size)
        if coord:
            coords.append(coord)
        if limit is not None and len(coords) >= limit:
            break
    return coords


async def _resolve_pending_ultimate_shadow_links(game: GoGame, send_fn) -> bool:
    if not game.ultimate_shadow_clone_links:
        return False
    pending = []
    modified = False
    for link in game.ultimate_shadow_clone_links:
        if game.ultimate_move_count < link["trigger_move"]:
            pending.append(link)
            continue
        changed = 0
        for px, py in _line_points_between(*link["from"], *link["to"]):
            if game.board[py][px] != link["color"]:
                game.board[py][px] = link["color"]
                changed += 1
        if changed:
            modified = True
            await send_fn({
                "type": "rogue_event",
                "msg": (
                    f"👥 影分身连线完成："
                    f"{coord_to_gtp(link['from'][0], link['from'][1], game.size)}"
                    f" 连到 "
                    f"{coord_to_gtp(link['to'][0], link['to'][1], game.size)}"
                    f"，铺开 {changed} 颗同色棋"
                ),
            })
    game.ultimate_shadow_clone_links = pending
    if modified:
        game.ko_point = None
    return modified


def _get_ai_rogue_forbidden_points(game: GoGame) -> list[tuple[int, int]]:
    card = game.ai_rogue_card
    if card in {"blackhole", "golden_corner", "fog"}:
        return list(game.ai_rogue_seal_points)
    return []


async def _challenge_apply_trap_bonus(game: GoGame, send_fn, source_name: str) -> None:
    if not _challenge_has_set(game, "trap"):
        return
    if random.random() > CHALLENGE_TRAP_EXTRA_TURN_CHANCE:
        return
    game.rogue_skip_ai = True
    await send_fn({
        "type": "rogue_event",
        "msg": f"陷阱套装触发：{source_name} 额外夺得一次落子权",
    })


def _weaken_rank(level: str, steps: int = 1) -> str:
    try:
        idx = _RANK_ORDER.index(level)
    except ValueError:
        return level
    return _RANK_ORDER[max(0, idx - steps)]


def _weaken_rank_one_step(level: str) -> str:
    return _weaken_rank(level, 1)


async def _challenge_maybe_reduce_ai_level(game: GoGame, send_fn) -> None:
    if not _challenge_has_set(game, "restriction"):
        return
    if random.random() >= CHALLENGE_RESTRICTION_DECAY_CHANCE:
        return
    new_level = _weaken_rank_one_step(game.level)
    if new_level == game.level:
        return
    game.level = new_level
    if engine.ready:
        visits = get_game_visits(game.level, len(game.moves), mode="rogue")
        await run_in_executor(engine.set_visits, visits)
    await send_fn({
        "type": "rogue_event",
        "msg": f"限制套装触发：AI 临时下调至 {RANK_LABELS.get(game.level, game.level)}",
    })


async def _challenge_emit_set_bonus_status(game: GoGame, send_fn) -> None:
    if not getattr(game, "challenge_beta", False):
        return
    counts = _challenge_category_counts(game)
    labels = {
        "derivative": "衍生",
        "trap": "陷阱",
        "zone": "限位",
        "restriction": "限制",
        "active": "主动",
    }
    active = [labels[key] for key, count in counts.items() if count >= CHALLENGE_SET_MIN_COUNT]
    if active:
        await send_fn({
            "type": "rogue_event",
            "msg": f"闯关套装已激活：{' / '.join(active)}",
        })


def _refresh_ai_rogue_player_turn(game: GoGame):
    if game.two_player or not game.ai_rogue_enabled:
        return
    if game.ai_rogue_card == "fog":
        if game.current_player == game.player_color:
            rng = random.Random(time.time_ns())
            player_move_count = sum(1 for c, m in game.moves if c == game.player_color and m.upper() != "PASS")
            if player_move_count < ROGUE_FOG_AI_MOVES:
                game.ai_rogue_seal_points = _pick_fog_mask(game.size, rng)
            else:
                fog_pts: list[tuple[int, int]] = []
                for _ in range(ROGUE_FOG_POST_MASK_POINTS):
                    fog_pts.extend(_pick_fog_point(game, rng))
                seen: set[tuple[int, int]] = set()
                game.ai_rogue_seal_points = [p for p in fog_pts if not (p in seen or seen.add(p))]
        else:
            game.ai_rogue_seal_points = []


def _prepare_player_turn_modifiers(game: GoGame):
    if game.two_player or game.current_player != game.player_color:
        return
    _refresh_ai_rogue_player_turn(game)
    if game.rogue_card == "quickthink" and game.rogue_quickthink_stage == 0:
        game.rogue_quickthink_stage = 1
    if game.ultimate and game.ultimate_player_card == "quickthink" and not game.ultimate_quickthink_active:
        game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True


def _clear_player_turn_modifiers(game: GoGame):
    game.rogue_quickthink_stage = 0
    _finish_ultimate_quickthink_turn(game)


async def _pick_analysis_point(game: GoGame, color: str, *, start_index: int = 0) -> Optional[tuple[int, int]]:
    if not engine.ready:
        return None

    def _analyze():
        visits = max(120, min(get_game_visits(game.level, len(game.moves), mode="rogue"), 800))
        lines, _ = engine.analyze(
            color,
            visits=visits,
            interval=40,
            duration=1.2,
            extra_args=["rootInfo", "true"],
        )
        result = engine.parse_analysis(lines, [], game.size, to_move_color=color)
        return result.get("top_moves", [])

    try:
        top_moves = await run_in_executor(_analyze)
    except Exception:
        return None

    for candidate in top_moves[start_index:]:
        move = candidate.get("move") or candidate.get("gtp")
        if not move or move.upper() == "PASS":
            continue
        coord = gtp_to_coord(move, game.size)
        if coord and game.board[coord[1]][coord[0]] == 0:
            return coord
    return None


async def _pick_second_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=1)


async def _pick_best_point(game: GoGame, color: str) -> Optional[tuple[int, int]]:
    return await _pick_analysis_point(game, color, start_index=0)


async def _activate_rogue_card(game: GoGame, send_fn, card_id: str):
    """Apply immediate effects when the player picks a rogue card."""
    cdef = get_rogue_card(card_id)
    game.rogue_card = card_id
    reset_rogue_effect_state(game)
    apply_rogue_card_uses(game, card_id, cdef)

    if card_id == "komi_relief":
        if game.player_color == "B":
            game.komi = max(0.5, game.komi - 7.0)
        else:
            game.komi = game.komi + 7.0
        if engine.ready:
            await run_in_executor(engine.send_command, f"komi {game.komi}")
    elif card_id == "seal":
        game.rogue_waiting_seal = True
    elif card_id == "blackhole":
        game.rogue_seal_points = _get_blackhole_points(game.size)
        await send_fn({"type": "rogue_event", "msg": "黑洞已锁定中央区域，整局都会限制 AI 进入"})
    elif card_id == "golden_corner":
        corner = random.randint(0, 3)
        game.rogue_seal_points = _get_golden_corner_points(game.size, corner, ROGUE_GOLDEN_CORNER_SPAN)
        corner_names = ["左上角", "右上角", "左下角", "右下角"]
        await send_fn({"type": "rogue_event",
                       "msg": f"黄金角已封锁 {corner_names[corner]} 的 {ROGUE_GOLDEN_CORNER_SPAN}x{ROGUE_GOLDEN_CORNER_SPAN} 区域，整局都会限制 AI 进入"})
    elif card_id == "joseki_ocd":
        game.rogue_joseki_targets = _pick_joseki_targets(
            game.size, ROGUE_JOSEKI_TARGET_COUNT)
        pts_str = ", ".join(
            coord_to_gtp(px, py, game.size)
            for px, py in game.rogue_joseki_targets)
        await send_fn({"type": "rogue_event",
                       "msg": f"定式强迫症已点亮 {ROGUE_JOSEKI_TARGET_COUNT} 个目标点：{pts_str}。"
                              f"命中其中 {ROGUE_JOSEKI_REQUIRED_HITS} 个后会自动补上剩余 "
                              f"{ROGUE_JOSEKI_TARGET_COUNT - ROGUE_JOSEKI_REQUIRED_HITS} 个点位"})
    elif card_id == "handicap_quest":
        await send_fn({"type": "rogue_event",
                       "msg": f"让子任务开始：你需要先虚手 {ROGUE_HANDICAP_REQUIRED_PASSES} 次，"
                              f"之后每下满 {ROGUE_HANDICAP_BONUS_INTERVAL} 手可再让 AI 虚手一次"})
    elif card_id == "god_hand":
        rng = random.Random(time.time_ns())
        game.rogue_godhand_center = _random_hidden_center(game.size, 2, rng)
        game.rogue_godhand_trigger = _diamond_points(
            game.rogue_godhand_center[0], game.rogue_godhand_center[1], ROGUE_GODHAND_RADIUS, game.size)
    elif card_id == "quickthink" and game.current_player == game.player_color:
        game.rogue_quickthink_stage = 1
    elif card_id == "coach_mode":
        game.rogue_uses.setdefault("coach_mode", 1)

    await send_fn({"type": "rogue_card_selected",
                   "card_id": card_id,
                   "name": cdef["name"],
                   "icon": cdef["icon"],
                   "waiting_seal": card_id == "seal",
                   **game.to_state()})


async def _activate_ai_rogue_card(game: GoGame, send_fn, card_id: str):
    cdef = get_rogue_card(card_id)
    game.ai_rogue_enabled = True
    game.ai_rogue_card = card_id
    game.ai_rogue_seal_points = []
    game.ai_rogue_sansan_trap_done = False

    if card_id == "blackhole":
        game.ai_rogue_seal_points = _get_blackhole_points(game.size)
    elif card_id == "golden_corner":
        corner = random.randint(0, 3)
        game.ai_rogue_seal_points = _get_golden_corner_points(game.size, corner, ROGUE_GOLDEN_CORNER_SPAN)
    elif card_id == "fog":
        _refresh_ai_rogue_player_turn(game)

    await send_fn({
        "type": "rogue_ai_selected",
        "card_id": card_id,
        "name": cdef["name"],
        "icon": cdef["icon"],
        **game.to_state(),
    })


async def _apply_challenge_rogue_loadout(game: GoGame, send_fn):
    cards = rogue_card_ids(game.challenge_cards)
    game.rogue_card = cards[-1] if cards else None
    reset_rogue_effect_state(game, reset_uses=True, reset_handicap=True)
    game.rogue_enabled = bool(cards)

    for card_id in cards:
        cdef = get_rogue_card(card_id)
        apply_rogue_card_uses(
            game,
            card_id,
            cdef,
            bonus=_challenge_active_use_bonus(game, card_id),
        )
        if card_id == "komi_relief":
            if game.player_color == "B":
                game.komi = max(0.5, game.komi - 7.0)
            else:
                game.komi = game.komi + 7.0
        elif card_id == "blackhole":
            game.rogue_seal_points.extend(_challenge_zone_points(game, _get_blackhole_points(game.size)))
        elif card_id == "golden_corner":
            corner = random.randint(0, 3)
            game.rogue_seal_points.extend(_challenge_zone_points(game, _get_golden_corner_points(game.size, corner, ROGUE_GOLDEN_CORNER_SPAN)))
        elif card_id == "joseki_ocd" and not game.rogue_joseki_targets:
            game.rogue_joseki_targets = _pick_joseki_targets(
                game.size, ROGUE_JOSEKI_TARGET_COUNT
            )
        elif card_id == "god_hand" and not game.rogue_godhand_trigger:
            rng = random.Random(time.time_ns())
            game.rogue_godhand_center = _random_hidden_center(game.size, 2, rng)
            game.rogue_godhand_trigger = _diamond_points(
                game.rogue_godhand_center[0], game.rogue_godhand_center[1], ROGUE_GODHAND_RADIUS, game.size
            )
        elif card_id == "quickthink" and game.current_player == game.player_color:
            game.rogue_quickthink_stage = 1
        elif card_id == "coach_mode":
            game.rogue_uses.setdefault("coach_mode", 1 + _challenge_active_use_bonus(game, card_id))

    if engine.ready:
        await run_in_executor(engine.send_command, f"komi {game.komi}")
    await _challenge_emit_set_bonus_status(game, send_fn)


async def _apply_player_rogue_move_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str, captured: int):
    """Apply player-side rogue effects after a successful move."""
    if _rogue_has(game, "erosion") and captured > 0:
        shift = ROGUE_EROSION_SHIFT * captured
        owner_color = color if game.two_player else game.player_color
        if owner_color == "B":
            game.komi -= shift
        else:
            game.komi += shift
        if engine.ready:
            await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                       "msg": f"蚕食触发：提掉 {captured} 子，当前贴目变为 {game.komi}"})

    board_effect = apply_player_rogue_board_effects(
        game,
        x=x,
        y=y,
        color=color,
        captured=captured,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )
    if board_effect.modified and engine.ready:
        await _sync_board_to_katago(game)
    for msg in board_effect.messages:
        await send_fn({"type": "rogue_event", "msg": msg})
    for source_name in board_effect.trap_bonus_sources:
        await _challenge_apply_trap_bonus(game, send_fn, source_name)

    if _rogue_has(game, "five_in_row"):
        await _trigger_rogue_five_in_row(game, send_fn, color)

    if _rogue_has(game, "last_stand"):
        await _trigger_rogue_last_stand(game, send_fn, color, (x, y))

    await _challenge_maybe_reduce_ai_level(game, send_fn)


async def _apply_ai_rogue_response_effects(game: GoGame, send_fn,
                                           x: int, y: int,
                                           color: str):
    if game.two_player or not game.ai_rogue_enabled:
        return
    if game.ai_rogue_card == "sansan_trap":
        coord = (x, y)
        if coord in _get_sansan_points(game.size):
            nearby = [
                (nx, ny)
                for nx, ny in _adjacent8_points(coord[0], coord[1], game.size)
                if game.board[ny][nx] == 0
            ]
            random.shuffle(nearby)
            changed = _spawn_bonus_points(game, nearby[:ROGUE_SANSAN_TRAP_STONES], game.ai_color)
            if changed:
                if engine.ready:
                    await _sync_board_to_katago(game)
                await send_fn({
                    "type": "rogue_event",
                    "msg": f"三三陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} 相邻点反打 {len(changed)} 子"
                })


def _sync_board_to_katago_locked(game: GoGame):
    """Reset KataGo board to match game.board using SGF loadsgf.
    Must be called while holding engine.command_lock."""
    sgf = f"(;GM[1]SZ[{game.size}]KM[{game.komi}]"
    blacks, whites = [], []
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] == 1:
                blacks.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
            elif game.board[y][x] == 2:
                whites.append(f"{chr(ord('a') + x)}{chr(ord('a') + y)}")
    if blacks:
        sgf += "AB" + "".join(f"[{p}]" for p in blacks)
    if whites:
        sgf += "AW" + "".join(f"[{p}]" for p in whites)
    sgf += ")"
    tmp = _gtp_safe_sync_sgf_path(game)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(sgf)
    engine._send_command_locked(f"loadsgf {tmp}")


def _has_gtp_unsafe_whitespace(path: str) -> bool:
    return any(ch.isspace() for ch in path)


def _gtp_safe_sync_sgf_path(game: GoGame) -> str:
    """Return a writable SGF path that KataGo GTP will not split on spaces."""
    base_drive = Path(BASE_DIR).anchor
    candidates = [
        os.environ.get("ROGUE_GO_ARENA_GTP_TMP"),
        tempfile.gettempdir(),
        os.path.join(base_drive, "rogue-go-arena-gtp") if base_drive else None,
        os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "rogue-go-arena-gtp"),
        r"C:\Temp\rogue-go-arena-gtp",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        candidate = os.path.abspath(candidate)
        if _has_gtp_unsafe_whitespace(candidate):
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            filename = f"sync-{os.getpid()}-{id(game)}.sgf"
            return Path(candidate, filename).as_posix()
        except OSError:
            continue
    raise RuntimeError("No whitespace-free writable path available for KataGo SGF sync")


async def _sync_board_to_katago(game: GoGame):
    """Reset KataGo board to match game.board (async wrapper)."""
    def _do():
        with engine.command_lock:
            _sync_board_to_katago_locked(game)
    await run_in_executor(_do)


def _ultimate_get_territory_forbidden(game: GoGame, for_color_val: int) -> set:
    """Get forbidden points for a color due to opponent's 绝对领地 card.
    for_color_val: the color (1=B,2=W) that wants to PLACE a stone."""
    forbidden = set()
    owner_val = 3 - for_color_val  # the card holder's stones
    for y in range(game.size):
        for x in range(game.size):
            if game.board[y][x] == owner_val:
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < game.size and 0 <= ny < game.size:
                            if abs(dx) + abs(dy) <= ULTIMATE_TERRITORY_RADIUS:
                                forbidden.add((nx, ny))
    return forbidden


async def _apply_ultimate_effect(game: GoGame, send_fn, x: int, y: int,
                                  color: str, card: str):
    """Apply a single ultimate card effect after a stone is placed at (x,y).
    Returns True if board was modified (needs KataGo sync)."""
    import time as _time
    rng = random.Random(_time.time_ns())
    size = game.size
    modified = False

    board_effect = apply_ultimate_board_effect(game, x=x, y=y, color=color, card=card)
    if board_effect is not None:
        for msg in board_effect.messages:
            await send_fn({"type": "rogue_event", "msg": msg})
        return board_effect.modified

    state_effect = apply_ultimate_state_effect(
        game,
        x=x,
        y=y,
        color=color,
        card=card,
        coord_to_gtp=coord_to_gtp,
        gtp_to_coord=gtp_to_coord,
    )
    if state_effect is not None:
        for msg in state_effect.messages:
            await send_fn({"type": "rogue_event", "msg": msg})
        return state_effect.modified

    if card == "five_in_row":
        if await _trigger_ultimate_five_in_row(game, send_fn, color):
            modified = True

    elif card == "last_stand":
        if await _trigger_ultimate_last_stand(game, send_fn, color):
            modified = True

    elif card == "foolish_wisdom":
        pending_shapes = _find_new_fool_shapes(game, color, game.ultimate_fool_shapes)
        wave = 0
        total_generated = 0
        while pending_shapes:
            for shape in pending_shapes:
                game.ultimate_fool_shapes.add(shape)
            empties = [
                (sx, sy)
                for sy in range(size)
                for sx in range(size)
                if game.board[sy][sx] == 0
            ]
            rng.shuffle(empties)
            batch = empties[:ULTIMATE_FOOLISH_FILL_COUNT]
            if not batch:
                break
            placed = _spawn_bonus_points(game, batch, color)
            if placed:
                modified = True
            wave += 1
            total_generated += len(placed)
            await send_fn({"type": "rogue_event",
                           "msg": f"🪤 大智若愚第 {wave} 波发动，识别到 {len(pending_shapes)} 个愚形，生成 {len(placed)} 颗己方棋子"})
            pending_shapes = _find_new_fool_shapes(game, color, game.ultimate_fool_shapes)
            if pending_shapes:
                await asyncio.sleep(ULTIMATE_FOOLISH_CHAIN_DELAY)
        if total_generated > 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"🪤 大智若愚连锁结束，本次共生成 {total_generated} 颗己方棋子"})

    return modified


async def _ultimate_force_score(game: GoGame, send_fn):
    """Force game end in ultimate mode — count stones for scoring."""
    game.game_over = True
    # Simple area scoring: count stones + enclosed territory
    b_score = 0
    w_score = 0
    size = game.size
    visited = [[False] * size for _ in range(size)]

    # Count stones
    for y in range(size):
        for x in range(size):
            if game.board[y][x] == 1:
                b_score += 1
            elif game.board[y][x] == 2:
                w_score += 1

    # Flood fill for territory
    for y in range(size):
        for x in range(size):
            if game.board[y][x] == 0 and not visited[y][x]:
                # BFS
                region = []
                stack = [(x, y)]
                borders = set()
                while stack:
                    cx, cy = stack.pop()
                    if visited[cy][cx]:
                        continue
                    visited[cy][cx] = True
                    region.append((cx, cy))
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < size and 0 <= ny < size:
                            if game.board[ny][nx] == 0 and not visited[ny][nx]:
                                stack.append((nx, ny))
                            elif game.board[ny][nx] != 0:
                                borders.add(game.board[ny][nx])
                if len(borders) == 1:
                    owner = borders.pop()
                    if owner == 1:
                        b_score += len(region)
                    else:
                        w_score += len(region)

    b_score_final = b_score
    w_score_final = w_score + game.komi
    if b_score_final > w_score_final:
        winner = "B"
        score_str = f"B+{b_score_final - w_score_final:.1f}"
    else:
        winner = "W"
        score_str = f"W+{w_score_final - b_score_final:.1f}"

    game.winner = winner
    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})
    await send_fn({"type": "game_over", "winner": winner,
                    "score": score_str, "reason": "ultimate_20moves"})


def _is_suspicious_ai_pass(game: GoGame, gtp_move: str, color: str) -> bool:
    if gtp_move.upper() != "PASS":
        return False
    non_pass_moves = sum(1 for c, m in game.moves if c == color and m.upper() != "PASS")
    empty_points = sum(1 for row in game.board for cell in row if cell == 0)
    return non_pass_moves < 3 and empty_points > max(20, game.size * 2)


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


async def _ultimate_ai_move(game: GoGame, send_fn,
                            allow_double_bonus: bool = True):
    """AI move in ultimate mode - generates move, applies AI's card effect."""
    if game.game_over or not engine.ready:
        return

    game.ultimate_extra_turn = False
    color = game.ai_color
    ai_card = game.ultimate_ai_card
    cv = 1 if color == "B" else 2

    forbidden = set()
    if game.ultimate_player_card == "territory":
        forbidden = _ultimate_get_territory_forbidden(game, cv)

    await _sync_board_to_katago(game)
    visits = get_game_visits(game.level, len(game.moves), mode="ultimate")

    def _gen():
        with engine.command_lock:
            engine._send_command_locked(f"kata-set-param maxVisits {visits}")
            resp = engine._send_command_locked(f"genmove {color}", timeout=30)
            engine._send_command_locked(
                f"kata-set-param maxVisits {get_game_visits(game.level, 0, mode='ultimate')}")
            return resp.replace("=", "").strip()

    gtp_move = await run_in_executor(_gen)
    if gtp_move.upper() == "RESIGN":
        gtp_move = await _ai_move_no_resign(game, color)

    if forbidden and gtp_move.upper() not in ("PASS", "RESIGN"):
        coord = gtp_to_coord(gtp_move, game.size)
        if coord and coord in forbidden:
            with engine.command_lock:
                engine._send_command_locked("undo")
            ranked = await _pick_ranked_legal_move(game, color, visits, forbidden, time_limit=1.2)
            gtp_move = ranked or "pass"

    if _is_suspicious_ai_pass(game, gtp_move, color):
        fallback_move = await _pick_nonpass_fallback_move(game, color, visits, forbidden)
        if fallback_move:
            _engine_log(f"Suspicious early PASS in ultimate mode, replaced with {fallback_move}")
            gtp_move = fallback_move

    coord = gtp_to_coord(gtp_move, game.size)
    if gtp_move.upper() != "PASS" and coord:
        x, y = coord
        if game.board[y][x] != 0:
            import time as _time
            rng = random.Random(_time.time_ns())
            empties = [(sx, sy) for sy in range(game.size) for sx in range(game.size)
                       if game.board[sy][sx] == 0
                       and game.is_legal_move(sx, sy, color)]
            if empties:
                x, y = rng.choice(empties)
                gtp_move = coord_to_gtp(x, y, game.size)
                coord = (x, y)
            else:
                gtp_move = "pass"
                coord = None

    # Ko guard: if the AI move violates ko, play elsewhere (ko threat)
    if gtp_move.upper() != "PASS" and coord and game.is_ko(coord[0], coord[1], color):
        gtp_move = await _ai_retry_avoiding_ko(game, color)
        coord = gtp_to_coord(gtp_move, game.size) if gtp_move.upper() not in ("PASS", "RESIGN") else None

    if allow_double_bonus:
        _record_ultimate_turn(game)
    game.moves.append((color, gtp_move))

    captured = 0
    if gtp_move.upper() != "PASS" and coord:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    await _check_capture_foul(game, send_fn, color, captured, ultimate=True)

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})

    board_modified = False
    opp_val = 1 if color == "W" else 2
    opp_before = _count_stones(game, opp_val)
    if ai_card and coord and gtp_move.upper() != "PASS":
        board_modified = await _apply_ultimate_effect(
            game, send_fn, coord[0], coord[1], color, ai_card)
    pending_modified = await _resolve_pending_ultimate_shadow_links(game, send_fn)
    if board_modified or pending_modified:
        # AI-side ultimate effects can rewrite the visible board directly.
        # Sync immediately so the engine does not continue from a stale
        # pre-effect position on the player's next move.
        await _sync_board_to_katago(game)
        # Card effects that removed opponent stones count toward capture-foul
        effect_removed = max(0, opp_before - _count_stones(game, opp_val))
        if effect_removed > 0:
            await _check_capture_foul(game, send_fn, color, effect_removed, ultimate=True)

    chain_bonus = (
        ai_card == "chain"
        and gtp_move.upper() != "PASS"
        and random.random() < ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
        and not game.game_over
    )
    double_bonus = (
        ai_card == "double"
        and allow_double_bonus
        and not game.game_over
        and gtp_move.upper() != "PASS"
    )

    if chain_bonus:
        game.ultimate_extra_turn = True
        game.current_player = color
        await send_fn({"type": "rogue_event", "msg": "AI 的连珠棋触发，AI 将继续落子"})
        await send_fn({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count < 20:
            await _ultimate_ai_move(game, send_fn)
            return

    if double_bonus:
        game.ultimate_extra_turn = True
        game.current_player = color
        await send_fn({"type": "rogue_event", "msg": "AI 的双刀流触发，AI 将继续落子"})
        await send_fn({"type": "game_state", **game.to_state()})
        if game.ultimate_move_count < 20:
            await _ultimate_ai_move(game, send_fn, allow_double_bonus=False)
            return

    game.ultimate_extra_turn = False
    game.current_player = game.player_color
    _prepare_player_turn_modifiers(game)
    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if game.ultimate_move_count >= 20:
        await _ultimate_force_score(game, send_fn)


async def _ai_move(game: GoGame, send_fn):
    if game.game_over or not engine.ready:
        return

    await _sync_board_to_katago(game)

    color = game.ai_color
    card = game.rogue_card
    rogue_cards = set(_rogue_card_ids(game))
    move_count = len(game.moves)
    ai_move_count = sum(1 for c, _ in game.moves if c == color)

    if "dice" in rogue_cards and random.random() < ROGUE_DICE_PASS_CHANCE:
        await run_in_executor(engine.send_command, f"play {color} pass")
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = game.player_color
        _prepare_player_turn_modifiers(game)
        game.push_history()
        await send_fn({"type": "game_state", **game.to_state()})
        await send_fn({"type": "ai_move", "gtp": "pass", "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "rogue_event",
                        "msg": "掷骰触发，AI 这手选择虚手"})
        return

    if "mirror" in rogue_cards and random.random() < ROGUE_MIRROR_CHANCE and move_count > 0:
        last_color, last_gtp = game.moves[-1]
        if last_color == game.player_color and last_gtp.upper() != "PASS":
            lc = gtp_to_coord(last_gtp, game.size)
            if lc:
                mx, my = _mirror_coord(lc[0], lc[1], game.size)
                if game.board[my][mx] == 0 and not game.is_ko(mx, my, color):
                    m_gtp = coord_to_gtp(mx, my, game.size)
                    resp = await run_in_executor(
                        engine.send_command, f"play {color} {m_gtp}")
                    if "?" not in resp:
                        game.moves.append((color, m_gtp))
                        game.place_stone(mx, my, color)
                        game.passed[color] = False
                        game.current_player = game.player_color
                        _prepare_player_turn_modifiers(game)
                        game.push_history()
                        await send_fn({"type": "game_state", **game.to_state()})
                        await send_fn({"type": "ai_move", "gtp": m_gtp,
                                        "color": color, "x": mx, "y": my})
                        await send_fn({"type": "rogue_event",
                                        "msg": f"镜像触发，AI 在对称点 {m_gtp} 落子"})
                        return

    if "exchange" in rogue_cards and game.rogue_skip_ai:
        game.rogue_skip_ai = False
        await run_in_executor(engine.send_command, f"play {color} pass")
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = game.player_color
        _prepare_player_turn_modifiers(game)
        game.push_history()
        await send_fn({"type": "game_state", **game.to_state()})
        await send_fn({"type": "ai_move", "gtp": "pass", "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "rogue_event",
                        "msg": "乾坤挪移生效，AI 本回合虚手并把回合交还给你"})
        return

    if "puppet" in rogue_cards and game.rogue_puppet_target is not None:
        tx, ty = game.rogue_puppet_target
        puppet_gtp = coord_to_gtp(tx, ty, game.size)
        game.rogue_puppet_target = None
        if game.board[ty][tx] != 0:
            await send_fn({"type": "rogue_event",
                           "msg": f"🎭 傀儡术目标 {puppet_gtp} 已被占用，AI 改为正常应手"})
        elif game.is_ko(tx, ty, color) or not game.is_legal_move(tx, ty, color):
            await send_fn({"type": "rogue_event",
                           "msg": f"🎭 傀儡术目标 {puppet_gtp} 当前不合法，AI 改为正常应手"})
        else:
            resp = await run_in_executor(engine.send_command, f"play {color} {puppet_gtp}")
            if "?" not in resp:
                if game.rogue_uses.get("puppet", 0) > 0:
                    game.rogue_uses["puppet"] -= 1
                await _finish_ai_move(
                    game,
                    send_fn,
                    color,
                    card,
                    puppet_gtp,
                    f"🎭 傀儡术生效，AI 被迫落子于 {puppet_gtp}",
                )
                await send_fn({"type": "rogue_uses_update", "uses": game.rogue_uses})
                return
            await send_fn({"type": "rogue_event",
                           "msg": f"🎭 傀儡术目标 {puppet_gtp} 执行失败，AI 改为正常应手"})

    ai_plan = plan_rogue_ai_search(
        game,
        rogue_cards,
        move_count=move_count,
        ai_move_count=ai_move_count,
        get_game_visits=get_game_visits,
        weaken_rank=_weaken_rank,
    )
    visits = ai_plan.visits
    time_limit = ai_plan.time_limit

    if "fog" in rogue_cards:
        rng = random.Random(time.time_ns())
        if ai_move_count < ROGUE_FOG_AI_MOVES:
            game.rogue_seal_points = _challenge_zone_points(game, _pick_fog_mask(game.size, rng))
            fog_msg = "🌫 战争迷雾刷新：3×3 禁区本回合对 AI 禁止落子"
        else:
            fog_pts: list[tuple[int, int]] = []
            for _ in range(ROGUE_FOG_POST_MASK_POINTS):
                fog_pts.extend(_challenge_zone_points(game, _pick_fog_point(game, rng)))
            # deduplicate while preserving order
            seen: set[tuple[int, int]] = set()
            unique_fog_pts = [p for p in fog_pts if not (p in seen or seen.add(p))]
            game.rogue_seal_points = unique_fog_pts
            fog_msg = f"🌫 战争迷雾残留：本回合随机封锁 {ROGUE_FOG_POST_MASK_POINTS} 个 AI 禁着点"
        await send_fn({"type": "game_state", **game.to_state()})
        if game.rogue_seal_points:
            await send_fn({"type": "rogue_event", "msg": fog_msg})

    if "tengen" in rogue_cards:
        target_plan = choose_tengen_target(game, ai_move_count)
        if target_plan:
            tx, ty = target_plan.coord
            if game.board[ty][tx] == 0 and not game.is_ko(tx, ty, color):
                t_gtp = coord_to_gtp(tx, ty, game.size)
                resp = await run_in_executor(
                    engine.send_command, f"play {color} {t_gtp}")
                if "?" not in resp:
                    game.moves.append((color, t_gtp))
                    game.place_stone(tx, ty, color)
                    game.passed[color] = False
                    game.current_player = game.player_color
                    _prepare_player_turn_modifiers(game)
                    await send_fn({"type": "game_state", **game.to_state()})
                    await send_fn({"type": "ai_move", "gtp": t_gtp,
                                    "color": color, "x": tx, "y": ty})
                    await send_fn({"type": "rogue_event", "msg": target_plan.message})
                    return
        restriction = tengen_followup_points(game, ai_move_count)
        if restriction:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, restriction.points)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move, restriction.message)
                return

    if "gravity" in rogue_cards:
        restriction = gravity_allowed_points(game, ai_move_count)
        if restriction:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, restriction.points)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                      restriction.message)
                return

    if "lowline" in rogue_cards:
        restriction = lowline_allowed_points(game, ai_move_count)
        if restriction:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, restriction.points)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                      restriction.message)
                return

    if "sansan" in rogue_cards:
        restriction = sansan_opening_restriction(game, ai_move_count)
        if restriction:
            if restriction.kind == "allow_only":
                gtp_move = await _ai_move_avoid_points_allow_only(
                    game, color, visits, time_limit, restriction.points)
                if gtp_move:
                    await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                          restriction.message)
                    return
            gtp_move = await _ai_move_avoid_points(
                game, color, visits, time_limit, restriction.points)
            await _finish_ai_move(game, send_fn, color, card, gtp_move, restriction.message)
            return

    if (
        "shadow" in rogue_cards
        and random.random() < gameplay_config.ROGUE_SHADOW_CHANCE
    ):
        restriction = shadow_followup_points(
            game,
            color,
            ai_move_count,
            gtp_to_coord=gtp_to_coord,
        )
        if restriction:
            gtp_move = await _ai_move_avoid_points_allow_only(
                game, color, visits, time_limit, restriction.points)
            if gtp_move:
                await _finish_ai_move(game, send_fn, color, card, gtp_move, restriction.message)
                return

    if ("nerf" in rogue_cards
            and ai_move_count < ROGUE_NERF_BACKUP_AI_MOVES
            and random.random() < ROGUE_NERF_BACKUP_CHANCE):
        gtp_move = await _ai_move_suboptimal(game, color, visits, time_limit, start_idx=1, end_idx=5)
        if gtp_move:
            await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                  "弱化触发，AI 在多个备选点里误选了一手")
            return

    if ("time_press" in rogue_cards
            and ai_move_count < ROGUE_TIME_PRESS_BACKUP_AI_MOVES
            and random.random() < ROGUE_TIME_PRESS_BACKUP_CHANCE):
        gtp_move = await _ai_move_suboptimal(game, color, visits, time_limit, start_idx=1, end_idx=4)
        if gtp_move:
            await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                  "限时压制触发，AI 仓促落在了备选点上")
            return

    if "suboptimal" in rogue_cards and ai_move_count < ROGUE_SUBOPTIMAL_AI_MOVES:
        gtp_move = await _ai_move_suboptimal(game, color, visits, time_limit)
        if gtp_move:
            await _finish_ai_move(game, send_fn, color, card, gtp_move,
                                  "次优之选触发，AI 采用了较弱备选点")
            return

    forbidden = rogue_forbidden_points(
        game,
        rogue_cards,
        ai_move_count,
        challenge_zone_points=_challenge_zone_points,
    )

    if forbidden:
        gtp_move = await _ai_move_avoid_points(
            game, color, visits, time_limit, forbidden)
    else:
        gtp_move = None
        if not rogue_cards and game.ai_style != "balanced":
            try:
                analysis = await do_analysis(game)
                gtp_move = choose_ai_style_move(
                    game,
                    color,
                    analysis.get("top_moves", []),
                    game.ai_style,
                    gtp_to_coord=gtp_to_coord,
                )
            except Exception:
                gtp_move = None
        if not gtp_move:
            resp = await _ai_generate_move(color, visits, time_limit)
            if game.game_over:
                return
            if "?" in resp:
                print(f"[AI] genmove returned error: {resp}")
                return
            gtp_move = resp.replace("=", "").strip()

    if _is_suspicious_ai_pass(game, gtp_move, color):
        fallback_move = await _pick_nonpass_fallback_move(game, color, visits)
        if fallback_move:
            _engine_log(f"Suspicious early PASS in rogue/normal mode, replaced with {fallback_move}")
            gtp_move = fallback_move

    if gtp_move.upper() == "RESIGN":
        if rogue_cards:
            gtp_move = await _ai_move_no_resign(game, color)
        else:
            game.game_over = True
            game.winner = game.player_color
            await send_fn({"type": "game_over", "winner": game.player_color,
                            "score": None, "reason": "ai_resign"})
            return

    slip_msg = None
    needs_sync = False
    if "slip" in rogue_cards and gtp_move.upper() not in {"PASS", "RESIGN"} and random.random() < ROGUE_SLIP_CHANCE:
        original_gtp = gtp_move
        original_coord = gtp_to_coord(gtp_move, game.size)
        if original_coord:
            nearby = [
                (nx, ny)
                for nx, ny in _adjacent_points(original_coord[0], original_coord[1], game.size)
                if game.board[ny][nx] == 0 and game.is_legal_move(nx, ny, color)
            ]
            if nearby:
                sx, sy = random.choice(nearby)
                gtp_move = coord_to_gtp(sx, sy, game.size)
                needs_sync = True
                slip_msg = f"手滑了触发，AI 原本想下 {original_gtp}，结果滑到 {gtp_move}"

    # Ko guard: if the AI move violates ko, play elsewhere (ko threat)
    if gtp_move.upper() not in ("PASS", "RESIGN"):
        _pre_coord = gtp_to_coord(gtp_move, game.size)
        if _pre_coord and game.is_ko(_pre_coord[0], _pre_coord[1], color):
            gtp_move = await _ai_retry_avoiding_ko(game, color)
            slip_msg = None

    game.moves.append((color, gtp_move))

    captured = 0
    if gtp_move.upper() != "PASS":
        coord = gtp_to_coord(gtp_move, game.size)
        if coord:
            captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        coord = None
        game.passed[color] = True

    extra_board_change = False
    if card == "sansan_trap" and coord in _get_sansan_points(game.size):
        player_color = game.player_color
        nearby = [(nx, ny) for nx, ny in _adjacent8_points(coord[0], coord[1], game.size) if game.board[ny][nx] == 0]
        random.shuffle(nearby)
        changed = _spawn_bonus_points(game, nearby[:ROGUE_SANSAN_TRAP_STONES], player_color)
        if changed:
            extra_board_change = True
            await send_fn({"type": "rogue_event",
                           "msg": f"△ 三三陷阱发动，在 {coord_to_gtp(coord[0], coord[1], game.size)} 相邻点反打 {len(changed)} 子"})
            await _challenge_apply_trap_bonus(game, send_fn, "三三陷阱")

    if (needs_sync or extra_board_change) and engine.ready:
        await _sync_board_to_katago(game)
        needs_sync = False
        extra_board_change = False

    if (
        _rogue_has(game, "no_regret")
        and random.random() < ROGUE_NO_REGRET_CHANCE
        and not game.game_over
    ):
        bonus = await _pick_best_point(game, game.player_color)
        if bonus:
            changed = _spawn_bonus_points(game, [bonus], game.player_color)
            if changed:
                extra_board_change = True
                await send_fn({"type": "rogue_event",
                               "msg": f"🚫 永不悔棋发动，AI 落子后在 {coord_to_gtp(bonus[0], bonus[1], game.size)} 赠送一子"})

    if needs_sync or extra_board_change:
        await _sync_board_to_katago(game)

    game.current_player = game.player_color
    _prepare_player_turn_modifiers(game)

    if card == "erosion" and captured > 0:
        shift = ROGUE_EROSION_SHIFT * captured
        if game.ai_color == "W":
            game.komi += shift
        else:
            game.komi -= shift
        await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                        "msg": f"蚕食反制：AI 提掉了 {captured} 子，当前贴目变为 {game.komi}"})

    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if game.passed["B"] and game.passed["W"]:
        resp_score = await run_in_executor(engine.send_command, "final_score")
        score_str = resp_score.replace("=", "").strip()
        winner = "B" if score_str.startswith("B") else "W"
        game.game_over = True
        game.winner = winner
        await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                        "x": None, "y": None})
        if slip_msg:
            await send_fn({"type": "rogue_event", "msg": slip_msg})
        await send_fn({"type": "game_over", "winner": winner,
                        "score": score_str, "reason": "double_pass"})
        return

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})
    if slip_msg:
        await send_fn({"type": "rogue_event", "msg": slip_msg})
    await _run_coach_turn_if_needed(game, send_fn)


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
    if game.game_over:
        return

    if gtp_move.upper() == "RESIGN":
        if card:
            gtp_move = await _ai_move_no_resign(game, color)
        else:
            game.game_over = True
            game.winner = game.player_color
            await send_fn({"type": "game_over", "winner": game.player_color,
                            "score": None, "reason": "ai_resign"})
            return

    coord = gtp_to_coord(gtp_move, game.size)
    # Ko guard: if the AI move violates ko, play elsewhere (ko threat)
    if coord and gtp_move.upper() != "PASS" and game.is_ko(coord[0], coord[1], color):
        gtp_move = await _ai_retry_avoiding_ko(game, color)
        coord = gtp_to_coord(gtp_move, game.size) if gtp_move.upper() not in ("PASS", "RESIGN") else None

    game.moves.append((color, gtp_move))
    captured = 0
    if gtp_move.upper() != "PASS":
        if coord:
            captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    await _check_capture_foul(game, send_fn, color, captured, ultimate=False)

    game.current_player = game.player_color
    _prepare_player_turn_modifiers(game)

    # Erosion effect (applies even with other cards — only if card is erosion)
    if card == "erosion" and captured > 0:
        shift = ROGUE_EROSION_SHIFT * captured
        if game.ai_color == "W":
            game.komi += shift
        else:
            game.komi -= shift
        await run_in_executor(engine.send_command, f"komi {game.komi}")
        await send_fn({"type": "rogue_event",
                        "msg": f"🐛 蚕食！AI 提 {captured} 子，贴目变为 {game.komi}"})

    game.push_history()
    await send_fn({"type": "game_state", **game.to_state()})

    if game.passed["B"] and game.passed["W"]:
        resp_score = await run_in_executor(engine.send_command, "final_score")
        score_str = resp_score.replace("=", "").strip()
        winner = "B" if score_str.startswith("B") else "W"
        game.game_over = True
        game.winner = winner
        await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                        "x": None, "y": None})
        await send_fn({"type": "game_over", "winner": winner,
                        "score": score_str, "reason": "double_pass"})
        return

    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color,
                    "x": coord[0] if coord else None,
                    "y": coord[1] if coord else None})
    if rogue_msg:
        await send_fn({"type": "rogue_event", "msg": rogue_msg})
    await _run_coach_turn_if_needed(game, send_fn)


async def _generate_ai_style_move(game: GoGame, color: str, visits: int, time_limit: float) -> str:
    await _sync_board_to_katago(game)
    style = game.ai_style
    if game.ai_observer:
        style = game.ai_style_black if color == "B" else game.ai_style_white
    chosen = None
    if style != "balanced":
        try:
            analysis = await do_analysis(game)
            chosen = choose_ai_style_move(
                game,
                color,
                analysis.get("top_moves", []),
                style,
                gtp_to_coord=gtp_to_coord,
            )
        except Exception:
            chosen = None
    if chosen:
        await run_in_executor(engine.send_command, f"play {color} {chosen}")
        return chosen

    resp = await _ai_generate_move(color, visits, time_limit)
    return resp.replace("=", "").strip()


async def _run_coach_turn_if_needed(game: GoGame, send_fn):
    if (
        game.game_over
        or game.two_player
        or game.current_player != game.player_color
        or game.rogue_card != "coach_mode"
        or game.rogue_coach_moves_left <= 0
        or not engine.ready
    ):
        return

    color = game.player_color
    visits = max(ROGUE_COACH_VISITS, get_game_visits(game.level, len(game.moves), mode="rogue"))
    time_limit = min(MAX_MOVE_TIME, 8.0)
    gtp_move = await _generate_ai_style_move(game, color, visits, time_limit)
    if gtp_move.upper() == "RESIGN":
        gtp_move = "pass"
    coord = gtp_to_coord(gtp_move, game.size)
    # Ko guard: play elsewhere instead of passing
    if coord and gtp_move.upper() != "PASS" and game.is_ko(coord[0], coord[1], color):
        gtp_move = await _ai_retry_avoiding_ko(game, color)
        coord = gtp_to_coord(gtp_move, game.size) if gtp_move.upper() not in ("PASS", "RESIGN") else None
    captured = 0
    game.moves.append((color, gtp_move))
    if gtp_move.upper() != "PASS" and coord:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    game.current_player = game.ai_color
    game.rogue_coach_moves_left = max(0, game.rogue_coach_moves_left - 1)
    await _check_capture_foul(game, send_fn, color, captured, ultimate=False)
    if coord:
        await _apply_player_rogue_move_effects(game, send_fn, coord[0], coord[1], color, captured)
        await _apply_ai_rogue_response_effects(game, send_fn, coord[0], coord[1], color)
    game.push_history()
    await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color, "x": coord[0] if coord else None, "y": coord[1] if coord else None})
    await send_fn({"type": "rogue_event", "msg": f"🎓 代练上号：强化 AI 接管了一手，剩余 {game.rogue_coach_moves_left} 手"})
    await send_fn({"type": "game_state", **game.to_state()})
    if game.rogue_coach_moves_left == 0 and not game.rogue_coach_bonus_checked:
        game.rogue_coach_bonus_checked = True
        if await _estimate_side_winrate(game, color) < ROGUE_COACH_BONUS_THRESHOLD:
            game.rogue_coach_moves_left += ROGUE_COACH_BONUS_TURNS
            await send_fn({"type": "rogue_event", "msg": f"🎓 代练上号追加触发：胜率仍低于 50%，额外再代打 {ROGUE_COACH_BONUS_TURNS} 手"})
    if not game.game_over and engine.ready and game.current_player == game.ai_color:
        await _ai_move(game, send_fn)


async def _run_ai_observer_loop(game: GoGame, send_fn):
    try:
        while not game.game_over and game.ai_observer and engine.ready:
            await _sync_board_to_katago(game)
            color = game.current_player
            level = game.ai_level_black if color == "B" else game.ai_level_white
            visits = get_game_visits(level, len(game.moves))
            time_limit = 4.0 if len(game.moves) < OPENING_MOVE_THRESHOLD else 8.0
            gtp_move = await _generate_ai_style_move(game, color, visits, time_limit)
            if _is_suspicious_ai_pass(game, gtp_move, color):
                fallback_move = await _pick_nonpass_fallback_move(game, color, visits)
                if fallback_move:
                    gtp_move = fallback_move
            coord = gtp_to_coord(gtp_move, game.size)
            captured = 0
            game.moves.append((color, gtp_move))
            if gtp_move.upper() != "PASS" and coord:
                captured = game.place_stone(coord[0], coord[1], color)
                game.passed[color] = False
            else:
                game.passed[color] = True
            await send_fn({"type": "ai_move", "gtp": gtp_move, "color": color, "x": coord[0] if coord else None, "y": coord[1] if coord else None})
            game.current_player = "W" if color == "B" else "B"
            game.push_history()
            await send_fn({"type": "game_state", **game.to_state()})
            if game.passed["B"] and game.passed["W"]:
                resp_score = await run_in_executor(engine.send_command, "final_score")
                score_str = resp_score.replace("=", "").strip()
                winner = "B" if score_str.startswith("B") else "W"
                game.game_over = True
                game.winner = winner
                await send_fn({"type": "game_over", "winner": winner, "score": score_str, "reason": "double_pass"})
                break
            await asyncio.sleep(0.35)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, reload=False)
