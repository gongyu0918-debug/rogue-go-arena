"""Exercise HTML style dropdowns through AI execution and observer termination."""
from __future__ import annotations

import asyncio
import copy
import threading
import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import server as s


STYLE_EXPECTED_MOVES = {
    "territory": "A9",
    "influence": "E5",
    "attack": "C5",
    "defense": "G2",
}


def make_style_game():
    game = s.GoGame(size=9)
    game.board[6][6] = 1
    game.board[3][2] = 2
    game.player_color, game.ai_color = "W", "B"
    game.current_player = "B"
    return game


async def inline_executor(fn, *args):
    return fn(*args)


class StyleEngine:
    def __init__(self, *, play_error=False, analysis_error=False):
        self.ready = True
        self.current_visits = 800
        self.command_lock = threading.Lock()
        self.commands = []
        self.history = []
        self.analyses = []
        self.play_error = play_error
        self.analysis_error = analysis_error

    def _send_command_locked(self, command, timeout=60):
        self.commands.append(command)
        if command.startswith("play "):
            if self.play_error:
                return "? style move rejected"
            _, color, move = command.split()
            self.history.append((color, move))
        elif command.startswith("genmove "):
            self.history.append((command.split()[1], "H1"))
            return "= H1"
        return "="

    def send_command(self, command, timeout=60):
        with self.command_lock:
            return self._send_command_locked(command, timeout)

    def analyze(self, color, visits, interval=50, duration=1.8, extra_args=None):
        self.analyses.append({"color": color, "visits": visits})
        if self.analysis_error:
            raise RuntimeError("analysis unavailable")
        return [], []

    def parse_analysis(self, *_args, **_kwargs):
        return {"top_moves": [{"move": move} for move in STYLE_EXPECTED_MOVES.values()]}


def runtime_patches(engine):
    stack = ExitStack()
    stack.enter_context(patch.object(s, "engine", engine))
    stack.enter_context(patch.object(s, "run_in_executor", inline_executor))
    stack.enter_context(patch.object(s, "_sync_board_to_katago", AsyncMock()))
    return stack


class AiStyleRegression(unittest.TestCase):
    def test_all_style_values_use_existing_scores_and_commit_once(self):
        for style, expected in STYLE_EXPECTED_MOVES.items():
            with self.subTest(style=style):
                game, engine = make_style_game(), StyleEngine()
                game.ai_style = style
                before = game._snapshot_state()
                with runtime_patches(engine):
                    move = asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
                self.assertEqual(move, expected)
                self.assertEqual(engine.history, [("B", expected)])
                self.assertEqual(len(engine.analyses), 1)
                self.assertFalse(any(command.startswith("genmove ") for command in engine.commands))
                self.assertEqual(game._snapshot_state(), before)

    def test_balanced_uses_engine_generation_without_style_analysis(self):
        game, engine = make_style_game(), StyleEngine()
        with runtime_patches(engine):
            move = asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
        self.assertEqual(move, "H1")
        self.assertEqual(engine.history, [("B", "H1")])
        self.assertEqual(engine.analyses, [])

    def test_normal_ai_applies_selected_style_to_engine_and_visible_board(self):
        game, engine, send = make_style_game(), StyleEngine(), AsyncMock()
        game.ai_style = "influence"
        with runtime_patches(engine):
            asyncio.run(s._ai_move(game, send))
        self.assertEqual(game.moves, [("B", "E5")])
        self.assertEqual(engine.history, game.moves)
        self.assertEqual(game.board[4][4], 1)
        self.assertEqual(game.current_player, "W")

    def test_failed_style_play_never_reaches_visible_history(self):
        game, engine, send = make_style_game(), StyleEngine(play_error=True), AsyncMock()
        game.ai_style = "influence"
        before = game._snapshot_state()
        with runtime_patches(engine):
            asyncio.run(s._ai_move(game, send))
        self.assertEqual(game._snapshot_state(), before)
        self.assertEqual(engine.history, [])
        events = [call.args[0] for call in send.call_args_list]
        self.assertTrue(any(event["type"] == "error" for event in events))
        self.assertFalse(any(event["type"] == "ai_move" for event in events))

    def test_style_generation_propagates_rejected_play(self):
        game, engine = make_style_game(), StyleEngine(play_error=True)
        game.ai_style = "influence"
        with runtime_patches(engine):
            move = asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
        self.assertTrue(move.startswith("?"))
        self.assertEqual(engine.history, [])
        self.assertFalse(any(command.startswith("genmove ") for command in engine.commands))

    def test_analysis_failure_falls_back_to_one_generated_move(self):
        game, engine = make_style_game(), StyleEngine(analysis_error=True)
        game.ai_style = "influence"
        with runtime_patches(engine):
            move = asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
        self.assertEqual(move, "H1")
        self.assertEqual(engine.history, [("B", "H1")])
        self.assertEqual(len(engine.analyses), 1)

    def test_style_choice_skips_ko_without_changing_its_scoring(self):
        game, engine = make_style_game(), StyleEngine()
        game.ai_style = "influence"
        game.ko_point = (4, 4, 1)
        with runtime_patches(engine):
            move = asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
        self.assertEqual(move, "C5")
        self.assertEqual(engine.history, [("B", "C5")])
        self.assertEqual(game.ko_point, (4, 4, 1))

    def test_observer_reads_the_selected_style_for_each_color(self):
        for color, style, expected in (("B", "territory", "A9"), ("W", "attack", "G2")):
            with self.subTest(color=color):
                game, engine = make_style_game(), StyleEngine()
                game.ai_observer = True
                game.ai_style = "influence"
                game.ai_style_black = "territory"
                game.ai_style_white = "attack"
                with runtime_patches(engine):
                    move = asyncio.run(s._generate_ai_style_move(game, color, 800, 3))
                self.assertEqual(move, expected, style)
                self.assertEqual(engine.history, [(color, expected)])

    def test_observer_resign_ends_game_without_recording_a_move(self):
        for color in ("B", "W"):
            with self.subTest(color=color):
                game, engine = make_style_game(), StyleEngine()
                game.ai_observer = True
                game.current_player = color
                board, moves, passed = copy.deepcopy(game.board), list(game.moves), dict(game.passed)
                events = []

                async def send(event):
                    events.append(event)
                    if event["type"] == "game_state":
                        game.ai_observer = False  # Bound the old, broken loop to one iteration.

                with runtime_patches(engine), patch.object(s, "_generate_ai_style_move", AsyncMock(return_value="RESIGN")):
                    asyncio.run(s._run_ai_observer_loop(game, send))
                self.assertTrue(game.game_over)
                self.assertEqual(game.winner, "W" if color == "B" else "B")
                self.assertEqual((game.board, game.moves, game.passed), (board, moves, passed))
                self.assertEqual(engine.history, [])
                self.assertFalse(any(event["type"] == "ai_move" for event in events))
                terminal = [event for event in events if event["type"] == "game_over"]
                self.assertEqual(len(terminal), 1)
                self.assertEqual(terminal[0]["winner"], game.winner)

    def test_observer_pass_still_records_one_move_and_releases_ko(self):
        game, engine = make_style_game(), StyleEngine()
        game.ai_observer = True
        game.ko_point = (1, 1, 1)

        async def send(event):
            if event["type"] == "game_state":
                game.ai_observer = False

        with runtime_patches(engine), patch.object(s, "_generate_ai_style_move", AsyncMock(return_value="PASS")), patch.object(s, "_is_suspicious_ai_pass", return_value=False):
            asyncio.run(s._run_ai_observer_loop(game, send))
        self.assertEqual(game.moves, [("B", "PASS")])
        self.assertIsNone(game.ko_point)
        self.assertTrue(game.passed["B"])
        self.assertFalse(game.game_over)

    def test_failed_sync_stops_style_analysis_and_generation(self):
        game, engine = make_style_game(), StyleEngine()
        game.ai_style = "influence"
        with runtime_patches(engine), patch.object(s, "_sync_board_to_katago", AsyncMock(side_effect=RuntimeError("sync failed"))):
            with self.assertRaisesRegex(RuntimeError, "sync failed"):
                asyncio.run(s._generate_ai_style_move(game, "B", 800, 3))
        self.assertEqual(engine.analyses, [])
        self.assertEqual(engine.commands, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
