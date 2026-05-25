# Multi-Agent Design

## Architecture Overview

ResearchAgent 采用 LangGraph Supervisor 模式实现多 Agent 协作。Supervisor 负责意图分类和任务路由，Specialist Agents 负责具体执行。

```
用户输入
   │
   ▼
┌─────────────┐
│  Supervisor │  ← route_node: 意图分类
│  (LangGraph │  ← execute_node: 分发到 Specialist
│   StateGraph)│  ← synthesize_node: 合并结果
└──────┬──────┘
       │ delegation
       ▼
┌──────────────────────────────────────┐
│         Specialist Agents            │
├──────────┬───────────┬──────────────┤
│Extractor │Summarizer │   QA Agent   │
│  Agent   │  Agent    │(RAG+Rerank)  │
├──────────┴───────────┴──────────────┤
│          Comparator Agent            │
└──────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│          Memory Layer                │
├────────────┬───────────┬────────────┤
│ ShortTerm  │ LongTerm  │  Semantic  │
│(对话历史)   │(偏好/历史) │(向量事实)   │
└────────────┴───────────┴────────────┘
```

## State Flow

SupervisorState (TypedDict):

```python
class SupervisorState(TypedDict, total=False):
    user_input: str
    task_type: TaskType
    delegations: list[Delegation]
    results: list[dict]
    final_answer: str
    error: str | None
    context: dict
```

## Routing Logic

`classify_intent()` 使用关键词匹配对用户输入进行意图分类：

| TaskType | 关键词示例 | 路由到 |
|----------|-----------|--------|
| upload | 上传, upload, 添加论文 | extractor |
| note | 笔记, note, 总结, summarize | summarizer |
| qa | 问, what, how, why, 回答 | qa |
| compare | 对比, compare, 比较 | comparator |
| search | 搜索, search, 检索 | qa |
| export | 导出, export, markdown | extractor |

默认 fallback: `qa`

## Specialist Agents

所有 Specialist 继承 `BaseSpecialist`:

```python
class BaseSpecialist(ABC):
    name: str
    role: str
    goal: str
    capabilities: list[str]

    @abstractmethod
    def execute(self, task: str, context: dict | None = None) -> AgentResult
```

### QA Agent
- RAG 检索 + CrossEncoder Rerank + 可选 Query Rewrite
- 注入 VectorStore / EmbeddingClient / LLMClient

### Summarizer Agent
- 调用 note_generator 生成 13 节论文笔记
- 支持 paper_id 上下文

### Extractor Agent
- 加载 parsed metadata，提取结构化信息
- 返回 title / abstract / sections 概要

### Comparator Agent
- 调用 paper_compare 服务
- 支持 2-5 篇论文对比

## Collaboration Scenarios

### Scenario A: Full Paper Analysis
```
extract → summarize → qa
```
LangGraph StateGraph 串行执行，每步结果写入 state。

### Scenario B: Multi-Paper Comparison
```
batch_extract → compare
```
先对每篇论文提取信息，再统一对比。

### Scenario C: Interactive Session
多轮对话，每轮通过 Supervisor 路由到不同 Specialist。

## Observability

- **AgentTracer**: 记录每步 span（tool_call / delegation / llm_call），支持嵌套
- **DecisionLogger**: 记录路由决策（分类结果 + 置信度分数 + rationale）
- **API**: `GET /api/traces` 查询历史，`GET /api/traces/stats` 聚合统计
- **UI**: Streamlit "Agent 监控" Tab 可视化时间线和工具统计

## Key Files

| File | Purpose |
|------|---------|
| `app/agents/supervisor.py` | Supervisor graph + classify_intent |
| `app/agents/state.py` | SupervisorState TypedDict + routing map |
| `app/agents/specialists/` | 4 个 Specialist Agent 实现 |
| `app/agents/scenarios/__init__.py` | 3 个协作场景 graph |
| `app/agents/tracing.py` | AgentTracer span 记录 |
| `app/agents/decision_logger.py` | DecisionLogger 路由日志 |
| `app/agents/memory/` | 三层记忆系统 |
| `app/services/memory_store.py` | SQLite 持久化层 |
