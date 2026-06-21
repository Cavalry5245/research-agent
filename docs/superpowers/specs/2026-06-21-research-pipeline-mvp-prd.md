# ResearchAgent Agent Workflow MVP PRD

Date: 2026-06-21
Status: Draft for user review
Owner: HC + Codex
Related design: `docs/superpowers/specs/2026-06-18-react-frontend-replacement-design.md`

## 1. 背景

ResearchAgent 的下一阶段目标不再是围绕旧的 JD、简历路线图或一次性实验脚本继续扩展，而是转向一个面向科研阅读与综述写作的完整 Agent Workflow Demo。

MVP 要证明的核心能力是：用户在网页中输入一个研究问题后，系统可以完成从问题规划、文献检索、论文阅读、跨论文综合到证据校验的闭环，并生成一份带引用、带校验状态的 Markdown 研究报告。

这个版本优先做“流程可信、结果可追踪、失败可解释”，而不是追求每个 Agent 都达到最强效果。

## 2. 产品目标

### 2.1 目标用户

V1 主要服务两类用户：

- 正在写 related work / literature review 的研究者。
- 正在做选题、proposal、gap finding 的学生或研究人员。

### 2.2 用户价值

用户希望减少从“我有一个研究问题”到“我得到一份可检查的文献综述草稿”的时间，同时保留对来源、证据和不确定性的控制。

系统不应该只输出一篇看似合理的报告，而要让用户看到：

- 系统检索了哪些论文。
- 哪些论文进入 Reader。
- 每篇论文抽取了哪些结构化信息。
- 报告中的关键 claim 由哪些论文或证据支撑。
- 哪些 claim 缺少证据，因此被标记为 `[UNVERIFIED]`。

## 3. MVP 范围

### 3.1 In Scope

- React 前端，用户可以创建 research run、查看进度、查看最终报告。
- FastAPI 后端保留并扩展，不重写现有服务层。
- 新 pipeline 代码放在 `app/research_pipeline/`。
- 支持三种文献来源：
  - Web Search：Semantic Scholar + arXiv。
  - Zotero Only：从本地 Zotero collection 导入。
  - Hybrid：Zotero collection 作为种子，再用 Semantic Scholar / arXiv 扩展。
- 完整 Agent Workflow：
  - Planner Agent
  - Retriever Agent
  - Reader Agent
  - Synthesis Agent
  - Harness 校验
- 异步 Research Run：
  - 后端保存 run 状态。
  - 前端通过轮询展示进度。
- SQLite 保存 run 历史、中间产物、报告和校验结果。
- 本地 FAISS + SQLite metadata 作为新 pipeline 的优先向量索引方案。
- 如果 FAISS 在 Windows 或依赖安装上阻塞，允许回退到现有 JSON cosine vector store，以保证 workflow demo 可跑通。
- Markdown 报告预览、复制和下载。
- 轻量人工标注 + 自动指标的 MVP 评估集。

### 3.2 Out of Scope

- 不做 Milvus 服务化部署。
- 不做多人协作、账号系统、权限管理。
- 不做富文本报告编辑器。
- 不做 Zotero 写回，例如自动创建 collection、写 note、打 tag。
- 不做 PDF 参考文献列表解析来构建 citation graph。
- 不做 table cell 级别的数字溯源。
- 不保证所有来源论文都能下载 PDF；无 PDF 时允许 abstract-only fallback。
- 不在 V1 删除 Streamlit；Streamlit 作为 legacy/debug 入口保留。

## 4. 核心用户故事

### 4.1 创建研究任务

作为用户，我可以在网页中输入研究问题，选择来源模式、Zotero collection、时间范围和最大阅读论文数量，然后启动一个 research run。

验收标准：

- 用户可以选择 Web Search、Zotero Only 或 Hybrid。
- 默认 `max_reader_papers=8`，允许配置 3-15。
- Zotero collection 可以通过本地 API 列表选择，也允许手动输入 collection key。
- 创建后进入 run detail 页面。

### 4.2 查看 workflow 进度

作为用户，我可以看到 Planner、Retriever、Reader、Synthesis、Harness 的执行状态。

验收标准：

- 每个阶段显示 queued、running、completed、failed 或 degraded。
- Reader 阶段显示每篇论文的进度与失败原因。
- 单篇论文失败不导致整个 run 直接失败。
- 用户可以在 run 未完成时查看已经产生的候选论文、PaperCard 和事件日志。

### 4.3 查看最终报告

作为用户，我可以查看一份 Markdown 研究报告，报告中关键 claim 带引用或校验状态。

验收标准：

- 报告包括问题概述、方法论地图、数据集与指标、SOTA 对比、局限性、冲突或不一致结论、研究 gap。
- 每个关键 claim 至少带一个 citation id 或 `[UNVERIFIED]`。
- 数字型 claim 优先展示证据 snippet、表格文本或原文位置。
- 报告支持复制和下载 Markdown。

### 4.4 审查低置信结果

作为用户，我可以快速查看哪些 claim 缺少证据、证据较弱或存在冲突。

验收标准：

- Harness Summary 展示 unsupported、weak evidence、numeric trace missing、conflict detected 的数量。
- 用户可以点击某个 claim 查看对应 evidence、paper id、section、page 或 source url。
- V1 不要求用户在前端直接编辑 Markdown。

## 5. Workflow 设计

### 5.1 Planner Agent

Planner 使用两阶段设计。

第一阶段在用户提交问题后执行，输出：

- normalized question
- 3-5 个 subquestions
- 检索关键词
- 时间窗
- venue 或领域过滤建议
- source strategy
- relevance criteria

第二阶段在 Retriever 返回候选论文后执行，输出：

- 进入 Reader 的论文列表
- 候选论文聚类
- 需要重点阅读的问题
- 可能的冲突点或 gap

第二阶段不重新触发大范围检索，只对候选集做选择和聚焦。

### 5.2 Retriever Agent

Retriever 负责从外部来源和本地 Zotero 拉取候选论文。

来源策略：

- Semantic Scholar：主检索与 metadata 来源，负责 title、abstract、authors、year、venue、citationCount、references、citations、openAccessPdf。
- arXiv：CS/ML 等领域的稳定 PDF 来源，补充 arXiv metadata 和 PDF URL。
- Zotero Local API：读取用户已经整理好的 collection，优先使用本地 PDF 附件。

Retriever 输出统一的 `PaperCandidate`，字段包括：

- paper_id
- source
- title
- authors
- year
- venue
- abstract
- doi
- arxiv_id
- semantic_scholar_id
- zotero_item_id
- url
- pdf_url
- local_pdf_path
- citation_count
- relevance_score
- metadata

### 5.3 Reader Agent

Reader 对进入阅读阶段的论文并发执行，默认并发数为 3。

输入：

- PaperCandidate
- Planner 分配的 reading focus
- PDF 或 abstract fallback

输出 `PaperCard`：

- paper_id
- bibliographic metadata
- research problem
- method
- dataset
- metrics
- key results
- limitations
- assumptions
- future work
- citation relations from metadata
- extracted claims
- evidence snippets

PDF 可用时，Reader 使用 PDF 解析和章节感知 chunk；PDF 不可用时，使用 title + abstract + metadata 生成 degraded PaperCard，并在状态中明确标记。

### 5.4 Synthesis Agent

Synthesis 根据 Planner 输出和多个 PaperCard 生成 Markdown 报告。

报告必须把观点绑定到 citation id，不允许只写泛泛结论。

推荐结构：

```markdown
# Research Report

## 1. Research Question

## 2. Methodology Landscape

## 3. Dataset And Metric Comparison

## 4. SOTA And Key Results

## 5. Limitations And Failure Modes

## 6. Conflicts Or Inconsistent Findings

## 7. Research Gaps

## 8. References
```

### 5.5 Harness

Harness 负责把报告从“像一份报告”校验成“可检查的报告”。

V1 校验规则：

- 每个关键 claim 必须有关联 citation id，否则标记 `[UNVERIFIED]`。
- citation id 必须对应进入 Reader 的 PaperCard。
- 数字型 claim 必须关联 evidence snippet、section/page 或 table text；无法关联时标记 `numeric_trace_missing`。
- 如果两个 PaperCard 对同一方法、数据集、指标给出明显冲突结论，标记 `conflict_detected`。
- Harness 不直接删除 claim，只增加状态和解释。

## 6. 前端信息架构

React V1 聚焦两个主页面。

### 6.1 Dashboard

展示：

- run list
- run status
- 最近失败原因
- 创建新 run 入口
- backend / Zotero / embedding / vector store 状态摘要

### 6.2 New Run

字段：

- research question
- source mode
- Zotero collection selector
- manual collection key fallback
- max reader papers
- reader concurrency
- year range
- optional venue filter
- optional keywords

### 6.3 Run Detail

展示：

- run header
- Agent Timeline
- Planner output
- Candidate Papers
- Reader Progress
- PaperCards
- Harness Summary
- Markdown Preview

交互原则：

- 页面以工作台为主，不做营销式 hero。
- 使用紧凑表格、状态 token、右侧详情抽屉或详情面板。
- 中间产物必须可见，避免用户只能等待最终报告。

## 7. 数据模型

V1 使用 SQLite 保存 pipeline 状态与结果。

核心表：

- `research_runs`
- `research_run_events`
- `research_plans`
- `paper_candidates`
- `paper_cards`
- `paper_evidence`
- `report_claims`
- `research_reports`
- `evaluation_runs`
- `evaluation_items`

### 7.1 ResearchRun

关键字段：

- id
- question
- source_mode
- status
- max_reader_papers
- reader_concurrency
- created_at
- started_at
- completed_at
- failed_at
- error

### 7.2 PaperCard

关键字段：

- id
- run_id
- paper_id
- source
- status
- extraction_mode: `pdf` or `abstract_only`
- method
- datasets
- metrics
- key_results
- limitations
- claims_json
- evidence_json

### 7.3 ReportClaim

关键字段：

- id
- run_id
- report_id
- claim_text
- claim_type
- citation_ids
- evidence_ids
- verification_status
- verification_reason

`verification_status` 取值：

- `supported`
- `weak`
- `unverified`
- `numeric_trace_missing`
- `conflict_detected`

## 8. 向量索引方案

V1 不部署 Milvus。

优先方案：

- embedding：BGE-M3 或沿用现有 embedding client。
- vector index：本地 FAISS。
- metadata：SQLite。

回退方案：

- 如果 FAISS 依赖在 Windows 环境中阻塞，则先复用现有 `app/services/vector_store.py` 的 JSON cosine store，保证 workflow demo 先跑通。

设计原则：

- 向量库只服务 Reader 内部 evidence retrieval 和 report grounding，不把它做成 V1 的独立基础设施项目。
- Milvus 留到 V2，当论文量、并发、多人使用或持久化索引管理成为真实瓶颈时再引入。

## 9. LLM 使用策略

V1 使用 LLM 的位置：

- Planner：结构化规划输出。
- Reader：PaperCard 与 claim/evidence 抽取。
- Synthesis：Markdown 报告生成。
- Harness：rule-first，LLM-assisted，用于辅助判断弱证据和冲突，不作为唯一校验依据。

V1 不使用 LLM 的位置：

- Retriever 默认不靠 LLM 决定外部 API 查询结果，只使用 Planner query、metadata filter 和 rerank。
- Zotero collection 导入不使用 LLM。

所有 LLM 输出都要尽量使用 schema，并保存原始中间产物，方便调试。

## 10. 评估方案

V1 采用轻量人工标注 + 自动指标。

### 10.1 Seed Evaluation Set

先建立 3 个研究问题，每个问题人工标注：

- 5-8 篇 gold papers
- 5 个 gold report points
- 5 条 gold claims + evidence snippets

预计人工工作量：

- 极简版本：每个问题 45-90 分钟，总计 3-4 小时。
- 更完整版本：每个问题 2-3 小时，总计 6-9 小时。

V1 采用极简版本。

### 10.2 自动指标

Workflow 指标：

- `workflow_completion_rate`
- `stage_success_rate`
- `time_to_report`
- `reader_paper_count`
- `degraded_paper_count`

报告可信度指标：

- `claim_verification_coverage`
- `unsupported_claim_rate`
- `citation_precision`
- `numeric_trace_coverage`
- `conflict_detection_count`

报告召回指标：

- `report_point_recall`
- `evidence_recall_at_k`
- `gold_claim_coverage`

Reader 抽取指标：

- `papercard_method_score`
- `papercard_dataset_score`
- `papercard_metric_score`
- `papercard_limitation_score`

### 10.3 MVP Gate

MVP 通过条件：

- 3 个 seed question 至少 2 个完整跑通。
- 单个 run 默认在 10 分钟内产出报告。
- 至少 5 篇论文进入 Reader。
- Zotero 打开且 collection 可用时，Zotero import 成功。
- 生成完整 Markdown 报告。
- 100% key claims 有 verification status。
- 无证据断言自动标记 `[UNVERIFIED]`。
- 失败时前端能展示 stage、reason 和已有中间结果。

### 10.4 Gold Annotation Template

```yaml
question: "..."
gold_papers:
  - title:
    doi:
    arxiv_id:
    semantic_scholar_id:
    relevance: 3
    reason:
gold_report_points:
  - point:
    expected_section: method_comparison | dataset_metrics | gap | limitation
    required_papers:
gold_claims:
  - claim:
    paper_id:
    evidence_snippet:
    page:
    section:
    numeric: true
```

## 11. 风险与应对

### 11.1 外部 API 限流或不可用

风险：Semantic Scholar 或 arXiv 请求失败、限流或返回不稳定。

应对：

- 设置 request timeout 和 retry。
- 保存 API 原始响应摘要。
- Hybrid 模式下允许 Zotero source 继续运行。
- 前端展示 degraded 状态。

### 11.2 PDF 不可用或解析失败

风险：候选论文没有 open PDF，或 PDF 解析失败。

应对：

- 支持 abstract-only fallback。
- PaperCard 标记 extraction_mode。
- Harness 对 abstract-only 证据降低置信度。

### 11.3 报告幻觉

风险：Synthesis 生成未被 PaperCard 支撑的结论。

应对：

- Synthesis prompt 要求 claim 带 citation id。
- Harness 二次扫描 claim。
- 无来源 claim 标记 `[UNVERIFIED]`。
- 前端展示 unsupported claim 列表。

### 11.4 Scope 膨胀

风险：React、pipeline、向量库、评估体系同时展开导致 MVP 延迟。

应对：

- 第一版只做 Dashboard + Run Detail。
- 不做 Milvus。
- 不做报告编辑器。
- 不做 Zotero 写回。
- 不做大规模 benchmark。

## 12. 里程碑

### M1: PRD 与实现计划

输出：

- 本 PRD。
- Slice-based implementation plan。
- 确认 3 个 seed research questions。

### M2: Backend Run Skeleton

输出：

- `app/research_pipeline/` 基础结构。
- SQLite schema。
- ResearchRun 创建、状态更新、事件记录。
- Planner stub + Retriever stub + Reader stub + Synthesis stub + Harness stub 串联跑通。

### M3: Real Sources

输出：

- Zotero Local API 接入。
- Semantic Scholar 接入。
- arXiv 接入。
- PaperCandidate 统一模型。

### M4: Reader And Report

输出：

- PDF / abstract Reader。
- PaperCard 结构化抽取。
- Markdown report。
- Harness claim verification。

### M5: React Workflow UI

输出：

- Dashboard。
- New Run。
- Run Detail。
- Agent Timeline。
- Markdown Preview。

### M6: Evaluation Harness

输出：

- 3 个 seed evaluation cases。
- 自动指标脚本。
- MVP gate report。

## 13. Open Questions

这些问题不阻塞 PRD，但会影响实现计划优先级：

- 第一批 3 个 seed research questions 选哪些主题。
- Semantic Scholar 是否配置 API key；无 key 时按 public API 限流策略执行。
- BGE-M3 与 FAISS 在当前 Windows 环境中的安装成本是否可接受。
- React Slice 1 是否沿用已有 frontend replacement plan，还是为 research pipeline 单独开更窄的 UI slice。
- 第一版报告模板是否固定为 8 节结构，还是允许根据 Planner 输出动态裁剪。

