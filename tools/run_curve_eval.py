"""Self-play check of the run curve: does a typical run stay level stage to stage?

For each stage, draws typical decks through the real challenge offer logic
(one card per stage, a random pick from each offer of three), sets the
stage up exactly like the server (AI stones, stage komi, card komi,
loadout), and plays a game where KataGo plays your side at the same
standard strength as the AI. Reports your final lead (positive = you win)
and the target per stage. The player bot is as strong as the AI, so the
absolute level says little about humans (the difficulty setting covers
that); what matters is that results stay level as the run goes on.

Run from the repository root, for example:

    python tools/run_curve_eval.py --stages 1 2 3 4 5 --decks 4 --plies 200
"""
import argparse
import asyncio
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Self-play check of the run difficulty curve")
    parser.add_argument("--stages", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--decks", type=int, default=4, help="games (random decks) per stage")
    parser.add_argument("--plies", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--difficulty", default="normal")
    parser.add_argument("--output", default="")
    return parser.parse_args()


ARGS = parse_args()
# Reuse the balance evaluator's player bot; it parses its own flags on import.
sys.argv = [sys.argv[0], "--size", "19", "--level", "standard", "--backend", "opencl"]
import tools.card_balance_eval as ev  # noqa: E402
import server as s  # noqa: E402
from app.data.cards import CHALLENGE_BETA_POOL, ROGUE_DISABLED_CARDS  # noqa: E402
from app.gameplay.card_komi import settle_card_komi  # noqa: E402
from app.gameplay.card_selection import pick_challenge_beta_choices  # noqa: E402
from app.gameplay.difficulty import difficulty_points  # noqa: E402
from app.gameplay.run_curve import game_target, run_stage_setup  # noqa: E402


def draw_deck(stage: int, rng: random.Random) -> list[str]:
    pool = [c for c in CHALLENGE_BETA_POOL if c not in ROGUE_DISABLED_CARDS]
    deck: list[str] = []
    for _ in range(stage):
        offer = pick_challenge_beta_choices(deck, 3, pool=[c for c in pool if c not in deck])
        deck.append(rng.choice(offer))
    return deck


async def play_stage(stage: int, deck: list[str]) -> dict:
    run = run_stage_setup(stage, difficulty_points(ARGS.difficulty))
    game = s.GoGame(size=19, komi=run.komi, handicap=run.handicap, player_color="W", level="standard", two_player=False)
    game.rogue_enabled = True
    game.challenge_beta = True
    game.challenge_stage = stage
    game.challenge_cards = list(deck)
    game.challenge_limits = {"undo": 0, "hint": 0, "coach": 3}
    game.challenge_usage = {"undo": 0, "hint": 0, "coach": 0}
    game.stage_komi_points = run.stage_points
    game.difficulty_points = run.difficulty_points
    settle_card_komi(game)

    await ev.clear_engine_board(game.komi)
    await s.run_in_executor(s.engine.send_command, f"kata-set-rules {game.rules}")
    if game.handicap:
        resp = await s.run_in_executor(s.engine.send_command, f"fixed_handicap {game.handicap}")
        for gtp in resp.lstrip("=").split():
            coord = s.gtp_to_coord(gtp, 19)
            if coord:
                game.place_stone(coord[0], coord[1], "B")
                game.moves.append(("B", gtp))
        game.current_player = "W"
    await s._apply_challenge_rogue_loadout(game, ev.noop_send)

    while not game.game_over and len(game.moves) < ARGS.plies:
        if game.current_player == game.ai_color:
            await s._ai_move(game, ev.noop_send)
        else:
            await ev.play_player_rogue_turn(game, "engine")

    analysis = await ev.analyze_top_moves(game, game.current_player, 500)
    lead = -float(analysis.get("score", 0.0))  # the player is White
    target = game_target(game)
    return {"stage": stage, "deck": deck, "lead": round(lead, 1), "target": target["points"],
            "margin": round(lead + target["points"], 1), "komi": game.komi, "moves": len(game.moves)}


async def main() -> None:
    exe, cfg, label = ev.choose_backend()
    model = s.engine_runtime.select_model()
    print(f"[curve] starting {label}: {exe.name} with {model.name}", file=sys.stderr)
    s.engine.start(exe, cfg, model, startup_timeout=120.0)
    rng = random.Random(ARGS.seed)
    results = []
    try:
        for stage in ARGS.stages:
            for _ in range(ARGS.decks):
                result = await play_stage(stage, draw_deck(stage, rng))
                results.append(result)
                print(json.dumps(result), file=sys.stderr, flush=True)
    finally:
        s.engine.stop()
    summary = {}
    for stage in ARGS.stages:
        leads = [r["lead"] for r in results if r["stage"] == stage]
        summary[stage] = {"mean_lead": round(statistics.mean(leads), 1), "games": len(leads),
                          "target": statistics.mean(r["target"] for r in results if r["stage"] == stage)}
    out = {"results": results, "summary": summary}
    if ARGS.output:
        Path(ARGS.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
