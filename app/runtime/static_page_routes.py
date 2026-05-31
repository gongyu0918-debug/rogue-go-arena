from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter

from app.runtime.static_pages import (
    serve_balance_lab_page,
    serve_card_editor_page,
    serve_react_preview_page,
    serve_root_page,
)


@dataclass(frozen=True)
class StaticPageRoutesBinding:
    static_dir: Path


StaticPageRoutesBindingProvider = Callable[[], StaticPageRoutesBinding]


def build_static_page_router(binding_provider: StaticPageRoutesBindingProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root():
        return serve_root_page(binding_provider().static_dir)

    @router.get("/react-preview")
    async def react_preview():
        return serve_react_preview_page(binding_provider().static_dir)

    @router.get("/balance-lab")
    async def balance_lab():
        return serve_balance_lab_page(binding_provider().static_dir)

    @router.get("/card-editor")
    async def card_editor():
        return serve_card_editor_page(binding_provider().static_dir)

    return router
