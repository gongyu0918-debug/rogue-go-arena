from __future__ import annotations

import asyncio

import server as s
from app.runtime.ai_style_adapters import (
    AiStyleMoveBinding,
    build_ai_style_move_deps,
    generate_ai_style_move,
)


class DummyGame:
    def __init__(self) -> None:
        self.ai_observer = False
        self.ai_style = "territory"
        self.ai_style_black = "influence"
        self.ai_style_white = "balanced"


async def fake_async(*_args, **_kwargs):
    return "async"


def fake_sync(*_args, **_kwargs):
    return "sync"


def smoke_binding_maps_every_field() -> None:
    binding = AiStyleMoveBinding(
        sync_board_to_katago=fake_async,
        choose_or_generate_style_move=fake_async,
        analyze_position=fake_async,
        choose_style_move=fake_sync,
        generate_move=fake_async,
        gtp_to_coord=fake_sync,
        play_chosen_move=fake_async,
    )

    deps = build_ai_style_move_deps(binding)

    assert deps.sync_board_to_katago is fake_async
    assert deps.choose_or_generate_style_move is fake_async
    assert deps.analyze_position is fake_async
    assert deps.choose_style_move is fake_sync
    assert deps.generate_move is fake_async
    assert deps.gtp_to_coord is fake_sync
    assert deps.play_chosen_move is fake_async


async def smoke_adapter_delegates_with_resolved_style() -> None:
    game = DummyGame()
    sent = []
    calls = []

    async def sync(game_arg):
        calls.append(("sync", game_arg is game))

    async def analyze(game_arg):
        calls.append(("analyze", game_arg is game))
        return {"moves": []}

    def choose_style(style, moves):
        calls.append(("choose_style", style, moves))
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
        sent.append(await kwargs["analyze_position"](game_arg))
        kwargs["choose_style_move"](kwargs["style"], [])
        await kwargs["generate_move"](kwargs["color"], kwargs["visits"], kwargs["time_limit"])
        kwargs["gtp_to_coord"]("D4", 9)
        await kwargs["play_chosen_move"]("play B D4")
        return "D4"

    result = await generate_ai_style_move(
        game,
        color="B",
        visits=123,
        time_limit=4.5,
        binding=AiStyleMoveBinding(
            sync_board_to_katago=sync,
            choose_or_generate_style_move=choose_or_generate,
            analyze_position=analyze,
            choose_style_move=choose_style,
            generate_move=generate,
            gtp_to_coord=gtp_to_coord,
            play_chosen_move=play,
        ),
    )

    assert result == "D4"
    assert sent == [{"moves": []}]
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
        ("analyze", True),
        ("choose_style", "territory", []),
        ("generate", "B", 123, 4.5),
        ("gtp", "D4", 9),
        ("play", "play B D4"),
    ]


async def smoke_server_binding_resolves_current_runtime() -> None:
    game = DummyGame()
    game.ai_observer = True
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

        binding = s._ai_style_move_binding()
        deps = s._ai_style_move_deps()
        assert binding.sync_board_to_katago is sync
        assert deps.choose_or_generate_style_move is choose_or_generate
        assert deps.analyze_position is analyze
        assert deps.choose_style_move is choose_style
        assert deps.generate_move is generate
        assert deps.gtp_to_coord is gtp_to_coord
        assert deps.play_chosen_move is play

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
    smoke_binding_maps_every_field()
    await smoke_adapter_delegates_with_resolved_style()
    await smoke_server_binding_resolves_current_runtime()
    print("ai style adapters smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
