from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI
from starlette.routing import Mount

import server as s
from app.runtime.app_shell import AppShellBinding, configure_app_shell


class FakeRuntime:
    def __init__(self) -> None:
        self.shutdown_calls = 0

    def handle_app_shutdown(self) -> None:
        self.shutdown_calls += 1


def mount_paths(app: FastAPI) -> dict[str, str]:
    return {
        route.path: str(route.app.directory)
        for route in app.routes
        if isinstance(route, Mount)
    }


async def smoke_app_shell_configures_static_mounts_and_lifecycle() -> None:
    app = FastAPI()
    logs = []
    first_runtime = FakeRuntime()
    second_runtime = FakeRuntime()

    with tempfile.TemporaryDirectory() as temp_dir:
        static_dir = Path(temp_dir)
        current = {"runtime": first_runtime}

        def binding_provider() -> AppShellBinding:
            return AppShellBinding(
                static_dir=static_dir,
                engine_runtime=current["runtime"],
                log_fn=logs.append,
            )

        configure_app_shell(app, binding_provider)

        assert mount_paths(app) == {
            "/static": str(static_dir),
            "/assets": str(static_dir / "assets"),
        }
        assert app.router.on_startup
        assert app.router.on_shutdown
        assert app.user_middleware

        await app.router.on_startup[-1]()
        current["runtime"] = second_runtime
        await app.router.on_shutdown[-1]()

    assert logs == ["[Server] KataGo will start on first game request"]
    assert first_runtime.shutdown_calls == 0
    assert second_runtime.shutdown_calls == 1


def smoke_server_app_shell_binding_maps_current_runtime_objects() -> None:
    binding = s._app_shell_binding()

    assert binding.static_dir == s.STATIC_DIR
    assert binding.engine_runtime is s.engine_runtime
    assert binding.log_fn is s.log
    assert mount_paths(s.app)["/static"] == str(s.STATIC_DIR)
    assert mount_paths(s.app)["/assets"] == str(s.STATIC_DIR / "assets")
    assert s.app.router.on_startup
    assert s.app.router.on_shutdown
    assert s.app.user_middleware


async def main() -> None:
    await smoke_app_shell_configures_static_mounts_and_lifecycle()
    smoke_server_app_shell_binding_maps_current_runtime_objects()
    print("app shell smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
