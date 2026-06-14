# LLM 可用性检查工具 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建独立命令行脚本 `scripts/check_llm.py`，快速验证 OpenAI 兼容 LLM API 的连通性、配置正确性，支持分级检查（快速/深度）与分级诊断（默认/verbose），并提供终端与 JSON 两种输出。

**Architecture:** 单文件脚本，复用项目的 `LLMClient`（`app/services/llm_client.py`）与 `settings`（`app/config.py`）。核心类 `LLMChecker` 负责配置校验与各项测试，`OutputFormatter` 负责终端/JSON 渲染，`main()` 负责 CLI 解析与退出码。

**Tech Stack:** Python 3、argparse、openai SDK（已安装）、项目现有 `LLMClient`/`settings`。无新增依赖。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `scripts/check_llm.py`（新建） | 全部逻辑：CLI、配置校验、快速/深度检查、错误分类、终端/JSON 输出 |
| `tests/test_check_llm.py`（新建） | 纯单元测试：错误分类、配置脱敏、JSON 结构、退出码逻辑（mock `LLMClient`，不触发真实网络） |

**说明：** 参考现有 `scripts/check_zotero.py` 的 `Colors` 类与 `supports_color()` 风格，保持脚本一致性。测试通过依赖注入/mock 避免真实 API 调用，使无 `.env` 配置时也能运行。

---

### Task 1: 脚本骨架 — Colors、CLI 解析、可导入

**Files:**
- Create: `scripts/check_llm.py`
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 模块可导入且暴露关键符号**

创建 `tests/test_check_llm.py`：

```python
import importlib.util
import os
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py::test_module_exposes_core_symbols -v`
Expected: FAIL — 文件不存在 / 无法导入。

- [ ] **Step 3: 写最小实现 — 骨架**

创建 `scripts/check_llm.py`：

```python
#!/usr/bin/env python3
"""
LLM Availability Checker
快速验证 OpenAI 兼容 LLM API 的连通性与配置正确性。

Usage:
    python scripts/check_llm.py              # 快速检查
    python scripts/check_llm.py --deep       # 深度检查
    python scripts/check_llm.py --verbose    # 详细诊断
    python scripts/check_llm.py --json       # JSON 输出

Author: ResearchAgent Project
"""

import argparse
import os
import platform
import sys
from pathlib import Path

# 确保可以导入 app 包
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.GREEN = cls.RED = cls.YELLOW = cls.BLUE = cls.BOLD = cls.RESET = ""


def supports_color() -> bool:
    if platform.system() == "Windows":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON"))
    return True


ERROR_SUGGESTIONS = {
    "api_key_missing": [
        "在 .env 文件中设置 LLM_API_KEY",
        "参考 .env.example 文件",
    ],
    "connection_error": [
        "检查网络连接和防火墙设置",
        "确认 LLM_BASE_URL 是否正确（注意 /v1 后缀）",
        "确认 API 服务是否正常运行",
        "如需代理请配置代理环境变量",
    ],
    "timeout": [
        "检查网络连接",
        "确认 LLM_BASE_URL 是否可达",
        "目标服务可能响应缓慢，可稍后重试",
    ],
    "authentication_failed": [
        "验证 API Key 是否正确",
        "检查 API Key 是否过期",
        "确认账户是否有足够余额",
    ],
    "rate_limit": [
        "等待几秒后重试",
        "检查账户的速率限制配置",
        "考虑升级 API 套餐",
    ],
    "model_not_found": [
        "检查 LLM_MODEL 配置是否正确",
        "查看供应商文档确认可用模型列表",
        "某些模型可能需要特殊权限",
    ],
    "bad_request": [
        "检查 LLM_MODEL 是否被该供应商支持",
        "确认请求参数符合供应商要求",
    ],
    "unknown": [
        "使用 --verbose 查看完整错误堆栈",
        "确认 .env 中 LLM_* 配置项均正确",
    ],
}


class LLMChecker:
    """LLM 可用性检查核心逻辑。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose


class OutputFormatter:
    """检查结果输出格式化。"""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and supports_color()
        if not self.use_color:
            Colors.disable()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查 OpenAI 兼容 LLM API 的可用性",
    )
    parser.add_argument(
        "--deep", action="store_true", help="启用深度检查（中文/学术/长文本）"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="显示详细诊断信息"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="以 JSON 格式输出"
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    # 后续任务填充调度逻辑
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py::test_module_exposes_core_symbols -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): scaffold LLM availability checker"
```

---

### Task 2: 错误分类 `_classify_error`

**Files:**
- Modify: `scripts/check_llm.py`（在 `LLMChecker` 内新增 `_classify_error`）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 异常 → 错误类别**

在 `tests/test_check_llm.py` 末尾追加：

```python
def test_classify_error_maps_known_exceptions():
    mod = _load_module()
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        NotFoundError,
        RateLimitError,
    )

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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k classify -v`
Expected: FAIL — `_classify_error` 未定义。

- [ ] **Step 3: 写实现**

在 `LLMChecker` 类中新增方法（放在 `__init__` 之后）：

```python
    def _classify_error(self, exc: Exception) -> str:
        """将异常归类为 ERROR_SUGGESTIONS 中的键。

        优先按异常类名匹配（兼容 openai SDK 异常），
        无法匹配时回退到异常消息关键词匹配。
        """
        name = type(exc).__name__.lower()
        type_map = {
            "ratelimiterror": "rate_limit",
            "authenticationerror": "authentication_failed",
            "permissiondeniederror": "authentication_failed",
            "notfounderror": "model_not_found",
            "badrequesterror": "bad_request",
            "apitimeouterror": "timeout",
            "apiconnectionerror": "connection_error",
        }
        if name in type_map:
            return type_map[name]

        message = str(exc).lower()
        keyword_map = [
            ("rate limit", "rate_limit"),
            ("timed out", "timeout"),
            ("timeout", "timeout"),
            ("api key", "authentication_failed"),
            ("authentication", "authentication_failed"),
            ("unauthorized", "authentication_failed"),
            ("does not exist", "model_not_found"),
            ("model not found", "model_not_found"),
            ("connection error", "connection_error"),
            ("connection", "connection_error"),
            ("bad request", "bad_request"),
        ]
        for keyword, category in keyword_map:
            if keyword in message:
                return category
        return "unknown"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k classify -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add LLM error classification"
```

---

### Task 3: 配置读取与脱敏 `check_config`

**Files:**
- Modify: `scripts/check_llm.py`（`LLMChecker.check_config`、模块级 `_mask_key`）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 脱敏与配置字典**

追加：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k config -v`
Expected: FAIL — `_mask_key`/`settings`/`check_config` 未定义。

- [ ] **Step 3: 写实现**

在 `scripts/check_llm.py` 顶部 import 区追加（在 `ROOT` 设置之后）：

```python
from app.config import settings  # noqa: E402
```

新增模块级函数（放在 `ERROR_SUGGESTIONS` 之后）：

```python
def _mask_key(key: str) -> str:
    """脱敏 API Key，仅保留首尾少量字符。"""
    if not key:
        return "(未设置)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"
```

在 `LLMChecker` 中新增方法：

```python
    def check_config(self) -> dict:
        """读取并校验 .env 配置，返回配置摘要字典。"""
        provider = getattr(settings, "llm_provider", "")
        base_url = getattr(settings, "llm_base_url", "")
        api_key = getattr(settings, "llm_api_key", "")
        model = getattr(settings, "llm_model", "")

        valid = True
        error_category = None
        if not api_key:
            valid = False
            error_category = "api_key_missing"
        elif not base_url:
            valid = False
            error_category = "bad_request"
        elif not model:
            valid = False
            error_category = "bad_request"

        return {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "api_key_present": bool(api_key),
            "api_key_masked": _mask_key(api_key),
            "valid": valid,
            "error_category": error_category,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k config -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add config validation and key masking"
```

---

### Task 4: 快速检查 `quick_check`

**Files:**
- Modify: `scripts/check_llm.py`（`LLMChecker.quick_check`，构造函数注入可选 `client_factory`）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 成功与失败路径（mock client）**

追加：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k quick_check -v`
Expected: FAIL — `client_factory`/`quick_check` 未定义。

- [ ] **Step 3: 写实现**

修改 `LLMChecker.__init__`：

```python
    def __init__(self, verbose: bool = False, client_factory=None):
        self.verbose = verbose
        self._client_factory = client_factory
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                from app.services.llm_client import LLMClient

                self._client = LLMClient()
        return self._client
```

新增 `quick_check`（使用 `time.perf_counter` 计时；在文件顶部 import 区补 `import time`）：

```python
    def _call(self, prompt: str) -> tuple[str, float]:
        start = time.perf_counter()
        response = self._get_client().generate_text(prompt)
        elapsed = time.perf_counter() - start
        return response, elapsed

    def quick_check(self) -> dict:
        prompt = "你好，请用一句话回复。"
        try:
            response, elapsed = self._call(prompt)
        except Exception as exc:  # noqa: BLE001
            category = self._classify_error(exc)
            return {
                "name": "快速检查",
                "success": False,
                "error_category": category,
                "error_message": str(exc),
                "suggestions": ERROR_SUGGESTIONS.get(category, ERROR_SUGGESTIONS["unknown"]),
            }

        if not response or not response.strip():
            return {
                "name": "快速检查",
                "success": False,
                "error_category": "unknown",
                "error_message": "LLM 返回了空内容",
                "suggestions": ERROR_SUGGESTIONS["unknown"],
            }

        preview = response.strip().replace("\n", " ")[:60]
        return {
            "name": "快速检查",
            "success": True,
            "latency_seconds": round(elapsed, 3),
            "response_preview": preview,
        }
```

确保顶部有 `import time`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k quick_check -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add quick connectivity check"
```

---

### Task 5: 深度检查 `deep_check`

**Files:**
- Modify: `scripts/check_llm.py`（`deep_check` 及三个子测试）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 深度检查返回三项结果**

追加：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k deep_check -v`
Expected: FAIL — `deep_check` 未定义。

- [ ] **Step 3: 写实现**

新增方法：

```python
    def _run_test(self, name: str, prompt: str, validate) -> dict:
        try:
            response, elapsed = self._call(prompt)
        except Exception as exc:  # noqa: BLE001
            category = self._classify_error(exc)
            return {
                "name": name,
                "success": False,
                "error_category": category,
                "error_message": str(exc),
                "suggestions": ERROR_SUGGESTIONS.get(category, ERROR_SUGGESTIONS["unknown"]),
            }
        ok, detail = validate(response)
        return {
            "name": name,
            "success": ok,
            "latency_seconds": round(elapsed, 3),
            "detail": detail,
            "response_length": len(response.strip()),
        }

    @staticmethod
    def _has_chinese(text: str) -> bool:
        return any("一" <= ch <= "鿿" for ch in text)

    def _test_chinese_support(self) -> dict:
        prompt = "请用中文简要说明什么是深度学习。要求：学术语言，不超过50字。"

        def validate(resp: str):
            resp = (resp or "").strip()
            if self._has_chinese(resp) and len(resp) >= 5:
                return True, f"响应长度: {len(resp)} 字符"
            return False, "未检测到有效中文响应"

        return self._run_test("中文支持测试", prompt, validate)

    def _test_academic_text(self) -> dict:
        prompt = (
            "以下是一段论文摘要，请用学术语言总结其核心贡献，不超过80字：\n"
            "本文提出一种基于注意力机制的神经网络模型，用于提升长文本语义理解能力，"
            "在多个基准数据集上取得了优于现有方法的性能。"
        )
        keywords = ["注意力", "模型", "方法", "性能", "神经网络", "语义", "贡献"]

        def validate(resp: str):
            resp = (resp or "").strip()
            if self._has_chinese(resp) and any(k in resp for k in keywords):
                return True, "关键词检测: 通过"
            return False, "关键词检测: 未通过"

        return self._run_test("学术文本生成测试", prompt, validate)

    def _test_long_context(self) -> dict:
        long_text = (
            "深度学习近年来在计算机视觉、自然语言处理和语音识别等领域取得了显著进展。"
            * 12
        )
        prompt = f"请用一句话总结以下文本的主题：\n{long_text}"
        input_len = len(prompt)

        def validate(resp: str):
            resp = (resp or "").strip()
            if len(resp) >= 5:
                return True, f"输入/输出: {input_len} 字 / {len(resp)} 字"
            return False, "响应过短或为空"

        return self._run_test("长文本处理测试", prompt, validate)

    def deep_check(self) -> list[dict]:
        return [
            self._test_chinese_support(),
            self._test_academic_text(),
            self._test_long_context(),
        ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k deep_check -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add deep functional checks"
```

---

### Task 6: 结果聚合 `run` 与 JSON 输出

**Files:**
- Modify: `scripts/check_llm.py`（`LLMChecker.run`、`OutputFormatter.to_json`/`print_json`）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — run 聚合结构 + JSON 可解析**

追加：

```python
import json


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k "run_ or json_output" -v`
Expected: FAIL — `run`/`to_json` 未定义。

- [ ] **Step 3: 写实现**

在文件顶部 import 区补 `import json` 与 `from datetime import datetime, timezone`。

在 `LLMChecker` 新增：

```python
    def run(self, deep: bool = False) -> dict:
        config = self.check_config()
        result = {
            "success": False,
            "config": config,
            "quick_check": None,
            "deep_check": {"enabled": deep, "tests": []},
        }

        if not config["valid"]:
            category = config["error_category"] or "unknown"
            result["error_category"] = category
            result["suggestions"] = ERROR_SUGGESTIONS.get(
                category, ERROR_SUGGESTIONS["unknown"]
            )
            return result

        quick = self.quick_check()
        result["quick_check"] = quick
        if not quick["success"]:
            return result

        if not deep:
            result["success"] = True
            return result

        deep_results = self.deep_check()
        result["deep_check"]["tests"] = deep_results
        result["success"] = all(r["success"] for r in deep_results)
        return result
```

在 `OutputFormatter` 新增：

```python
    def to_json(self, result: dict) -> str:
        payload = dict(result)
        payload["timestamp"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def print_json(self, result: dict) -> None:
        print(self.to_json(result))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k "run_ or json_output" -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add result aggregation and JSON output"
```

---

### Task 7: 终端输出 `print_terminal`

**Files:**
- Modify: `scripts/check_llm.py`（`OutputFormatter.print_terminal` 及辅助打印）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — 终端输出包含关键文本（capsys）**

追加：

```python
def test_print_terminal_success_contains_conclusion(capsys):
    mod = _load_module()
    mod.Colors.disable()
    result = {
        "success": True,
        "config": {
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key_present": True,
            "api_key_masked": "sk-1****cdef",
            "valid": True,
            "error_category": None,
        },
        "quick_check": {
            "name": "快速检查",
            "success": True,
            "latency_seconds": 1.23,
            "response_preview": "你好！",
        },
        "deep_check": {"enabled": False, "tests": []},
    }
    mod.OutputFormatter(use_color=False).print_terminal(result)
    out = capsys.readouterr().out
    assert "配置信息" in out
    assert "deepseek-chat" in out
    assert "快速检查" in out
    assert "LLM 配置正常" in out
    assert "sk-1****cdef" in out


def test_print_terminal_failure_shows_suggestions(capsys):
    mod = _load_module()
    mod.Colors.disable()
    result = {
        "success": False,
        "config": {
            "provider": "openai_compatible",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4",
            "api_key_present": False,
            "api_key_masked": "(未设置)",
            "valid": False,
            "error_category": "api_key_missing",
        },
        "quick_check": None,
        "deep_check": {"enabled": False, "tests": []},
        "error_category": "api_key_missing",
        "suggestions": ["在 .env 文件中设置 LLM_API_KEY", "参考 .env.example 文件"],
    }
    mod.OutputFormatter(use_color=False).print_terminal(result)
    out = capsys.readouterr().out
    assert "常见问题排查" in out
    assert "LLM_API_KEY" in out
    assert "无法使用" in out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k print_terminal -v`
Expected: FAIL — `print_terminal` 未定义。

- [ ] **Step 3: 写实现**

在 `OutputFormatter` 新增（`_icon` 辅助 + 主方法）：

```python
    def _icon(self, ok: bool) -> str:
        return f"{Colors.GREEN}✓{Colors.RESET}" if ok else f"{Colors.RED}✗{Colors.RESET}"

    def _print_suggestions(self, suggestions) -> None:
        if not suggestions:
            return
        print(f"\n{Colors.YELLOW}常见问题排查:{Colors.RESET}")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s}")

    def print_terminal(self, result: dict, verbose: bool = False) -> None:
        cfg = result["config"]
        deep_enabled = result["deep_check"]["enabled"]

        title = "LLM 可用性检查（深度模式）" if deep_enabled else "LLM 可用性检查"
        print(f"\n{Colors.BOLD}{Colors.BLUE}=== {title} ==={Colors.RESET}\n")

        print("配置信息:")
        print(f"  Provider: {cfg['provider']}")
        print(f"  Base URL: {cfg['base_url']}")
        print(f"  Model: {cfg['model']}")
        print(f"  API Key: {cfg['api_key_masked']}")

        # 配置无效：直接给出结论
        if not cfg["valid"]:
            print(f"\n[配置检查]")
            print(f"{self._icon(False)} 配置校验失败")
            self._print_suggestions(result.get("suggestions"))
            print(f"\n结论: {self._icon(False)} LLM 配置异常，无法使用")
            return

        # 快速检查
        quick = result["quick_check"]
        print(f"\n[快速检查]")
        if quick and quick["success"]:
            print(f"{self._icon(True)} API 连通性测试通过")
            print(f"  响应时间: {quick['latency_seconds']}s")
            print(f"  响应内容: {quick['response_preview']}")
        else:
            print(f"{self._icon(False)} API 连通性测试失败")
            if quick:
                print(f"  错误信息: {quick.get('error_message', '')}")
                if verbose:
                    print(f"  错误类别: {quick.get('error_category', '')}")
                self._print_suggestions(quick.get("suggestions"))
            print(f"\n结论: {self._icon(False)} LLM 配置异常，无法使用")
            return

        # 深度检查
        if deep_enabled:
            print(f"\n[深度检查]")
            latencies = []
            for t in result["deep_check"]["tests"]:
                print(f"{self._icon(t['success'])} {t['name']}")
                if t["success"]:
                    print(f"  {t.get('detail', '')} ({t['latency_seconds']}s)")
                    latencies.append(t["latency_seconds"])
                else:
                    print(f"  错误信息: {t.get('error_message', '')}")
                    self._print_suggestions(t.get("suggestions"))
            if latencies:
                avg = round(sum(latencies) / len(latencies), 3)
                print(f"\n性能统计:")
                print(f"  平均响应时间: {avg}s")

        ok = result["success"]
        conclusion = (
            "LLM 配置正常，所有功能测试通过"
            if deep_enabled and ok
            else "LLM 配置正常，可以使用"
            if ok
            else "部分功能测试未通过"
        )
        print(f"\n结论: {self._icon(ok)} {conclusion}")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k print_terminal -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): add terminal output rendering"
```

---

### Task 8: `main()` 调度与退出码

**Files:**
- Modify: `scripts/check_llm.py`（`main` 完整实现）
- Test: `tests/test_check_llm.py`

- [ ] **Step 1: 写失败测试 — main 退出码与输出选择**

追加：

```python
def test_main_returns_zero_on_success(monkeypatch, capsys):
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
    monkeypatch.setattr(
        mod.LLMChecker, "_get_client", lambda self: FakeClient(), raising=True
    )

    code = mod.main(["--json"])
    out = capsys.readouterr().out
    assert code == 0
    parsed = json.loads(out)
    assert parsed["success"] is True


def test_main_returns_one_on_failure(monkeypatch, capsys):
    mod = _load_module()
    fake = type("S", (), {
        "llm_provider": "openai_compatible",
        "llm_base_url": "https://api.example.com/v1",
        "llm_api_key": "",
        "llm_model": "gpt-4",
    })()
    monkeypatch.setattr(mod, "settings", fake, raising=False)

    code = mod.main([])
    assert code == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_check_llm.py -k main -v`
Expected: FAIL — `main` 仍是占位（始终返回 0）。

- [ ] **Step 3: 写实现 — 替换占位 `main`**

将 Task 1 中的 `main` 替换为：

```python
def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    checker = LLMChecker(verbose=args.verbose)
    result = checker.run(deep=args.deep)

    formatter = OutputFormatter(use_color=not args.as_json)
    if args.as_json:
        formatter.print_json(result)
    else:
        formatter.print_terminal(result, verbose=args.verbose)

    return 0 if result["success"] else 1
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_check_llm.py -k main -v`
Expected: PASS。

- [ ] **Step 5: 全量测试 + 提交**

Run: `python -m pytest tests/test_check_llm.py -v`
Expected: 全部 PASS。

```bash
git add scripts/check_llm.py tests/test_check_llm.py
git commit -m "feat(scripts): wire up main dispatch and exit codes"
```

---

### Task 9: 真实调用冒烟验证 + 文档

**Files:**
- Modify: `scripts/check_llm.py`（仅在需要时微调）
- Modify: `README.md`（新增使用说明小节）

- [ ] **Step 1: 用真实 `.env` 运行快速检查**

Run: `python scripts/check_llm.py`
Expected: 若 `.env` 已配置有效 LLM，输出 `结论: ✓ LLM 配置正常，可以使用`；否则给出清晰的错误类别与排查建议。
（记录实际输出到完成note。）

- [ ] **Step 2: 运行深度检查与 JSON 输出**

Run: `python scripts/check_llm.py --deep`
Run: `python scripts/check_llm.py --json`
Run: `python scripts/check_llm.py --deep --json --verbose`
Expected: 深度模式跑三项测试；`--json` 输出可被 `python -c "import json,sys; json.load(sys.stdin)"` 解析。

- [ ] **Step 3: 失败路径验证**

临时在 shell 中用错误配置验证（不修改 `.env`，通过临时环境变量）：

Run: `LLM_API_KEY="" python scripts/check_llm.py`
Expected: 退出码 1，提示 `api_key_missing` 及建议。
（注：`settings` 由 pydantic-settings 读取，环境变量优先级高于 `.env`，可用于临时覆盖验证。）

- [ ] **Step 4: 更新 README**

在 `README.md` 中找到工具/脚本相关章节（若无则在“开发命令”或“测试”附近新增），加入：

```markdown
### 检查 LLM 可用性

切换 LLM 供应商或模型后，可用独立脚本快速验证连通性：

\`\`\`bash
python scripts/check_llm.py            # 快速连通性检查
python scripts/check_llm.py --deep     # 深度检查（中文/学术/长文本）
python scripts/check_llm.py --verbose  # 详细诊断
python scripts/check_llm.py --json     # JSON 输出（便于脚本解析）
\`\`\`

退出码：0 表示可用，1 表示异常。配置读取自 `.env`。
```

- [ ] **Step 5: 提交**

```bash
git add scripts/check_llm.py README.md
git commit -m "docs: document LLM checker usage and smoke-test"
```

---

## Self-Review 结果

**Spec coverage：**
- 独立命令行脚本 → Task 1, 8 ✓
- 只读 `.env` 配置 → Task 3 ✓
- 快速检查 → Task 4 ✓
- 深度检查（中文/学术/长文本）→ Task 5 ✓
- 终端 + JSON 输出 → Task 6, 7 ✓
- 分级诊断（默认/verbose）→ Task 7（verbose 分支）, 8 ✓
- 错误分类 + 修复建议 → Task 2, 配合 `ERROR_SUGGESTIONS`（Task 1）✓
- API Key 脱敏 → Task 3 ✓
- 退出码 0/1 → Task 8 ✓
- 测试策略（手动/失败路径/JSON/退出码）→ Task 9 + 各任务单测 ✓

**Placeholder scan：** 无 TODO/TBD；每个代码步骤均含完整代码。

**Type consistency：**
- `LLMChecker(verbose, client_factory)` — Task 1 定义骨架，Task 4 扩展签名（同名一致）
- `_classify_error` 返回的类别键与 `ERROR_SUGGESTIONS` 键一致（rate_limit/authentication_failed/timeout/connection_error/model_not_found/bad_request/api_key_missing/unknown）✓
- `run()` 输出结构（`config`/`quick_check`/`deep_check`/`success`）在 Task 6 定义，Task 7/8 消费一致 ✓
- `quick_check`/各深度测试返回字段（`name`/`success`/`latency_seconds`/`response_preview`/`detail`/`error_message`/`suggestions`）跨任务一致 ✓

无遗漏，无需补任务。
