# Memory System

## Overview

ResearchAgent 实现三层记忆系统，支持对话持久化、用户偏好学习和语义事实检索。

## Architecture

```
┌─────────────────────────────────────────────┐
│            PaperResearchAgent               │
│  ┌───────────┬───────────┬───────────────┐  │
│  │ShortTerm  │ LongTerm  │   Semantic    │  │
│  │Memory     │ Memory    │   Memory      │  │
│  └─────┬─────┴─────┬─────┴───────┬───────┘  │
│        │           │             │           │
│        └───────────┼─────────────┘           │
│                    ▼                         │
│            ┌─────────────┐                   │
│            │ MemoryStore │                   │
│            │  (SQLite)   │                   │
│            └─────────────┘                   │
└─────────────────────────────────────────────┘
```

## SQLite Schema

```sql
-- 对话管理
conversations (id, title, created_at, updated_at, metadata)
messages (id, conversation_id, role, content, created_at, metadata)

-- 用户偏好
user_preferences (key, value, updated_at)

-- 阅读历史
reading_history (id, paper_id, action, created_at, metadata)

-- 语义事实
semantic_facts (id, content, created_at, metadata)

-- Agent 追踪
agent_traces (id, conversation_id, agent_id, action, input_data, output_data, duration_ms, created_at, metadata)
```

配置: WAL mode + foreign keys ON + thread-local connections

## Three-Tier Memory

### ShortTerm Memory
- 管理对话历史（sliding window）
- `max_messages` 控制窗口大小（默认 50）
- 超出时自动删除最早消息
- API: `create_conversation()`, `add_message()`, `get_context()`

### LongTerm Memory
- 用户偏好 CRUD（key-value）
- 阅读历史记录（paper_id + action）
- 常见问题统计（基于 event metadata 中的 question 字段）
- API: `set_preference()`, `get_recently_read_papers()`, `get_frequent_questions()`

### Semantic Memory
- 向量化事实存储
- 使用 EmbeddingClient 生成 embedding
- 余弦相似度召回
- API: `add_fact()`, `recall(query, top_k)`

## Integration

### Agent Execution
```python
agent = PaperResearchAgent(memory_store=store)
result = agent.execute("问题", conversation_id="conv-123")
# 自动: 创建/复用 conversation → 存 user message → 执行 → 存 assistant message
```

### API Endpoints
- `GET /api/conversations` — 列出对话
- `GET /api/conversations/{id}` — 对话详情 + 消息
- `DELETE /api/conversations/{id}` — 删除对话
- `GET /api/traces` — Agent 执行追踪
- `GET /api/traces/stats` — 追踪统计

### Supervisor Mode
```python
result = agent.execute_supervisor(task, context=ctx, conversation_id="conv-123")
# 同样自动管理对话历史
```

## QA Thread Memory

`QAMemoryService`（`app/services/qa_memory.py`）在 `/qa` 同步问答之上叠加会话记忆，复用同一个 `MemoryStore`：

- **会话与消息**：每轮问答在 `kind="qa"` 的 conversation 下追加一条 user、一条 assistant message；assistant metadata 记录 `status`、`sources`、`rewritten_question`、`rewrite_failed`、`retrieval_time`/`llm_time`。
- **查询改写**：结合会话摘要、最近若干轮、当前 paper 范围与上一轮改写问题，把追问改写成独立检索查询（`build_query_rewrite_prompt`）。改写失败时回退原问题并标记 `rewrite_failed`。
- **摘要更新**：消息数超过阈值且有足够新消息时，用 `build_summary_update_prompt` 增量更新 conversation metadata 的 `summary`，供后续改写复用。
- **会话级 metadata**：`summary`、`summary_message_count`、`summary_updated_at`、`default_paper_id`、`last_rewritten_question`。无 paper 范围的追问不会覆盖已存的 `default_paper_id`。
- **kind 过滤**：`GET /api/conversations?kind=qa` 经 `list_conversations_by_kind`（SQL `json_extract` 过滤）返回 QA 会话，`total` 为该 kind 的真实总数。

## Storage

默认路径: `app/storage/memory.db`

MemoryStore 支持自定义路径:
```python
store = MemoryStore(db_path="/custom/path/memory.db")
```

## Thread Safety

- 每线程独立 SQLite connection（`threading.local()`）
- WAL mode 允许并发读
- 写操作通过 `conn.commit()` 序列化
