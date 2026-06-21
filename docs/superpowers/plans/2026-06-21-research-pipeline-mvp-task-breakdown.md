# Research Pipeline MVP Task Breakdown

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` when implementing these tasks. Each task is intentionally small and has explicit goal, input, output, files, acceptance criteria, and test method.

**Goal:** Break the Research Pipeline MVP into implementation tasks that can be assigned, tested, and reviewed independently.

**Architecture:** Add a new `app/research_pipeline/` path and `/research-pipeline` API while keeping the existing `/research-runs` Zotero knowledge-pack workflow unchanged. Persist pipeline state in SQLite, reuse existing Zotero/PDF/LLM/embedding/vector-store services, and extend the existing React shell with Workflow pages.

**Tech Stack:** FastAPI, Pydantic v2, SQLite, pytest, existing ResearchAgent services, Vite, React, TypeScript, TanStack Query, Vitest.

---

## Scope Boundary

This task breakdown implements the PRD at:

`docs/superpowers/specs/2026-06-21-research-pipeline-mvp-prd.md`

It follows the technical design at:

`docs/superpowers/specs/2026-06-21-research-pipeline-mvp-technical-design.md`

Do not delete Streamlit, do not remove `/research-runs`, and do not rewrite existing backend services when a narrow adapter can reuse them.

## Slice 1: Backend Skeleton And SQLite Store

### Task 1: Create Research Pipeline Package Skeleton

**任务目标:** 建立新 pipeline 的包结构，明确新旧 workflow 边界。

**输入:** 技术方案中的 `app/research_pipeline/` 模块设计。

**输出:** 可 import 的空包、子包和最小模块文件。

**涉及文件:**

- Create: `app/research_pipeline/__init__.py`
- Create: `app/research_pipeline/schemas.py`
- Create: `app/research_pipeline/store.py`
- Create: `app/research_pipeline/service.py`
- Create: `app/research_pipeline/runner.py`
- Create: `app/research_pipeline/events.py`
- Create: `app/research_pipeline/router.py`
- Create: `app/research_pipeline/agents/__init__.py`
- Create: `app/research_pipeline/sources/__init__.py`
- Create: `app/research_pipeline/indexing/__init__.py`
- Create: `app/research_pipeline/evaluation/__init__.py`

**验收标准:**

- `import app.research_pipeline` 成功。
- 不修改 `app/research_workflow/` 的旧 schema 和 service。
- 新包中每个文件只放本 slice 必需的最小结构。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -c "import app.research_pipeline; import app.research_pipeline.schemas; import app.research_pipeline.store"
```

Expected: command exits with code 0.

### Task 2: Define Core Pipeline Schemas

**任务目标:** 定义 run、stage、event、candidate、PaperCard、report、claim 等核心 Pydantic schema。

**输入:** PRD 第 7 节数据模型和技术方案第 7 节核心 schema。

**输出:** 后端可复用的 Pydantic 模型和 Literal 状态枚举。

**涉及文件:**

- Modify: `app/research_pipeline/schemas.py`
- Test: `tests/research_pipeline/test_schemas.py`

**验收标准:**

- 支持 `source_mode`: `web_search`、`zotero_only`、`hybrid`。
- 支持 run status: `queued`、`running`、`completed`、`failed`、`cancelled`、`degraded`。
- 支持 stage status: `queued`、`running`、`completed`、`failed`、`degraded`。
- `ResearchRunCreateRequest` 默认 `max_reader_papers=8`、`reader_concurrency=3`。
- `max_reader_papers` 限制为 3-15。
- `ReportClaim.verification_status` 包含 PRD 要求的五种状态。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_schemas.py -q
```

Expected: schema defaults, validation ranges, and allowed status tests pass.

### Task 3: Implement SQLite Schema Initialization

**任务目标:** 初始化 research pipeline SQLite 数据库和核心表。

**输入:** 技术方案第 6 节 SQLite 表结构。

**输出:** 可重复执行的 schema 初始化逻辑。

**涉及文件:**

- Modify: `app/research_pipeline/store.py`
- Test: `tests/research_pipeline/test_store_schema.py`

**验收标准:**

- 创建 `research_runs`、`research_run_stages`、`research_run_events`、`research_plans`、`paper_candidates`、`paper_cards`、`paper_evidence`、`research_reports`、`report_claims`。
- 初始化函数可重复调用，不重复报错。
- 测试使用临时 SQLite 文件，不写入真实 `app/storage/metadata`。
- 所有表至少包含技术方案中列出的核心字段。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_store_schema.py -q
```

Expected: temporary database contains all required tables and repeated initialization passes.

### Task 4: Implement Run And Stage Store CRUD

**任务目标:** 提供创建 run、读取 run、列出 run、更新 run status、更新 stage、写 event 的 store 方法。

**输入:** Task 2 schema 和 Task 3 SQLite 表。

**输出:** `ResearchPipelineStore` 可被 service 和 runner 调用。

**涉及文件:**

- Modify: `app/research_pipeline/store.py`
- Test: `tests/research_pipeline/test_store_runs.py`

**验收标准:**

- `create_run()` 会写入 run，并初始化五个 stage：planner、retriever、reader、synthesis、harness。
- `get_run_detail()` 返回 run、stages、events 的组合数据。
- `list_runs(limit=...)` 按 `created_at` 倒序返回。
- `append_event()` 保存 stage、level、message、payload。
- 更新不存在的 run 返回明确异常或 `None`，不静默成功。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_store_runs.py -q
```

Expected: CRUD lifecycle tests pass against temporary SQLite database.

### Task 5: Add Research Pipeline Service

**任务目标:** 在 store 之上提供业务入口，负责创建 run、读取详情、取消 run 和组装响应。

**输入:** `ResearchPipelineStore`、`ResearchRunCreateRequest`。

**输出:** `ResearchPipelineService`。

**涉及文件:**

- Modify: `app/research_pipeline/service.py`
- Test: `tests/research_pipeline/test_service.py`

**验收标准:**

- `create_run()` 校验参数并创建 queued run。
- `create_run()` 可以接收可注入的 runner 调度函数，便于测试不启动真实后台任务。
- `cancel_run()` 只允许取消 queued/running/degraded run。
- completed/failed/cancelled run 再取消时返回冲突错误。
- `get_run_detail()` 返回前端需要的 stages、events、candidates、paper_cards、report summary 空数组结构。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_service.py -q
```

Expected: service validation, cancellation, and response-shape tests pass.

### Task 6: Add Minimal FastAPI Router

**任务目标:** 暴露 `/research-pipeline` 的最小 API。

**输入:** `ResearchPipelineService`。

**输出:** 可通过 FastAPI TestClient 调用的 router。

**涉及文件:**

- Modify: `app/research_pipeline/router.py`
- Modify: `app/main.py`
- Test: `tests/research_pipeline/test_router.py`

**验收标准:**

- `POST /research-pipeline/runs` 创建 run。
- `GET /research-pipeline/runs` 列出 runs。
- `GET /research-pipeline/runs/{run_id}` 返回 detail。
- `POST /research-pipeline/runs/{run_id}/cancel` 取消 run。
- 不改变旧 `/research-runs` 路由行为。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_router.py tests/test_research_run_router.py -q
```

Expected: new router tests pass and existing research run router tests still pass.

### Task 7: Implement Stub Pipeline Runner

**任务目标:** 用 fake agents 串起完整 stage 状态流，证明异步 workflow 状态机能跑通。

**输入:** run_id、store、五个 stub stage。

**输出:** 一个不依赖 LLM、外部 API、PDF 的 completed run。

**涉及文件:**

- Modify: `app/research_pipeline/runner.py`
- Modify: `app/research_pipeline/events.py`
- Test: `tests/integration/test_research_pipeline_stub_e2e.py`

**验收标准:**

- runner 按顺序执行 planner、retriever、reader、synthesis、harness。
- 每个 stage 都经历 running 到 completed。
- 每个 stage 至少写一条 event。
- runner 完成后 run status 为 completed。
- runner 失败时 run status 为 failed，并记录 failed stage 与 error。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/integration/test_research_pipeline_stub_e2e.py -q
```

Expected: stub run lifecycle test passes without network and without LLM key.

## Slice 2: Real Retriever Sources

### Task 8: Add PaperCandidate Normalizer And Dedupe

**任务目标:** 将 Zotero、Semantic Scholar、arXiv 的原始数据归一化为统一 `PaperCandidate`，并实现去重。

**输入:** 三类来源的 raw payload。

**输出:** `PaperCandidate` 列表。

**涉及文件:**

- Create: `app/research_pipeline/sources/normalizer.py`
- Modify: `app/research_pipeline/schemas.py`
- Test: `tests/research_pipeline/test_candidate_normalizer.py`

**验收标准:**

- DOI 优先作为去重 key。
- 无 DOI 时使用 arXiv ID、Semantic Scholar ID、normalized title。
- 作者、年份、venue、abstract、pdf_url、local_pdf_path 字段能正确映射。
- Zotero seed 论文的 `source` 为 `zotero`。
- 输入缺少可选字段时不会崩溃。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_candidate_normalizer.py -q
```

Expected: mapping and dedupe tests pass.

### Task 9: Add Zotero Source Adapter

**任务目标:** 复用现有 Zotero local API 客户端，给 pipeline 提供 collection 列表和 candidate 导入能力。

**输入:** Zotero collection key。

**输出:** Zotero collections 和 Zotero `PaperCandidate`。

**涉及文件:**

- Create: `app/research_pipeline/sources/zotero.py`
- Modify: `app/research_pipeline/router.py`
- Test: `tests/research_pipeline/test_zotero_source.py`

**验收标准:**

- 调用 `ZoteroLocalHttpClient.list_collections()` 获取 collection 列表。
- 调用 `ZoteroLocalHttpClient.list_collection_items()` 获取 collection items。
- 本地 PDF 附件映射到 `local_pdf_path`。
- 无 PDF 时仍生成 candidate，但 `local_pdf_path=None`。
- Zotero API 失败时返回明确错误，router 不吞掉错误。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_zotero_source.py -q
```

Expected: mocked Zotero client tests pass.

### Task 10: Add Semantic Scholar Source Adapter

**任务目标:** 为 pipeline 提供 Semantic Scholar 搜索能力，并输出统一 candidate。

**输入:** Planner query、limit、year range。

**输出:** Semantic Scholar `PaperCandidate`。

**涉及文件:**

- Create: `app/research_pipeline/sources/semantic_scholar.py`
- Test: `tests/research_pipeline/test_semantic_scholar_source.py`

**验收标准:**

- 支持注入 fake client，测试不访问网络。
- 映射 `paperId`、title、authors、year、venue、abstract、citationCount、openAccessPdf。
- timeout 或 client exception 会返回 source-level failure，runner 可将 run 标记 degraded。
- 不使用 LLM 来选择搜索结果。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_semantic_scholar_source.py -q
```

Expected: candidate mapping and failure-path tests pass.

### Task 11: Add arXiv Source Adapter

**任务目标:** 为 pipeline 提供 arXiv 搜索能力，并补充稳定 PDF URL。

**输入:** Planner query、max_results。

**输出:** arXiv `PaperCandidate`。

**涉及文件:**

- Create: `app/research_pipeline/sources/arxiv.py`
- Test: `tests/research_pipeline/test_arxiv_source.py`

**验收标准:**

- 支持注入 fake client。
- 映射 arXiv ID、title、authors、year、abstract、url、pdf_url。
- 可处理空结果。
- source adapter 失败不抛到整个 process 顶层，而是返回可记录的错误。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_arxiv_source.py -q
```

Expected: arXiv mapping and empty/failure tests pass.

### Task 12: Implement Retriever Agent

**任务目标:** 根据 `source_mode` 调用来源 adapter，写入 candidates，并执行候选集排序。

**输入:** run、initial plan、source mode、source adapters。

**输出:** `paper_candidates` 表记录和 retriever stage events。

**涉及文件:**

- Create: `app/research_pipeline/agents/retriever.py`
- Modify: `app/research_pipeline/store.py`
- Modify: `app/research_pipeline/runner.py`
- Test: `tests/research_pipeline/test_retriever_agent.py`

**验收标准:**

- `web_search` 调用 Semantic Scholar 和 arXiv。
- `zotero_only` 只调用 Zotero。
- `hybrid` 先保留 Zotero seed，再合并 Web Search。
- source 失败会写 event 并允许 run degraded。
- 候选论文可通过 `GET /research-pipeline/runs/{run_id}` 查看。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_retriever_agent.py -q
```

Expected: source mode routing, candidate persistence, and degraded tests pass.

## Slice 3: Planner, Reader, And PaperCard

### Task 13: Implement Planner Agent With Deterministic Fallback

**任务目标:** 生成初始检索计划和候选选择计划；LLM 失败时能 deterministic fallback。

**输入:** 用户问题、source mode、候选论文列表。

**输出:** `research_plans` 中的 `initial` 和 `candidate_selection` plan。

**涉及文件:**

- Create: `app/research_pipeline/agents/planner.py`
- Modify: `app/research_pipeline/store.py`
- Test: `tests/research_pipeline/test_planner_agent.py`

**验收标准:**

- LLM 返回合法 JSON 时保存 normalized question、subquestions、queries、relevance criteria。
- LLM 不可用或 JSON 解析失败时使用原问题作为 query fallback。
- candidate selection plan 最多选择 `max_reader_papers` 篇。
- 第二阶段不重新触发外部检索。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_planner_agent.py -q
```

Expected: LLM success path, fallback path, and selection limit tests pass.

### Task 14: Add PaperCard Store Methods

**任务目标:** 持久化 Reader 输出的 PaperCard 和 evidence。

**输入:** `PaperCard`、evidence snippets。

**输出:** `paper_cards` 和 `paper_evidence` 表记录。

**涉及文件:**

- Modify: `app/research_pipeline/store.py`
- Test: `tests/research_pipeline/test_store_paper_cards.py`

**验收标准:**

- 可保存 completed、degraded、failed PaperCard。
- evidence 可按 run_id、paper_id、paper_card_id 查询。
- `get_run_detail()` 返回 PaperCards 和 evidence summary。
- JSON 字段保持 UTF-8，不转义中文内容。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_store_paper_cards.py -q
```

Expected: PaperCard persistence and detail response tests pass.

### Task 15: Implement Abstract-Only Reader

**任务目标:** 在没有 PDF 或 PDF 暂不下载时，根据 title、abstract、metadata 生成 degraded PaperCard。

**输入:** `PaperCandidate`、reading focus。

**输出:** `PaperCard(extraction_mode="abstract_only")`。

**涉及文件:**

- Create: `app/research_pipeline/agents/reader.py`
- Test: `tests/research_pipeline/test_reader_abstract_only.py`

**验收标准:**

- 无 PDF 的 candidate 生成 `extraction_mode=abstract_only`。
- 不伪造 page、section 或 table evidence。
- LLM 不可用时生成结构化 fallback card，字段至少包含 title、abstract-derived summary、status degraded。
- error 或 degraded reason 写入 PaperCard。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_reader_abstract_only.py -q
```

Expected: abstract-only and no-fake-evidence tests pass.

### Task 16: Implement PDF Reader Path

**任务目标:** 对有本地 PDF 的 candidate 复用现有 PDF parser 生成 PaperCard。

**输入:** `PaperCandidate.local_pdf_path`。

**输出:** `PaperCard(extraction_mode="pdf")` 和 evidence snippets。

**涉及文件:**

- Modify: `app/research_pipeline/agents/reader.py`
- Test: `tests/research_pipeline/test_reader_pdf.py`

**验收标准:**

- 使用 `app.services.pdf_parser.parse_pdf()` 解析本地 PDF。
- 解析失败时该论文 PaperCard 标记 failed 或 degraded，不让整个 run failed。
- 成功时 evidence 至少包含 snippet 和 section/page 中可用字段。
- Reader 不写入旧 paper metadata JSON，除非通过现有 parser 明确需要临时文件。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_reader_pdf.py -q
```

Expected: parser success and parser failure isolation tests pass.

### Task 17: Add Reader Concurrency And Failure Isolation

**任务目标:** 并发处理 Reader 论文，并保证单篇失败不会终止整个 run。

**输入:** selected candidates、reader_concurrency。

**输出:** 多个 PaperCards 和 reader stage summary。

**涉及文件:**

- Modify: `app/research_pipeline/agents/reader.py`
- Modify: `app/research_pipeline/runner.py`
- Test: `tests/research_pipeline/test_reader_concurrency.py`

**验收标准:**

- 默认并发数为 3。
- 并发数来自 run request，受 schema 校验保护。
- 单篇失败会保存 failed PaperCard 和 event。
- 至少一篇成功时 reader stage 可以 completed 或 degraded。
- 全部失败时 reader stage failed，run failed。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_reader_concurrency.py -q
```

Expected: concurrency limit and failure isolation tests pass.

## Slice 4: Report And Harness

### Task 18: Implement Report Store Methods

**任务目标:** 保存 Markdown report 和 claim verification 结果。

**输入:** Markdown report、ReportClaim 列表。

**输出:** `research_reports` 和 `report_claims` 表记录。

**涉及文件:**

- Modify: `app/research_pipeline/store.py`
- Test: `tests/research_pipeline/test_store_reports.py`

**验收标准:**

- 每个 run 可保存一个当前 report。
- report markdown 可完整读取。
- claim status 可按 run_id 汇总。
- `GET /research-pipeline/runs/{run_id}/report` 所需数据可从 store 组装。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_store_reports.py -q
```

Expected: report persistence and claim summary tests pass.

### Task 19: Implement Synthesis Agent

**任务目标:** 根据 plan 和 PaperCards 生成固定 8 节 Markdown 研究报告。

**输入:** initial plan、candidate selection plan、PaperCards、evidence。

**输出:** Markdown report。

**涉及文件:**

- Create: `app/research_pipeline/agents/synthesis.py`
- Test: `tests/research_pipeline/test_synthesis_agent.py`

**验收标准:**

- 报告包含 8 个 PRD 指定章节。
- References 只包含进入 Reader 的论文。
- LLM 不可用时可以生成 deterministic skeleton report，明确标记缺少综合结论。
- 已知 PaperCard claim 会以 `[CITE:paper_id]` 形式引用。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_synthesis_agent.py -q
```

Expected: report structure, citation, and fallback tests pass.

### Task 20: Implement Rule-First Harness

**任务目标:** 校验报告关键 claim 的 citation 和 evidence 状态。

**输入:** Markdown report、PaperCards、paper_evidence。

**输出:** `ReportClaim` 列表和 Harness summary。

**涉及文件:**

- Create: `app/research_pipeline/agents/harness.py`
- Test: `tests/research_pipeline/test_harness_rules.py`

**验收标准:**

- 没有 citation 的关键 claim 标记 `unverified`。
- citation id 不属于 Reader PaperCard 时标记 `unverified`。
- 数字型 claim 缺少 evidence 时标记 `numeric_trace_missing`。
- evidence 仅来自 abstract-only PaperCard 时默认不高于 `weak`。
- Harness 不删除报告原文。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_harness_rules.py -q
```

Expected: unverified, numeric trace, weak evidence, and no-mutation tests pass.

### Task 21: Expose Report API

**任务目标:** 提供报告预览和 Markdown 下载 API。

**输入:** stored report 和 claim summary。

**输出:** JSON report response 和 `.md` 文件响应。

**涉及文件:**

- Modify: `app/research_pipeline/router.py`
- Modify: `app/research_pipeline/service.py`
- Test: `tests/research_pipeline/test_report_router.py`

**验收标准:**

- `GET /research-pipeline/runs/{run_id}/report` 返回 markdown、claims、summary。
- `GET /research-pipeline/runs/{run_id}/report.md` 返回 `text/markdown`。
- report 不存在时返回 404。
- completed report 的 claim summary 数量正确。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_report_router.py -q
```

Expected: report preview, download, and 404 tests pass.

## Slice 5: React Workflow UI

### Task 22: Add Frontend Research Pipeline API Client

**任务目标:** 在 React 中封装 `/research-pipeline` API。

**输入:** 后端 API contract。

**输出:** typed TypeScript API client。

**涉及文件:**

- Create: `frontend/src/api/researchPipeline.ts`
- Test: `frontend/src/api/researchPipeline.test.ts`

**验收标准:**

- 支持 list runs、create run、get run detail、cancel run、get report、list Zotero collections。
- TypeScript 类型使用 snake_case，与后端 JSON 保持一致。
- API error 复用现有 `ApiError`。

**测试方式:**

```powershell
cd frontend
npm test -- src/api/researchPipeline.test.ts
npm run lint
```

Expected: API client tests and typecheck pass.

### Task 23: Implement Workflow Run List Page

**任务目标:** 将 `/workflow` 从占位页替换为 research pipeline run list。

**输入:** `getResearchPipelineRuns()`。

**输出:** Run list、状态、失败原因和 New Run 入口。

**涉及文件:**

- Modify: `frontend/src/pages/workflow/WorkflowPage.tsx`
- Test: `frontend/src/pages/workflow/WorkflowPage.test.tsx`

**验收标准:**

- 显示 run question、status、source_mode、created_at、最近错误。
- 空列表显示可操作 empty state。
- 点击 New Run 进入 `/workflow/new`。
- 点击 run 进入 `/workflow/:runId`。

**测试方式:**

```powershell
cd frontend
npm test -- src/pages/workflow/WorkflowPage.test.tsx
npm run lint
```

Expected: loading, empty, success, and navigation tests pass.

### Task 24: Implement New Run Page

**任务目标:** 提供创建 research run 的表单。

**输入:** 用户问题、source mode、Zotero collection、参数配置。

**输出:** 创建 run，并跳转到 run detail。

**涉及文件:**

- Create: `frontend/src/pages/workflow/NewRunPage.tsx`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/pages/workflow/NewRunPage.test.tsx`

**验收标准:**

- 支持 Web Search、Zotero Only、Hybrid。
- 默认 `max_reader_papers=8`，范围 3-15。
- 默认 `reader_concurrency=3`。
- Zotero collection selector 加载失败时仍可手动输入 collection key。
- submit 成功后跳转 `/workflow/:runId`。

**测试方式:**

```powershell
cd frontend
npm test -- src/pages/workflow/NewRunPage.test.tsx
npm run lint
```

Expected: form validation, Zotero fallback, submit, and redirect tests pass.

### Task 25: Implement Run Detail Page And Polling

**任务目标:** 展示 run 的实时状态和中间产物。

**输入:** run_id。

**输出:** Run header、Agent Timeline、events、candidates、PaperCards、Harness Summary、Markdown Preview。

**涉及文件:**

- Create: `frontend/src/pages/workflow/RunDetailPage.tsx`
- Modify: `frontend/src/app/router.tsx`
- Test: `frontend/src/pages/workflow/RunDetailPage.test.tsx`

**验收标准:**

- queued/running/degraded run 每 2 秒轮询。
- completed/failed/cancelled run 停止轮询。
- failed/degraded 显示 stage 和 reason。
- run 未完成时也显示已有 candidates、PaperCards、events。
- report 存在时显示 Markdown Preview。

**测试方式:**

```powershell
cd frontend
npm test -- src/pages/workflow/RunDetailPage.test.tsx
npm run lint
```

Expected: polling, stop-polling, partial artifact, and failure display tests pass.

### Task 26: Add Workflow Components

**任务目标:** 将 Run Detail 中的复杂 UI 拆成可测试组件。

**输入:** run detail response。

**输出:** 可复用 workflow components。

**涉及文件:**

- Create: `frontend/src/components/workflow/AgentTimeline.tsx`
- Create: `frontend/src/components/workflow/CandidatePaperTable.tsx`
- Create: `frontend/src/components/workflow/PaperCardPanel.tsx`
- Create: `frontend/src/components/workflow/HarnessSummary.tsx`
- Create: `frontend/src/components/workflow/MarkdownReportPreview.tsx`
- Test: `frontend/src/components/workflow/AgentTimeline.test.tsx`
- Test: `frontend/src/components/workflow/HarnessSummary.test.tsx`
- Test: `frontend/src/components/workflow/MarkdownReportPreview.test.tsx`

**验收标准:**

- Agent Timeline 展示五个 stage 的 status 和 message。
- Candidate table 展示 source、title、year、selected_for_reader。
- PaperCard panel 展示 extraction_mode、method、datasets、metrics、limitations。
- Harness Summary 展示 unsupported、weak、numeric trace missing、conflict detected 数量。
- Markdown Preview 支持复制和下载入口。

**测试方式:**

```powershell
cd frontend
npm test -- src/components/workflow
npm run lint
```

Expected: component tests and typecheck pass.

## Slice 6: Evaluation Harness

### Task 27: Add Seed Evaluation Dataset Format

**任务目标:** 建立 3 个 seed research questions 的 gold annotation 文件格式和 loader。

**输入:** PRD 第 10.4 节 Gold Annotation Template。

**输出:** seed evaluation dataset 和 loader。

**涉及文件:**

- Create: `app/research_pipeline/evaluation/seed_loader.py`
- Create: `app/evaluation/datasets/research_pipeline_seed.jsonl`
- Test: `tests/research_pipeline/test_evaluation_seed_loader.py`

**验收标准:**

- loader 校验 question、gold_papers、gold_report_points、gold_claims。
- JSONL 中至少包含 3 条 seed question。
- 每条 seed question 至少有 5 篇 gold papers、5 个 gold report points、5 条 gold claims。
- 缺字段时测试能给出明确错误。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_evaluation_seed_loader.py -q
```

Expected: loader validation and dataset shape tests pass.

### Task 28: Implement Evaluation Metrics

**任务目标:** 根据 pipeline run 和 gold annotations 计算 MVP 指标。

**输入:** run detail、report claims、gold seed item。

**输出:** metrics dict 和 markdown summary。

**涉及文件:**

- Create: `app/research_pipeline/evaluation/metrics.py`
- Test: `tests/research_pipeline/test_evaluation_metrics.py`

**验收标准:**

- 计算 `workflow_completion_rate`。
- 计算 `stage_success_rate`。
- 计算 `claim_verification_coverage`。
- 计算 `unsupported_claim_rate`。
- 计算 `report_point_recall`。
- 计算 `gold_claim_coverage`。
- 空 report 或 failed run 不导致指标脚本崩溃。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_evaluation_metrics.py -q
```

Expected: metric formula and empty/failure tests pass.

### Task 29: Add MVP Gate Report Script

**任务目标:** 一键生成 MVP gate report，用于判断 demo 是否达标。

**输入:** seed dataset、run ids 或 stored evaluation outputs。

**输出:** JSON 和 Markdown gate report。

**涉及文件:**

- Create: `app/research_pipeline/evaluation/run_mvp_gate.py`
- Create: `app/evaluation/reports/research_pipeline_mvp_gate.md`
- Test: `tests/research_pipeline/test_mvp_gate_report.py`

**验收标准:**

- 报告包含 PRD 第 10.3 节 MVP Gate 条件。
- 至少输出 completion、time_to_report、reader_paper_count、claim verification coverage。
- gate 未达标时返回非通过状态，但保留详细原因。
- 脚本支持使用 fixture 数据运行，不要求真实外部 API。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_mvp_gate_report.py -q
```

Expected: report generation and pass/fail gate tests pass.

## Cross-Slice Verification

### Task 30: Run Backend Regression Set

**任务目标:** 确认新 pipeline 没有破坏现有 ResearchAgent 后端关键路径。

**输入:** 所有 backend slices。

**输出:** 回归测试结果。

**涉及文件:**

- Verify only; no planned source changes.

**验收标准:**

- research pipeline tests pass。
- existing `/system/status` test pass。
- existing `/research-runs` tests pass。
- Streamlit source-token guard test pass。

**测试方式:**

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline tests/test_system_status_endpoint.py tests/test_research_run_router.py tests/test_research_workflow_ui_import.py -q
```

Expected: all selected backend regression tests pass.

### Task 31: Run Frontend Regression Set

**任务目标:** 确认 React Workflow UI 与已有 dashboard shell 一起通过测试。

**输入:** 所有 frontend workflow slices。

**输出:** Vitest、TypeScript、build 结果。

**涉及文件:**

- Verify only; no planned source changes.

**验收标准:**

- API client tests pass。
- Workflow page tests pass。
- Dashboard existing tests still pass。
- `npm run lint` pass。
- `npm run build` pass。

**测试方式:**

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Expected: frontend test, typecheck, and production build pass.

## Implementation Order

1. Task 1-7: backend skeleton first.
2. Task 8-12: real retriever sources.
3. Task 13-17: planner and reader.
4. Task 18-21: report and harness.
5. Task 22-26: React Workflow UI.
6. Task 27-29: evaluation harness.
7. Task 30-31: final regression.

## Review Checklist

- 每个任务都有任务目标、输入、输出、涉及文件、验收标准、测试方式。
- 每个 slice 都能产生可测试的软件状态。
- 新 pipeline 不覆盖旧 `/research-runs`。
- 无批量删除文件或目录的操作。
- 所有 PowerShell 测试命令使用项目已知可靠解释器：`D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe`。
