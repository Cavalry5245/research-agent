# QA Thread Memory Design

## 背景

ResearchAgent 的 QA 页面已经具备聊天形态，但当前记忆主要停留在前端 `localStorage`。后端 `POST /qa` 每次仍按单轮 RAG 处理，不接收 `conversation_id`，也不会把历史追问用于检索改写或回答生成。

项目已有可复用的记忆基础：

- `app/services/memory_store.py` 提供 SQLite conversations、messages、user_preferences、reading_history、semantic_facts 和 agent_traces。
- `app/routers/conversations.py` 已暴露会话列表、详情和删除 API。
- `app/agents/paper_research_agent.py` 已在 Agent chat 链路中使用 `ShortTermMemory`、`LongTermMemory` 和 `SemanticMemory`。
- `frontend/src/pages/qa/QaPage.tsx` 当前只在浏览器本地保存最近 QA 消息。

本设计将 QA 对话改造成类似 Codex thread 的会话内记忆：稳定 thread id、后端追加保存消息、长对话摘要、最近会话恢复，以及基于历史的追问理解。

## 目标

第一版只做 QA 会话内记忆，不做跨会话科研事实记忆。

核心目标：

- QA 请求支持创建或复用 `conversation_id`。
- 同一 QA conversation 内支持自然追问，例如“它的指标是多少？”。
- 后端持久化 user/assistant 消息和结构化 metadata。
- 运行时使用 `conversation_summary + recent_turns` 理解追问。
- 使用历史改写检索 query，同时把最近对话注入回答 prompt。
- 页面刷新或重新进入 QA 页面后，可以从最近 QA 会话恢复消息和 sources。
- 支持删除整个 QA conversation，作为第一版遗忘能力。

非目标：

- 不做跨会话 semantic memory 召回。
- 不把历史 assistant 回答当成论文事实来源。
- 不做单条消息删除、编辑、分支或复杂 thread 管理。
- 不替换现有 RAG、rerank、parent-child context 回填逻辑。

## 设计原则

1. 论文证据优先：会话历史只用于理解问题，不作为事实依据。最终回答必须基于本轮检索 sources。
2. 复用现有存储：使用 `MemoryStore` 的 conversations/messages，不新增独立数据库。
3. 追加优先：消息原文尽量 append-only；允许更新 conversation metadata 中的 title、summary、default scope。
4. 可降级：query rewrite 或 summary update 失败时，不阻断本轮 QA。
5. 明确遗忘：删除 conversation 后，后端历史和前端当前状态都应消失。

## 推荐方案

采用方案 2：Codex-like QA Thread。

每个 QA conversation 是一个稳定 thread：

- `conversations.metadata.kind = "qa"`。
- user 和 assistant 消息全量保存在 `messages`。
- assistant 消息 metadata 保存 `sources`、`rewritten_question`、scope、耗时和失败状态。
- conversation metadata 保存 `summary`、`summary_updated_at`、`default_paper_id` 等会话状态。
- 运行时使用 `summary + recent_turns`，而不是把完整历史全部塞进 prompt。
- QA 页面显示最近几个 QA thread，用户可以点开继续。

## 架构

新增后端服务层 `QAMemoryService`，位于 FastAPI `/qa` endpoint 和现有 `answer_question()` 之间。

数据流：

```text
User question
  -> POST /qa
  -> QAMemoryService.load_or_create_thread()
  -> QAMemoryService.build_memory_context()
  -> rewrite question from summary + recent turns
  -> answer_question(rewritten_question, existing retriever/reranker/vector store)
  -> save user message
  -> save assistant message with sources + rewritten_question metadata
  -> maybe update conversation summary
  -> return answer + sources + conversation_id + rewritten_question
```

`QAMemoryService` 的职责：

- 创建或校验 QA conversation。
- 读取 `conversation_summary` 和最近 N 轮消息。
- 调用 query rewrite prompt 生成独立检索问题。
- 调用现有 `answer_question()` 完成本轮 RAG。
- 写入本轮 user/assistant 消息。
- 在阈值触发时更新 conversation summary。

`answer_question()` 的职责保持收敛：

- 基于给定 question 检索。
- rerank。
- parent document 回填。
- 构造论文证据 context。
- 调用 LLM 生成 answer。
- 返回 sources 和耗时。

## 数据模型

复用现有 SQLite schema，不新增表。结构化数据写入 `metadata` JSON。

`conversations.metadata` 示例：

```json
{
  "kind": "qa",
  "summary": "本 QA 会话主要围绕 Grounding DINO 的方法、zero-shot 指标和实验设置。用户后续的“它”通常指 Grounding DINO。",
  "summary_updated_at": 1783276800.0,
  "default_paper_id": "paper_001",
  "last_rewritten_question": "Grounding DINO 的 zero-shot 检测指标是多少？"
}
```

user message metadata 示例：

```json
{
  "kind": "qa_user",
  "paper_id": "paper_001",
  "top_k": 5
}
```

assistant message metadata 示例：

```json
{
  "kind": "qa_assistant",
  "paper_id": "paper_001",
  "top_k": 5,
  "rewritten_question": "Grounding DINO 的 zero-shot 检测指标是多少？",
  "sources": [],
  "retrieval_time": 0.42,
  "llm_time": 1.8,
  "rewrite_failed": false
}
```

失败 assistant message metadata 示例：

```json
{
  "kind": "qa_assistant",
  "status": "error",
  "error": "upstream 503",
  "rewritten_question": "Grounding DINO 的 zero-shot 检测指标是多少？",
  "rewrite_failed": false
}
```

## API 设计

### POST /qa

保持现有路由，向后兼容扩展 request 和 response。

请求：

```json
{
  "question": "它的 zero-shot 指标是多少？",
  "paper_id": "paper_001",
  "top_k": 5,
  "conversation_id": "optional-qa-thread-id"
}
```

响应：

```json
{
  "question": "它的 zero-shot 指标是多少？",
  "rewritten_question": "Grounding DINO 的 zero-shot 检测指标是多少？",
  "answer": "...",
  "sources": [],
  "conversation_id": "qa-thread-id"
}
```

规则：

- `conversation_id` 为空时，创建新的 QA conversation。
- `conversation_id` 存在时，必须能找到 conversation，且 metadata `kind` 必须是 `qa`。
- conversation 不存在返回 404。
- conversation 不是 QA 类型返回 400。
- query rewrite 失败时使用原始 `question` 检索，并在 metadata 中记录 `rewrite_failed=true`。
- summary update 失败时只记录日志，不影响本轮 response。

### GET /api/conversations

扩展现有列表接口，支持可选 query 参数：

```text
GET /api/conversations?kind=qa&limit=8&offset=0
```

规则：

- 不传 `kind` 时保持当前行为。
- `kind=qa` 时只返回 metadata 中 `kind == "qa"` 的会话。
- response 可继续使用现有 `ConversationListResponse`，但建议在 `ConversationOut` 中暴露 `metadata`，方便前端显示 thread 类型和默认 scope。

### GET /api/conversations/{id}

复用现有详情接口，扩展 message response 暴露 `metadata`。

前端需要通过 assistant message metadata 恢复：

- sources。
- rewritten question。
- error status。
- scope 信息。

### DELETE /api/conversations/{id}

复用现有删除接口，作为第一版遗忘能力。

规则：

- 删除整个 conversation 和关联 messages。
- QA 页面 `Clear conversation` 应调用该接口。
- 删除后继续使用旧 `conversation_id` 请求 `/qa` 返回 404。

## Prompt 策略

### Query Rewrite Prompt

目标：把当前追问改写成独立、适合检索的科研问题。

输入：

- conversation summary。
- recent turns。
- current question。
- current paper scope。
- previous rewritten question。

输出：

- 单个 `rewritten_question` 字符串。

约束：

- 只补全指代、省略和上下文对象。
- 不引入历史中没有出现的新事实。
- 不回答问题。
- 如果问题已经独立，保持原意并轻微规范化。
- 保持用户语言，中文问题输出中文。

示例：

```text
当前问题：它的 zero-shot 指标是多少？
历史上下文：上一轮讨论 Grounding DINO 的核心方法。
输出：Grounding DINO 的 zero-shot 检测指标是多少？
```

### QA Answer Prompt

现有 `build_qa_prompt(question, context)` 扩展为包含会话记忆：

```text
你是一个严谨的科研论文问答助手。请只根据本轮检索到的论文证据回答用户问题。

会话摘要：
{conversation_summary}

最近对话：
{recent_turns}

用户原始问题：
{question}

用于检索的改写问题：
{rewritten_question}

本轮检索到的论文证据：
{context}

要求：
1. 会话摘要和最近对话只用于理解指代和任务上下文，不能作为论文事实依据。
2. 答案必须来自本轮检索到的论文证据。
3. 如果证据不足，明确说明“根据当前论文片段无法判断”。
4. 如果历史和本轮证据冲突，以本轮证据为准。
5. 回答后列出依据片段编号或来源信息。
```

### Summary Update Prompt

触发条件：

- conversation 消息数超过 8-10 条。
- 距上次 summary update 至少新增若干轮。
- 可作为同步 best-effort 操作，失败不阻断 QA。

输入：

- 旧 summary。
- 最近若干轮 user/assistant。
- 本轮 rewritten question。
- 本轮 sources 的简要引用 metadata。

输出：

- 新 `conversation_summary`。

摘要内容：

- 这段 QA 主要围绕哪篇论文或主题。
- 当前被反复指代的对象。
- 用户关注的维度，例如方法、指标、实验设置、局限。
- 后续追问需要知道的任务上下文。

摘要禁区：

- 不把 assistant answer 改写成无来源的长期事实。
- 不把无法从 sources 支持的内容写成确定结论。
- 不替代论文检索。

## 前端交互

QA 页面保留当前聊天主界面，但将 `localStorage` 降级为当前 `conversation_id` 便利缓存。

新增或调整：

- 最近 QA 会话列表：显示最近 5-8 个 `kind=qa` conversation。
- New chat：清空当前消息并丢弃当前 `conversation_id`，下一次提问创建新 thread。
- 点击历史会话：调用 `GET /api/conversations/{id}` 恢复消息、sources 和 rewritten question。
- 追问：`POST /qa` 请求携带当前 `conversation_id`。
- Clear conversation：调用 `DELETE /api/conversations/{id}`，刷新最近列表。
- assistant 卡片保留 Sources 按钮。
- rewritten query 默认折叠展示，作为 QA 记忆调试信号。

## 错误处理

- conversation 不存在：返回 404，前端提示会话不存在或已删除，并允许新建对话。
- conversation 类型错误：返回 400，避免混用 Agent chat thread。
- query rewrite 失败：用原始问题检索，metadata 记录失败。
- summary update 失败：记录日志，不影响本轮回答。
- QA 回答失败：保存 user message 和 assistant error message，前端恢复失败状态并允许用户重试。
- sources 过大：assistant metadata 可保存完整 SourceItem 的必要字段，避免保存 parent document 全文。

## 测试计划

后端测试：

- `POST /qa` 不带 `conversation_id` 会创建 `kind=qa` conversation，并返回 id。
- 第二轮带同一 `conversation_id` 会追加消息。
- 最近历史会传给 query rewrite prompt。
- `rewritten_question` 用于检索，而不是原始追问。
- assistant message metadata 保存 `sources`、`rewritten_question`、scope、耗时。
- query rewrite 失败时降级原始问题并记录 `rewrite_failed=true`。
- 长会话超过阈值会更新 `conversation_summary`。
- summary update 失败不影响 QA response。
- `GET /api/conversations?kind=qa` 只返回 QA 会话。
- 删除 conversation 后继续使用旧 id 返回 404。

前端测试：

- 首问后保存后端返回的 `conversation_id`。
- 追问时请求携带当前 `conversation_id`。
- 页面能加载最近 QA 会话。
- 点击历史 QA 会话能恢复 messages 和 sources。
- New chat 不继承旧 `conversation_id`。
- Clear conversation 调用 DELETE，而不是只清 `localStorage`。
- rewritten query 可折叠显示。

## 验收场景

最小验收 demo：

1. 用户问：“Grounding DINO 的核心方法是什么？”
2. 系统回答并返回 sources，同时创建 QA conversation。
3. 用户追问：“它的 zero-shot 指标是多少？”
4. 后端将第二问改写为包含 Grounding DINO 和指标语义的独立问题。
5. 第二轮回答基于本轮 sources，而不是只凭上一轮回答。
6. 刷新页面后，可以从最近 QA 会话恢复两轮消息和 sources。
7. 删除该会话后，它从最近列表消失，继续使用旧 id 返回 404。

## 实施切片建议

Slice 1：后端 QA thread 基础

- 扩展 schemas。
- 增加 `QAMemoryService`。
- 扩展 `/qa`。
- 扩展 conversations metadata 输出和 kind filter。
- 添加后端单元测试。

Slice 2：Prompt 和摘要

- 新增 query rewrite prompt。
- 扩展 QA prompt。
- 新增 summary update prompt。
- 添加 rewrite 和 summary 降级测试。

Slice 3：前端 thread UI

- 扩展 QA API client/types。
- 加最近 QA 会话列表、New chat、恢复历史。
- Clear conversation 调后端删除。
- 添加前端测试。

## 风险和缓解

- 风险：历史回答污染科研事实。
  缓解：prompt 明确历史只用于指代理解，事实必须来自本轮 sources。

- 风险：metadata 保存过大。
  缓解：sources 只保存 SourceItem 必要字段和片段摘要，不保存父文档全文。

- 风险：query rewrite 引入新事实。
  缓解：rewrite prompt 限制只补全上下文对象；测试覆盖追问改写。

- 风险：与 Agent chat conversation 混用。
  缓解：使用 `metadata.kind = "qa"` 并在 `/qa` 中校验。

- 风险：长对话摘要不准确。
  缓解：摘要仅作为会话状态，不作为事实证据；旧消息原文保留。

## 决策记录

- 记忆范围选择会话内追问记忆。
- 追问处理选择 query rewrite + prompt history。
- 存储选择后端 `MemoryStore` 持久化。
- UI 选择轻量最近 QA 会话列表。
- 长会话策略选择 summary + recent turns。
- 第一版不做跨会话 semantic memory。
