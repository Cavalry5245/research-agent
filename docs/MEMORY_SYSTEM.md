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
