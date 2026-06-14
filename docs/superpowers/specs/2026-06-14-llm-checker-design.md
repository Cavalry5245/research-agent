# LLM 可用性检查工具 — 设计文档

## 概述

一个独立的命令行脚本 `scripts/check_llm.py`，用于快速验证第三方 OpenAI 兼容 LLM API 的连通性和配置正确性。主要服务于频繁切换不同供应商和模型时的快速测试场景。

## 背景与目标

ResearchAgent 使用 OpenAI 兼容 API 调用 LLM，支持多种第三方供应商（DeepSeek、Qwen、Ollama 等）。用户需要经常切换供应商和模型进行测试，但当前缺少独立的预检工具：

- 现有检查仅验证 `llm_api_key` 是否为空字符串
- 不验证 API Key 有效性、网络连通性、模型可用性
- 配置错误只有在实际调用时才会暴露

**目标：** 提供一个独立、快速、可分级的检查工具，让用户在切换配置后立即验证 LLM 是否可用。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 调用方式 | 独立命令行脚本 | 切换 `.env` 后立即运行，无需启动服务器 |
| 检查深度 | 分级检查（快速 / `--deep`） | 频繁测试用快速，新供应商首次配置用深度 |
| 输出格式 | 终端 + `--json` | 手动测试友好，自动化可解析 |
| 配置来源 | 只读 `.env` | 保持简单，符合 config-driven 设计 |
| 诊断详细度 | 分级（默认 / `--verbose`） | 日常简洁，调试时详细 |
| 架构模式 | 复用现有 `LLMClient` | YAGNI，保证与生产代码一致 |

## 架构

单文件命令行脚本，复用项目的 `LLMClient` 类。

```
scripts/check_llm.py
  ├─ LLMChecker        核心检查逻辑
  │   ├─ check_config()      读取并验证 .env 配置
  │   ├─ quick_check()       基础连通性测试
  │   └─ deep_check()        中文 / 学术 / 长文本测试
  ├─ OutputFormatter   输出格式化（终端 / JSON）
  └─ main()            CLI 参数解析与调度
        ↓ 复用
app/config.py (settings)
app/services/llm_client.py (LLMClient)
```

**文件位置：** `scripts/check_llm.py`（与现有 `check_zotero.py` 同级）

**依赖：** 仅项目现有依赖，无需额外安装

## 命令行接口

```bash
python scripts/check_llm.py                  # 快速检查
python scripts/check_llm.py --deep           # 深度检查
python scripts/check_llm.py --verbose        # 详细输出 / 诊断
python scripts/check_llm.py --json           # JSON 输出
python scripts/check_llm.py --deep --json    # 组合使用
```

| 参数 | 作用 |
|------|------|
| `--deep` | 启用深度检查（中文、学术文本、长文本） |
| `--verbose` | 显示请求参数、错误堆栈、token 统计等 |
| `--json` | 输出 JSON 格式（机器可读） |

## 功能模块

### 配置读取与验证

- 从 `.env` 读取配置（通过 `app.config.settings`）
- 验证必需字段：`llm_api_key`、`llm_base_url`、`llm_model`、`llm_provider`
- 显示配置摘要（API Key 脱敏为 `sk-****...****`）

### 快速检查（默认模式）

**目标：** 验证基础连通性，<5 秒完成。

测试步骤：
1. 实例化 `LLMClient`（验证配置加载）
2. 发送简单 prompt：`"你好，请用一句话回复。"`
3. 验证响应为非空字符串
4. 记录延迟时间

**成功标准：** API 调用成功、响应非空、无异常。

### 深度检查（`--deep` 模式）

**目标：** 验证完整功能，适合新供应商首次配置。

| 测试 | Prompt 内容 | 验证点 |
|------|------------|--------|
| 中文支持 | `"请用中文简要说明什么是深度学习。要求：学术语言，不超过50字。"` | 含中文字符，长度合理 |
| 学术文本生成 | 模拟论文摘要总结任务（~100 字输入） | 学术格式，含关键词 |
| 长文本处理 | 发送 ~500 字文本要求总结 | 能处理长输入，响应合理 |

**成功标准：** 所有测试通过，无异常或超时。

## 输出格式

### 终端输出（默认）

快速检查成功：
```
=== LLM 可用性检查 ===

配置信息:
  Provider: openai_compatible
  Base URL: https://api.deepseek.com/v1
  Model: deepseek-chat
  API Key: sk-****...****

[快速检查]
✓ 配置加载成功
✓ API 连通性测试通过
  响应时间: 1.23s
  响应内容: 你好！有什么我可以帮助你的吗？

结论: ✓ LLM 配置正常，可以使用
```

快速检查失败：
```
[快速检查]
✓ 配置加载成功
✗ API 连通性测试失败
  错误类型: 网络超时
  错误信息: Connection timeout after 90s

常见问题排查:
  1. 检查网络连接和防火墙设置
  2. 确认 LLM_BASE_URL 是否正确
  3. 确认 API 服务是否正常运行

结论: ✗ LLM 配置异常，无法使用
```

深度检查：
```
=== LLM 可用性检查（深度模式）===

[快速检查]
✓ 基础连通性测试通过 (1.23s)

[深度检查]
✓ 中文支持测试通过 (1.45s)
  响应长度: 48 字符
✓ 学术文本生成测试通过 (2.31s)
  关键词检测: 通过
✓ 长文本处理测试通过 (3.12s)
  输入/输出: 523 字 / 89 字

性能统计:
  平均响应时间: 2.03s
  总测试时间: 8.11s

结论: ✓ LLM 配置正常，所有功能测试通过
```

### JSON 输出（`--json` 模式）

```json
{
  "success": true,
  "config": {
    "provider": "openai_compatible",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key_present": true
  },
  "quick_check": {
    "success": true,
    "latency_seconds": 1.23,
    "response_preview": "你好！有什么我可以帮助..."
  },
  "deep_check": {
    "enabled": false
  },
  "timestamp": "2026-06-14T21:30:45Z"
}
```

注：`timestamp` 由脚本运行时生成（脚本可使用 `datetime`），设计文档中的时间为示例值。

## 错误处理与诊断

### 错误分类

| 类别 | 触发条件 |
|------|---------|
| 配置错误 | `LLM_API_KEY` 未设置、`LLM_BASE_URL` 为空/格式错误、`LLM_MODEL` 未配置 |
| 网络错误 | 连接超时、DNS 解析失败、网络不可达 |
| 认证错误 | API Key 无效/过期、权限不足 |
| API 错误 | 速率限制、模型不存在、500 内部错误、400 请求格式错误 |

### 诊断建议映射

每类错误附带常见修复建议（`ERROR_SUGGESTIONS` 字典），例如：

- **api_key_missing**：在 `.env` 设置 `LLM_API_KEY`；参考 `.env.example`
- **connection_timeout**：检查网络；确认 `LLM_BASE_URL`；检查防火墙；尝试代理
- **authentication_failed**：验证 API Key；检查是否过期；确认账户余额
- **rate_limit**：等待重试；检查速率限制；考虑升级套餐
- **model_not_found**：检查 `LLM_MODEL`；查看供应商可用模型；确认权限

错误分类通过捕获异常类型（OpenAI SDK 异常）+ 异常消息关键词匹配实现。

### Verbose 模式额外信息

`--verbose` 时额外显示：完整请求参数（脱敏）、完整错误堆栈、HTTP 状态码（如有）、重试次数与间隔、token 使用统计（如 API 返回）。

## 代码结构

```python
# scripts/check_llm.py

# 1. 导入与常量
class Colors: ...                  # ANSI 颜色（参考 check_zotero.py）
ERROR_SUGGESTIONS = {...}          # 错误类型 → 修复建议

# 2. 核心检查
class LLMChecker:
    def __init__(self, verbose=False)
    def check_config() -> dict
    def quick_check() -> dict
    def deep_check() -> list[dict]
    def _test_chinese_support() -> dict
    def _test_academic_text() -> dict
    def _test_long_context() -> dict
    def _classify_error(exc) -> str   # 异常 → 错误类别

# 3. 输出格式化
class OutputFormatter:
    def print_terminal(result)
    def print_json(result)

# 4. CLI 入口
def main():
    # argparse: --deep, --verbose, --json
    # 调度 checker + formatter
    # 退出码: 0 成功, 1 失败
```

**文件大小估算：** ~250-300 行。

## 测试策略

- 手动验证：用真实 `.env` 配置运行快速检查与深度检查
- 失败路径验证：临时设置错误的 `LLM_BASE_URL` / `LLM_API_KEY`，确认错误分类与建议正确
- JSON 输出验证：确认 `--json` 输出可被 `json.loads` 解析
- 退出码验证：成功返回 0，失败返回 1（便于脚本/CI 使用）

## 非目标（YAGNI）

- 不支持命令行参数覆盖配置（只读 `.env`）
- 不支持多供应商配置文件预设
- 不集成到 FastAPI 端点
- 不支持 Anthropic 原生格式（项目仅保留 OpenAI 兼容格式）
- 不做并发/压力测试（已有 `tests/performance/`）

