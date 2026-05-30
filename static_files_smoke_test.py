from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi.responses import FileResponse

import server as s
from app.runtime.static_files import serve_existing_file


def body_text(response) -> str:
    return response.body.decode("utf-8")


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
            assert Path((await s.root()).path) == root / "index.html"
            assert Path((await s.react_preview()).path) == root / "react" / "index.html"
            assert Path((await s.balance_lab()).path) == root / "card_editor.html"
            assert Path((await s.card_editor()).path) == root / "card_editor.html"

            (root / "index.html").unlink()
            (root / "react" / "index.html").unlink()
            (root / "card_editor.html").unlink()

            missing_root = await s.root()
            assert missing_root.status_code == 500
            assert body_text(missing_root) == "static/index.html not found"

            missing_preview = await s.react_preview()
            assert missing_preview.status_code == 404
            assert body_text(missing_preview) == (
                "static/react/index.html not found. Run npm run build --prefix frontend."
            )

            missing_editor = await s.balance_lab()
            assert missing_editor.status_code == 500
            assert body_text(missing_editor) == "static/card_editor.html not found"
        finally:
            s.STATIC_DIR = original_static_dir


async def main() -> None:
    smoke_static_file_helper_preserves_file_and_missing_responses()
    await smoke_server_static_routes_preserve_paths_and_missing_messages()
    print("static files smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
