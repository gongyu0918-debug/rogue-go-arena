from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio
from types import SimpleNamespace

import server as s
from app.gameplay.ultimate_ai_flow import UltimateAiMoveChoice
from app.runtime.ultimate_ai_adapters import (
    UltimateAiBonusTurnBinding,
    UltimateAiMoveSelection,
    UltimateAiMoveSelectionBinding,
    UltimateAiTurnFinishBinding,
    finish_selected_ultimate_ai_move,
    run_ultimate_ai_bonus_turn_adapter,
    select_ultimate_ai_move,
)
from app.runtime.ultimate_ai_runtime import (
    UltimateAiBonusFns,
    UltimateAiDependencies,
    UltimateAiFinishFns,
    UltimateAiSelectionMoveFns,
    UltimateAiSelectionRuntimeFns,
    UltimateAiTuning,
    build_ultimate_ai_bonus_turn_binding,
    build_ultimate_ai_move_selection_binding,
    build_ultimate_ai_turn_finish_binding,
)


class FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeEngine:
    def __init__(self) -> None:
        self.command_lock = FakeLock()
        self.commands = []

    def _send_command_locked(self, command: str, timeout=None) -> str:
        self.commands.append((command, timeout))
        if command.startswith("genmove"):
            return "= D4"
        return "="


class DummyGame:
    def __init__(self) -> None:
        self.game_over = False
        self.ultimate_extra_turn = True
        self.level = "5k"
        self.size = 9
        self.board = [[0 for _ in range(9)] for _ in range(9)]
        self.ultimate_move_count = 0

    def is_ko(self, *_args):
        return False

    def to_state(self):
        return {"state": "ok"}


async def fake_async(*_args, **_kwargs):
    return None


def smoke_ultimate_ai_runtime_builders_group_dependencies() -> None:
    engine = FakeEngine()

    async def selection_sync_board(*_args, **_kwargs):
        return None

    async def finish_sync_board(*_args, **_kwargs):
        return None

    def plan_search(*_args, **_kwargs):
        return SimpleNamespace(color="W")

    async def run_executor(*_args, **_kwargs):
        return "D4"

    def get_visits(*_args, **_kwargs):
        return 500

    def log_fn(_message: str):
        return None

    async def no_resign(*_args, **_kwargs):
        return "D4"

    async def pick_ranked(*_args, **_kwargs):
        return "Q16"

    async def pick_fallback(*_args, **_kwargs):
        return "E5"

    async def retry_ko(*_args, **_kwargs):
        return "C3"

    def suspicious(*_args, **_kwargs):
        return False

    def resolve_occupied(*_args, **_kwargs):
        return "F6", (5, 5)

    def gtp_to_coord(*_args, **_kwargs):
        return (3, 3)

    def coord_to_gtp(*_args, **_kwargs):
        return "D4"

    def apply_result(*_args, **_kwargs):
        return 2

    def record_turn(*_args, **_kwargs):
        return None

    async def check_capture(*_args, **_kwargs):
        return None

    async def post_effects(*_args, **_kwargs):
        return False

    def count_stones(*_args, **_kwargs):
        return 10

    async def apply_effect(*_args, **_kwargs):
        return True

    async def resolve_pending(*_args, **_kwargs):
        return False

    def choose_bonus(*_args, **_kwargs):
        return None

    async def run_bonus(*_args, **_kwargs):
        return False

    def finish_normal(*_args, **_kwargs):
        return None

    def prepare_modifiers(*_args, **_kwargs):
        return None

    async def force_score(*_args, **_kwargs):
        return None

    def start_bonus(*_args, **_kwargs):
        return None

    async def run_next(*_args, **_kwargs):
        return None

    def chain_random() -> float:
        return 0.2

    dependencies = UltimateAiDependencies(
        selection_runtime=UltimateAiSelectionRuntimeFns(
            engine_ready=lambda: True,
            sync_board_to_katago=selection_sync_board,
            plan_search=plan_search,
            engine=engine,
            run_in_executor=run_executor,
            get_game_visits=get_visits,
            log_fn=log_fn,
        ),
        selection_moves=UltimateAiSelectionMoveFns(
            no_resign_move=no_resign,
            pick_ranked_legal_move=pick_ranked,
            pick_nonpass_fallback_move=pick_fallback,
            retry_avoiding_ko=retry_ko,
            is_suspicious_ai_pass=suspicious,
            resolve_occupied_ai_move=resolve_occupied,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=coord_to_gtp,
        ),
        finish=UltimateAiFinishFns(
            apply_ai_move_result=apply_result,
            record_ultimate_turn=record_turn,
            check_capture_foul=check_capture,
            post_move_effects=post_effects,
            count_stones=count_stones,
            apply_ultimate_effect=apply_effect,
            resolve_pending_ultimate_shadow_links=resolve_pending,
            sync_board_to_katago=finish_sync_board,
            choose_bonus_turn=choose_bonus,
            run_bonus_turn=run_bonus,
            finish_normal_turn=finish_normal,
            prepare_player_turn_modifiers=prepare_modifiers,
            force_score=force_score,
        ),
        bonus=UltimateAiBonusFns(
            start_bonus_turn=start_bonus,
            run_next_ai_move=run_next,
        ),
        tuning=UltimateAiTuning(
            chain_chance=0.35,
            chain_random=chain_random,
        ),
    )

    selection = build_ultimate_ai_move_selection_binding(dependencies)
    finish = build_ultimate_ai_turn_finish_binding(dependencies)
    bonus = build_ultimate_ai_bonus_turn_binding(dependencies)

    assert selection.engine_ready() is True
    assert selection.sync_board_to_katago is selection_sync_board
    assert selection.plan_search is plan_search
    assert selection.engine is engine
    assert selection.run_in_executor is run_executor
    assert selection.get_game_visits is get_visits
    assert selection.no_resign_move is no_resign
    assert selection.pick_ranked_legal_move is pick_ranked
    assert selection.pick_nonpass_fallback_move is pick_fallback
    assert selection.retry_avoiding_ko is retry_ko
    assert selection.is_suspicious_ai_pass is suspicious
    assert selection.resolve_occupied_ai_move is resolve_occupied
    assert selection.gtp_to_coord is gtp_to_coord
    assert selection.coord_to_gtp is coord_to_gtp
    assert selection.log_fn is log_fn
    assert finish.chain_chance == 0.35
    assert finish.chain_random is chain_random
    assert finish.apply_ai_move_result is apply_result
    assert finish.record_ultimate_turn is record_turn
    assert finish.check_capture_foul is check_capture
    assert finish.post_move_effects is post_effects
    assert finish.count_stones is count_stones
    assert finish.apply_ultimate_effect is apply_effect
    assert finish.resolve_pending_ultimate_shadow_links is resolve_pending
    assert finish.sync_board_to_katago is finish_sync_board
    assert finish.choose_bonus_turn is choose_bonus
    assert finish.run_bonus_turn is run_bonus
    assert finish.finish_normal_turn is finish_normal
    assert finish.prepare_player_turn_modifiers is prepare_modifiers
    assert finish.force_score is force_score
    assert bonus.start_bonus_turn is start_bonus
    assert bonus.run_next_ai_move is run_next


async def smoke_selection_guard_skips_before_sync() -> None:
    calls = []
    game = DummyGame()

    async def sync(_game):
        calls.append("sync")

    binding = UltimateAiMoveSelectionBinding(
        engine_ready=lambda: False,
        sync_board_to_katago=sync,
        plan_search=lambda _game: calls.append("plan"),
        engine=FakeEngine(),
        run_in_executor=lambda func, *args: func(*args),
        get_game_visits=lambda *_args, **_kwargs: 800,
        no_resign_move=lambda *_args: None,
        pick_ranked_legal_move=lambda *_args, **_kwargs: None,
        pick_nonpass_fallback_move=lambda *_args: None,
        retry_avoiding_ko=lambda *_args: None,
        is_suspicious_ai_pass=lambda *_args: False,
        resolve_occupied_ai_move=lambda _game, _color, move, coord, **_kwargs: (move, coord),
        gtp_to_coord=lambda _move, _size: None,
        coord_to_gtp=lambda *_args: "A1",
        log_fn=lambda _message: None,
    )

    assert await select_ultimate_ai_move(game, binding) is None
    assert calls == []
    assert game.ultimate_extra_turn is True

    game.game_over = True
    assert await select_ultimate_ai_move(
        game,
        UltimateAiMoveSelectionBinding(**{**binding.__dict__, "engine_ready": lambda: True}),
    ) is None
    assert calls == []


async def smoke_selection_binds_engine_generation_and_returns_choice() -> None:
    game = DummyGame()
    engine = FakeEngine()
    calls = []
    search_plan = SimpleNamespace(color="W", ai_card="meteor", forbidden=set(), visits=321)

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def run_in_executor(func, *args):
        calls.append(("executor", func.__name__, args))
        return func(*args)

    def plan_search(game_arg):
        calls.append(("plan", game_arg is game))
        return search_plan

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (3, 3)

    def resolve(game_arg, color, move, coord, **kwargs):
        calls.append(("resolve", game_arg is game, color, move, coord, kwargs["coord_to_gtp"] is fake_coord_to_gtp))
        return move, coord

    def fake_coord_to_gtp(*_args):
        return "D4"

    selection = await select_ultimate_ai_move(
        game,
        UltimateAiMoveSelectionBinding(
            engine_ready=lambda: True,
            sync_board_to_katago=sync,
            plan_search=plan_search,
            engine=engine,
            run_in_executor=run_in_executor,
            get_game_visits=lambda level, move_count, *, mode: calls.append(("visits", level, move_count, mode)) or 999,
            no_resign_move=lambda *_args: None,
            pick_ranked_legal_move=lambda *_args, **_kwargs: None,
            pick_nonpass_fallback_move=lambda *_args: None,
            retry_avoiding_ko=lambda *_args: None,
            is_suspicious_ai_pass=lambda *_args: False,
            resolve_occupied_ai_move=resolve,
            gtp_to_coord=gtp_to_coord,
            coord_to_gtp=fake_coord_to_gtp,
            log_fn=lambda _message: None,
        ),
    )

    assert selection is not None
    assert selection.search_plan is search_plan
    assert selection.choice == UltimateAiMoveChoice(gtp_move="D4", coord=(3, 3))
    assert game.ultimate_extra_turn is False
    assert engine.commands == [
        ("kata-set-param maxVisits 321", None),
        ("genmove W", 30),
        ("kata-set-param maxVisits 999", None),
    ]
    assert calls == [
        ("sync", True),
        ("plan", True),
        ("executor", "generate_locked", ()),
        ("visits", "5k", 0, "ultimate"),
        ("gtp", "D4", 9),
        ("resolve", True, "W", "D4", (3, 3), True),
    ]


async def smoke_finish_adapter_maps_selection_and_binding() -> None:
    game = DummyGame()
    sent = []
    calls = []
    selection = UltimateAiMoveSelection(
        search_plan=SimpleNamespace(color="W", ai_card="meteor"),
        choice=UltimateAiMoveChoice(gtp_move="D4", coord=(3, 3)),
    )

    async def send(payload):
        sent.append(payload)
        calls.append(("send", payload["type"]))

    def apply_result(game_arg, color, move, coord, **kwargs):
        calls.append(("apply", game_arg is game, color, move, coord, kwargs["count_turn"]))
        return 2

    async def capture_foul(game_arg, send_fn, color, captured, *, ultimate):
        calls.append(("capture", game_arg is game, send_fn is send, color, captured, ultimate))

    async def post(game_arg, send_fn, **kwargs):
        calls.append(("post", game_arg is game, send_fn is send, kwargs["ai_card"], kwargs["gtp_move"]))
        return False

    def choose_bonus(game_arg, **kwargs):
        calls.append(("bonus", game_arg is game, kwargs["chain_chance"]))
        return None

    def finish_normal(game_arg, **kwargs):
        calls.append(("normal", game_arg is game, kwargs["prepare_player_turn_modifiers_fn"] is prepare))

    def prepare(_game):
        calls.append("prepare")

    recursed = await finish_selected_ultimate_ai_move(
        game,
        send,
        selection,
        allow_double_bonus=False,
        binding=UltimateAiTurnFinishBinding(
            chain_chance=0.25,
            chain_random=lambda: 0.5,
            apply_ai_move_result=apply_result,
            record_ultimate_turn=lambda _game: calls.append("record"),
            check_capture_foul=capture_foul,
            post_move_effects=post,
            count_stones=lambda *_args: 0,
            apply_ultimate_effect=lambda *_args: None,
            resolve_pending_ultimate_shadow_links=lambda *_args: None,
            sync_board_to_katago=lambda *_args: None,
            choose_bonus_turn=choose_bonus,
            run_bonus_turn=lambda *_args: None,
            finish_normal_turn=finish_normal,
            prepare_player_turn_modifiers=prepare,
            force_score=lambda *_args: None,
        ),
    )

    assert recursed is False
    assert calls == [
        ("apply", True, "W", "D4", (3, 3), False),
        ("capture", True, True, "W", 2, True),
        ("send", "ai_move"),
        ("post", True, True, "meteor", "D4"),
        ("bonus", True, 0.25),
        ("normal", True, True),
        ("send", "game_state"),
    ]
    assert sent[0] == {"type": "ai_move", "gtp": "D4", "color": "W", "x": 3, "y": 3}


async def smoke_bonus_adapter_delegates_runtime_edges() -> None:
    game = DummyGame()
    bonus = SimpleNamespace(message="bonus", next_allow_double_bonus=False)
    calls = []
    sent = []

    async def send(payload):
        sent.append(payload)

    def start(game_arg, color):
        calls.append(("start", game_arg is game, color))

    async def next_move(game_arg, send_fn, allow_double):
        calls.append(("next", game_arg is game, send_fn is send, allow_double))

    recursed = await run_ultimate_ai_bonus_turn_adapter(
        game,
        send,
        "B",
        bonus,
        UltimateAiBonusTurnBinding(
            start_bonus_turn=start,
            run_next_ai_move=next_move,
        ),
    )

    assert recursed is True
    assert calls == [("start", True, "B"), ("next", True, True, False)]
    assert sent[0] == {"type": "rogue_event", "msg": "bonus"}
    assert sent[1]["type"] == "game_state"


async def smoke_server_ultimate_ai_wrapper_uses_current_adapters() -> None:
    game = DummyGame()
    sent = []
    calls = []
    selection = UltimateAiMoveSelection(
        search_plan=SimpleNamespace(color="W", ai_card="blackout"),
        choice=UltimateAiMoveChoice(gtp_move="Q16", coord=(6, 2)),
    )

    async def send(payload):
        sent.append(payload)

    async def select(game_arg, binding):
        calls.append((
            "select",
            game_arg is game,
            binding.engine_ready() is True,
            binding.engine is s.engine,
            binding.get_game_visits is s.get_game_visits,
        ))
        return selection

    async def finish(game_arg, send_fn, selection_arg, *, allow_double_bonus, binding):
        calls.append((
            "finish",
            game_arg is game,
            send_fn is send,
            selection_arg is selection,
            allow_double_bonus,
            binding.chain_chance == s.ULTIMATE_CHAIN_EXTRA_TURN_CHANCE,
            binding.apply_ai_move_result is s.apply_ultimate_ai_move_result_state,
            binding.run_bonus_turn is s._run_ultimate_ai_bonus_turn,
        ))
        await send_fn({"type": "done"})
        return False

    def territory(game_arg, color_value):
        calls.append(("territory", game_arg is game, color_value))
        return {(1, 1)}

    def get_visits(*_args, **_kwargs):
        return 777

    def plan_search(game_arg, **kwargs):
        calls.append((
            "plan",
            game_arg is game,
            kwargs["get_territory_forbidden"] is territory,
            kwargs["get_game_visits"] is get_visits,
        ))
        kwargs["get_territory_forbidden"](game_arg, 2)
        return SimpleNamespace(color="B", visits=777)

    def start_bonus(game_arg, color):
        calls.append(("bonus_start", game_arg is game, color))

    async def ultimate_move(game_arg, send_fn, *, allow_double_bonus):
        calls.append(("next_ultimate", game_arg is game, send_fn is send, allow_double_bonus))

    originals = {
        "select_ultimate_ai_move": s.select_ultimate_ai_move,
        "finish_selected_ultimate_ai_move": s.finish_selected_ultimate_ai_move,
        "plan_ultimate_ai_search": s.plan_ultimate_ai_search,
        "_ultimate_get_territory_forbidden": s._ultimate_get_territory_forbidden,
        "get_game_visits": s.get_game_visits,
        "start_ultimate_ai_bonus_turn_state": s.start_ultimate_ai_bonus_turn_state,
        "_ultimate_ai_move": s._ultimate_ai_move,
        "engine_ready": s.engine.ready,
    }
    try:
        s.select_ultimate_ai_move = select
        s.finish_selected_ultimate_ai_move = finish
        s.plan_ultimate_ai_search = plan_search
        s._ultimate_get_territory_forbidden = territory
        s.get_game_visits = get_visits
        s.start_ultimate_ai_bonus_turn_state = start_bonus
        s._ultimate_ai_move = ultimate_move
        s.engine.ready = True

        selection_binding = s._ultimate_ai_move_selection_binding()
        finish_binding = s._ultimate_ai_turn_finish_binding()
        bonus_binding = s._ultimate_ai_bonus_turn_binding()
        assert selection_binding.engine_ready() is True
        assert selection_binding.engine is s.engine
        assert selection_binding.get_game_visits is get_visits
        assert selection_binding.plan_search(game).visits == 777
        assert finish_binding.run_bonus_turn is s._run_ultimate_ai_bonus_turn
        assert bonus_binding.start_bonus_turn is start_bonus
        await bonus_binding.run_next_ai_move(game, send, False)

        await originals["_ultimate_ai_move"](game, send, allow_double_bonus=False)
    finally:
        s.select_ultimate_ai_move = originals["select_ultimate_ai_move"]
        s.finish_selected_ultimate_ai_move = originals["finish_selected_ultimate_ai_move"]
        s.plan_ultimate_ai_search = originals["plan_ultimate_ai_search"]
        s._ultimate_get_territory_forbidden = originals["_ultimate_get_territory_forbidden"]
        s.get_game_visits = originals["get_game_visits"]
        s.start_ultimate_ai_bonus_turn_state = originals["start_ultimate_ai_bonus_turn_state"]
        s._ultimate_ai_move = originals["_ultimate_ai_move"]
        s.engine.ready = originals["engine_ready"]

    assert calls == [
        ("plan", True, True, True),
        ("territory", True, 2),
        ("next_ultimate", True, True, False),
        ("select", True, True, True, True),
        ("finish", True, True, True, False, True, True, True),
    ]
    assert sent == [{"type": "done"}]


async def main() -> None:
    smoke_ultimate_ai_runtime_builders_group_dependencies()
    await smoke_selection_guard_skips_before_sync()
    await smoke_selection_binds_engine_generation_and_returns_choice()
    await smoke_finish_adapter_maps_selection_and_binding()
    await smoke_bonus_adapter_delegates_runtime_edges()
    await smoke_server_ultimate_ai_wrapper_uses_current_adapters()
    print("ultimate ai adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
