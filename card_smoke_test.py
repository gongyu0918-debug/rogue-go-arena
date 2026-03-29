import asyncio
import copy
import random
import threading

import server as s


class DummyEngine:
    def __init__(self, queued_moves=None):
        self.ready = True
        self.command_lock = threading.Lock()
        self.current_visits = 400
        self._queued_moves = list(queued_moves or [])
        self._played = []

    def _next_empty_gtp(self, game, forbidden=None):
        forbidden = forbidden or set()
        for y in range(game.size):
            for x in range(game.size):
                gtp = s.coord_to_gtp(x, y, game.size)
                if game.board[y][x] == 0 and gtp.upper() not in forbidden:
                    return gtp
        return "pass"

    def _send_command_locked(self, cmd, timeout=60):
        if cmd.startswith("genmove "):
            if self._queued_moves:
                return "= " + self._queued_moves.pop(0)
            return "= pass"
        if cmd.startswith("play "):
            parts = cmd.split()
            if len(parts) >= 3:
                self._played.append((parts[1], parts[2]))
            return "="
        if cmd.startswith("loadsgf "):
            return "="
        if cmd.startswith("kata-set-param "):
            return "="
        if cmd in {"undo", "clear_board"}:
            return "="
        if cmd == "final_score":
            return "= B+1.5"
        return "="

    def send_command(self, cmd, timeout=60):
        with self.command_lock:
            return self._send_command_locked(cmd, timeout)

    def analyze(self, color, visits, interval=50, duration=2.0, extra_args=None):
        lines = [
            "info move D4 visits 100 winrate 5200 scoreMean 1.0 pv D4",
            "info move C3 visits 80 winrate 5100 scoreMean 0.5 pv C3",
            "info move Q16 visits 70 winrate 5000 scoreMean 0.2 pv Q16",
            "info move K10 visits 60 winrate 4950 scoreMean 0.1 pv K10",
            "info move E5 visits 50 winrate 4900 scoreMean -0.2 pv E5",
        ]
        return lines, []

    def parse_analysis(self, lines, ownership_data, size, to_move_color):
        top_moves = []
        for line in lines:
            parts = line.split()
            try:
                move = parts[parts.index("move") + 1]
            except (ValueError, IndexError):
                continue
            top_moves.append({"move": move, "gtp": move})
        return {"top_moves": top_moves}


def make_game(size=9):
    game = s.GoGame(size=size, komi=7.5, player_color="B", level="5k", two_player=False)
    game.current_player = game.player_color
    return game


def seed_board(game):
    for y in range(game.size):
        for x in range(game.size):
            if (x + y) % 7 == 0:
                game.board[y][x] = 1
            elif (x * 2 + y) % 9 == 0:
                game.board[y][x] = 2
    game.board[4][4] = 0
    game.board[3][3] = 0
    game.board[2][2] = 0
    game.board[1][1] = 0


async def collect_messages(fn, *args, **kwargs):
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    await fn(*args, send, *kwargs.get("tail_args", ()))
    return sent


async def smoke_activate_rogue_cards():
    for card_id in s.ROGUE_CARDS:
        game = make_game()
        seed_board(game)
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        await s._activate_rogue_card(game, send, card_id)
        assert game.rogue_card == card_id
        assert any(msg.get("type") == "rogue_card_selected" for msg in sent)


async def smoke_player_rogue_effects():
    cards = list(s.ROGUE_CARDS.keys())
    for card_id in cards:
        game = make_game()
        seed_board(game)
        game.rogue_card = card_id
        game.moves = [("B", s.coord_to_gtp(4, 4, game.size))]
        game.rogue_joseki_targets = [(4, 4), (3, 3), (2, 2), (5, 5), (6, 6), (1, 1)]
        game.rogue_handicap_active = True
        game.rogue_handicap_passes = s.ROGUE_HANDICAP_REQUIRED_PASSES
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        await s._apply_player_rogue_move_effects(game, send, 4, 4, "B", 2)
        assert isinstance(sent, list)


async def smoke_joseki_completion():
    game = make_game()
    seed_board(game)
    game.rogue_card = "joseki_ocd"
    game.rogue_joseki_targets = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7)]
    game.rogue_joseki_hits = s.ROGUE_JOSEKI_REQUIRED_HITS - 1
    game.moves = [("B", s.coord_to_gtp(1, 1, game.size)), ("B", s.coord_to_gtp(2, 2, game.size))]
    sent = []
    synced = {"count": 0}

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_sync = s._sync_board_to_katago
    try:
        async def fake_sync(_game):
            synced["count"] += 1

        s._sync_board_to_katago = fake_sync
        await s._apply_player_rogue_move_effects(game, send, 3, 3, "B", 0)
    finally:
        s._sync_board_to_katago = old_sync

    assert game.rogue_joseki_done is True
    assert synced["count"] == 1
    for x, y in game.rogue_joseki_targets:
        assert game.board[y][x] == 1
    assert any(msg.get("type") == "rogue_event" for msg in sent)


async def smoke_ai_rogue_cards():
    for card_id in s.ROGUE_CARDS:
        game = make_game()
        seed_board(game)
        game.rogue_card = card_id
        game.current_player = game.ai_color
        game.moves = [("B", "D4")]
        if card_id == "mirror":
            game.moves = [("B", "D4")]
        if card_id == "seal":
            game.rogue_seal_points = [(0, 0), (1, 0), (0, 1)]
        if card_id == "golden_corner":
            game.rogue_seal_points = s._get_golden_corner_points(game.size, 0)
        if card_id == "exchange":
            game.rogue_skip_ai = True
        if card_id == "handicap_quest":
            game.rogue_handicap_active = True
            game.rogue_handicap_bonuses = 0
            game.rogue_handicap_passes = s.ROGUE_HANDICAP_REQUIRED_PASSES
            game.moves = [("B", "D4")] * s.ROGUE_HANDICAP_BONUS_INTERVAL

        queued = ["E5", "C3", "F6", "G7", "B2", "H8"]
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        old_engine = s.engine
        old_random = s.random.random
        try:
            s.engine = DummyEngine(queued)
            if card_id in {"dice", "mirror"}:
                s.random.random = lambda: 0.0
            else:
                s.random.random = lambda: 1.0
            await s._ai_move(game, send)
        finally:
            s.engine = old_engine
            s.random.random = old_random
        assert isinstance(sent, list)


async def smoke_slip_card():
    game = make_game()
    seed_board(game)
    game.rogue_card = "slip"
    game.current_player = game.ai_color
    game.moves = [("B", "D4")]
    sent = []
    synced = {"count": 0}

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    old_sync = s._sync_board_to_katago
    old_random = s.random.random
    old_choice = s.random.choice
    try:
        s.engine = DummyEngine(["E5"])

        async def fake_sync(_game):
            synced["count"] += 1

        s._sync_board_to_katago = fake_sync
        s.random.random = lambda: 0.0
        s.random.choice = lambda items: items[0]
        await s._ai_move(game, send)
    finally:
        s.engine = old_engine
        s._sync_board_to_katago = old_sync
        s.random.random = old_random
        s.random.choice = old_choice

    ai_move = next(msg for msg in sent if msg.get("type") == "ai_move")
    assert ai_move["gtp"] != "E5"
    assert synced["count"] == 1
    assert any(msg.get("type") == "rogue_event" for msg in sent)


async def smoke_new_rogue_cards():
    game = make_game()
    game.rogue_card = "god_hand"
    game.rogue_godhand_center = (4, 4)
    game.rogue_godhand_trigger = s._diamond_points(4, 4, 1, game.size)
    game.board[4][5] = 2
    game.board[5][4] = 2
    synced = {"count": 0}

    async def send(_payload):
        return None

    old_sync = s._sync_board_to_katago
    try:
        async def fake_sync(_game):
            synced["count"] += 1

        s._sync_board_to_katago = fake_sync
        await s._apply_player_rogue_move_effects(game, send, 4, 4, "B", 0)
    finally:
        s._sync_board_to_katago = old_sync

    assert game.rogue_godhand_done is True
    assert synced["count"] == 1
    assert sum(1 for x, y in s._diamond_points(4, 4, 2, game.size) if game.board[y][x] == 1) >= 5

    game = make_game()
    game.rogue_card = "corner_helper"
    game.board[0][0] = 1
    game.board[1][1] = 1
    old_sync = s._sync_board_to_katago
    try:
        async def fake_sync(_game):
            return None

        s._sync_board_to_katago = fake_sync
        await s._apply_player_rogue_move_effects(game, send, 1, 1, "B", 0)
    finally:
        s._sync_board_to_katago = old_sync
    assert game.rogue_corner_helper_done is True
    assert sum(1 for x, y in s._get_corner_helper_spawn_points(game.size, 0, 5) if game.board[y][x] == 1) >= 2

    game = make_game()
    game.rogue_card = "sanrensei"
    game.moves = [("B", "C7"), ("W", "E5"), ("B", "E7"), ("W", "D5"), ("B", "G7")]
    old_sync = s._sync_board_to_katago
    try:
        async def fake_sync(_game):
            return None

        s._sync_board_to_katago = fake_sync
        await s._apply_player_rogue_move_effects(game, send, 6, 2, "B", 0)
    finally:
        s._sync_board_to_katago = old_sync
    assert game.rogue_sanrensei_done is True

    game = make_game()
    game.rogue_card = "no_regret"
    old_pick = s._pick_second_best_point
    old_random = s.random.random
    old_sync = s._sync_board_to_katago
    try:
        async def fake_pick(_game, _color):
            return (4, 4)

        async def fake_sync(_game):
            return None

        s._pick_second_best_point = fake_pick
        s.random.random = lambda: 0.0
        s._sync_board_to_katago = fake_sync
        await s._apply_player_rogue_move_effects(game, send, 3, 3, "B", 0)
    finally:
        s._pick_second_best_point = old_pick
        s.random.random = old_random
        s._sync_board_to_katago = old_sync
    assert game.board[4][4] == 1


async def smoke_sansan_trap():
    game = make_game()
    game.rogue_card = "sansan_trap"
    game.current_player = game.ai_color
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    try:
        s.engine = DummyEngine(["C7"])
        await s._ai_move(game, send)
    finally:
        s.engine = old_engine

    assert game.rogue_sansan_trap_done is True
    assert sum(1 for x, y in s._adjacent8_points(2, 2, game.size) if game.board[y][x] == 1) >= 3
    assert any(msg.get("type") == "rogue_event" for msg in sent)


async def smoke_new_ultimate_cards():
    game = make_game()
    game.ultimate = True
    game.ultimate_godhand_center = (4, 4)
    game.ultimate_godhand_trigger = s._diamond_points(4, 4, 2, game.size)
    for y in range(game.size):
        for x in range(game.size):
            if (x + y) % 2 == 0:
                game.board[y][x] = 2
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    modified = await s._apply_ultimate_effect(game, send, 4, 4, "B", "god_hand")
    assert modified is True
    assert game.ultimate_godhand_done is True
    assert all(cell != 2 for row in game.board for cell in row)
    assert sum(1 for row in game.board for cell in row if cell == 1) >= 10

    game = make_game()
    game.ultimate = True
    game.board[0][0] = 1
    game.board[1][1] = 1
    game.board[2][2] = 2
    modified = await s._apply_ultimate_effect(game, send, 1, 1, "B", "corner_helper")
    assert modified is True
    assert game.ultimate_corner_helper_done is True

    game = make_game()
    game.ultimate = True
    game.moves = [("B", "C7"), ("W", "E5"), ("B", "E7"), ("W", "D5"), ("B", "G7")]
    modified = await s._apply_ultimate_effect(game, send, 6, 2, "B", "sanrensei")
    assert modified is True
    assert game.ultimate_sanrensei_done is True


async def smoke_quickthink_flow():
    game = make_game()
    game.rogue_card = "quickthink"
    game.rogue_quickthink_stage = 1
    game.current_player = game.player_color
    game.moves.append(("B", s.coord_to_gtp(4, 4, game.size)))
    game.place_stone(4, 4, "B")
    game.current_player = game.ai_color
    game.rogue_quickthink_stage = 0
    assert game.current_player == "W"
    assert game.rogue_quickthink_stage == 0

    old_engine = s.engine
    try:
        s.engine = DummyEngine(["E5"])
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        await s._ai_move(game, send)
    finally:
        s.engine = old_engine

    final_state = next(msg for msg in reversed(sent) if msg.get("type") == "game_state")
    assert final_state["current_player"] == "B"
    assert final_state["rogue_quickthink_stage"] == 1

    game = make_game()
    game.ultimate = True
    game.current_player = game.player_color
    game.ultimate_player_card = "quickthink"
    game.ultimate_quickthink_active = True
    game.ultimate_quickthink_token = 1
    game.ultimate_move_count += 1
    game.moves.append(("B", s.coord_to_gtp(4, 4, game.size)))
    game.place_stone(4, 4, "B")
    assert game.ultimate_quickthink_active is True
    assert game.ultimate_quickthink_token == 1

    old_engine = s.engine
    try:
        s.engine = DummyEngine(["E5"])
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        game.ultimate_quickthink_active = False
        game.current_player = game.ai_color
        await s._ultimate_ai_move(game, send)
    finally:
        s.engine = old_engine

    final_state = next(msg for msg in reversed(sent) if msg.get("type") == "game_state")
    assert final_state["current_player"] == "B"
    assert final_state["ultimate_quickthink_active"] is True
    assert final_state["ultimate_quickthink_token"] == 2


async def smoke_featured_pools():
    class FakeRng:
        def __init__(self, *_args, **_kwargs):
            pass

        def shuffle(self, items):
            return None

        def choice(self, items):
            return items[0]

    old_random_cls = s.random.Random
    try:
        s.random.Random = FakeRng
        rogue = s.pick_rogue_choices(3)
        ultimate = s.pick_ultimate_choices(3)
    finally:
        s.random.Random = old_random_cls

    assert len(rogue) == 3
    assert len(set(rogue)) == 3
    assert any(card in s.ROGUE_FEATURED_CARDS for card in rogue)

    assert len(ultimate) == 3
    assert len(set(ultimate)) == 3
    assert any(card in s.ULTIMATE_FEATURED_CARDS for card in ultimate)


async def smoke_suboptimal_extended():
    game = make_game()
    game.rogue_card = "suboptimal"
    game.current_player = game.ai_color
    game.moves = []
    for i in range(6):
        game.moves.append(("B" if i % 2 == 0 else "W", s.coord_to_gtp(i, 0, game.size)))

    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    old_suboptimal = s._ai_move_suboptimal
    marker = {"called": False}
    try:
        s.engine = DummyEngine(["E5"])

        async def fake_suboptimal(_game, _color, _visits, _time_limit):
            marker["called"] = True
            return "D4"

        s._ai_move_suboptimal = fake_suboptimal
        await s._ai_move(game, send)
    finally:
        s.engine = old_engine
        s._ai_move_suboptimal = old_suboptimal

    assert marker["called"] is True


async def smoke_fog_mask_refresh():
    game = make_game()
    game.rogue_card = "fog"
    game.current_player = game.ai_color
    game.moves = [("B", "D4")]
    sent = []
    marker = {"forbidden": None}

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    old_pick = s._pick_fog_mask
    old_avoid = s._ai_move_avoid_points
    try:
        s.engine = DummyEngine(["E5"])
        s._pick_fog_mask = lambda _size, _rng: [(3, 3), (3, 4), (4, 3), (4, 4)]

        async def fake_avoid(_game, _color, _visits, _time_limit, forbidden):
            marker["forbidden"] = list(forbidden)
            return "E5"

        s._ai_move_avoid_points = fake_avoid
        await s._ai_move(game, send)
    finally:
        s.engine = old_engine
        s._pick_fog_mask = old_pick
        s._ai_move_avoid_points = old_avoid

    assert marker["forbidden"] == [(3, 3), (3, 4), (4, 3), (4, 4)]
    assert game.rogue_seal_points == [(3, 3), (3, 4), (4, 3), (4, 4)]
    assert any(msg.get("type") == "rogue_event" for msg in sent)


async def smoke_foolish_wisdom_rogue():
    game = make_game()
    game.rogue_card = "foolish_wisdom"
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1
    synced = {"count": 0}

    async def send(_payload):
        return None

    old_sync = s._sync_board_to_katago
    old_shuffle = s.random.shuffle
    try:
        async def fake_sync(_game):
            synced["count"] += 1

        s._sync_board_to_katago = fake_sync
        s.random.shuffle = lambda _items: None
        await s._apply_player_rogue_move_effects(game, send, 2, 3, "B", 0)
    finally:
        s._sync_board_to_katago = old_sync
        s.random.shuffle = old_shuffle

    assert len(game.rogue_fool_shapes) == 1
    assert synced["count"] == 1
    assert sum(1 for row in game.board for cell in row if cell == 1) >= 4


async def smoke_foolish_wisdom_ultimate():
    game = make_game()
    game.ultimate = True
    game.board[2][2] = 1
    game.board[2][3] = 1
    game.board[3][2] = 1
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_sleep = s.asyncio.sleep
    old_shuffle = s.random.shuffle
    try:
        async def fake_sleep(_seconds):
            return None

        s.asyncio.sleep = fake_sleep
        s.random.shuffle = lambda _items: None
        modified = await s._apply_ultimate_effect(game, send, 2, 3, "B", "foolish_wisdom")
    finally:
        s.asyncio.sleep = old_sleep
        s.random.shuffle = old_shuffle

    assert modified is True
    assert len(game.ultimate_fool_shapes) >= 1
    assert sum(1 for row in game.board for cell in row if cell == 1) >= 23
    assert "foolish_wisdom" not in s.AI_ULTIMATE_POOL


async def smoke_two_player_rogue_shared_cards():
    game = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=True)
    game.rogue_enabled = True
    game.rogue_card = "sprout"
    game.current_player = "B"
    game.moves.append(("B", s.coord_to_gtp(4, 4, game.size)))
    game.place_stone(4, 4, "B")
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    try:
        s.engine = DummyEngine()
        await s._apply_player_rogue_move_effects(game, send, 4, 4, "B", 0)
    finally:
        s.engine = old_engine

    black_stones = sum(1 for row in game.board for cell in row if cell == 1)
    assert black_stones >= 2
    assert any(msg.get("type") == "rogue_event" for msg in sent)

    game = s.GoGame(size=9, komi=7.5, player_color="B", level="5k", two_player=True)
    game.rogue_enabled = True
    game.rogue_card = "sansan_trap"
    game.current_player = "W"
    game.moves.append(("W", s.coord_to_gtp(2, 2, game.size)))
    game.place_stone(2, 2, "W")
    sent = []

    async def send_white(payload):
        sent.append(copy.deepcopy(payload))

    await s._apply_player_rogue_move_effects(game, send_white, 2, 2, "W", 0)
    white_stones = sum(1 for row in game.board for cell in row if cell == 2)
    assert white_stones >= 4
    assert any(msg.get("type") == "rogue_event" for msg in sent)

    choices = s.pick_rogue_choices(3, pool=s.TWO_PLAYER_ROGUE_POOL)
    assert len(choices) == 3
    assert all(card in s.TWO_PLAYER_ROGUE_POOL for card in choices)


async def smoke_ai_rogue_support():
    game = make_game()
    game.rogue_enabled = True
    game.ai_rogue_enabled = True
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    await s._activate_ai_rogue_card(game, send, "golden_corner")
    assert game.ai_rogue_card == "golden_corner"
    assert len(game.ai_rogue_seal_points) == 16
    assert any(msg.get("type") == "rogue_ai_selected" for msg in sent)

    game = make_game()
    game.rogue_enabled = True
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "fog"
    game.current_player = game.player_color
    old_pick = s._pick_fog_mask
    try:
        s._pick_fog_mask = lambda _size, _rng: [(3, 3), (3, 4), (4, 3), (4, 4)]
        s._refresh_ai_rogue_player_turn(game)
    finally:
        s._pick_fog_mask = old_pick
    assert s._get_ai_rogue_forbidden_points(game) == [(3, 3), (3, 4), (4, 3), (4, 4)]
    game.current_player = game.ai_color
    s._refresh_ai_rogue_player_turn(game)
    assert s._get_ai_rogue_forbidden_points(game) == []

    game = make_game()
    game.ai_rogue_enabled = True
    game.ai_rogue_card = "sansan_trap"
    game.moves.append(("B", s.coord_to_gtp(2, 2, game.size)))
    game.place_stone(2, 2, "B")
    sent = []

    async def send_trap(payload):
        sent.append(copy.deepcopy(payload))

    old_sync = s._sync_board_to_katago
    try:
        async def fake_sync(_game):
            return None

        s._sync_board_to_katago = fake_sync
        await s._apply_ai_rogue_response_effects(game, send_trap, 2, 2, "B")
    finally:
        s._sync_board_to_katago = old_sync

    assert game.ai_rogue_sansan_trap_done is True
    assert sum(1 for x, y in s._adjacent8_points(2, 2, game.size) if game.board[y][x] == 2) >= 3
    assert any(msg.get("type") == "rogue_event" for msg in sent)


async def smoke_seal_fallback():
    game = make_game()
    seed_board(game)
    game.current_player = game.ai_color
    forbidden = [(0, 0), (0, 1), (1, 0), (1, 1)]
    queued = ["A9", "A8", "B9", "B8", "A9", "A8"]
    sent = []

    async def send(payload):
        sent.append(copy.deepcopy(payload))

    old_engine = s.engine
    try:
        s.engine = DummyEngine(queued)
        move = await s._ai_move_avoid_points(game, game.ai_color, 200, 1.0, forbidden)
    finally:
        s.engine = old_engine
    assert move.upper() not in {s.coord_to_gtp(x, y, game.size).upper() for x, y in forbidden}


async def smoke_ultimate_effects():
    for card_id in s.ULTIMATE_CARDS:
        game = make_game()
        game.ultimate = True
        seed_board(game)
        game.board[4][4] = 1
        game.moves = [("W", "C3"), ("W", "D4"), ("B", "E5")]
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        await s._apply_ultimate_effect(game, send, 4, 4, "B", card_id)
        assert isinstance(sent, list)


async def smoke_ultimate_turn_flow():
    async def run_case(card_id, queued_moves, random_values):
        game = make_game()
        game.ultimate = True
        game.current_player = game.ai_color
        game.ultimate_ai_card = card_id
        game.board[4][4] = 1
        game.moves.append(("B", s.coord_to_gtp(4, 4, game.size)))
        sent = []

        async def send(payload):
            sent.append(copy.deepcopy(payload))

        old_engine = s.engine
        old_sync = s._sync_board_to_katago
        old_random = s.random.random
        values = iter(random_values)
        try:
            s.engine = DummyEngine(queued_moves)

            async def noop_sync(_game):
                return None

            s._sync_board_to_katago = noop_sync
            s.random.random = lambda: next(values)
            await s._ultimate_ai_move(game, send)
        finally:
            s.engine = old_engine
            s._sync_board_to_katago = old_sync
            s.random.random = old_random
        states = [msg for msg in sent if msg.get("type") == "game_state"]
        assert states
        assert states[0]["current_player"] == game.ai_color
        assert states[-1]["current_player"] == game.player_color

    await run_case("chain", ["C3", "D3"], [0.0, 1.0])
    await run_case("double", ["E3", "F3"], [1.0, 1.0])


async def main():
    old_engine = s.engine
    try:
        s.engine = DummyEngine(["D4", "E5", "F6"])
        await smoke_activate_rogue_cards()
        await smoke_player_rogue_effects()
        await smoke_joseki_completion()
        await smoke_ai_rogue_cards()
        await smoke_slip_card()
        await smoke_new_rogue_cards()
        await smoke_sansan_trap()
        await smoke_seal_fallback()
        await smoke_ultimate_effects()
        await smoke_new_ultimate_cards()
        await smoke_ultimate_turn_flow()
        await smoke_quickthink_flow()
        await smoke_featured_pools()
        await smoke_suboptimal_extended()
        await smoke_fog_mask_refresh()
        await smoke_foolish_wisdom_rogue()
        await smoke_foolish_wisdom_ultimate()
        await smoke_two_player_rogue_shared_cards()
        await smoke_ai_rogue_support()
    finally:
        s.engine = old_engine
    print("card smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
