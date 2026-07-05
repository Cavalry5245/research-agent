from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import get_logger
from app.services.llm_client import (
    UserLLMConfig,
    reset_user_llm_override,
    set_user_llm_override,
)

logger = get_logger(__name__)


class ByokMiddleware(BaseHTTPMiddleware):
    """Per-request Bring-Your-Own-Key.

    Reads visitor-supplied LLM config from the ``X-LLM-Base-URL`` /
    ``X-LLM-API-Key`` / ``X-LLM-Model`` request headers and publishes it to
    LLMClient via a ContextVar, so every LLM call during the request uses the
    visitor's own key instead of the operator-configured one.

    Keys are never persisted server-side — they live only for the duration of
    the request. If no ``X-LLM-API-Key`` header is present, no override is set
    and LLMClient falls back to the operator's ``settings.llm_*``.
    """

    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get("X-LLM-API-Key")
        override = None
        if api_key:
            override = UserLLMConfig(
                base_url=request.headers.get("X-LLM-Base-URL", ""),
                api_key=api_key,
                model=request.headers.get("X-LLM-Model", ""),
            )
            # Don't log the key. Path only, for visibility into BYOK usage.
            logger.info("byok_override_applied path=%s", request.url.path)
        token = set_user_llm_override(override)
        try:
            return await call_next(request)
        finally:
            reset_user_llm_override(token)
