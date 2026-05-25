import logging
import time

import httpx
from openai import APITimeoutError, InternalServerError, OpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (InternalServerError, RateLimitError, APITimeoutError)
MAX_RETRIES = 3
BACKOFF_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 90.0
_HTTPX_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


class LLMClient:
    def __init__(self):
        if not settings.llm_api_key:
            raise ValueError(
                "LLM API Key 未配置。请在 .env 文件中设置 LLM_API_KEY"
            )
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=_HTTPX_TIMEOUT,
            max_retries=0,
        )

    def generate_text(self, prompt: str) -> str:
        logger.info("LLM call: model=%s, prompt_chars=%d", self.model, len(prompt))

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
                raise RuntimeError(f"LLM API 调用失败: {e}") from e

        raise RuntimeError(
            f"LLM API 调用失败: {last_error}。服务暂时不可用，已重试 {MAX_RETRIES} 次。"
        ) from last_error
