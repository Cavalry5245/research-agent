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
