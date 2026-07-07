# QA Thread Memory — 分支审查待办

> 分支：`codex/qa-thread-memory`
> 审查日期：2026-07-06
> 说明：本文件记录该分支审查中发现的所有问题，按【功能完整性 / 代码冗余与错误 / 项目目录干净度】三类组织。
> 每项带 `file:line` 定位与严重级。解决完一项就勾掉对应 checkbox；**全部解决后删除本文件**。

---

## 一、功能完整性

端到端 happy path 跑通，但实现多处偏离自有设计计划：
- `docs/superpowers/plans/2026-07-06-qa-thread-memory-implementation.md`
- `docs/superpowers/specs/2026-07-06-qa-thread-memory-design.md`

### 后端偏离计划

- [x] **[Major] 响应 `question` 返回改写后问题而非原问题** ✅ `ac883173`
  - `app/services/qa_memory.py:132-140` 用 `dict(result)` 后未覆盖 `question`；`result["question"]` 来自传入 `answer_fn` 的 `rewritten_question`（`qa_memory.py:75`）。
  - `app/main.py:1523` 据此构造 `QAResponse(question=...)`，前端 `QaPage.tsx:252` 又把它当用户原问题渲染。
  - 计划要求返回原问题。无测试断言 `result["question"]`，bug 静默。

- [x] **[Major] `default_paper_id` 在无 paper 追问轮被覆盖为 None** ✅ `ac883173`
  - `app/services/qa_memory.py:123-129` 无条件写入 metadata；缺计划中的 `if paper_id:` 守卫。
  - `app/services/memory_store.py:148-149` merge 覆盖旧值 → 首个 scope-less 追问即丢失 paper scope。

- [x] **[Major] `last_rewritten_question` 存而不读** ✅ `6c6968cf`
  - `qa_memory.py:126` 写入；`_rewrite_question`（`qa_memory.py:173-191`）从不读回，也不传给 `build_query_rewrite_prompt`。死数据 + 计划特性缺失。

- [x] **[Major] 改写/摘要 prompt 丢多个计划输入** ✅ `6c6968cf`
  - `qa_memory.py:182-186` 调 `build_query_rewrite_prompt(question, conversation_summary, recent_turns)` —— 缺 `paper_id`、`previous_rewritten_question`。
  - `qa_memory.py:214-217` 调 `build_summary_update_prompt(existing_summary, turns)` —— 缺 `rewritten_question`、`source_notes`；`_source_notes` helper 未实现。
  - `app/prompts/qa_prompt.py:22-24, 85` 签名比计划窄。

- [x] **[Major] `_format_turns` 丢失 `(rewritten: …)` 标注** ✅ `6c6968cf`
  - `qa_memory.py:233-240` 仅输出 `f"{role}: {content}"`，未附 rewritten 标注，削弱跨轮指代消解。

- [x] **[Major] 改写 prompt 缺"保持用户语言"规则** ✅ `ac883173` + `6c6968cf`（中文 prompt 内置）
  - `app/prompts/qa_prompt.py:27-45` 无语言保持指令；计划要求 `保持用户语言，中文问题输出中文`。中文追问可能被翻成英文检索中文库。

- [x] **[Major] prompt 被改为英文，计划要求中文** ✅ `6c6968cf`
  - `app/prompts/qa_prompt.py:1-103` 全英文，缺中文标记：`会话摘要`、`最近对话`、`本轮检索到的论文证据`、`不能作为论文事实依据`、`不要回答问题`、`只输出改写后的检索问题`、`不要把 assistant answer 改写成无来源的长期事实`。
  - `tests/test_paper_qa.py:68-119` 断言被同步改为英文短语，中文契约不再被验证。

### 前端缺口

- [~] **[Major] 会话摘要从未在 UI 展示** ⏸ 决定：纯内部（summary 喂回改写 prompt，不做 UI）
  - 后端存 `summary` / `summary_message_count` / `default_paper_id` / `last_rewritten_question` 于 `ConversationListItem.metadata`；`frontend/src/pages/qa/QaPage.tsx` 仅渲染 `title`（`:355`）。记忆服务核心产物在 UI 不可见。

- [x] **[Major] `conversationsQuery.error` 与 `deleteMutation.onError` 未处理** ✅ `ac883173`
  - `QaPage.tsx:143-161`：列表拉取失败静默不渲染（`:342` falsy check）；DELETE 失败无反馈、不清本地状态。对比 `papersQuery.error` 有 `<ErrorState>`（`:306-308`）。

- [x] **[Major] KB 页深链失效** ✅ `ac883173`（删链，后端无 KB-scoped QA）
  - `frontend/src/pages/knowledge-base/KnowledgeBasePage.tsx:198` 链到 `/qa?scope=kb&kb_id=...`；`QaPage` 不读 URL 参数，落地为普通 QA 页。

- [ ] **[Minor] 硬编码 `limit=8` 无分页**
  - `frontend/src/api/conversations.ts:8-13`；后端支持 `limit/offset`（默认 50）。超过 8 个会话的老人无法访问。

---

## 二、代码冗余与错误

### 真实 bug

- [x] **[Major] 前端读不存在的 `metadata.question` key** ✅ `cc479080`

- [x] **[Minor] 空结果路径缺 timing 字段** ✅ `cc479080`

- [x] **[Minor] 错误路径 assistant 消息 content 为空** ✅ `cc479080`（+ 关闭测试缺口 T3）

- [x] **[Minor] `qa_endpoint` 缺 `except HTTPException: raise`** ✅ `cc479080`（+ 关闭测试缺口 T4）

- [x] **[Minor] `summary_updated_at` 未跟踪** ✅ `6c6968cf`
  - `qa_memory.py:225-231` 更新 summary / summary_message_count 但不写 `summary_updated_at`（计划含此字段）。

- [x] **[Minor] status 值漂移** ✅ `cc479080`（ok→done）

### 冗余 / 死代码

- [x] **[Minor] `_metadata_dict` 重复三份** ✅ `2a833174`（抽 `parse_metadata` 到 memory_store 模块级）

- [x] **[Minor] 死导入 `Depends`** ✅ `2a833174`

- [x] **[Minor] 每轮两次 `update_conversation_metadata`** ✅ `2a833174`（`_maybe_update_summary` 返回字段，ask 单次合并写入）

- [x] **[Minor] `list_conversations_by_kind` 全表加载后 Python 过滤** ✅ `2a833174`（改用 `json_extract` SQL WHERE）

- [x] **[Minor] `ConversationListResponse.total` 语义误导** ✅ `2a833174`（加 count 方法，返回真实总数）

- [x] **[Nit] 前端 `localStorage` 写 `activeConversationId` 冗余** ✅ `2a833174`（删 6 处显式调用，保留 effect 单一来源）

- [x] **[Nit] `_format_turns` 不折叠空白** ✅ `6c6968cf`（`" ".join(...split())`）

- [ ] **[Nit] `_maybe_update_summary` 用 `messages[summary_message_count:]`**
  - 取至多 10000 条后切片；计划限 `recent_message_limit`，长会话会把全部 post-summary 历史塞进摘要 prompt。

### 测试缺口

- [x] **[Major] 无测试覆盖 M1（`question` 回错值）** ✅ `ac883173` — service+API 均补断言
- [x] **[Major] 无测试覆盖 M2（`default_paper_id` 被覆盖）** ✅ `ac883173` — 专项回归测试
- [x] **[Major] 无 `answer_fn` 异常路径测试** ✅ `cc479080`
- [x] **[Major] 无 `/qa` 400 非 QA 会话拒绝的 API 级测试** ✅ `cc479080`
- [ ] **[Minor] 无 rewrite/summary 失败的 API 级测试** — 仅 unit 级。
- [x] **[Minor] 无 `previous_rewritten_question` / `paper_id` 在改写 prompt 中的断言** ✅ `6c6968cf`
- [x] **[Minor] 无 `source_notes` / `rewritten_question` 在摘要 prompt 中的断言** ✅ `6c6968cf`
- [ ] **[Minor] `test_qa_endpoint_reuses_conversation_id` 不验证改写上下文** — `test_qa_thread_api.py:68-94`。
- [x] **[Minor] 前端无 QA mutation `onError` 测试** ✅ `ac883173` — 列表/delete 错误分支 3 个测试
- [ ] **[Minor] 前端无 `paper_id` 从已存会话恢复的断言** — `QaPage.test.tsx:175` 只查 `top_k`。
- [ ] **[Minor] 前端无会话列表首答后刷新/高亮/摘要展示/多会话/`loadConversation.catch`/`MAX_VISIBLE_MESSAGES` 截断/score 格式化测试。**

---

## 三、项目目录干净度

git 工作区干净，但不满足 CLAUDE.md cleanliness 规则。

### Major

- [ ] **`.codex/plans/current-plan.md` + `.codex/tasks/current-tasks.md` 过时**
  - 内容为 M3/M4 MCP Hub / Obsidian Knowledge Pack 里程碑（已 ship），与本分支无关。平行于已删的 `.claude/` 那两份。

- [ ] **CLAUDE.md 规定的 pre-edit 流程已坏**
  - `CLAUDE.md` 要求编辑前读 `.claude/plans/current-plan.md` 与 `.claude/tasks/current-tasks.md`，二者均已删。需更新 CLAUDE.md 指令或重建权威 plan/task 路径。

- [ ] **4 个死 hook 脚本**
  - `.claude/hooks/block_dangerous_bash.py`、`.claude/hooks/check_task_completion.py`、`.codex/hooks/block_dangerous_bash.py`、`.codex/hooks/check_task_completion.py` —— tracked 但 settings 的 `hooks` 已清空。接回或删。

- [ ] **`.superpowers/sdd/` 25 个陈旧 SDD 产物**
  - `progress.md` + `task-{1..12}-report.md` + `task-{1..12}-review-package.txt`，2026-06-21 research-pipeline MVP 记录，无引用。纯历史包袱。

- [ ] **gitignore 自相矛盾**
  - `.gitignore:36-38` ignore `.codex/`/`.claude/`/`.agents/`，但这俩目录下共 11 个文件 tracked（ignore 对已跟踪文件无效）。要么 untrack 要么删 ignore 行。

- [ ] **repo 根目录字面 `~/` 目录**
  - 含 `.cache/`，疑为 `mkdir ~` 未展开。CLAUDE.md 明令禁止。gitignored 但仍在工作树。

### Minor

- [ ] **`app/storage/parent_docs/` 空且无 `.gitkeep`**
  - 兄弟目录（papers/notes/vector_db/metadata/analytics/logs）都有；fresh clone 不会重建此 RAG 存储目录。

- [ ] **`.claude/` 残留过时计划/任务**
  - `.claude/plans/pdf-rag-optimization-plan.md`、`.claude/tasks/phase6-detailed-tasks.md`、`phase6-quick-guide.md`、`phase6-tasks-part2.md`、`task_2.3_completion_report.md`。

- [ ] **多套并行 plan/task 目录**
  - Plans：`.claude/plans`、`.codex/plans`、`docs/plans`（空）、`docs/superpowers/plans`。
  - Tasks：`.claude/tasks`、`.codex/tasks`。应合并为单一权威位置。

- [ ] **`docs/CRON_WORK_LOG.md` 2205 行运行日志 tracked 在源码树**

- [ ] **`docs/MEMORY_SYSTEM.md` 未更新本分支特性**
  - 仅文档化旧 3-tier agent memory，未提及 `QAMemoryService` / conversation schema / QA thread memory。本分支自身功能文档漂移。

- [ ] **`docs/ASYNC_TASKS.md` 无 QA-thread 条目**

- [ ] **`.paper-search-download-check/` 空目录残留**（gitignored）

- [ ] **`app/agents/scenarios/` 仅为 re-export 门面**
  - 只 `__init__.py` 转发 `app/agents/specialists/`；候选合并进 `specialists/`。

### Nit

- [ ] **工作树测试产物**（均 gitignored）：`.coverage`、`htmlcov/`、`.pytest_cache/`、34 个 `__pycache__/`。CLAUDE.md 严格读法下应清理。

---

## 解决进度

- 后端 bug（确定性）：第一节 M1/M2 + 第二节"真实 bug"小节
- 计划对齐（需拍板是否认同计划）：第一节其余 Major + 测试缺口
- 目录清理：第三节
- 前端补全：第一节前端缺口 + 第二节前端测试缺口

**全部勾完后删除本文件。**
