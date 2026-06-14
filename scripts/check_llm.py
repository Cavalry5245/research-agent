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
import time
from pathlib import Path

# 确保可以导入 app 包
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402


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


def _mask_key(key: str) -> str:
    """脱敏 API Key，仅保留首尾少量字符。"""
    if not key:
        return "(未设置)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


class LLMChecker:
    """LLM 可用性检查核心逻辑。"""

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
