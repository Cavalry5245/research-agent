import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPT_PATH = ROOT / "scripts" / "check_llm.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_llm", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_exposes_core_symbols():
    mod = _load_module()
    assert hasattr(mod, "LLMChecker")
    assert hasattr(mod, "OutputFormatter")
    assert hasattr(mod, "ERROR_SUGGESTIONS")
    assert hasattr(mod, "build_arg_parser")


def test_classify_error_maps_known_exceptions():
    mod = _load_module()
    checker = mod.LLMChecker()

    # Test keyword fallback: RuntimeError with message keywords
    assert checker._classify_error(RuntimeError("Connection error.")) == "connection_error"
    assert checker._classify_error(RuntimeError("request timed out")) == "timeout"
    assert checker._classify_error(RuntimeError("invalid api key")) == "authentication_failed"
    assert checker._classify_error(RuntimeError("rate limit exceeded")) == "rate_limit"
    assert checker._classify_error(RuntimeError("model does not exist")) == "model_not_found"
    assert checker._classify_error(RuntimeError("something weird")) == "unknown"


def test_classify_error_prefers_exception_type():
    mod = _load_module()
    checker = mod.LLMChecker()

    # Test type-based classification: exception class name matching
    class FakeRateLimit(Exception):
        pass
    class FakeAuthError(Exception):
        pass
    class FakeTimeout(Exception):
        pass

    FakeRateLimit.__name__ = "RateLimitError"
    FakeAuthError.__name__ = "AuthenticationError"
    FakeTimeout.__name__ = "APITimeoutError"

    assert checker._classify_error(FakeRateLimit("x")) == "rate_limit"
    assert checker._classify_error(FakeAuthError("x")) == "authentication_failed"
    assert checker._classify_error(FakeTimeout("x")) == "timeout"


def test_mask_key_hides_middle():
    mod = _load_module()
    assert mod._mask_key("sk-1234567890abcdef") == "sk-1****cdef"
    assert mod._mask_key("") == "(未设置)"
    assert mod._mask_key("short") == "****"


def test_check_config_returns_summary(monkeypatch):
    mod = _load_module()
    checker = mod.LLMChecker()

    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.deepseek.com/v1",
        "llm_api_key": "sk-abcdefghijklmnop",
        "llm_model": "deepseek-chat",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    cfg = checker.check_config()
    assert cfg["provider"] == "openai_compatible"
    assert cfg["base_url"] == "https://api.deepseek.com/v1"
    assert cfg["model"] == "deepseek-chat"
    assert cfg["api_key_present"] is True
    assert cfg["valid"] is True
    assert "sk-abcdefghijklmnop" not in cfg["api_key_masked"]


def test_check_config_flags_missing_key(monkeypatch):
    mod = _load_module()
    checker = mod.LLMChecker()
    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.example.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    cfg = checker.check_config()
    assert cfg["valid"] is False
    assert cfg["api_key_present"] is False
    assert cfg["error_category"] == "api_key_missing"
