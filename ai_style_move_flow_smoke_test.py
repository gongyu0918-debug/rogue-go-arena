from __future__ import annotations

import asyncio

import server as s
from app.gameplay.ai_style_move_flow import (
    AiStyleMoveDeps,
    generate_ai_style_move_event,
    resolve_ai_style_for_color,
)


class DummyGame:
    def __init__(self) -> None:
        self.ai_style = "territory"
        self.ai_observer = False
        self.ai_style_black = "influence"
        self.ai_style_white = "balanced"


async def smoke_flow_selects_style_and_passes_runtime_deps() -> None:
    game = DummyGame()
    calls = []

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def analyze(*args, **kwargs):
        calls.append(("analyze", args, kwargs))
        return {"winrate": 0.5}

    def choose_style(*args, **kwargs):
        calls.append(("choose_style", args, kwargs))
        return "D4"

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "Q16"

    def gtp_to_coord(move, size):
        calls.append(("gtp", move, size))
        return (3, 3)

    async def play(command):
        calls.append(("play", command))
        return "= ok"

    async def choose_or_generate(game_arg, **kwargs):
        calls.append((
            "choose_or_generate",
            game_arg is game,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["style"],
            kwargs["analyze_position"] is analyze,
            kwargs["choose_style_move"] is choose_style,
            kwargs["generate_move"] is generate,
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["play_chosen_move"] is play,
        ))
        await kwargs["analyze_position"](game_arg)
        kwargs["choose_style_move"]("territory", [])
        await kwargs["generate_move"](kwargs["color"], kwargs["visits"], kwargs["time_limit"])
        kwargs["gtp_to_coord"]("D4", 9)
        await kwargs["play_chosen_move"]("play B D4")
        return "D4"

    deps = AiStyleMoveDeps(
        sync_board_to_katago=sync,
        choose_or_generate_style_move=choose_or_generate,
        analyze_position=analyze,
        choose_style_move=choose_style,
        generate_move=generate,
        gtp_to_coord=gtp_to_coord,
        play_chosen_move=play,
    )

    result = await generate_ai_style_move_event(
        game,
        color="B",
        visits=123,
        time_limit=4.5,
        deps=deps,
    )

    assert result == "D4"
    assert calls == [
        ("sync", True),
        (
            "choose_or_generate",
            True,
            "B",
            123,
            4.5,
            "territory",
            True,
            True,
            True,
            True,
            True,
        ),
        ("analyze", (game,), {}),
        ("choose_style", ("territory", []), {}),
        ("generate", "B", 123, 4.5),
        ("gtp", "D4", 9),
        ("play", "play B D4"),
    ]

    game.ai_observer = True
    assert resolve_ai_style_for_color(game, "B") == "influence"
    assert resolve_ai_style_for_color(game, "W") == "balanced"


async def smoke_server_style_wrapper_resolves_runtime_deps_late() -> None:
    game = DummyGame()
    calls = []

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def analyze(*_args, **_kwargs):
        calls.append(("analyze",))
        return {}

    def choose_style(*_args, **_kwargs):
        calls.append(("choose_style",))
        return "D4"

    async def generate(color, visits, time_limit):
        calls.append(("generate", color, visits, time_limit))
        return "Q16"

    def gtp_to_coord(_move, _size):
        calls.append(("gtp",))
        return (0, 0)

    async def play(command):
        calls.append(("play", command))
        return "= ok"

    async def choose_or_generate(game_arg, **kwargs):
        calls.append((
            "choose_or_generate",
            game_arg is game,
            kwargs["color"],
            kwargs["visits"],
            kwargs["time_limit"],
            kwargs["style"],
            kwargs["analyze_position"] is analyze,
            kwargs["choose_style_move"] is choose_style,
            kwargs["generate_move"] is generate,
            kwargs["gtp_to_coord"] is gtp_to_coord,
            kwargs["play_chosen_move"] is play,
        ))
        return "K10"

    originals = {
        "_sync_board_to_katago": s._sync_board_to_katago,
        "choose_or_generate_ai_style_move": s.choose_or_generate_ai_style_move,
        "_analyze_current_position": s._analyze_current_position,
        "choose_ai_style_move": s.choose_ai_style_move,
        "_ai_generate_move": s._ai_generate_move,
        "gtp_to_coord": s.gtp_to_coord,
        "_send_engine_command": s._send_engine_command,
    }
    try:
        s._sync_board_to_katago = sync
        s.choose_or_generate_ai_style_move = choose_or_generate
        s._analyze_current_position = analyze
        s.choose_ai_style_move = choose_style
        s._ai_generate_move = generate
        s.gtp_to_coord = gtp_to_coord
        s._send_engine_command = play

        game.ai_observer = True
        result = await s._generate_ai_style_move(game, "W", 77, 3.0)
    finally:
        for name, value in originals.items():
            setattr(s, name, value)

    assert result == "K10"
    assert calls == [
        ("sync", True),
        (
            "choose_or_generate",
            True,
            "W",
            77,
            3.0,
            "balanced",
            True,
            True,
            True,
            True,
            True,
        ),
    ]


async def main() -> None:
    await smoke_flow_selects_style_and_passes_runtime_deps()
    await smoke_server_style_wrapper_resolves_runtime_deps_late()
    print("ai style move flow smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
