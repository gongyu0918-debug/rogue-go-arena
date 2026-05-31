from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.runtime.no_cache import apply_no_cache_headers_for_html


@dataclass(frozen=True)
class AppShellBinding:
    static_dir: Path
    engine_runtime: Any
    log_fn: Callable[[str], None]


AppShellBindingProvider = Callable[[], AppShellBinding]


def build_no_cache_html_middleware():
    async def no_cache_html(request, call_next):
        response = await call_next(request)
        return apply_no_cache_headers_for_html(response)

    return no_cache_html


def mount_static_assets(app: FastAPI, static_dir: Path) -> None:
    app.mount("/static", StaticFiles(directory=str(static_dir), check_dir=False), name="static")
    app.mount(
        "/assets",
        StaticFiles(directory=str(static_dir / "assets"), check_dir=False),
        name="assets",
    )


def configure_app_shell(app: FastAPI, binding_provider: AppShellBindingProvider) -> None:
    mount_static_assets(app, binding_provider().static_dir)

    @app.on_event("startup")
    async def startup():
        binding_provider().log_fn("[Server] KataGo will start on first game request")

    @app.on_event("shutdown")
    async def shutdown():
        binding_provider().engine_runtime.handle_app_shutdown()

    app.middleware("http")(build_no_cache_html_middleware())
