from __future__ import annotations

import asyncio

from fastapi.responses import JSONResponse, Response

from app.runtime.app_shell import build_no_cache_html_middleware
from app.runtime.no_cache import apply_no_cache_headers_for_html


def smoke_no_cache_helper_only_marks_html_responses() -> None:
    html = Response(content="<html></html>", media_type="text/html")
    returned = apply_no_cache_headers_for_html(html)

    assert returned is html
    assert html.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert html.headers["Pragma"] == "no-cache"
    assert html.headers["Expires"] == "0"

    json_response = JSONResponse({"ok": True})
    apply_no_cache_headers_for_html(json_response)

    assert "Cache-Control" not in json_response.headers
    assert "Pragma" not in json_response.headers
    assert "Expires" not in json_response.headers


async def smoke_no_cache_middleware_uses_shared_helper() -> None:
    calls = []

    async def html_call_next(request):
        calls.append(("html", request))
        return Response(content="<html></html>", media_type="text/html")

    async def json_call_next(request):
        calls.append(("json", request))
        return JSONResponse({"ok": True})

    middleware = build_no_cache_html_middleware()
    html_response = await middleware("request-html", html_call_next)
    json_response = await middleware("request-json", json_call_next)

    assert calls == [("html", "request-html"), ("json", "request-json")]
    assert html_response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
    assert "Cache-Control" not in json_response.headers


async def main() -> None:
    smoke_no_cache_helper_only_marks_html_responses()
    await smoke_no_cache_middleware_uses_shared_helper()
    print("no cache smoke test: OK")


if __name__ == "__main__":
    asyncio.run(main())
