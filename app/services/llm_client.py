from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional

import httpx
from openai import APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (InternalServerError, RateLimitError, APITimeoutError)
MAX_RETRIES = 5
BACKOFF_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 150.0
_HTTPX_TIMEOUT = httpx.Timeout(connect=15.0, read=180.0, write=60.0, pool=10.0)


# --- Per-request BYOK override -------------------------------------------------
# Bring-Your-Own-Key: a visitor supplies their own LLM base_url / api_key / model
# via X-LLM-* headers (see app.middleware.byok.ByokMiddleware). The middleware
# stashes the override in this ContextVar for the duration of the request, and
# every LLMClient() constructed during that request picks it up — without
# threading a parameter through ~20 call sites.
#
# Keys never touch server-side storage: they flow browser (localStorage) ->
# request header -> ContextVar -> OpenAI client, and are discarded with the
# request. Falls back to settings (operator-configured) when no override is set.
_user_llm_override: ContextVar[Optional["UserLLMConfig"]] = ContextVar(
    "user_llm_override", default=None
)


@dataclass
class UserLLMConfig:
    base_url: str
    api_key: str
    model: str


def set_user_llm_override(cfg: Optional[UserLLMConfig]) -> Token:
    return _user_llm_override.set(cfg)


def reset_user_llm_override(token: Token) -> None:
    _user_llm_override.reset(token)


def get_user_llm_override() -> Optional[UserLLMConfig]:
    return _user_llm_override.get()


# ---------------------------------------------------------------------------


class LLMClient:
    def __init__(self, user_override: Optional[UserLLMConfig] = None):
        # Explicit parameter wins over the request-scoped contextvar, which in
        # turn wins over the operator-configured settings.
        override = user_override or _user_llm_override.get()
        if override and override.api_key:
            self.base_url = override.base_url or settings.llm_base_url
            self.api_key = override.api_key
            self.model = override.model or settings.llm_model
            self._source = "byok"
        else:
            if not settings.llm_api_key:
                raise ValueError(
                    "LLM API Key 未配置。请在 .env 中设置 LLM_API_KEY，"
                    "或在 Settings 页面填入你自己的 Key（BYOK）。"
                )
            self.base_url = settings.llm_base_url
            self.api_key = settings.llm_api_key
            self.model = settings.llm_model
            self._source = "env"
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=_HTTPX_TIMEOUT,
            max_retries=0,
        )

    def generate_text(self, prompt: str) -> str:
        logger.info(
            "LLM call: source=%s, model=%s, prompt_chars=%d",
            self._source,
            self.model,
            len(prompt),
        )

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                content = response.choices[0].message.content
                if content is None:
                    raise RuntimeError("LLM 返回了空内容")
                logger.info("LLM response: chars=%d", len(content))
                return content
            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt >= MAX_RETRIES:
                    break
                sleep_seconds = BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "LLM transient error on attempt %d/%d: %s. Retry in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    e,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
            except Exception as e:
                last_error = e
                if attempt >= MAX_RETRIES:
                    break
                sleep_seconds = BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "LLM unexpected error on attempt %d/%d: %s. Retry in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    e,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        raise RuntimeError(
            f"LLM API 调用失败: {last_error}。服务暂时不可用，已重试 {MAX_RETRIES} 次。"
        ) from last_error
