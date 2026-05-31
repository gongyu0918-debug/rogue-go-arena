from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi.responses import FileResponse

import server as s
from app.runtime.static_files import serve_existing_file
from app.runtime.static_page_routes import StaticPageRoutesBinding, build_static_page_router
from app.runtime.static_pages import (
    serve_balance_lab_page,
    serve_card_editor_page,
    serve_react_preview_page,
    serve_root_page,
)


def body_text(response) -> str:
    return response.body.decode("utf-8")


def endpoint_for(routes, path: str, method: str = "GET"):
    for route in routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def smoke_static_file_helper_preserves_file_and_missing_responses() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        existing = root / "index.html"
        existing.write_text("<html>ok</html>", encoding="utf-8")

        file_response = serve_existing_file(
            existing,
            missing_message="missing",
            missing_status_code=503,
        )
        assert isinstance(file_response, FileResponse)
        assert Path(file_response.path) == existing
        assert file_response.status_code == 200

        missing_response = serve_existing_file(
            root / "missing.html",
            missing_message="custom missing",
            missing_status_code=404,
        )
        assert missing_response.status_code == 404
        assert missing_response.media_type == "text/plain; charset=utf-8"
        assert body_text(missing_response) == "custom missing"


def smoke_static_page_helpers_preserve_paths_and_missing_messages() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "react").mkdir()
        (root / "index.html").write_text("legacy", encoding="utf-8")
        (root / "react" / "index.html").write_text("react", encoding="utf-8")
        (root / "card_editor.html").write_text("editor", encoding="utf-8")

        assert Path(serve_root_page(root).path) == root / "index.html"
        assert Path(serve_react_preview_page(root).path) == root / "react" / "index.html"
        assert Path(serve_balance_lab_page(root).path) == root / "card_editor.html"
        assert Path(serve_card_editor_page(root).path) == root / "card_editor.html"

        (root / "index.html").unlink()
        (root / "react" / "index.html").unlink()
        (root / "card_editor.html").unlink()

        missing_root = serve_root_page(root)
        assert missing_root.status_code == 500
        assert body_text(missing_root) == "static/index.html not found"

        missing_preview = serve_react_preview_page(root)
        assert missing_preview.status_code == 404
        assert body_text(missing_preview) == (
            "static/react/index.html not found. Run npm run build --prefix frontend."
        )

        missing_editor = serve_balance_lab_page(root)
        assert missing_editor.status_code == 500
        assert body_text(missing_editor) == "static/card_editor.html not found"

        missing_card_editor = serve_card_editor_page(root)
        assert missing_card_editor.status_code == 500
        assert body_text(missing_card_editor) == "static/card_editor.html not found"


async def smoke_static_page_router_preserves_paths_and_late_binding() -> None:
    current = {}

    def binding_provider() -> StaticPageRoutesBinding:
        return StaticPageRoutesBinding(static_dir=current["static_dir"])

    router = build_static_page_router(binding_provider)
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "react").mkdir()
        (root / "index.html").write_text("legacy", encoding="utf-8")
        (root / "react" / "index.html").write_text("react", encoding="utf-8")
        (root / "card_editor.html").write_text("editor", encoding="utf-8")
        current["static_dir"] = root

        assert Path((await endpoint_for(router.routes, "/")()).path) == root / "index.html"
        assert Path((await endpoint_for(router.routes, "/react-preview")()).path) == (
            root / "react" / "index.html"
        )
        assert Path((await endpoint_for(router.routes, "/balance-lab")()).path) == (
            root / "card_editor.html"
        )
        assert Path((await endpoint_for(router.routes, "/card-editor")()).path) == (
            root / "card_editor.html"
        )

        (root / "index.html").unlink()
        (root / "react" / "index.html").unlink()
        (root / "card_editor.html").unlink()

        missing_root = await endpoint_for(router.routes, "/")()
        assert missing_root.status_code == 500
        assert body_text(missing_root) == "static/index.html not found"

        missing_preview = await endpoint_for(router.routes, "/react-preview")()
        assert missing_preview.status_code == 404
        assert body_text(missing_preview) == (
            "static/react/index.html not found. Run npm run build --prefix frontend."
        )

        missing_editor = await endpoint_for(router.routes, "/balance-lab")()
        assert missing_editor.status_code == 500
        assert body_text(missing_editor) == "static/card_editor.html not found"

        missing_card_editor = await endpoint_for(router.routes, "/card-editor")()
        assert missing_card_editor.status_code == 500
        assert body_text(missing_card_editor) == "static/card_editor.html not found"


async def smoke_server_static_routes_preserve_paths_and_missing_messages() -> None:
    original_static_dir = s.STATIC_DIR
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "react").mkdir()
        (root / "index.html").write_text("legacy", encoding="utf-8")
        (root / "react" / "index.html").write_text("react", encoding="utf-8")
        (root / "card_editor.html").write_text("editor", encoding="utf-8")

        try:
            s.STATIC_DIR = root
            assert s._static_page_routes_binding().static_dir == root
            assert Path((await endpoint_for(s.app.routes, "/")()).path) == root / "index.html"
            assert Path((await endpoint_for(s.app.routes, "/react-preview")()).path) == (
                root / "react" / "index.html"
            )
            assert Path((await endpoint_for(s.app.routes, "/balance-lab")()).path) == (
                root / "card_editor.html"
            )
            assert Path((await endpoint_for(s.app.routes, "/card-editor")()).path) == (
                root / "card_editor.html"
            )

            (root / "index.html").unlink()
            (root / "react" / "index.html").unlink()
            (root / "card_editor.html").unlink()

            missing_root = await endpoint_for(s.app.routes, "/")()
            assert missing_root.status_code == 500
            assert body_text(missing_root) == "static/index.html not found"

            missing_preview = await endpoint_for(s.app.routes, "/react-preview")()
            assert missing_preview.status_code == 404
            assert body_text(missing_preview) == (
                "static/react/index.html not found. Run npm run build --prefix frontend."
            )

            missing_editor = await endpoint_for(s.app.routes, "/balance-lab")()
            assert missing_editor.status_code == 500
            assert body_text(missing_editor) == "static/card_editor.html not found"

            missing_card_editor = await endpoint_for(s.app.routes, "/card-editor")()
            assert missing_card_editor.status_code == 500
            assert body_text(missing_card_editor) == "static/card_editor.html not found"
        finally:
            s.STATIC_DIR = original_static_dir


async def main() -> None:
    smoke_static_file_helper_preserves_file_and_missing_responses()
    smoke_static_page_helpers_preserve_paths_and_missing_messages()
    await smoke_static_page_router_preserves_paths_and_late_binding()
    await smoke_server_static_routes_preserve_paths_and_missing_messages()
    print("static files smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
