import os
import sys
from unittest.mock import patch

import pytest
from openai import APITimeoutError, InternalServerError, RateLimitError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.llm_client import LLMClient


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()]


class _DummyChat:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = 0
        self.completions = self

    def create(self, **kwargs):
        self.calls += 1
        item = self._side_effects.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _DummyClient:
    def __init__(self, side_effects):
        self.chat = _DummyChat(side_effects)


def _make_internal_server_error(message: str = "Service temporarily unavailable"):
    resp = type("Resp", (), {"request": None, "status_code": 503, "headers": {}, "text": message})()
    return InternalServerError(message=message, response=resp, body={"error": {"message": message}})


def _make_rate_limit_error(message: str = "rate limited"):
    resp = type("Resp", (), {"request": None, "status_code": 429, "headers": {}, "text": message})()
    return RateLimitError(message=message, response=resp, body={"error": {"message": message}})


@pytest.fixture
def llm_env():
    old = {
        "llm_api_key": LLMClient.__init__.__globals__["settings"].llm_api_key,
        "llm_base_url": LLMClient.__init__.__globals__["settings"].llm_base_url,
        "llm_model": LLMClient.__init__.__globals__["settings"].llm_model,
    }
    settings = LLMClient.__init__.__globals__["settings"]
    settings.llm_api_key = "test-key"
    settings.llm_base_url = "http://localhost:18080/v1"
    settings.llm_model = "gpt-5.4"
    try:
        yield settings
    finally:
        settings.llm_api_key = old["llm_api_key"]
        settings.llm_base_url = old["llm_base_url"]
        settings.llm_model = old["llm_model"]


def test_generate_text_retries_on_503_then_succeeds(llm_env):
    fake_client = _DummyClient([
        _make_internal_server_error(),
        _FakeResponse("ok after retry"),
    ])

    with patch("app.services.llm_client.OpenAI", return_value=fake_client), patch("time.sleep") as sleep_mock:
        client = LLMClient()
        result = client.generate_text("hello")

    assert result == "ok after retry"
    assert fake_client.chat.calls == 2
    sleep_mock.assert_called_once_with(1.0)


def test_generate_text_retries_on_429_then_succeeds(llm_env):
    fake_client = _DummyClient([
        _make_rate_limit_error(),
        _FakeResponse("ok after retry"),
    ])

    with patch("app.services.llm_client.OpenAI", return_value=fake_client), patch("time.sleep") as sleep_mock:
        client = LLMClient()
        result = client.generate_text("hello")

    assert result == "ok after retry"
    assert fake_client.chat.calls == 2
    sleep_mock.assert_called_once_with(1.0)


def test_generate_text_retries_on_timeout_then_succeeds(llm_env):
    request = type("Req", (), {"method": "POST", "url": "http://localhost:18080/v1/chat/completions"})()
    fake_client = _DummyClient([
        APITimeoutError(request=request),
        _FakeResponse("ok after timeout retry"),
    ])

    with patch("app.services.llm_client.OpenAI", return_value=fake_client), patch("time.sleep") as sleep_mock:
        client = LLMClient()
        result = client.generate_text("hello")

    assert result == "ok after timeout retry"
    assert fake_client.chat.calls == 2
    sleep_mock.assert_called_once_with(1.0)


def test_generate_text_raises_after_max_retries(llm_env):
    fake_client = _DummyClient([
        _make_internal_server_error("temporary outage 1"),
        _make_internal_server_error("temporary outage 2"),
        _make_internal_server_error("temporary outage 3"),
    ])

    with patch("app.services.llm_client.OpenAI", return_value=fake_client), patch("time.sleep") as sleep_mock:
        client = LLMClient()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_text("hello")

    assert "temporary outage 3" in str(exc_info.value)
    assert fake_client.chat.calls == 3
    assert sleep_mock.call_args_list == [((1.0,),), ((2.0,),)]


def test_generate_text_does_not_retry_on_value_error(llm_env):
    fake_client = _DummyClient([
        ValueError("non retryable failure"),
    ])

    with patch("app.services.llm_client.OpenAI", return_value=fake_client), patch("time.sleep") as sleep_mock:
        client = LLMClient()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_text("hello")

    assert "non retryable failure" in str(exc_info.value)
    assert fake_client.chat.calls == 1
    sleep_mock.assert_not_called()
