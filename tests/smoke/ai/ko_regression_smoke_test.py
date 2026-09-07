from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
import re
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.domain.coordinates import coord_to_gtp, gtp_to_coord
from app.domain.game_state import GoGame
from app.gameplay.ai_move_flow import (
    AiMoveAdjustment,
    AiMoveResolution,
    apply_ai_move_to_board,
    finalize_forced_ai_pass,
    prepare_generated_ai_move,
    retry_ai_move_avoiding_ko,
)
from app.gameplay.ai_moves import AiMoveService
from app.gameplay.move_placement import place_auxiliary_ai_move_on_board
from app.gameplay.turn_modifiers import apply_ultimate_ai_move_result
from app.gameplay.ultimate_ai_flow import choose_ultimate_ai_move
from app.runtime.board_sync import build_board_sync_sgf, sync_board_to_katago_locked
from app.runtime.ws_turn_actions import handle_pass


def make_ko_game() -> GoGame:
    game = GoGame(size=9)
    for color, move in [
        ("B", "A8"), ("W", "B8"), ("B", "B9"), ("W", "A7"),
        ("B", "C8"), ("W", "C7"), ("B", "H1"), ("W", "B6"), ("B", "B7"),
    ]:
        coord = gtp_to_coord(move, game.size)
        assert coord is not None and game.place_stone(*coord, color) >= 0
        game.moves.append((color, move))
        game.current_player = "W" if color == "B" else "B"
        game.push_history()
    assert game.ko_point == (1, 1, 2)
    return game


def replay_sync_sgf(sgf: str) -> GoGame:
    """Replay the small SGF subset used for engine synchronization."""
    game = GoGame(size=int(re.search(r"SZ\[(\d+)\]", sgf)[1]))
    for prop, values in re.findall(r"(AB|AW)((?:\[[a-z]{2}\])+)", sgf):
        for point in re.findall(r"\[([a-z]{2})\]", values):
            game.board[ord(point[1]) - 97][ord(point[0]) - 97] = 1 if prop == "AB" else 2
    for color, point in re.findall(r";([BW])\[([a-z]{2})?\]", sgf):
        if point:
            x, y = ord(point[0]) - 97, ord(point[1]) - 97
            assert game.board[y][x] == 0 and game.place_stone(x, y, color) >= 0
            move = coord_to_gtp(x, y, game.size)
        else:
            move = "pass"
            game.ko_point = None
        game.moves.append((color, move))
    return game


async def inline_executor(fn, *args):
    return fn(*args)


class RetryEngine:
    """GTP genmove commits a vertex/pass; resign and errors commit no move."""

    def __init__(self, *, candidates=None, responses=None, undo_error=False):
        self.command_lock = threading.Lock()
        self.current_visits = 800
        self.commands = []
        self.history = ["previous player move", "W B8"]
        self.candidates = [{"gtp": "B8"}, {"gtp": "A8"}, {"gtp": "D4"}] if candidates is None else candidates
        self.responses = list(responses or [])
        self.undo_error = undo_error
        self.analysis_args = None

    def _send_command_locked(self, command, timeout=60):
        self.commands.append(command)
        if command == "undo":
            if self.undo_error:
                return "? cannot undo"
            self.history.pop()
        elif command.startswith("genmove "):
            response = self.responses.pop(0) if self.responses else "= B8"
            move = response.removeprefix("=").strip()
            if not response.startswith("?") and move.upper() != "RESIGN":
                self.history.append(f"{command.split()[1]} {move}")
            return response
        elif command.startswith("play "):
            self.history.append(command.removeprefix("play "))
        return "="

    def analyze(self, color, visits, interval, duration, extra_args):
        self.analysis_args = extra_args
        return [], []

    def parse_analysis(self, *_args, **_kwargs):
        return {"top_moves": self.candidates}


def service_for(engine):
    return AiMoveService(
        engine=engine, run_in_executor=inline_executor, engine_log=lambda _msg: None,
        coord_to_gtp=coord_to_gtp, gtp_to_coord=gtp_to_coord,
    )


class KoRegression(unittest.TestCase):
    def test_sync_preserves_ko_and_ordinary_move_history(self):
        game = make_ko_game()
        restored = replay_sync_sgf(build_board_sync_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.ko_point, game.ko_point)
        self.assertEqual(restored.moves, game.moves)

    def test_sync_preserves_ko_after_card_board_edit(self):
        game = make_ko_game()
        game.board[1][7] = 2  # A card spawned a stone absent from ordinary move history.
        restored = replay_sync_sgf(build_board_sync_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.ko_point, game.ko_point)

    def test_sync_keeps_manual_position_and_player_to_move(self):
        game = GoGame(size=9)
        game.board[4][4] = 2
        game.current_player = "W"
        sgf = build_board_sync_sgf(game)
        self.assertEqual(replay_sync_sgf(sgf).board, game.board)
        self.assertIn("PL[W]", sgf)

    def test_sync_preserves_handicap_and_capture_history(self):
        game = GoGame(size=9, handicap=2)
        for color, move in [("B", "C7"), ("B", "G3"), ("W", "E5")]:
            game.place_stone(*gtp_to_coord(move, 9), color)
            game.moves.append((color, move))
        restored = replay_sync_sgf(build_board_sync_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.moves, game.moves)

    def test_failed_loadsgf_stops_sync(self):
        engine = SimpleNamespace(_send_command_locked=lambda _cmd: "? cannot load file")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(RuntimeError):
            sync_board_to_katago_locked(make_ko_game(), engine, base_dir=Path(tmp), temp_dir=tmp)

    def test_ko_retry_uses_ranked_legal_alternative_once(self):
        engine = RetryEngine()
        move = asyncio.run(service_for(engine).retry_avoiding_ko(make_ko_game(), "W"))
        self.assertEqual(move, "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])
        self.assertEqual(engine.commands, ["undo", "play W D4"])
        self.assertIn("avoid", engine.analysis_args)
        i = engine.analysis_args.index("avoid")
        self.assertEqual(engine.analysis_args[i:i + 4], ["avoid", "W", "B8", "1"])

    def test_ko_retry_without_ranked_move_passes_without_random_placement(self):
        engine = RetryEngine(candidates=[])
        with patch("app.gameplay.ai_moves.random.shuffle", side_effect=AssertionError("random ko fallback")):
            move = asyncio.run(service_for(engine).retry_avoiding_ko(make_ko_game(), "W"))
        self.assertEqual(move, "pass")
        self.assertEqual(engine.history, ["previous player move", "W pass"])

    def test_failed_ko_undo_does_not_continue_search(self):
        engine = RetryEngine(undo_error=True)
        move = asyncio.run(service_for(engine).retry_avoiding_ko(make_ko_game(), "W"))
        self.assertTrue(move.startswith("?"))
        self.assertEqual(engine.commands, ["undo"])

    def test_failed_ko_retry_stops_generated_move_preparation(self):
        game = make_ko_game()
        send = AsyncMock()
        prepared = asyncio.run(prepare_generated_ai_move(
            game, send, color="W", gtp_move="B8", visits=800, rogue_cards=[],
            apply_suspicious_pass_fallback_fn=AsyncMock(return_value="B8"),
            is_suspicious_pass=lambda *_args: False, pick_nonpass_fallback_move=AsyncMock(),
            log_event=lambda _msg: None,
            resolve_resign_move=AsyncMock(return_value=AiMoveResolution("B8")),
            no_resign_move=AsyncMock(),
            apply_slip_move=lambda *_args, **_kwargs: AiMoveAdjustment("B8"),
            roll_random=lambda: 1, choose_point=lambda points: points[0],
            gtp_to_coord=gtp_to_coord, coord_to_gtp=coord_to_gtp,
            adjacent_points=lambda *_args: [], retry_ko_move=retry_ai_move_avoiding_ko,
            retry_avoiding_ko=AsyncMock(return_value="? cannot undo"),
        ))
        self.assertTrue(prepared.completed)
        self.assertEqual(len(game.moves), 9)
        self.assertEqual(send.call_args.args[0]["type"], "error")

    def test_failed_ko_retry_stops_ultimate_move_choice(self):
        choice = asyncio.run(choose_ultimate_ai_move(
            make_ko_game(), color="W", visits=800, forbidden=set(),
            generate_move=AsyncMock(return_value="B8"), no_resign_move=AsyncMock(),
            undo_engine_move=lambda: None, restore_engine_pass=None, play_engine_move=None,
            pick_ranked_legal_move=AsyncMock(), pick_nonpass_fallback_move=AsyncMock(),
            retry_avoiding_ko=AsyncMock(return_value="? cannot undo"),
            is_suspicious_ai_pass=lambda *_args: False,
            resolve_occupied_ai_move=lambda _game, _color, move, coord, **_kwargs: (move, coord),
            gtp_to_coord=gtp_to_coord, coord_to_gtp=coord_to_gtp, log_fn=lambda _msg: None,
        ))
        self.assertIsNotNone(choice.error_message)
        self.assertIsNone(choice.coord)

    def test_resign_retry_does_not_undo_previous_real_move(self):
        engine = RetryEngine(responses=["= resign", "= D4"])
        engine.history = ["previous player move"]
        self.assertEqual(asyncio.run(service_for(engine).no_resign_move(make_ko_game(), "W")), "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])

    def test_rejected_pass_is_undone_before_restricted_retry(self):
        engine = RetryEngine(responses=["= pass", "= D4"])
        engine.history = ["previous player move"]
        move = asyncio.run(service_for(engine).avoid_points(make_ko_game(), "W", 800, 3.0, {(1, 1)}))
        self.assertEqual(move, "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])

    def test_all_ai_pass_paths_clear_ko(self):
        for kind in ("normal", "auxiliary", "ultimate", "forced"):
            with self.subTest(kind=kind):
                game = make_ko_game()
                if kind == "normal":
                    apply_ai_move_to_board(game, color="W", gtp_move="pass", gtp_to_coord=gtp_to_coord)
                elif kind == "auxiliary":
                    place_auxiliary_ai_move_on_board(game, "W", "pass", None)
                elif kind == "ultimate":
                    apply_ultimate_ai_move_result(game, "W", "pass", None, count_turn=False)
                else:
                    asyncio.run(finalize_forced_ai_pass(
                        game, AsyncMock(), color="W", message="forced pass",
                        prepare_player_turn_modifiers=lambda _game: None, run_engine_command=AsyncMock(return_value="="),
                    ))
                self.assertIsNone(game.ko_point)
                self.assertEqual(game.last_captured_points, [])

    def test_player_pass_clears_ko_in_normal_and_ultimate_games(self):
        for ultimate in (False, True):
            with self.subTest(ultimate=ultimate):
                game = make_ko_game()
                game.player_color = "W"
                game.ai_color = "B"
                game.two_player = not ultimate
                game.ultimate = ultimate
                ctx = SimpleNamespace(
                    restore_game=lambda: game, engine=SimpleNamespace(ready=False), send=AsyncMock(),
                    record_ultimate_player_action=lambda _game: None,
                    finish_ultimate_quickthink_turn=lambda _game: None,
                )
                with patch("app.runtime.ws_turn_actions.ensure_engine_ready_for_game", AsyncMock(return_value=True)):
                    asyncio.run(handle_pass(ctx, {}))
                self.assertIsNone(game.ko_point)
                self.assertEqual(game.last_captured_points, [])

    def test_rebuild_clears_ko_on_pass(self):
        game = make_ko_game()
        game.moves.append(("W", "pass"))
        game.rebuild_board(strict=True)
        self.assertIsNone(game.ko_point)


if __name__ == "__main__":
    unittest.main(verbosity=2)
