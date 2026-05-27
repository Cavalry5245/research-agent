from __future__ import annotations

import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import get_logger

logger = get_logger(__name__)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("X-Request-ID")
        request_id = (
            incoming
            if incoming and _REQUEST_ID_PATTERN.fullmatch(incoming)
            else str(uuid.uuid4())
        )
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "api_request",
            extra={
                "ra_request_id": request_id,
                "ra_method": request.method,
                "ra_path": request.url.path,
                "ra_status_code": response.status_code,
                "ra_duration_ms": round(duration_ms, 2),
            },
        )
        return response
