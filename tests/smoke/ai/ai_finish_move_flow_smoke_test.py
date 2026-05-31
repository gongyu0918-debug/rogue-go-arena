from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import asyncio

import server as s
from app.gameplay.ai_finish_move_flow import AiFinishMoveDeps, finish_ai_move_event


async def smoke_finish_flow_injects_runtime_deps() -> None:
    game = object()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (1, 2)

    async def no_resign(game_arg, color):
        calls.append(("no_resign", game_arg is game, color))
        return "D4"

    async def retry_ko(game_arg, color):
        calls.append(("retry", game_arg is game, color))
        return "E5"

    async def capture_foul(game_arg, send_fn, color, captured, **kwargs):
        calls.append(("capture", game_arg is game, send_fn is send, color, captured, kwargs))

    def prepare(game_arg):
        calls.append(("prepare", game_arg is game))

    async def run_engine(command):
        calls.append(("engine", command))
        return "= ok"

    async def coach(game_arg, send_fn):
        calls.append(("coach", game_arg is game, send_fn is send))

    async def finalize(game_arg, send_fn, **kwargs):
        calls.append((
            "finalize",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["no_resign_move"] is no_resign,
            kwargs["retry_avoiding_ko"] is retry_ko,
            kwargs["check_capture_foul"] is capture_foul,
            kwargs["prepare_player_turn_modifiers"] is prepare,
            kwargs["run_engine_command"] is run_engine,
            kwargs["run_coach_turn_if_needed"] is coach,
        ))
        kwargs["gtp_to_coord"]("D4", 9)
        await kwargs["no_resign_move"](game_arg, kwargs["color"])
        await kwargs["retry_avoiding_ko"](game_arg, kwargs["color"])
        await kwargs["check_capture_foul"](game_arg, send_fn, kwargs["color"], 0, ultimate=False)
        kwargs["prepare_player_turn_modifiers"](game_arg)
        await kwargs["run_engine_command"]("play W D4")
        await kwargs["run_coach_turn_if_needed"](game_arg, send_fn)
        await send_fn({"type": "ai_move", "gtp": kwargs["gtp_move"]})

    deps = AiFinishMoveDeps(
        finalize_ai_move=finalize,
        gtp_to_coord=gtp_to_coord,
        no_resign_move=no_resign,
        retry_avoiding_ko=retry_ko,
        check_capture_foul=capture_foul,
        prepare_player_turn_modifiers=prepare,
        run_engine_command=run_engine,
        run_coach_turn_if_needed=coach,
    )

    await finish_ai_move_event(
        game,
        send,
        color="W",
        card="mirror",
        gtp_move="D4",
        rogue_msg="forced",
        deps=deps,
    )

    assert calls == [
        (
            "finalize",
            True,
            True,
            "W",
            "mirror",
            "D4",
            "forced",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ),
        ("gtp", "D4", 9),
        ("no_resign", True, "W"),
        ("retry", True, "W"),
        ("capture", True, True, "W", 0, {"ultimate": False}),
        ("prepare", True),
        ("engine", "play W D4"),
        ("coach", True, True),
    ]
    assert sent == [{"type": "ai_move", "gtp": "D4"}]


async def smoke_server_finish_wrapper_resolves_runtime_deps_late() -> None:
    game = object()
    sent = []
    calls = []

    async def send(payload):
        sent.append(payload)

    def gtp_to_coord(_move, _size):
        calls.append(("gtp",))
        return (0, 0)

    async def no_resign(_game, _color):
        calls.append(("no_resign",))
        return "D4"

    async def retry_ko(_game, _color):
        calls.append(("retry",))
        return "E5"

    async def capture_foul(_game, _send, _color, _captured, **_kwargs):
        calls.append(("capture",))

    def prepare(_game):
        calls.append(("prepare",))

    async def run_engine(_command):
        calls.append(("engine",))
        return "= ok"

    async def coach(_game, _send):
        calls.append(("coach",))

    async def finalize(game_arg, send_fn, **kwargs):
        calls.append((
            "finalize",
            game_arg is game,
            send_fn is send,
            kwargs["color"],
            kwargs["card"],
            kwargs["gtp_move"],
            kwargs["rogue_msg"],
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["no_resign_move"] is no_resign,
            kwargs["retry_avoiding_ko"] is retry_ko,
            kwargs["check_capture_foul"] is capture_foul,
            kwargs["prepare_player_turn_modifiers"] is prepare,
            kwargs["run_engine_command"] is run_engine,
            kwargs["run_coach_turn_if_needed"] is coach,
        ))

    originals = {
        "finalize_ai_move": s.finalize_ai_move,
        "gtp_to_coord": s.gtp_to_coord,
        "_ai_move_no_resign": s._ai_move_no_resign,
        "_ai_retry_avoiding_ko": s._ai_retry_avoiding_ko,
        "_check_capture_foul": s._check_capture_foul,
        "_prepare_player_turn_modifiers": s._prepare_player_turn_modifiers,
        "_send_engine_command": s._send_engine_command,
        "_run_coach_turn_if_needed": s._run_coach_turn_if_needed,
    }
    try:
        s.finalize_ai_move = finalize
        s.gtp_to_coord = gtp_to_coord
        s._ai_move_no_resign = no_resign
        s._ai_retry_avoiding_ko = retry_ko
        s._check_capture_foul = capture_foul
        s._prepare_player_turn_modifiers = prepare
        s._send_engine_command = run_engine
        s._run_coach_turn_if_needed = coach

        await s._finish_ai_move(
            game,
            send,
            "B",
            "dice",
            "pass",
            "forced pass",
        )
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert calls == [
        (
            "finalize",
            True,
            True,
            "B",
            "dice",
            "pass",
            "forced pass",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        )
    ]
    assert sent == []


async def main() -> None:
    await smoke_finish_flow_injects_runtime_deps()
    await smoke_server_finish_wrapper_resolves_runtime_deps_late()
    print("ai finish move flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
