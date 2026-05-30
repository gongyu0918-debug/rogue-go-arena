from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class JsonBodyRead:
    body: Any = None
    error_response: JSONResponse | None = None

    @property
    def ok(self) -> bool:
        return self.error_response is None


async def read_json_body(
    request: Any,
    *,
    error_message: str = "request body must be JSON",
) -> JsonBodyRead:
    try:
        return JsonBodyRead(body=await request.json())
    except Exception:
        return JsonBodyRead(
            error_response=JSONResponse(
                {"ok": False, "errors": [error_message]},
                status_code=400,
            )
        )
