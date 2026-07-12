import argparse
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rough card balance evaluator")
    parser.add_argument("--mode", choices=["rogue", "ultimate", "both"], default="both")
    parser.add_argument("--backend", choices=["auto", "opencl", "cpu"], default="auto")
    parser.add_argument("--size", type=int, default=9)
    parser.add_argument("--level", default="5k")
    parser.add_argument("--rogue-plies", type=int, default=24)
    parser.add_argument("--rogue-games", type=int, default=1)
    parser.add_argument("--ultimate-games", type=int, default=1)
    parser.add_argument("--rogue-cards", nargs="*", default=None)
    parser.add_argument("--ultimate-cards", nargs="*", default=None)
    parser.add_argument("--rogue-strategy", choices=["engine", "guided"], default="guided")
    return parser.parse_args()


ARGS = parse_args()

# Avoid server.py consuming this script's CLI flags.
sys.argv = [sys.argv[0]]

import server as s  # noqa: E402
from app.gameplay.card_balance_scoring import (  # noqa: E402
    CardBalanceInputs,
    MoveEligibilitySample,
    score_card_balance,
)
from app.gameplay.effect_utils import is_lowline  # noqa: E402


DEFAULT_ROGUE_CARDS = [
    "dice",
    "nerf",
    "time_press",
    "suboptimal",
    "fog",
    "seal",
    "blackhole",
    "golden_corner",
    "joseki_ocd",
    "corner_helper",
    "sanrensei",
    "foolish_wisdom",
    "five_in_row",
    "god_hand",
    "sansan_trap",
    "handicap_quest",
    "capture_foul",
    "last_stand",
]

DEFAULT_ULTIMATE_CARDS = [
    "chain",
    "wildgrow",
    "territory",
    "joseki_burst",
    "shadow_clone",
    "meteor",
    "quantum",
    "timewarp",
    "wall",
]

ROGUE_INTENT_CARDS = {
    "corner_helper",
    "sanrensei",
    "foolish_wisdom",
    "five_in_row",
    "joseki_ocd",
    "last_stand",
    "god_hand",
    "sansan_trap",
    "handicap_quest",
}

ROGUE_AI_WEAKENER_WEIGHTS = {
    "dice": 0.58,
    "nerf": 0.38,
    "time_press": 0.45,
    "suboptimal": 0.52,
    "gravity": 0.72,
    "lowline": 0.78,
    "mirror": 0.82,
    "slip": 0.74,
    "shadow": 0.76,
    "sansan": 0.72,
    "fog": 0.68,
    "blackhole": 0.74,
    "golden_corner": 0.76,
    "seal": 0.80,
}

ROGUE_TARGET_MIN = 5.0
ROGUE_TARGET_MAX = 10.0

CARD_AI_SEARCH_SCALE = {
    "nerf": 0.05,
    "time_press": 0.08,
    "suboptimal": 0.55,
    "dice": 0.94,
}


def choose_backend() -> tuple[Path, Path, str]:
    model = s.engine_runtime.select_model()
    if not model:
        raise RuntimeError("No KataGo model found")

    if ARGS.backend == "opencl":
        if not s.KATAGO_OPENCL_EXE.exists():
            raise RuntimeError("katago_opencl.exe not found")
        return s.KATAGO_OPENCL_EXE, s.KATAGO_CONFIG, "OpenCL"

    if ARGS.backend == "cpu":
        if not s.KATAGO_CPU_EXE.exists():
            raise RuntimeError("katago_cpu.exe not found")
        cfg = s.KATAGO_CPU_CONFIG if s.KATAGO_CPU_CONFIG.exists() else s.KATAGO_CONFIG
        return s.KATAGO_CPU_EXE, cfg, "CPU"

    has_gpu, candidates = s.engine_runtime.build_candidates()
    if not candidates:
        raise RuntimeError("No KataGo engine candidates found")
    preferred = None
    for item in candidates:
        if item["label"] == "OpenCL":
            preferred = item
            break
    chosen = preferred or candidates[-1]
    return chosen["exe"], chosen["config"], chosen["label"]


async def noop_send(_payload: dict):
    return None


async def clear_engine_board(komi: float):
    await s.run_in_executor(s.engine.send_command, "clear_board")
    await s.run_in_executor(s.engine.send_command, f"komi {komi}")


async def analyze_top_moves(game: s.GoGame, color: str, visits: int) -> dict:
    def _analyze():
        lines, ownership = s.engine.analyze(
            color,
            visits=max(50, min(visits, 500)),
            interval=50,
            duration=1.2,
            extra_args=["rootInfo", "true"],
        )
        return s.engine.parse_analysis(lines, ownership, game.size, to_move_color=color)

    return await s.run_in_executor(_analyze)


def parse_score_margin(score_str: str) -> tuple[str, float]:
    score_str = (score_str or "").strip().upper()
    if score_str.startswith("B+"):
        try:
            return "B", float(score_str[2:])
        except ValueError:
            return "B", 0.0
    if score_str.startswith("W+"):
        try:
            return "W", float(score_str[2:])
        except ValueError:
            return "W", 0.0
    return "draw", 0.0


async def choose_legal_player_move(
    game: s.GoGame,
    color: str,
    visits: int,
    prefer_targets: list[tuple[int, int]] | None = None,
    forbidden: set[tuple[int, int]] | None = None,
) -> tuple[str, tuple[int, int] | None]:
    forbidden = forbidden or set()

    if not prefer_targets and not forbidden:
        def _genmove():
            with s.engine.command_lock:
                mv = 10000000 if visits == 0 else visits
                s.engine._send_command_locked(f"kata-set-param maxVisits {mv}")
                s.engine.current_visits = visits
                s.engine._send_command_locked("kata-set-param maxTime 3")
                resp = s.engine._send_command_locked(
                    f"genmove {color}", timeout=30
                )
                s.engine._send_command_locked("kata-set-param maxTime 1e20")
                return resp.replace("=", "").strip()

        gtp = await s.run_in_executor(_genmove)
        if gtp.upper() == "RESIGN":
            gtp = await s._ai_move_no_resign(game, color)
        coord = s.gtp_to_coord(gtp, game.size) if gtp.upper() != "PASS" else None
        return gtp, coord

    analysis = await analyze_top_moves(game, color, visits)
    top_moves = analysis.get("top_moves", [])

    target_set = set(prefer_targets or [])
    target_gtps = []
    if target_set:
        ranked = []
        for move in top_moves:
            gtp = (move.get("move") or move.get("gtp") or "").upper()
            coord = s.gtp_to_coord(gtp, game.size) if gtp else None
            if coord in target_set and coord not in forbidden and game.board[coord[1]][coord[0]] == 0:
                ranked.append((gtp, coord))
        target_gtps.extend(ranked)
        for coord in prefer_targets or []:
            if coord in forbidden:
                continue
            x, y = coord
            if game.board[y][x] == 0:
                target_gtps.append((s.coord_to_gtp(x, y, game.size), coord))

    candidates: list[tuple[str, tuple[int, int] | None]] = []
    seen = set()
    for gtp, coord in target_gtps:
        key = gtp.upper()
        if key not in seen:
            candidates.append((gtp, coord))
            seen.add(key)

    for move in top_moves:
        gtp = (move.get("move") or move.get("gtp") or "").upper()
        if not gtp or gtp in seen or gtp in {"PASS", "RESIGN"}:
            continue
        coord = s.gtp_to_coord(gtp, game.size)
        if not coord:
            continue
        x, y = coord
        if coord in forbidden or game.board[y][x] != 0:
            continue
        candidates.append((gtp, coord))
        seen.add(gtp)

    if not candidates:
        for y in range(game.size):
            for x in range(game.size):
                if game.board[y][x] == 0 and (x, y) not in forbidden:
                    return s.coord_to_gtp(x, y, game.size), (x, y)
        return "pass", None

    for gtp, coord in candidates:
        resp = await s.run_in_executor(s.engine.send_command, f"play {color} {gtp}")
        if "?" not in resp:
            return gtp, coord
    await s.run_in_executor(s.engine.send_command, f"play {color} pass")
    return "pass", None


async def maybe_use_rogue_ability(game: s.GoGame):
    card = game.rogue_card
    if card == "twin" and game.rogue_uses.get("twin", 0) > 0 and not game.rogue_skip_ai:
        game.rogue_uses["twin"] -= 1
        game.rogue_skip_ai = True
        return

    if card == "exchange" and game.rogue_uses.get("exchange", 0) > 0 and not game.rogue_skip_ai:
        game.rogue_uses["exchange"] -= 1
        game.rogue_skip_ai = True
        return

    if card == "puppet" and game.rogue_uses.get("puppet", 0) > 0:
        preferred = [
            (0, game.size - 1),
            (game.size - 1, 0),
            (0, 0),
            (game.size - 1, game.size - 1),
        ]
        target = None
        for x, y in preferred:
            if game.board[y][x] == 0:
                target = (x, y)
                break
        if target is None:
            for y in range(game.size):
                for x in range(game.size):
                    if game.board[y][x] == 0:
                        target = (x, y)
                        break
                if target:
                    break
        if target:
            x, y = target
            gtp = s.coord_to_gtp(x, y, game.size)
            resp = await s.run_in_executor(s.engine.send_command, f"play {game.ai_color} {gtp}")
            if "?" not in resp:
                game.rogue_uses["puppet"] -= 1
                game.moves.append((game.ai_color, gtp))
                game.place_stone(x, y, game.ai_color)
                game.passed[game.ai_color] = False
                game.current_player = game.player_color


async def auto_setup_seal(game: s.GoGame):
    if game.rogue_card != "seal" or not game.rogue_waiting_seal:
        return
    analysis = await analyze_top_moves(game, game.ai_color, 350)
    chosen = []
    for move in analysis.get("top_moves", []):
        gtp = (move.get("move") or move.get("gtp") or "").upper()
        coord = s.gtp_to_coord(gtp, game.size)
        if coord and coord not in chosen:
            chosen.append(coord)
        if len(chosen) >= 3:
            break
    while len(chosen) < 3:
        fallback = [
            (game.size // 2, game.size // 2),
            (2, 2),
            (game.size - 3, game.size - 3),
        ][len(chosen)]
        if fallback not in chosen:
            chosen.append(fallback)
    game.rogue_seal_points = chosen[:3]
    game.rogue_waiting_seal = False


def guided_rogue_targets(
    game: s.GoGame,
    color: str,
    card: str | None,
    strategy: str = "guided",
) -> list[tuple[int, int]] | None:
    if strategy != "guided" or not card:
        return None

    if card == "joseki_ocd" and not game.rogue_joseki_done:
        return list(game.rogue_joseki_targets)

    if card == "sanrensei":
        return list(s._get_star_points(game.size))

    if card == "corner_helper":
        return [(1, 1), (2, 1), (1, 2), (2, 2)]

    if card == "foolish_wisdom":
        c = game.size // 2
        return [
            (c, c),
            (min(game.size - 1, c + 1), c),
            (c, min(game.size - 1, c + 1)),
            (min(game.size - 1, c + 2), c),
            (c, max(0, c - 1)),
        ]

    if card == "five_in_row":
        y = game.size // 2
        start = max(0, (game.size // 2) - 2)
        end = min(game.size, start + 5)
        return [(x, y) for x in range(start, end)]

    if card == "last_stand":
        c = game.size // 2
        return [(c, c), (max(0, c - 1), c), (c, max(0, c - 1))]

    if card == "god_hand":
        c = game.size // 2
        return [(c, c), (c + 1, c), (c, c + 1), (max(0, c - 1), c), (c, max(0, c - 1))]

    if card == "sansan_trap":
        return [(2, 2), (game.size - 3, 2), (2, game.size - 3), (game.size - 3, game.size - 3)]

    return None


async def play_player_rogue_turn(game: s.GoGame, strategy: str = "guided"):
    tempo = {"extra_turns": 0, "skipped_ai_turns": 0}
    color = game.player_color
    card = game.rogue_card

    await maybe_use_rogue_ability(game)
    if game.current_player != color:
        return tempo

    if (card == "handicap_quest"
            and not game.rogue_handicap_active
            and game.rogue_handicap_passes < s.ROGUE_HANDICAP_REQUIRED_PASSES):
        await s.run_in_executor(s.engine.send_command, f"play {color} pass")
        game.moves.append((color, "pass"))
        game.passed[color] = True
        game.current_player = game.ai_color
        game.rogue_handicap_passes += 1
        if game.rogue_handicap_passes >= s.ROGUE_HANDICAP_REQUIRED_PASSES:
            game.rogue_handicap_active = True
        await s._ai_move(game, noop_send)
        return tempo

    prefer_targets = guided_rogue_targets(game, color, card, strategy)

    visits = s.get_game_visits(game.level, len(game.moves), mode="rogue")
    gtp, coord = await choose_legal_player_move(game, color, visits, prefer_targets=prefer_targets)
    game.moves.append((color, gtp))
    captured = 0
    if gtp.upper() != "PASS" and coord:
        captured = game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    game.current_player = game.ai_color
    if coord:
        await s._apply_player_rogue_move_effects(game, noop_send, coord[0], coord[1], color, captured)

    if card == "quickthink" and not game.two_player:
        if game.rogue_quickthink_stage == 1:
            game.rogue_quickthink_stage = 2
            game.current_player = game.player_color
            tempo["extra_turns"] += 1
            tempo["skipped_ai_turns"] += 1
            return tempo
        game.rogue_quickthink_stage = 0

    if game.rogue_skip_ai:
        game.rogue_skip_ai = False
        game.current_player = game.player_color
        tempo["extra_turns"] += 1
        tempo["skipped_ai_turns"] += 1
        return tempo

    await s._ai_move(game, noop_send)
    return tempo


async def evaluate_rogue_card(card_id: str | None, player_color: str, strategy: str = "guided") -> dict:
    game = s.GoGame(
        size=ARGS.size,
        komi=7.5,
        player_color=player_color,
        level=ARGS.level,
        two_player=False,
    )
    await clear_engine_board(game.komi)
    if card_id:
        await s._activate_rogue_card(game, noop_send, card_id)
        await auto_setup_seal(game)

    eligibility_samples = [sample_rogue_move_eligibility(game, card_id)]

    if game.ai_color == game.current_player:
        await s._ai_move(game, noop_send)
        eligibility_samples.append(sample_rogue_move_eligibility(game, card_id))

    while not game.game_over and len(game.moves) < ARGS.rogue_plies:
        tempo = {"extra_turns": 0, "skipped_ai_turns": 0}
        if game.current_player != game.player_color:
            await s._ai_move(game, noop_send)
        else:
            tempo = await play_player_rogue_turn(game, strategy)
        if len(eligibility_samples) < 6:
            eligibility_samples.append(with_tempo(
                sample_rogue_move_eligibility(game, card_id),
                **tempo,
            ))

    analysis = await analyze_top_moves(game, game.current_player, 500)
    black_score = float(analysis.get("score", 0.0))
    holder_advantage = black_score if player_color == "B" else -black_score
    return {
        "card": card_id or "baseline",
        "player_color": player_color,
        "moves": len(game.moves),
        "black_score": round(black_score, 1),
        "holder_advantage": round(holder_advantage, 1),
        "eligibility_samples": [sample.__dict__ for sample in eligibility_samples],
    }


async def play_player_ultimate_turn(game: s.GoGame):
    tempo = {"extra_turns": 0, "skipped_ai_turns": 0}
    color = game.player_color
    forbidden = set()
    if game.ultimate_ai_card == "territory":
        forbidden = s._ultimate_get_territory_forbidden(game, 1 if color == "B" else 2)

    await s._sync_board_to_katago(game)
    visits = s.get_game_visits(game.level, len(game.moves), mode="ultimate")

    gtp, coord = await choose_legal_player_move(
        game,
        color,
        visits,
        forbidden=forbidden,
    )

    s._record_ultimate_player_action(game)
    game.moves.append((color, gtp))
    if gtp.upper() != "PASS" and coord:
        game.place_stone(coord[0], coord[1], color)
        game.passed[color] = False
    else:
        game.passed[color] = True
    game.current_player = game.ai_color

    if game.ultimate_player_card == "quickthink":
        if not game.ultimate_quickthink_active:
            game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True
        if not hasattr(game, "_balance_quickthink_bonus_budget"):
            setattr(game, "_balance_quickthink_bonus_budget", ultimate_quickthink_bonus_budget(game))
        burst_moves = getattr(game, "_balance_quickthink_burst_moves", 0) + 1
        setattr(game, "_balance_quickthink_burst_moves", burst_moves)
        if (
            burst_moves <= getattr(game, "_balance_quickthink_bonus_budget", 0)
            and game.ultimate_move_count < 20
        ):
            game.current_player = game.player_color
            tempo["extra_turns"] += 1
            tempo["skipped_ai_turns"] += 1
            return tempo
        s._finish_ultimate_quickthink_turn(game)
        setattr(game, "_balance_quickthink_burst_moves", 0)
        if hasattr(game, "_balance_quickthink_bonus_budget"):
            delattr(game, "_balance_quickthink_bonus_budget")
        game.current_player = game.ai_color
        if game.ultimate_move_count >= 20:
            await s._ultimate_force_score(game, noop_send)
        else:
            await s._ultimate_ai_move(game, noop_send)
        return tempo

    board_modified = False
    if coord and gtp.upper() != "PASS" and game.ultimate_player_card:
        board_modified = await s._apply_ultimate_effect(
            game, noop_send, coord[0], coord[1], color, game.ultimate_player_card
        )
    if board_modified:
        await s._sync_board_to_katago(game)

    if game.ultimate_move_count >= 20:
        await s._ultimate_force_score(game, noop_send)
        return tempo

    if (
        game.ultimate_player_card == "chain"
        and gtp.upper() != "PASS"
        and s.random.random() < s.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE
    ):
        game.current_player = game.player_color
        tempo["extra_turns"] += 1
        tempo["skipped_ai_turns"] += 1
        return tempo

    if game.ultimate_player_card == "double" and not game.ultimate_double_pending:
        game.ultimate_double_pending = True
        game.current_player = game.player_color
        tempo["extra_turns"] += 1
        tempo["skipped_ai_turns"] += 1
        return tempo

    game.ultimate_double_pending = False
    await s._ultimate_ai_move(game, noop_send)
    return tempo


async def evaluate_ultimate_card(card_id: str | None, player_color: str) -> dict:
    game = s.GoGame(
        size=ARGS.size,
        komi=7.5,
        player_color=player_color,
        level=ARGS.level,
        two_player=False,
    )
    game.ultimate = True
    game.ultimate_player_card = card_id
    game.ultimate_ai_card = None
    game.ultimate_move_count = 0
    if card_id == "quickthink" and game.current_player == game.player_color:
        game.ultimate_quickthink_token += 1
        game.ultimate_quickthink_active = True

    await clear_engine_board(game.komi)
    eligibility_samples = [sample_ultimate_move_eligibility(game, card_id)]

    if game.ai_color == game.current_player:
        await s._ultimate_ai_move(game, noop_send)
        eligibility_samples.append(sample_ultimate_move_eligibility(game, card_id))

    while not game.game_over and game.ultimate_move_count < 20:
        tempo = {"extra_turns": 0, "skipped_ai_turns": 0}
        if game.current_player != game.player_color:
            await s._ultimate_ai_move(game, noop_send)
        else:
            tempo = await play_player_ultimate_turn(game)
        if len(eligibility_samples) < 6:
            eligibility_samples.append(with_tempo(
                sample_ultimate_move_eligibility(game, card_id),
                **tempo,
            ))

    if not game.game_over:
        await s._ultimate_force_score(game, noop_send)

    winner, margin = parse_score_margin(getattr(game, "score", ""))
    score_str = getattr(game, "score", None)
    if not score_str:
        final_msgs = []

        async def capture_send(payload: dict):
            final_msgs.append(payload)

        await s._ultimate_force_score(game, capture_send)
        for msg in reversed(final_msgs):
            if msg.get("type") == "game_over":
                score_str = msg.get("score")
                break
        winner, margin = parse_score_margin(score_str or "")
    holder_advantage = margin if winner == player_color else (-margin if winner != "draw" else 0.0)
    return {
        "card": card_id or "baseline",
        "player_color": player_color,
        "score": score_str,
        "holder_advantage": round(holder_advantage, 1),
        "eligibility_samples": [sample.__dict__ for sample in eligibility_samples],
    }


def avg_advantage(runs: list[dict]) -> float:
    return round(sum(item["holder_advantage"] for item in runs) / len(runs), 2)


def blend_rogue_layers(card_id: str, engine_avg: float, guided_avg: float) -> float:
    if card_id in ROGUE_AI_WEAKENER_WEIGHTS:
        return round(guided_avg * ROGUE_AI_WEAKENER_WEIGHTS[card_id], 2)
    if card_id in ROGUE_INTENT_CARDS:
        return round((engine_avg * 0.25) + (guided_avg * 0.75), 2)
    return round((engine_avg * 0.65) + (guided_avg * 0.35), 2)


def rogue_balance_verdict(score: float) -> str:
    if score < ROGUE_TARGET_MIN:
        return "buff"
    if score > ROGUE_TARGET_MAX:
        return "nerf"
    return "ok"


def empty_points(game: s.GoGame) -> int:
    return sum(1 for row in game.board for cell in row if cell == 0)


def legal_point_set(game: s.GoGame, color: str) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y in range(game.size)
        for x in range(game.size)
        if game.board[y][x] == 0 and game.is_legal_move(x, y, color)
    }


def count_legal_subset(
    legal_points: set[tuple[int, int]],
    points: list[tuple[int, int]] | set[tuple[int, int]],
) -> int:
    return len(legal_points.intersection(set(points)))


def ultimate_quickthink_bonus_budget(game: s.GoGame) -> int:
    """Estimate bonus click opportunities from the runtime quickthink timer."""
    seconds = max(1, int(getattr(s, "ULTIMATE_QUICKTHINK_SECONDS", 1)))
    player_legal = legal_point_set(game, game.player_color)
    return min(max(0, seconds - 1), max(0, len(player_legal) - 1))


def with_tempo(
    sample: MoveEligibilitySample,
    *,
    extra_turns: int = 0,
    skipped_ai_turns: int = 0,
) -> MoveEligibilitySample:
    return replace(
        sample,
        extra_turns=sample.extra_turns + extra_turns,
        skipped_ai_turns=sample.skipped_ai_turns + skipped_ai_turns,
    )


def sample_rogue_move_eligibility(game: s.GoGame, card_id: str | None) -> MoveEligibilitySample:
    card = card_id or ""
    ai_move_count = sum(
        1 for color, move in game.moves
        if color == game.ai_color and move.upper() != "PASS"
    )
    ai_legal = legal_point_set(game, game.ai_color)
    player_legal = legal_point_set(game, game.player_color)
    legal_points = max(1, len(ai_legal))
    ai_forbidden = set(s._get_ai_rogue_forbidden_points(game))
    ai_allowed: int | None = None
    forced_points = 0

    if card in {"seal", "fog", "golden_corner"} and game.rogue_seal_points:
        ai_forbidden.update(tuple(point) for point in game.rogue_seal_points)
    elif card == "blackhole":
        ai_forbidden.update(s._get_blackhole_points(game.size))

    if card == "tengen":
        if ai_move_count == 0:
            c = game.size // 2
            forced_points = count_legal_subset(ai_legal, [(c, c)])
            ai_allowed = forced_points
        elif ai_move_count < s.gameplay_config.ROGUE_TENGEN_AI_MOVES:
            c = game.size // 2
            ai_allowed = count_legal_subset(ai_legal, s._diamond_points(c, c, 2, game.size))
    elif card == "gravity" and ai_move_count < s.gameplay_config.ROGUE_GRAVITY_AI_MOVES:
        ai_allowed = count_legal_subset(ai_legal, s._get_star_points(game.size))
    elif card == "sansan" and ai_move_count < 3:
        sansan_points = [
            (x, y)
            for base_x in (0, game.size - 3)
            for base_y in (0, game.size - 3)
            for y in range(base_y, base_y + 3)
            for x in range(base_x, base_x + 3)
        ]
        ai_allowed = count_legal_subset(ai_legal, sansan_points)
    elif card == "lowline" and ai_move_count < s.gameplay_config.ROGUE_LOWLINE_AI_MOVES:
        ai_allowed = count_legal_subset(ai_legal, [
            (x, y)
            for x in range(game.size)
            for y in range(game.size)
            if is_lowline(x, y, game.size)
        ])
    elif card == "shadow":
        previous_ai = None
        for color, move in reversed(game.moves):
            if color == game.ai_color and move.upper() != "PASS":
                previous_ai = s.gtp_to_coord(move, game.size)
                break
        adjacent_allowed = 0
        if previous_ai:
            adjacent_allowed = count_legal_subset(
                ai_legal,
                s._adjacent_points(previous_ai[0], previous_ai[1], game.size),
            )
        if adjacent_allowed > 0:
            expected_ratio = (
                s.gameplay_config.ROGUE_SHADOW_CHANCE * (adjacent_allowed / legal_points)
                + (1.0 - s.gameplay_config.ROGUE_SHADOW_CHANCE)
            )
            ai_allowed = max(1, round(legal_points * expected_ratio))

    return MoveEligibilitySample(
        legal_points=legal_points,
        ai_forbidden_points=count_legal_subset(ai_legal, ai_forbidden),
        ai_allowed_points=ai_allowed,
        forced_ai_points=forced_points,
        player_legal_points=max(1, len(player_legal)),
        ai_search_scale=CARD_AI_SEARCH_SCALE.get(card, 1.0),
    )


def sample_ultimate_move_eligibility(game: s.GoGame, card_id: str | None) -> MoveEligibilitySample:
    card = card_id or ""
    ai_legal = legal_point_set(game, game.ai_color)
    player_legal = legal_point_set(game, game.player_color)
    legal_points = max(1, len(ai_legal))
    ai_forbidden = 0
    if card == "territory":
        ai_forbidden = count_legal_subset(
            ai_legal,
            s._ultimate_get_territory_forbidden(game, 1 if game.ai_color == "B" else 2),
        )
    forced_points = 4 if card == "wall" else 0
    return MoveEligibilitySample(
        legal_points=legal_points,
        ai_forbidden_points=ai_forbidden,
        forced_ai_points=forced_points,
        player_legal_points=max(1, len(player_legal)),
    )


def merge_scored_runs(card_id: str, runs: list[dict], *, ultimate: bool = False) -> dict:
    samples = [
        MoveEligibilitySample(**sample)
        for run in runs
        for sample in run.get("eligibility_samples", [])
    ]
    return score_card_balance(CardBalanceInputs(
        card_id=card_id,
        holder_advantage_points=avg_advantage(runs),
        eligibility_samples=samples,
        ai_search_scale=1.0 if ultimate else CARD_AI_SEARCH_SCALE.get(card_id, 1.0),
    ))


async def run_mode(mode: str):
    results = []

    if mode in {"rogue", "both"}:
        cards = ARGS.rogue_cards or DEFAULT_ROGUE_CARDS
        baseline_engine_runs = []
        baseline_guided_runs = []
        for color in ("B", "W"):
            for _ in range(ARGS.rogue_games):
                baseline_engine_runs.append(await evaluate_rogue_card(None, color, "engine"))
                baseline_guided_runs.append(await evaluate_rogue_card(None, color, "guided"))
        results.append({
            "mode": "rogue",
            "card": "baseline",
            "ai_rating": merge_scored_runs("baseline", baseline_engine_runs + baseline_guided_runs),
            "layers": {
                "engine": {"runs": baseline_engine_runs, "avg_advantage": avg_advantage(baseline_engine_runs)},
                "guided": {"runs": baseline_guided_runs, "avg_advantage": avg_advantage(baseline_guided_runs)},
                "player_weighted": {"avg_advantage": avg_advantage(baseline_guided_runs)},
            },
        })
        for card_id in cards:
            engine_runs = []
            guided_runs = []
            for color in ("B", "W"):
                for _ in range(ARGS.rogue_games):
                    engine_runs.append(await evaluate_rogue_card(card_id, color, "engine"))
                    guided_runs.append(await evaluate_rogue_card(card_id, color, "guided"))
            engine_avg = avg_advantage(engine_runs)
            guided_avg = avg_advantage(guided_runs)
            blended = blend_rogue_layers(card_id, engine_avg, guided_avg)
            results.append({
                "mode": "rogue",
                "card": card_id,
                "target_band": [ROGUE_TARGET_MIN, ROGUE_TARGET_MAX],
                "verdict": rogue_balance_verdict(blended),
                "ai_rating": merge_scored_runs(card_id, engine_runs + guided_runs),
                "layers": {
                    "engine": {"runs": engine_runs, "avg_advantage": engine_avg},
                    "guided": {"runs": guided_runs, "avg_advantage": guided_avg},
                    "player_weighted": {"avg_advantage": blended},
                },
            })

    if mode in {"ultimate", "both"}:
        cards = ARGS.ultimate_cards or DEFAULT_ULTIMATE_CARDS
        baseline_runs = []
        for color in ("B", "W"):
            for _ in range(ARGS.ultimate_games):
                baseline_runs.append(await evaluate_ultimate_card(None, color))
        results.append({
            "mode": "ultimate",
            "card": "baseline",
            "runs": baseline_runs,
            "avg_advantage": avg_advantage(baseline_runs),
            "ai_rating": merge_scored_runs("baseline", baseline_runs, ultimate=True),
        })
        for card_id in cards:
            runs = []
            for color in ("B", "W"):
                for _ in range(ARGS.ultimate_games):
                    runs.append(await evaluate_ultimate_card(card_id, color))
            results.append({
                "mode": "ultimate",
                "card": card_id,
                "runs": runs,
                "avg_advantage": avg_advantage(runs),
                "ai_rating": merge_scored_runs(card_id, runs, ultimate=True),
            })

    print(json.dumps(results, ensure_ascii=False, indent=2))


async def main():
    exe, cfg, label = choose_backend()
    model = s.engine_runtime.select_model()
    if not model:
        raise RuntimeError("No KataGo model found")
    print(f"[eval] starting {label}: {exe.name} with {model.name}")
    s.engine.start(exe, cfg, model, startup_timeout=120.0)
    try:
        await run_mode(ARGS.mode)
    finally:
        s.engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
