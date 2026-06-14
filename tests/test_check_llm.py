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
