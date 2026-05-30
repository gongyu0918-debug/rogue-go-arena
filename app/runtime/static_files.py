from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse, Response


def serve_existing_file(
    path: Path,
    *,
    missing_message: str,
    missing_status_code: int = 500,
) -> FileResponse | Response:
    if not path.exists():
        return Response(
            content=missing_message,
            media_type="text/plain; charset=utf-8",
            status_code=missing_status_code,
        )
    return FileResponse(str(path))
