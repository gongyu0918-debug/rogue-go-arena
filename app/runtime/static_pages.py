from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse, Response

from app.runtime.static_files import serve_existing_file


def serve_root_page(static_dir: Path) -> FileResponse | Response:
    return serve_existing_file(
        static_dir / "index.html",
        missing_message="static/index.html not found",
        missing_status_code=500,
    )


def serve_react_preview_page(static_dir: Path) -> FileResponse | Response:
    return serve_existing_file(
        static_dir / "react" / "index.html",
        missing_message="static/react/index.html not found. Run npm run build --prefix frontend.",
        missing_status_code=404,
    )


def serve_balance_lab_page(static_dir: Path) -> FileResponse | Response:
    return serve_existing_file(
        static_dir / "card_editor.html",
        missing_message="static/card_editor.html not found",
        missing_status_code=500,
    )


def serve_card_editor_page(static_dir: Path) -> FileResponse | Response:
    return serve_balance_lab_page(static_dir)
