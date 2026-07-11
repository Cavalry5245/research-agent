import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.services.llm_client import LLMClient


@pytest.fixture
def real_llm_client():
    """真实 LLM 客户端 fixture - 从 .env 读取配置"""
    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-ci-dummy"):
        pytest.skip("未配置真实 LLM_API_KEY（或为 CI dummy key），跳过真实调用测试")
    return LLMClient()


def test_real_llm_call_basic(real_llm_client):
    """测试真实 LLM API 调用 - 基础响应"""
    prompt = "请用一句话回复：你好"

    result = real_llm_client.generate_text(prompt)

    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"\n[真实调用测试]")
    print(f"  提供商: {settings.llm_provider}")
    print(f"  模型: {settings.llm_model}")
    print(f"  BASE_URL: {settings.llm_base_url}")
    print(f"  响应: {result}")


def test_real_llm_call_chinese_academic(real_llm_client):
    """测试真实 LLM API 调用 - 中文学术响应"""
    prompt = """请用中文简要说明深度学习中的注意力机制（Attention Mechanism）。
要求：
1. 使用学术语言
2. 不超过100字
3. 不要编造内容"""

    result = real_llm_client.generate_text(prompt)

    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 20
    # 检查是否包含相关关键词
    assert any(
        keyword in result
        for keyword in ["注意力", "权重", "特征", "相关", "关注", "机制", "加权"]
    )
    print(f"\n[学术测试]")
    print(f"  模型: {settings.llm_model}")
    print(f"  响应长度: {len(result)} 字符")
    print(f"  响应内容: {result}")


def test_real_llm_call_model_info(real_llm_client):
    """测试真实 LLM API 调用 - 模型自我识别"""
    prompt = "你是什么模型？请直接回答模型名称。"

    result = real_llm_client.generate_text(prompt)

    assert result is not None
    assert isinstance(result, str)
    print(f"\n[模型识别测试]")
    print(f"  配置的模型: {settings.llm_model}")
    print(f"  模型自述: {result}")


@pytest.mark.skipif(
    "claude" not in settings.llm_model.lower(),
    reason="仅在使用 Claude 模型时运行"
)
def test_real_claude_specific(real_llm_client):
    """测试 Claude 模型特定功能"""
    prompt = """请完成以下任务：
1. 用中文回复
2. 证明你是 Claude
3. 说明你的模型版本
4. 简要描述你的能力"""

    result = real_llm_client.generate_text(prompt)

    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 50
    print(f"\n[Claude 专项测试]")
    print(f"  模型: {settings.llm_model}")
    print(f"  完整响应:\n{result}")
    print(f"  响应长度: {len(result)} 字符")
