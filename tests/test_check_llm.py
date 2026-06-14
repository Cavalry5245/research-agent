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

    # 用最简构造：这些异常需要 request/response，改用消息关键词回退路径验证
    assert checker._classify_error(RuntimeError("Connection error.")) == "connection_error"
    assert checker._classify_error(RuntimeError("request timed out")) == "timeout"
    assert checker._classify_error(RuntimeError("invalid api key")) == "authentication_failed"
    assert checker._classify_error(RuntimeError("rate limit exceeded")) == "rate_limit"
    assert checker._classify_error(RuntimeError("model does not exist")) == "model_not_found"
    assert checker._classify_error(RuntimeError("something weird")) == "unknown"


def test_classify_error_prefers_exception_type():
    mod = _load_module()

    class FakeRateLimit(Exception):
        pass

    # 通过类名匹配（不依赖 openai 构造签名）
    FakeRateLimit.__name__ = "RateLimitError"
    assert checker_classify(mod, FakeRateLimit("x")) == "rate_limit"


def checker_classify(mod, exc):
    return mod.LLMChecker()._classify_error(exc)
