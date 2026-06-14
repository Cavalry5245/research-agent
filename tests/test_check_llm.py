import importlib.util
import json
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


def test_check_config_flags_missing_base_url(monkeypatch):
    mod = _load_module()
    checker = mod.LLMChecker()
    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "",
        "llm_api_key": "sk-validkey123",
        "llm_model": "gpt-4",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    cfg = checker.check_config()
    assert cfg["valid"] is False
    assert cfg["error_category"] == "bad_request"


def test_check_config_flags_missing_model(monkeypatch):
    mod = _load_module()
    checker = mod.LLMChecker()
    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.example.com/v1",
        "llm_api_key": "sk-validkey123",
        "llm_model": "",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    cfg = checker.check_config()
    assert cfg["valid"] is False
    assert cfg["error_category"] == "bad_request"


def test_mask_key_boundary_cases():
    mod = _load_module()
    assert mod._mask_key("12345678") == "****"  # exactly 8
    assert mod._mask_key("123456789") == "1234****6789"  # 9 chars


def test_quick_check_success(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            return "你好！很高兴见到你。"

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    result = checker.quick_check()
    assert result["success"] is True
    assert result["response_preview"]
    assert isinstance(result["latency_seconds"], float)
    assert result["latency_seconds"] >= 0


def test_quick_check_empty_response_fails(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            return ""

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    result = checker.quick_check()
    assert result["success"] is False
    assert result["error_category"] == "unknown"


def test_quick_check_exception_classified(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            raise RuntimeError("invalid api key")

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    result = checker.quick_check()
    assert result["success"] is False
    assert result["error_category"] == "authentication_failed"
    assert result["suggestions"]


def test_deep_check_runs_three_tests(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            # 返回含中文与关键词的文本，满足三项验证
            return "深度学习是一种基于神经网络的机器学习方法，通过多层特征表示学习数据规律。"

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    results = checker.deep_check()
    assert len(results) == 3
    names = {r["name"] for r in results}
    assert names == {"中文支持测试", "学术文本生成测试", "长文本处理测试"}
    assert all(r["success"] for r in results)


def test_deep_check_handles_failure(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            raise RuntimeError("rate limit exceeded")

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    results = checker.deep_check()
    assert len(results) == 3
    assert all(r["success"] is False for r in results)
    assert all(r["error_category"] == "rate_limit" for r in results)


def test_run_aggregates_quick_only(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            return "你好。"

    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.deepseek.com/v1",
        "llm_api_key": "sk-abcdefghijklmnop",
        "llm_model": "deepseek-chat",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    result = checker.run(deep=False)
    assert result["success"] is True
    assert result["config"]["model"] == "deepseek-chat"
    assert result["quick_check"]["success"] is True
    assert result["deep_check"]["enabled"] is False


def test_run_short_circuits_on_invalid_config(monkeypatch):
    mod = _load_module()
    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.example.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    checker = mod.LLMChecker()  # 不应实例化真实 client
    result = checker.run(deep=False)
    assert result["success"] is False
    assert result["config"]["valid"] is False
    assert result["quick_check"] is None


def test_json_output_is_parseable(monkeypatch):
    mod = _load_module()

    class FakeClient:
        def generate_text(self, prompt):
            return "你好。"

    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.deepseek.com/v1",
        "llm_api_key": "sk-abcdefghijklmnop",
        "llm_model": "deepseek-chat",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    checker = mod.LLMChecker(client_factory=lambda: FakeClient())
    result = checker.run(deep=False)
    payload = mod.OutputFormatter().to_json(result)
    parsed = json.loads(payload)
    assert parsed["success"] is True
    assert "timestamp" in parsed
