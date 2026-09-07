from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import argparse
import json
import math
import tempfile
from pathlib import Path

from app.domain.coordinates import coord_to_gtp, gtp_to_coord
from app.domain.game_state import GoGame
from app.runtime.board_sync import sync_board_to_katago_locked
from app.runtime.engine import KataGoEngine


ROOT = Path(__file__).resolve().parents[3]
KO_SETUP = ((0, 1), (1, 1), (2, 1), (0, 2), (1, 0), (2, 2), (4, 4), (1, 3), (1, 2))


def make_ko(size: int, capturing_color: str, card_edit: bool = False) -> GoGame:
    game = GoGame(size=size)
    for index, (x, y) in enumerate(KO_SETUP):
        color = capturing_color if index % 2 == 0 else ("W" if capturing_color == "B" else "B")
        assert game.is_legal_move(x, y, color)
        assert game.place_stone(x, y, color) >= 0
        game.moves.append((color, coord_to_gtp(x, y, size)))
        game.current_player = "W" if color == "B" else "B"
        game.push_history()
    assert game.is_ko(1, 1, game.current_player)
    if card_edit:
        game.board[size - 1][size - 2] = 1
    return game


def sync(engine: KataGoEngine, game: GoGame, temp_dir: Path) -> None:
    with engine.command_lock:
        sync_board_to_katago_locked(game, engine, base_dir=ROOT, temp_dir=str(temp_dir))


def engine_marks_ko_illegal(engine: KataGoEngine, size: int) -> bool:
    # GTP play intentionally tolerates ko violations. Raw policy marks illegal
    # vertices as NAN/negative, and is a stronger oracle than play's response.
    response = engine.send_command("kata-raw-nn 0")
    assert response.startswith("="), response
    tokens = response.split()
    start = tokens.index("policy") + 1
    policy = [float(value) for value in tokens[start:start + size * size]]
    return math.isnan(policy[size + 1]) or policy[size + 1] < 0


def check_ko(engine: KataGoEngine, size: int, capturing_color: str, temp_dir: Path, card_edit: bool) -> dict:
    game = make_ko(size, capturing_color, card_edit)
    defending_color = game.current_player
    recapture = coord_to_gtp(1, 1, size)
    sync(engine, game, temp_dir)
    assert engine_marks_ko_illegal(engine, size), f"{size}/{capturing_color}/{card_edit}: sync lost ko ban"

    # A genuine threat and response must release the ban in both implementations.
    for color, point in ((defending_color, (size - 1, 0)), (capturing_color, (size - 1, 1))):
        x, y = point
        move = coord_to_gtp(x, y, size)
        assert engine.send_command(f"play {color} {move}").startswith("=")
        assert game.is_legal_move(x, y, color)
        game.place_stone(x, y, color)
        game.moves.append((color, move))
        game.current_player = "W" if color == "B" else "B"
        game.push_history()
    assert game.is_legal_move(1, 1, defending_color)
    assert not engine_marks_ko_illegal(engine, size), "ko remained banned after a threat and reply"
    assert engine.send_command(f"play {defending_color} {recapture}").startswith("=")

    # The generated reply after another sync must obey the server's ko ban too.
    sync(engine, make_ko(size, capturing_color, card_edit), temp_dir)
    response = engine.send_command(f"genmove {defending_color}")
    assert response.startswith("="), response
    move = response.lstrip("= ").strip().upper()
    original = make_ko(size, capturing_color, card_edit)
    if move != "PASS":
        point = gtp_to_coord(move, size)
        assert point is not None and original.is_legal_move(*point, defending_color), f"illegal generated reply: {move}"
    return {"size": size, "capturing_color": capturing_color, "card_edit": card_edit, "ko_excluded_from_policy": True,
            "recapture_after_threat": True, "legal_ai_reply": move}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ko sync using a real, locally installed KataGo engine.")
    parser.add_argument("--katago-dir", type=Path, default=ROOT / "katago")
    parser.add_argument("--backend", choices=("cuda", "opencl", "cpu"), default="cpu")
    parser.add_argument("--rules-only", action="store_true")
    args = parser.parse_args()
    exe = args.katago_dir / f"katago_{args.backend}.exe"
    model = args.katago_dir / "model_b18.bin.gz"
    if not exe.is_file() or not model.is_file():
        parser.error("KataGo executable/model missing; supply --katago-dir and --backend. No engine is downloaded.")
    with tempfile.TemporaryDirectory(prefix="rogue-ko-smoke-") as temp:
        temp_dir = Path(temp)
        config = temp_dir / "ko.cfg"
        config.write_text(
            "rules = chinese\nnumSearchThreads = 2\nmaxVisits = 16\nmaxTime = 1.0\n"
            "resignEnabled = false\nlogAllGTPCommunication = false\nlogSearchInfo = false\nlogToStderr = false\n"
            f"homeDataDir = {temp_dir.as_posix()}\n", encoding="utf-8",
        )
        engine = KataGoEngine(default_exe=exe, default_config=config, default_model=model,
                              log_fn=lambda _message: None, ensure_dirs_fn=lambda: None,
                              coord_parser=gtp_to_coord)
        try:
            engine.start(startup_timeout=90)
            results = [] if args.rules_only else [check_ko(engine, size, color, temp_dir, card_edit)
                       for size in (5, 9, 19) for color in ("B", "W") for card_edit in (False, True)]
            rule_results = [check_rules(engine, rule, komi, temp_dir, changed_komi)
                            for rule, komi in (("chinese", 7.5), ("japanese", 6.5))
                            for changed_komi in (False, True)]
            print(json.dumps({"ok": True, "backend": args.backend, "cases": results,
                              "rule_cases": rule_results}, indent=2))
        finally:
            engine.stop()


def check_rules(engine: KataGoEngine, rule: str, komi: float, temp_dir: Path, changed_komi: bool) -> dict:
    game = make_ko(9, "B", card_edit=changed_komi)
    game.komi = komi
    assert engine.send_command(f"kata-set-rules {rule}").startswith("=")
    assert engine.send_command(f"komi {komi}").startswith("=")
    before = json.loads(engine.send_command("kata-get-rules").lstrip("= "))
    if changed_komi:
        # Card effects may change komi; this must not switch the chosen ruleset.
        game.komi = 6.5 if komi == 7.5 else 7.5
    sync(engine, game, temp_dir)
    after = json.loads(engine.send_command("kata-get-rules").lstrip("= "))
    assert before == after, f"loadsgf changed {rule} rules: {before} -> {after}"
    assert float(engine.send_command("get_komi").lstrip("= ")) == game.komi
    return {"rule": rule, "initial_komi": komi, "komi_after_sync": game.komi,
            "card_changed_komi": changed_komi, "rules_before": before, "rules_after": after}


if __name__ == "__main__":
    main()
