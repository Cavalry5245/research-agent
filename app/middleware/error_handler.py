from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.logging_config import get_logger

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = _request_id(request)
    content = {
        "error": "http_error",
        "message": str(exc.detail),
        "request_id": request_id,
        "status_code": exc.status_code,
    }
    headers = dict(exc.headers or {})
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        extra={"ra_request_id": request_id, "ra_path": request.url.path},
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Internal server error",
            "request_id": request_id,
            "status_code": 500,
        },
        headers=headers,
    )
