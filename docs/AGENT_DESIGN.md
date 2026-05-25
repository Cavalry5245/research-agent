# AGENT_DESIGN.md — ResearchAgent Phase 1

## 设计目标

将 ResearchAgent 从基础 RAG 应用升级为具备工具调用和工作流编排能力的 Agent 系统。

## 架构概览

```
User Task (natural language)
  ↓
PaperResearchAgent (langchain.agents.create_agent)
  ├── LLM: ChatOpenAI (OpenAI-compatible API)
  ├── Tools: 6x StructuredTool (via adapter)
  └── System Prompt: AGENT_SYSTEM_PROMPT
  ↓
Tool Execution → Result → Agent Loop → Final Answer
```

## 模块设计

### 1. 工具基类 (BaseTool)

路径: `app/agents/tools/base.py`

```python
class BaseTool(ABC):
    name: str          # 工具唯一标识
    description: str   # 工具功能描述（给 LLM 看）
    parameters: list[ToolParameter]  # 参数定义
    execute(**kwargs) → ToolResult   # 执行逻辑
```

### 2. LangChain 适配器

路径: `app/agents/langchain_adapter.py`

**核心转换函数**: `convert_to_langchain_tool()`

处理逻辑：
1. 从 `tool.parameters` 动态生成 Pydantic `args_schema`
2. 包装 `tool.execute()` 为字符串输出函数（JSON 序列化 ToolResult）
3. 创建 `StructuredTool(name, description, args_schema, func)`

**类型映射**:
| ToolParameter.type | Python type |
|---|---|
| string | str |
| integer/int | int |
| number | float |
| array | list |
| boolean | bool |

### 3. Agent 主体

路径: `app/agents/paper_research_agent.py`

使用 `langchain.agents.create_agent` (基于 LangGraph StateGraph)：
- 自动处理 tool calling loop
- 支持对话历史注入（HumanMessage/AIMessage 转换）
- 单例工厂 `get_agent()` 供 FastAPI 复用

### 4. 工作流编排

路径: `app/agents/workflows/`

**research_workflow.py** — 单篇论文完整分析:
```
parse → index → note → (optional qa)
```

**comparison_workflow.py** — 多论文对比:
```
parse_papers → compare → export
```

每个工作流使用:
- `TypedDict` 定义状态
- `StateGraph` 编排节点和条件边
- 错误短路机制（任一节点失败 → END）
- `export_mermaid()` 导出可视化图

### 5. API 端点

**POST /agent/execute**:
```json
{
  "task": "帮我分析 paper_001 的核心创新",
  "chat_history": [{"role": "user", "content": "..."}]
}
→ {"task": "...", "answer": "分析结果..."}
```

### 6. Streamlit Agent Tab

三种工作模式:
- **自由对话**: chat_input + 对话历史，调用 PaperResearchAgent
- **完整论文分析工作流**: 上传 PDF → 自动运行 research_workflow
- **多论文对比工作流**: 上传多篇 PDF → 自动运行 comparison_workflow

## 工具列表

| 工具名 | 功能 | 核心依赖 |
|--------|------|----------|
| upload_paper | 上传解析 PDF | PyMuPDF, pdf_parser |
| generate_note | 生成结构化笔记 | LLM, note_generator |
| index_paper | 构建向量索引 | EmbeddingClient, VectorStore |
| qa | RAG 问答检索 | VectorStore, Embedding, LLM |
| compare_papers | 多论文对比分析 | LLM, paper_compare |
| export_markdown | 导出 Markdown | 文件 I/O |

## 测试策略

- **test_agent_tools.py** (27 tests): 工具基类和 6 个工具单元测试
- **test_langchain_adapter.py** (6 tests): 适配器转换逻辑测试
- **test_paper_research_agent.py** (6 tests): Agent 创建、执行、历史管理测试
- **test_workflows.py** (19 tests): 工作流节点、路由、完整执行、状态持久化测试

## 设计约束

- 不修改现有 service 层（纯适配器模式）
- LLM provider 通过 `.env` 配置，无硬编码
- 工具可插拔：通过 `extra_tools` 参数扩展
- 工作流状态可 JSON 序列化（支持持久化）