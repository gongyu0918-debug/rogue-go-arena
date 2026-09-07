"""Stateful regressions for HTML branch ko synchronization and AI retries."""
from __future__ import annotations

import asyncio
import copy
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import server as s
from app.runtime.game_store import ActiveGameStore


def make_ko_game():
    game = s.GoGame(size=9)
    for color, move in [
        ("B", "A8"), ("W", "B8"), ("B", "B9"), ("W", "A7"),
        ("B", "C8"), ("W", "C7"), ("B", "H1"), ("W", "B6"), ("B", "B7"),
    ]:
        assert game.place_stone(*s.gtp_to_coord(move, 9), color) >= 0
        game.moves.append((color, move))
        game.current_player = "W" if color == "B" else "B"
        game.push_history()
    assert game.ko_point == (1, 1, 2)
    return game


def replay_sync_sgf(sgf):
    game = s.GoGame(size=int(re.search(r"SZ\[(\d+)\]", sgf)[1]))
    for prop, values in re.findall(r"(AB|AW)((?:\[[a-z]{2}\])+)", sgf):
        for point in re.findall(r"\[([a-z]{2})\]", values):
            game.board[ord(point[1]) - 97][ord(point[0]) - 97] = 1 if prop == "AB" else 2
    for color, point in re.findall(r";([BW])\[([a-z]{2})?\]", sgf):
        if point:
            x, y = ord(point[0]) - 97, ord(point[1]) - 97
            assert game.board[y][x] == 0 and game.place_stone(x, y, color) >= 0
            move = s.coord_to_gtp(x, y, game.size)
        else:
            move = "pass"
            game.ko_point = None
        game.moves.append((color, move))
    return game


async def inline_executor(fn, *args):
    return fn(*args)


class RetryEngine:
    """Model GTP mutations: genmove commits PASS/vertex; errors/RESIGN do not."""

    def __init__(self, *, candidates=None, responses=None, undo_error=False, sync_error=False, pass_error=False):
        self.command_lock = threading.Lock()
        self.current_visits = 800
        self.ready = True
        self.commands = []
        self.history = ["previous player move", "W B8"]
        self.candidates = [{"gtp": "B8"}, {"gtp": "A8"}, {"gtp": "D4"}] if candidates is None else candidates
        self.responses = list(responses or [])
        self.undo_error = undo_error
        self.sync_error = sync_error
        self.pass_error = pass_error
        self.analysis_args = None
        self.sgf = None

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
            if command.lower().endswith(" pass") and self.pass_error:
                return "? cannot play pass"
            self.history.append(command.removeprefix("play "))
        elif command.startswith("loadsgf "):
            if self.sync_error:
                return "? cannot load file"
            self.sgf = Path(command.removeprefix("loadsgf ")).read_text(encoding="utf-8")
        elif command == "final_score":
            return "= B+1.5"
        return "="

    def send_command(self, command, timeout=60):
        with self.command_lock:
            return self._send_command_locked(command, timeout)

    def analyze(self, color, visits, interval=50, duration=2.0, extra_args=None):
        self.analysis_args = extra_args
        return [], []

    def parse_analysis(self, *_args, **_kwargs):
        return {"top_moves": self.candidates}


def capture_sgf(game):
    engine = RetryEngine()
    with tempfile.TemporaryDirectory() as tmp, patch.object(s, "BASE_DIR", Path(tmp)), patch.object(s, "engine", engine):
        s._sync_board_to_katago_locked(game)
    return engine.sgf


class KoRegression(unittest.TestCase):
    def test_sync_preserves_ko_and_move_history(self):
        game = make_ko_game()
        restored = replay_sync_sgf(capture_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.ko_point, game.ko_point)
        self.assertEqual(restored.moves, game.moves)

    def test_sync_preserves_ko_after_card_board_edit(self):
        game = make_ko_game()
        game.board[1][7] = 2
        restored = replay_sync_sgf(capture_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.ko_point, game.ko_point)

    def test_sync_keeps_manual_position_and_player(self):
        game = s.GoGame(size=9)
        game.board[4][4] = 2
        game.current_player = "W"
        sgf = capture_sgf(game)
        self.assertEqual(replay_sync_sgf(sgf).board, game.board)
        self.assertIn("PL[W]", sgf)

    def test_sync_keeps_handicap_move_history(self):
        game = s.GoGame(size=9, handicap=2)
        for color, move in [("B", "C7"), ("B", "G3"), ("W", "E5")]:
            game.place_stone(*s.gtp_to_coord(move, 9), color)
            game.moves.append((color, move))
        restored = replay_sync_sgf(capture_sgf(game))
        self.assertEqual(restored.board, game.board)
        self.assertEqual(restored.moves, game.moves)

    def test_failed_sync_blocks_ai_generation(self):
        game = make_ko_game()
        engine = RetryEngine(sync_error=True)
        before = copy.deepcopy(game._snapshot_state())
        with tempfile.TemporaryDirectory() as tmp, patch.object(s, "BASE_DIR", Path(tmp)), patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            with self.assertRaisesRegex(RuntimeError, "board sync failed"):
                asyncio.run(s._ai_move(game, AsyncMock()))
        self.assertFalse(any(cmd.startswith("genmove ") for cmd in engine.commands))
        self.assertEqual(game._snapshot_state(), before)

    def test_sync_uses_gtp_safe_path_with_spaces_in_workspace(self):
        engine = RetryEngine()
        with tempfile.TemporaryDirectory(prefix="ko workspace ") as tmp, patch.object(s, "BASE_DIR", Path(tmp)), patch.object(s, "engine", engine):
            s._sync_board_to_katago_locked(make_ko_game())
        self.assertEqual(len(engine.commands[0].split()), 2)

    def test_ko_retry_uses_ranked_legal_alternative_once(self):
        engine = RetryEngine()
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_retry_avoiding_ko(make_ko_game(), "W"))
        self.assertEqual(move, "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])
        self.assertEqual(engine.commands, ["undo", "play W D4"])
        self.assertIn("avoid", engine.analysis_args)
        index = engine.analysis_args.index("avoid")
        self.assertEqual(engine.analysis_args[index:index + 4], ["avoid", "W", "B8", "1"])

    def test_ko_retry_without_candidate_passes_without_random_placement(self):
        engine = RetryEngine(candidates=[])
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor), patch.object(s.random, "shuffle", side_effect=AssertionError("random ko fallback")):
            move = asyncio.run(s._ai_retry_avoiding_ko(make_ko_game(), "W"))
        self.assertEqual(move, "pass")
        self.assertEqual(engine.history, ["previous player move", "W pass"])

    def test_failed_ko_undo_stops_search(self):
        engine = RetryEngine(undo_error=True)
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_retry_avoiding_ko(make_ko_game(), "W"))
        self.assertTrue(move.startswith("?"))
        self.assertEqual(engine.commands, ["undo"])

    def test_failed_ko_pass_is_reported(self):
        engine = RetryEngine(candidates=[], pass_error=True)
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_retry_avoiding_ko(make_ko_game(), "W"))
        self.assertTrue(move.startswith("?"))

    def test_failed_retry_never_enters_ai_game_history(self):
        for kind in ("normal", "ultimate", "forced", "coach"):
            with self.subTest(kind=kind):
                game = make_ko_game()
                if kind == "coach":
                    game.player_color, game.ai_color = "W", "B"
                    game.rogue_card = "coach_mode"
                    game.rogue_coach_moves_left = 2
                before = copy.deepcopy(game.moves)
                board_before = copy.deepcopy(game.board)
                send = AsyncMock()
                engine = RetryEngine(responses=["= B8"])
                with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor), patch.object(s, "_sync_board_to_katago", AsyncMock()), patch.object(s, "_ai_retry_avoiding_ko", AsyncMock(return_value="? cannot undo")):
                    if kind == "normal":
                        asyncio.run(s._ai_move(game, send))
                    elif kind == "ultimate":
                        asyncio.run(s._ultimate_ai_move(game, send))
                    elif kind == "forced":
                        asyncio.run(s._finish_ai_move(game, send, "W", "seal", "B8"))
                    else:
                        with patch.object(s, "_ai_move", AsyncMock()):
                            asyncio.run(s._run_coach_turn_if_needed(game, send))
                self.assertEqual(game.moves, before)
                self.assertEqual(game.board, board_before)
                self.assertTrue(any(call.args[0]["type"] == "error" for call in send.call_args_list))

    def test_resign_retry_keeps_previous_real_move(self):
        engine = RetryEngine(responses=["= resign", "= D4"])
        engine.history = ["previous player move"]
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_move_no_resign(make_ko_game(), "W"))
        self.assertEqual(move, "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])

    def test_occupied_ultimate_response_stops_without_move_or_card_effect(self):
        for full_board in (False, True):
            with self.subTest(full_board=full_board):
                game = make_ko_game()
                game.ultimate = True
                game.ultimate_ai_card = "meteor"
                if full_board:
                    game.board = [[1] * game.size for _ in range(game.size)]
                before = game._snapshot_state()
                send = AsyncMock()
                effect = AsyncMock(return_value=False)
                engine = RetryEngine(responses=["= A8"])
                with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor), patch.object(s, "_sync_board_to_katago", AsyncMock()), patch.object(s, "_apply_ultimate_effect", effect):
                    asyncio.run(s._ultimate_ai_move(game, send))
                self.assertEqual(game._snapshot_state(), before)
                effect.assert_not_awaited()
                self.assertEqual([call.args[0]["type"] for call in send.call_args_list], ["error"])
                self.assertFalse(any(cmd.startswith("play ") or cmd == "undo" for cmd in engine.commands))

    def test_restricted_retry_undoes_rejected_pass(self):
        engine = RetryEngine(responses=["= pass", "= D4"])
        engine.history = ["previous player move"]
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_move_avoid_points(make_ko_game(), "W", 800, 3.0, {(1, 1)}))
        self.assertEqual(move, "D4")
        self.assertEqual(engine.history, ["previous player move", "W D4"])

    def test_restricted_generation_error_never_undoes_real_move(self):
        engine = RetryEngine(responses=["? engine failure"])
        engine.history = ["previous player move"]
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_move_avoid_points_allow_only(make_ko_game(), "W", 800, 3.0, [(3, 5)]))
        self.assertTrue(move.startswith("?"))
        self.assertNotIn("undo", engine.commands)
        self.assertEqual(engine.history, ["previous player move"])

    def test_restricted_pass_failure_is_not_reported_as_a_move(self):
        game = make_ko_game()
        engine = RetryEngine(candidates=[], responses=["= pass"] * 6, pass_error=True)
        engine.history = ["previous player move"]
        forbidden = {(x, y) for y in range(game.size) for x in range(game.size)}
        with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
            move = asyncio.run(s._ai_move_avoid_points(game, "W", 800, 3.0, forbidden))
        self.assertTrue(move.startswith("?"))
        self.assertEqual(engine.history, ["previous player move"])

    def test_replacing_early_pass_keeps_exactly_one_committed_move(self):
        for candidates, expected in (([{"gtp": "D4"}], "W D4"), ([], "W pass")):
            with self.subTest(candidates=candidates):
                engine = RetryEngine(candidates=candidates)
                engine.history = ["previous player move", "W pass"]
                with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor):
                    asyncio.run(s._pick_nonpass_fallback_move(make_ko_game(), "W", 800))
                self.assertEqual(engine.history, ["previous player move", expected])

    def test_all_ai_pass_paths_clear_ko(self):
        for kind in ("normal", "ultimate", "forced", "dice", "exchange", "coach"):
            with self.subTest(kind=kind):
                game = make_ko_game()
                engine = RetryEngine(responses=["= pass"])
                if kind in {"dice", "exchange"}:
                    game.rogue_card = kind
                    game.rogue_enabled = True
                    game.rogue_skip_ai = kind == "exchange"
                if kind == "coach":
                    game.player_color, game.ai_color = "W", "B"
                    game.rogue_card = "coach_mode"
                    game.rogue_coach_moves_left = 2
                with patch.object(s, "engine", engine), patch.object(s, "run_in_executor", inline_executor), patch.object(s, "_sync_board_to_katago", AsyncMock()), patch.object(s, "_is_suspicious_ai_pass", return_value=False), patch.object(s.random, "random", return_value=0):
                    if kind == "ultimate":
                        asyncio.run(s._ultimate_ai_move(game, AsyncMock()))
                    elif kind == "forced":
                        asyncio.run(s._finish_ai_move(game, AsyncMock(), "W", "seal", "pass"))
                    elif kind == "coach":
                        with patch.object(s, "_ai_move", AsyncMock()):
                            asyncio.run(s._run_coach_turn_if_needed(game, AsyncMock()))
                    else:
                        asyncio.run(s._ai_move(game, AsyncMock()))
                self.assertIsNone(game.ko_point)

    def test_player_pass_clears_ko_in_normal_and_ultimate(self):
        for ultimate in (False, True):
            with self.subTest(ultimate=ultimate):
                game = make_ko_game()
                game.player_color, game.ai_color = "W", "B"
                game.two_player = not ultimate
                game.ultimate = ultimate
                store = ActiveGameStore(3600)
                store.set("ko-pass", game)
                socket = type("Socket", (), {})()
                socket.accept = AsyncMock()
                socket.send_text = AsyncMock()
                socket.receive_text = AsyncMock(side_effect=[json.dumps({"action": "pass"}), s.WebSocketDisconnect()])
                engine = RetryEngine()
                engine.ready = False
                with patch.object(s, "engine", engine), patch.object(s, "active_games", store):
                    asyncio.run(s.websocket_endpoint(socket, "ko-pass"))
                self.assertIsNone(game.ko_point)
                self.assertEqual(game.moves[-1], ("W", "pass"))

    def test_failed_player_pass_keeps_turn_and_history(self):
        game = make_ko_game()
        game.two_player = True
        before = game._snapshot_state()
        store = ActiveGameStore(3600)
        store.set("ko-pass-error", game)
        socket = type("Socket", (), {})()
        socket.accept = AsyncMock()
        socket.send_text = AsyncMock()
        socket.receive_text = AsyncMock(side_effect=[json.dumps({"action": "pass"}), s.WebSocketDisconnect()])
        engine = RetryEngine(pass_error=True)
        with patch.object(s, "engine", engine), patch.object(s, "active_games", store), patch.object(s, "run_in_executor", inline_executor):
            asyncio.run(s.websocket_endpoint(socket, "ko-pass-error"))
        self.assertEqual(game._snapshot_state(), before)
        self.assertTrue(any(json.loads(call.args[0])["type"] == "error" for call in socket.send_text.call_args_list))

    def test_rebuild_clears_ko_on_pass_or_empty_history(self):
        game = make_ko_game()
        game.moves.append(("W", "pass"))
        game.rebuild_board()
        self.assertIsNone(game.ko_point)
        game.ko_point = (1, 1, 2)
        game.moves = []
        game.rebuild_board()
        self.assertIsNone(game.ko_point)


if __name__ == "__main__":
    unittest.main(verbosity=2)
