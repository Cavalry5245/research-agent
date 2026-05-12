# DEVELOPMENT_LOG.md — ResearchAgent

## 项目概述

AI 科研论文阅读助手，基于 FastAPI + Streamlit。支持 PDF 解析、结构化笔记生成、RAG 问答、多论文对比和 Markdown 导出。

## 已完成模块

### Phase 1: 项目初始化

**文件**: `app/main.py`, `app/config.py`, `app/schemas.py`, `.env.example`

- FastAPI skeleton + `GET /health`
- Streamlit 最小页面
- pydantic-settings 读取 `.env`
- 12 项配置（LLM / Embedding / VectorStore / Storage）

### Phase 2: PDF 解析

**文件**: `app/services/pdf_parser.py`

- PyMuPDF 逐页提取全文文本
- 字体大小检测 title（回退：首行有意义短文本）
- 正则提取 abstract（关键词 "Abstract" → 下一节标题之前）
- 10 个关键词章节切分（Introduction, Method, Experiments 等）
- 生成 paper_id: `paper_YYYYMMDD_NNN`
- 解析结果保存为 JSON: `metadata/{paper_id}_parsed.json`
- 支持 `find_pdf_path` / `load_parsed_result` / `list_papers`

### Phase 3: LLM Client + 笔记生成

**文件**: `app/services/llm_client.py`, `app/services/note_generator.py`, `app/services/markdown_exporter.py`, `app/prompts/paper_note_prompt.py`

- LLMClient: OpenAI-compatible API 封装，temperature=0.3，key 缺失抛 ValueError
- note_generator: 读 parsed JSON → 拼 13 段 Markdown 模板 prompt → 调 LLM → 返回笔记
- 超长论文处理: >8000 chars 时用 abstract + sections 替代 full_text
- markdown_exporter: 写入 `notes/{paper_id}_note.md`，覆盖策略

### Phase 4: 文本切块

**文件**: `app/services/chunker.py`

- 滑动窗口: chunk_size=800, overlap=100
- 按 section 切分，跳过 <20 chars 的短/空文本
- chunk_id: `{paper_id}_chunk_{seq:04d}`
- 每个 chunk 含 paper_id / title / section / content

### Phase 5: Embedding + 向量库

**文件**: `app/services/embedding_client.py`, `app/services/vector_store.py`

- EmbeddingClient: 延迟加载 sentence-transformers，`embed_texts` / `embed_query`
- VectorStore: 余弦相似度检索，支持 `paper_id` 过滤，delete_paper
- 向量索引以本地 JSON 形式持久化到 `CHROMA_PERSIST_DIR`，重启后可重新加载
- 新增索引状态查询：支持单篇 chunk 数/section 列表，以及全库论文数/总 chunk 汇总
- 模型默认 `bge-small-zh-v1.5`，可配置切换

### Phase 6: RAG 论文问答

**文件**: `app/services/paper_qa.py`, `app/prompts/qa_prompt.py`

- 检索 → 拼 context → LLM 生成回答 → 返回 sources
- Prompt 约束: 不编造、不足说明"无法判断"、列出依据片段
- sources 含 paper_id / title / section / chunk_id / content

### Phase 7: 多论文对比 + Streamlit 前端

**文件**: `app/services/paper_compare.py`, `app/prompts/compare_prompt.py`, `ui/streamlit_app.py`

- 2–5 篇论文对比，9 维度 Markdown 对比表
- Streamlit 5 Tab: 上传 / 笔记 / 问答 / 对比 / 知识库
- 直接调用 service 层（无需单独启动 uvicorn）
- `@st.cache_resource` 持久化 VectorStore / Embedding / LLM Client

## API 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/papers` | 论文列表 |
| POST | `/papers/upload` | 上传 PDF（自动解析） |
| POST | `/papers/{id}/parse` | 重新解析 |
| POST | `/papers/{id}/note` | 生成笔记 |
| GET | `/papers/{id}/note` | 读取笔记 |
| GET | `/papers/{id}/download` | 下载笔记 |
| POST | `/papers/{id}/index` | 切块入库 |
| GET | `/papers/{id}/index-status` | 单篇论文索引状态 |
| GET | `/library/index-status` | 知识库索引汇总 |
| DELETE | `/papers/{id}` | 删除论文及其文件/索引 |
| POST | `/qa` | RAG 问答 |
| POST | `/papers/compare` | 多论文对比 |

## 测试覆盖

| 测试文件 | 用例数 | 覆盖模块 |
|----------|--------|----------|
| test_pdf_parser.py | 10 | PDF 解析 + ID 生成 + JSON 读写 + 异常 |
| test_note_generator.py | 9 | Prompt 拼接 + 内容截断 + Mock LLM + 文件保存 |
| test_chunker.py | 8 | 滑动窗口 + 多 section + 空跳过 + overlap |
| test_retrieval.py | 8 | 向量库增删查 + 语义排序 + embedding client |
| test_paper_status.py | 3 | 单篇/全库索引状态汇总 |
| test_paper_qa.py | 6 | QA prompt + context 拼接 + Mock QA 全流程 |
| test_evaluation_schemas.py | 4 | evaluation schema 数据结构校验 |
| test_seed_dataset_builder.py | 6 | seed dataset 自动生成与阻塞场景 |
| test_evaluation_metrics.py | 8 | Hit@k / Recall@k / MRR 纯函数指标 |
| test_evaluation_reporting.py | 4 | baseline report 渲染与失败案例摘要 |
| test_evaluation_judges.py | 6 | answer / citation rule-based judge |
| test_qa_evaluator.py | 5 | QA benchmark scaffold 与 JSON 报告 |

**说明：** 当前已新增 Phase 1 evaluation 定向测试，最近一次定向验证命令通过 42 项测试：
`python -m pytest tests/test_evaluation_schemas.py tests/test_seed_dataset_builder.py tests/test_evaluation_metrics.py tests/test_retrieval.py tests/test_evaluation_reporting.py tests/test_evaluation_judges.py tests/test_qa_evaluator.py -q`

## Phase 1: 评测体系补齐（Benchmark / Dataset / Reports）

**文件**: `app/evaluation/schemas.py`, `app/evaluation/metrics.py`, `app/evaluation/reporting.py`, `app/evaluation/judges.py`, `app/evaluation/scripts/build_seed_dataset.py`, `app/evaluation/scripts/evaluate_retrieval.py`, `app/evaluation/scripts/evaluate_qa.py`

- 新增 `app/evaluation/` 模块，形成可复用评测层
- 定义 `QAEvalSample`、`ComparisonEvalSample`、`RetrievalEvalResult` / `RetrievalMatch` 等基础数据结构
- 基于 `app/storage/metadata/*_parsed.json` 自动生成 seed benchmark：
  - `app/evaluation/datasets/qa_eval_seed.jsonl`
  - `app/evaluation/datasets/comparison_eval_seed.jsonl`
- 新增 retrieval benchmark 脚本与报告：
  - `app/evaluation/scripts/evaluate_retrieval.py`
  - `app/evaluation/reports/retrieval_eval_seed_report.json`
  - `app/evaluation/reports/baseline_report.md`
- 新增 answer / citation evaluation scaffold：
  - `app/evaluation/scripts/evaluate_qa.py`
  - `app/evaluation/reports/qa_eval_seed_report.json`
- 当前 baseline report 已形成可引用路径：`app/evaluation/reports/baseline_report.md`

### 当前 benchmark 事实

- Seed QA 数据集规模：11 条样本
- 覆盖论文数：4 篇
- Supporting-section labels：6
- Retrieval baseline（来自 `baseline_report.md`）：
  - Hit@3 = 1.000
  - Recall@3 = 1.000
  - MRR = 1.000
- QA scaffold baseline（来自 `qa_eval_seed_report.json`）：
  - answer_pass_rate = 1.000
  - citation_pass_rate = 1.000
  - mean_answer_score = 1.000
  - mean_citation_score = 1.000

### 解释边界（非常重要）

以上分数来自离线 deterministic seed baseline，而不是真实线上检索链路：
- retrieval 脚本会把 gold supporting section 注入 rank 1
- QA 脚本会直接使用 seed expected answer 作为预测答案
- 因此当前结果的意义是：评测 schema、dataset、脚本、报告与 rule-based judge 已经打通
- 当前结果不能被表述为真实 RAG 检索或真实 LLM 问答质量已经达到 100%

### 运行环境

- 默认验证环境：WSL + conda
- 当前 Phase 1 评测为离线验证
- 真实 embedding 检索链路、真实 LLM 回答链路、联网模型波动仍待后续接入验证
- 2026-05-12 14:41 CST：继续细化 Phase 3 comparison report 的 failure-case 可解释性。这一轮没有改 evaluator 核心打分逻辑，而是优先把上一轮新增的 semantic evidence mismatch 边界真正暴露到 Markdown 报告层：在 `tests/test_comparison_evaluator.py` 新增 `test_build_comparison_report_markdown_includes_semantic_evidence_mismatch_details`，构造一个 `dataset` 维度 `section_alignment=1.0`、`paper_alignment` 全对、但 `evidence_quality_issues=['dataset']` 的 comparison report payload，断言 `build_comparison_report_markdown(...)` 会明确渲染 `Evidence quality issues: dataset`，同时保持 `Section alignment issues: 无` 与 `Paper alignment issues: 无`。这样离线 comparison report 读者可以直接看出“结构对齐正常，但证据 snippet 在语义上并没有真正支撑该 aspect”，而不必只从 summary 指标反推。定向测试 `tests/test_comparison_evaluator.py -k 'semantic_evidence_mismatch or includes_semantic_evidence_mismatch_details' -q` → `2 passed, 18 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `20 passed`，全量测试 `tests -q` → `151 passed`。
- 2026-05-12 14:06 CST：继续细化 Phase 3 comparison evaluator 的 evidence-quality 边界。这一轮没有扩大 compare helper/CLI seam，而是优先补一个更细的 evaluator 回归：在 `tests/test_comparison_evaluator.py` 新增 `test_evaluate_comparison_dataset_flags_semantic_evidence_mismatch_separately_from_section_alignment`，构造 `dataset` aspect 的 evidence 虽然全部位于 gold `Experiments` section、因此 `section_alignment=1.0`，但 snippet 内容实际上只在描述 Transformer/CNN 方法而非数据集。测试断言 evaluator 会把这种情况单独记到 `evidence_quality_issues=['dataset']`，同时保持 `section_alignment_issues=[]`、`paper_alignment_issues={}`，从而继续把“section 命中”和“语义支撑充分”两种信号分开。这样后续即使 compare payload 结构合法、section 对齐良好，只要 snippet 语义没有真正支撑当前 aspect，也会在离线 comparison report 中被识别出来。定向测试 `tests/test_comparison_evaluator.py -k 'semantic_evidence_mismatch or distinguishes_missing_evidence_from_section_mismatch' -q` → `2 passed, 18 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `20 passed`，全量测试 `tests -q` → `151 passed`。
- 2026-05-12 13:34 CST：继续推进 Phase 3 comparison evaluator 的 compare helper 失败契约。这一轮没有扩大 compare 逻辑本身，而是优先补齐 `--compare-batch-script` seam 在 helper 子进程非零退出时的 CLI 回归：`tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_helper_failure_surfaces_stdout_stderr_and_exit_code`，复用仓库中已与真实 parsed metadata 对齐的 comparison seed 样本，临时写出一个会打印 `helper stdout before failure` / `helper stderr before failure` 并以 `SystemExit(7)` 退出的 helper script，再通过 `sys.executable app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...` 直接跑真实 CLI 子进程。测试断言主脚本不会吞掉 helper 失败上下文：stdout 保留 helper stdout，stderr 同时保留 helper stderr、`compare batch helper failed with exit code 7` 与 `STDOUT/STDERR` 摘要，并且 compare payload / JSON report / Markdown report 都不会被错误生成。这样把 `helper script -> compare-output artifact -> main CLI` 这条 seam 的失败交付契约也锁进了回归，后续即使 helper 执行失败，也能让 cron/人工排障直接看到真实子进程输出。定向测试 `tests/test_comparison_evaluator.py -k 'helper_failure or success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `4 passed, 15 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `19 passed`，全量测试 `tests -q` → `149 passed, 1 skipped`。
- 2026-05-12 12:52 CST：继续推进 Phase 3 comparison evaluator 的 CLI 失败边界验证。这一轮不再把 `test_cli_generate_live_compare_surfaces_compare_stage_invalid_json_clearly` 落在 fixture-only dataset 的 metadata prerequisite failure 上，而是改为复用仓库中已与真实 parsed metadata 对齐的 comparison seed 样本，并借助上一轮新增的 `--compare-batch-script` seam，临时写出一个 helper script 向 `--compare-output` 写入故意损坏的 JSON。随后通过 `sys.executable app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...` 直接跑真实 CLI 子进程，断言 stderr 明确暴露 `CompareBatchRunResult` 的 `Invalid JSON` 校验失败，stdout 保留 helper 的 `wrote invalid compare payload` 输出，且不会再误报 `论文解析结果不存在` 或 `结构化对比结果解析失败`。这样把 live compare CLI 的失败契约真正推进到 compare-stage 输出损坏边界，而不是继续停留在 metadata 缺失前置错误。定向测试 `tests/test_comparison_evaluator.py -k 'success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `tests -q` → `149 passed`。
- 2026-05-12 12:07 CST：继续推进 Phase 3 comparison evaluator 的 CLI 成功路径验证，这一轮不再停留在“in-process 伪造 stdout contract”层面，而是给 `app/evaluation/scripts/evaluate_comparison.py` 增加了一个显式 `--compare-batch-script` 注入 seam。启用后脚本会以当前解释器在仓库根目录执行外部 helper script，由该脚本把受控 `CompareBatchRunResult` 写入 `--compare-output`，然后主脚本继续走 `inject_live_compare_predictions(...) -> evaluate_comparison_dataset(...) -> Markdown/JSON report` 的真实 CLI 闭环。对应地，`tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_success_subprocess_with_injection_seam`：它复用仓库内已与真实 parsed metadata 对齐的 comparison seed 样本，临时写出 stub compare helper script，再以 `sys.executable` 直接运行 `app/evaluation/scripts/evaluate_comparison.py --generate-live-compare --compare-batch-script ...`，断言成功态 stdout 会稳定打印 comparison report 路径、Markdown report 路径、live compare payload 路径与 `sample_count`，且最终报告明确标记 `comparison_source=predicted_comparison`、`uses_structured_summaries=True`。这一步把“真实子进程入口 + 受控 compare 输出注入”的中间验证里程碑补齐，避免继续误用 parent pytest monkeypatch 去假装覆盖 CLI 子进程。定向测试 `tests/test_comparison_evaluator.py -k 'success_subprocess_with_injection_seam or compare_stage_invalid_json or partial_batch_payload' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `tests -q` → `148 passed, 1 skipped`。
- 2026-05-12 11:35 CST：继续推进 Phase 3 comparison evaluator 的 live compare 注入一致性回归。这一轮没有去伪造新的 CLI 成功路径，而是优先把已有双向一致性保护补成独立回归：在 `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_rejects_partial_batch_payload_clearly`，构造“两条 comparison dataset + 单条 persisted live compare payload”的不一致场景，并直接调用 `inject_live_compare_predictions(...)` 断言其抛出 `Dataset contains sample_ids missing from live compare payload`，且错误信息必须明确列出缺失样本 `cmp-live-partial-002`。这样把先前实现过的 dataset↔payload 双向一致性检查真正锁成回归，避免未来批处理或 CLI 重构时再度退化为部分 payload 被静默接受。定向测试 `tests/test_comparison_evaluator.py -k 'partial_batch_payload or compare_stage_invalid_json or generate_live_compare_cli_output_lines' -q` → `3 passed, 15 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `18 passed`，全量测试 `tests -q` → `148 passed, 1 skipped`。
- 2026-05-12 10:49 CST：继续推进 Phase 3 comparison evaluator 的 CLI 前置失败边界回归。这一轮没有伪造 compare-stage invalid JSON 成功注入到 CLI 子进程里，而是回到当前脚本真实可验证的 prerequisite boundary：在 `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_surfaces_compare_stage_invalid_json_clearly`，直接用 `sys.executable` 运行 `app/evaluation/scripts/evaluate_comparison.py --generate-live-compare`，对 fixture-only comparison dataset 断言 CLI 会以非零退出，并在 stderr 中明确打印 `论文解析结果不存在` 与 `paper_a_parsed.json`，且不会误报 `结构化对比结果解析失败`。这样把 live compare 脚本当前最靠前、最真实的失败边界继续锁定住，同时与已有 `test_generate_live_compare_cli_output_lines` 形成“成功态 stdout 契约 + 失败态 stderr 契约”的组合回归。定向测试 `tests/test_comparison_evaluator.py -k 'compare_stage_invalid_json or generate_live_compare_cli_output_lines' -q` → `2 passed, 15 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `17 passed`，全量测试 `tests -q` → `147 passed, 1 skipped`。
- 2026-05-12 09:54 CST：继续推进 Phase 3 comparison evaluator 的 CLI/脚本交付契约。这一轮没有再往真实外部 LLM 成功链路硬推，而是优先补一个稳定、可离线验证的输出层回归：在 `tests/test_comparison_evaluator.py` 新增 `test_generate_live_compare_cli_output_lines`，用受控 `CompareBatchRunResult` 驱动 `live compare payload -> dataset 注入 -> evaluator -> Markdown/JSON report` 闭环，并显式断言成功态下应输出三类路径行（comparison report、Markdown report、live compare payload）以及包含 `sample_count` 的 summary JSON。这样即使后续脚本内部继续重构，只要打破了 CLI/cron 消费方依赖的标准输出格式，就会被回归立即捕获。定向测试 `tests/test_comparison_evaluator.py -q` → `16 passed`，全量测试 `tests -q` → `147 passed`；附加脚本验证普通 comparison report CLI 仍成功生成 `app/evaluation/reports/comparison_eval_seed_report.json/.md`。
- 2026-05-12 09:05 CST：继续推进 Phase 3 live compare 成功链路的可验证闭环。这一轮没有依赖真实外部 LLM/网络去赌 `--generate-live-compare` 成功，而是先在 `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_with_real_metadata_and_stubbed_llm_generates_live_report`：复用仓库自带 `comparison_eval_seed.jsonl` 中与 `app/storage/metadata/*_parsed.json` 对齐的真实样本，通过在测试中 patch `compare_papers_batch` 内部依赖，构造受控的 `structured_summaries + comparison` 输出，然后串联验证 `generate_live_compare_predictions(...)`、`inject_live_compare_predictions(...)`、`evaluate_comparison_dataset(...)` 以及 Markdown 报告构建。这样把“真实 metadata 已满足时，live compare payload 一旦生成，评测层必须消费真实 `predicted_comparison` 而不是回退 deterministic stub”的后置契约锁定下来。定向测试 `tests/test_comparison_evaluator.py -k 'stubbed_llm or real_metadata_generates_reports' -q` → `2 passed, 13 deselected`，完整 comparison evaluator 测试 `tests/test_comparison_evaluator.py -q` → `15 passed`，全量测试 `tests -q` → `145 passed, 1 skipped`；普通 comparison report CLI 复跑继续成功生成 `app/evaluation/reports/comparison_eval_seed_report.json/.md`。
- 2026-05-12 08:28 CST：继续推进 Phase 3 comparison evaluator 的 CLI 成功路径验证。这一轮没有直接强行打通 `--generate-live-compare` 的真实 LLM 链路，而是先补一个“真实 metadata 已齐备时，普通 comparison report CLI 应可稳定成功产出”的回归：在 `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_with_real_metadata_generates_reports`，从仓库自带 `app/evaluation/datasets/comparison_eval_seed.jsonl` 中筛出 `paper_ids` 均存在于 `app/storage/metadata/*_parsed.json` 的样本，复制到临时 dataset 后用 `sys.executable` 调起 `app/evaluation/scripts/evaluate_comparison.py`，断言 report JSON / Markdown 成功生成，且在未显式开启 `--generate-live-compare` 时继续标记 `comparison_source=deterministic_stub`。随后用 `/home/chase/miniconda3/envs/research_agent/bin/python -m pytest tests/test_comparison_evaluator.py -q` 验证 `14 passed`，再跑全量 `tests -q` 得到 `144 passed, 1 skipped`；附加脚本验证 comparison seed dataset 可直接生成 `app/evaluation/reports/comparison_eval_seed_report.json` 与 `.md`。
- 2026-05-12 07:55 CST：继续推进 Phase 3 live compare CLI 路径的可验证边界。这一轮没有为了让 `--generate-live-compare` 在 fixture-only comparison dataset 上“看起来通过”而伪造 parsed metadata 文件，而是先在 `tests/test_comparison_evaluator.py` 新增 `test_cli_generate_live_compare_reports_missing_metadata_fixture_clearly`，直接以 `sys.executable` 调起 `app/evaluation/scripts/evaluate_comparison.py --generate-live-compare`，断言当数据集里的 `paper_a` / `paper_b` 并不存在于 `app/storage/metadata/*_parsed.json` 时，CLI 会以非零退出，并在 stderr 中明确暴露 `论文解析结果不存在: app/storage/metadata/paper_a_parsed.json`。这样先把“fixture 数据无法满足真实 metadata 前置条件”的失败边界锁定，避免后续把 live compare 前置缺件误判为 compare/evaluator 主逻辑 bug。定向测试 `tests/test_comparison_evaluator.py -q` → `13 passed`，全量测试 `tests -q` → `143 passed, 1 skipped`。
- 2026-05-12 07:17 CST：继续推进 Phase 3 live compare → evaluator/report 的完整性边界。这一轮先在 `tests/test_comparison_evaluator.py` 补“dataset 中存在 sample，但 live compare payload 缺少对应 `sample_id` 时必须显式失败”的回归，避免 `inject_live_compare_predictions(...)` 只写回部分样本后，evaluator 继续用一部分真实 compare 结果和一部分 deterministic stub 混合生成报告。随后在 `app/evaluation/scripts/evaluate_comparison.py` 中把注入前校验升级为双向一致性检查：不仅拒绝 compare batch 里出现 dataset 不存在的 `sample_id`，也拒绝 dataset 里存在但 batch payload 未覆盖的 `sample_id`；只有一一匹配时才允许把 `predicted_comparison` 落回 JSONL。定向测试 `tests/test_comparison_evaluator.py -q` → `13 passed`，全量测试 `tests -q` → `143 passed, 1 skipped`。
- 2026-05-12 06:37 CST：继续推进 Phase 3 live compare → evaluator/report 的可验证闭环。这一轮没有伪造真实 metadata 条件去跑 `--generate-live-compare` CLI 子进程，而是先按最小可验证原则补两类回归到 `tests/test_comparison_evaluator.py`：一类强化 `generate_live_compare_predictions(...)` 的持久化断言，明确 compare batch JSON 中必须保留 `structured_summaries.paper_a.dataset` 等关键信息；另一类则构造已落盘 live compare payload，经过 `inject_live_compare_predictions(...)` 注入 dataset 后，再调用 `evaluate_comparison_dataset(...)` 断言结果会标记 `comparison_source=predicted_comparison` 且 `uses_structured_summaries=True`。这样至少把“live compare payload 已存在时，evaluator/report 不会误退回 deterministic stub”的闭环锁死。定向测试 `tests/test_comparison_evaluator.py -q` → `12 passed`，全量测试 `tests -q` → `142 passed, 1 skipped`。
- 2026-05-12 05:57 CST：继续推进 Phase 3 structured comparison evaluator 的报告可解释性。先在 `tests/test_comparison_evaluator.py` 补 Markdown 回归，要求 comparison failure case 报告不仅展示 `section_alignment_issues`，还要把 `paper_alignment` 与 `paper_alignment_issues` 中的论文级错位信息直接渲染出来，例如 `paper_a=1.000, paper_b=0.000` 与 `dataset: paper_b`。随后在 `app/evaluation/reporting.py` 的 `build_comparison_report_markdown(...)` 中新增 `Paper alignment` 与 `Paper alignment issues` 展示逻辑，使人工阅读 Markdown 报告时能直接定位“哪个 aspect 错、错了哪篇论文”，不必回退查看 JSON。定向测试 `tests/test_comparison_evaluator.py -q` → `11 passed`，全量测试 `tests -q` → `141 passed, 1 skipped`。
- 2026-05-12 05:10 CST：继续推进 Phase 3 comparison evaluator 的 evidence/section 对齐细化，这一轮把 `section_alignment` 从“aspect 级全有或全无”细化为“按论文粒度累计的对齐率”。先在 `tests/test_comparison_evaluator.py` 补 partial alignment 回归：当同一 comparison aspect 中只有部分论文的 evidence section 命中各自 gold `supporting_sections` 时，要求 evaluator 同时保留 aspect 级 `section_alignment_issues`，并额外输出 `paper_alignment` 与 `paper_alignment_issues`。随后在 `app/evaluation/scripts/evaluate_comparison.py` 新增 `_aspect_paper_alignment(...)`，按 `paper_id` 计算每个 aspect 的 section 对齐得分，并把样本级 `section_alignment` 改为论文级平均值；这样可以区分“整个 aspect 全错位”和“只错一篇论文”两类情况。定向测试 `tests/test_comparison_evaluator.py -q` → `11 passed`，全量测试 `tests -q` → `141 passed, 1 skipped`。
- 2026-05-12 04:30 CST：继续细化 Phase 3 structured comparison evaluator 的 evidence 质量判定边界。先在 `tests/test_comparison_evaluator.py` 补“evidence 非空但 section 未命中 gold supporting_sections 时，应与 missing evidence 分开统计”的失败基线，再在 `app/evaluation/scripts/evaluate_comparison.py` 增加 `_aspect_sections_align(...)`、`section_alignment` 与 `section_alignment_issues`，让 evaluator 同时输出 evidence completeness、evidence quality 与 section alignment 三层信号。随后更新 `app/evaluation/reporting.py`，让 comparison Markdown 报告展示 `mean_section_alignment`、样本级 section alignment 分数与错位维度。定向测试 `tests/test_comparison_evaluator.py -q` → `10 passed`，全量测试 `tests -q` → `140 passed, 1 skipped`。
- 2026-05-12 03:58 CST：继续补强 Phase 3 live compare → evaluator 闭环的安全边界。先在 `tests/test_comparison_evaluator.py` 补“compare batch 输出包含 dataset 中不存在的 sample_id 时必须显式失败”的回归，再在 `app/evaluation/scripts/evaluate_comparison.py` 的 `inject_live_compare_predictions(...)` 中加入 sample_id 对齐校验：先读取 comparison dataset 的全部 `sample_id`，再比对 live compare batch payload；若存在未匹配 sample，直接抛出 `ValueError`，避免静默写入错误预测结果。定向测试 `tests/test_comparison_evaluator.py -q` → `9 passed`，全量测试 `tests -q` → `139 passed, 1 skipped`。
- 2026-05-12 03:19 CST：继续推进 Phase 3，把 comparison batch 输出真正接回 evaluator 输入数据。`app/evaluation/scripts/evaluate_comparison.py` 新增 `inject_live_compare_predictions(...)`，会读取 `comparison_eval_seed_predictions.json` 中的 `CompareBatchRunResult`，按 `sample_id` 把真实 `PaperComparisonResult` 写回 JSONL 数据集的 `metadata.predicted_comparison`，使 `--generate-live-compare` 能在同一次运行中形成“真实 compare 生成 → dataset 注入 → evaluator/report 落盘”的最小闭环。`tests/test_comparison_evaluator.py` 新增回归，验证 live compare payload 会正确注入 dataset 并持久化回磁盘。定向测试 `tests/test_comparison_evaluator.py -q` → `8 passed`，全量测试 `tests -q` → `139 passed`。
- 2026-05-12 02:38 CST：继续推进 Phase 3，把 comparison evaluator 所需的“真实 compare 输出落盘”前置层先固定下来。`app/schemas.py` 新增 `CompareBatchSampleResult` / `CompareBatchRunResult`，`app/services/paper_compare.py` 新增 `compare_papers_batch(...)` 与 `save_compare_batch_result(...)`，可按 comparison seed dataset 批量运行 compare service 并统一落盘每条 sample 的 `PaperComparisonResult`。同时 `app/evaluation/scripts/evaluate_comparison.py` 新增 `generate_live_compare_predictions(...)` 以及 `--generate-live-compare` / `--compare-output` / `--metadata-dir` CLI 骨架，为下一步真正串起“真实 compare 生成 → evaluator 消费 → report 落盘”闭环做准备。定向测试 `tests/test_comparison_evaluator.py -q` → `7 passed`，全量测试 `tests -q` → `137 passed, 1 skipped`。
- 2026-05-12 01:58 CST：继续推进 Phase 3，把 comparison evaluator 从 deterministic stub 再向真实 compare pipeline 靠近。先在 `tests/test_comparison_evaluator.py` 补 live compare payload 回归：要求 evaluator 优先读取 `metadata.predicted_comparison`、识别 `structured_summaries` 已随 compare 输出透传，并对“evidence 非空但与当前 aspect 不匹配”的 dataset 维度打标。随后在 `app/evaluation/scripts/evaluate_comparison.py` 增加 `comparison_source`、`uses_structured_summaries`、`evidence_quality`、`evidence_quality_issues`，并扩展 `app/evaluation/reporting.py` 的 Markdown 报告，让 failure case 明确展示 compare 来源、是否使用 structured summaries 以及 aspect-level evidence quality。定向测试 `tests/test_comparison_evaluator.py -q` → `5 passed`，脚本生成 `app/evaluation/reports/comparison_eval_seed_report.json` 与 `comparison_eval_seed_report.md`，全量测试 `tests -q` → `135 passed, 1 skipped`。
- 2026-05-12 01:23 CST：继续收紧 Phase 3 comparison pipeline 与 evaluator 之间的边界。先在 `tests/test_paper_compare.py` 补 compare 第二阶段非法 JSON 的失败基线，明确两阶段错误应区分 extraction-stage 与 compare-stage；再补 `structured_summaries` 透传断言，要求 compare 结果保留 per-paper 结构化抽取产物，供后续 evaluator 或报告层直接复用。实现侧在 `app/schemas.py` 为 `PaperComparisonResult` 新增 `structured_summaries`，并在 `app/services/paper_compare.py` 的 `_normalize_comparison_result(...)` 中挂回抽取摘要。定向测试 `tests/test_paper_compare.py -q` → `9 passed`，联合回归 `tests/test_comparison_evaluator.py tests/test_paper_compare.py -q` → `13 passed`，全量测试 `tests -q` → `135 passed`。
- 2026-05-12 00:40 CST：推进 Phase 3 / Task 3.4。新增 `tests/test_comparison_evaluator.py`，先为 structured comparison evaluator 建立 completeness / evidence completeness / paper balance 的失败/通过基线与 CLI 脚本产物断言；随后新增 `app/evaluation/scripts/evaluate_comparison.py`，支持读取 `ComparisonEvalSample.metadata.predicted_comparison` 或基于 supporting sections 生成 deterministic comparison stub，并输出 `app/evaluation/reports/comparison_eval_seed_report.json` 与 `comparison_eval_seed_report.md`。同时在 `app/evaluation/reporting.py` 增补 comparison report payload/markdown 渲染，在 `app/evaluation/metrics.py` 补 `load_comparison_samples(...)` 复用 comparison seed dataset。定向测试 `4 passed`，全量测试 `132 passed, 1 skipped`。
- 2026-05-12 00:05 CST：推进 Phase 3 / Task 3.3。先在 `tests/test_paper_compare.py` 补“compare aspect 未返回 evidence 时应自动回填”的失败基线，再在 `app/services/paper_compare.py` 新增 `COMPARE_ASPECT_TO_SUMMARY_FIELD` 与 `_infer_aspect_evidence(...)`，当 LLM 输出的 `CompareAspect.evidence` 为空时，自动从 per-paper structured summary 的同维度证据回填，保证 `method` / `dataset` / `metrics` 等核心维度具备最小 evidence grounding，并同步进入 Markdown“证据摘录”。定向测试 `7 passed`，全量测试 `128 passed, 1 skipped`。
- 2026-05-11 20:19 CST：切换到 `/home/chase/miniconda3/envs/research_agent/bin/python` 后完成 Task 2.1 / 2.2 验证；同时修复多处测试脚本对子进程 `python` 命令的硬编码，改为 `sys.executable`，避免 cron / 非交互环境 PATH 差异导致假失败；当前全量测试 `115 passed`
- 2026-05-11 20:44 CST：推进 Phase 2 / Task 2.3，新增 `HybridReranker` 作为轻量 hybrid retrieval baseline，用 token-overlap sparse signal 对 dense 并列结果做二次重排；同时为 `VectorStore.query(...)` 增加 `hybrid_query_text` 可选参数，并以定向测试验证 hybrid rerank 行为，结果 `23 passed`
- 2026-05-11 22:16 CST：推进 Phase 2 / Task 2.5。先补 `tests/test_evaluation_metrics.py` 与 `tests/test_evaluation_reporting.py`，为 retrieval evaluator 增加多策略对比断言：支持 dense、dense_rerank、hybrid、hybrid_rerank 四种策略统一汇总，并验证 `evaluate_retrieval.py --mode compare` 与 upgrade markdown report。实现侧新增 `build_retrieval_variant_results(...)`、`RETRIEVAL_STRATEGIES`、`build_seed_retrieval_comparison_results(...)`、`build_retrieval_upgrade_report_payload(...)`、`build_retrieval_upgrade_report_markdown(...)`，同时修复 retrieval recall 统计逻辑：从“相关 chunk 数”改为“命中的相关 section 数”，避免多 chunk 命中同一 supporting section 时 recall 超过 1。产物新增 `app/evaluation/reports/retrieval_compare_report.json` 与 `app/evaluation/reports/retrieval_upgrade_report.md`。定向测试 `14 passed`，全量测试 `122 passed`。
- 2026-05-11 22:52 CST：开始推进 Phase 3 / Task 3.1。新增 `tests/test_paper_compare.py`，为结构化 comparison schema、`/papers/compare` 的 structured payload，以及非法 JSON 响应失败场景建立基线；随后在 `app/schemas.py` 增补 `PaperEvidence`、`CompareAspect`、`PaperComparisonResult`，并升级 `app/services/paper_compare.py` 为“LLM 输出 JSON → 服务侧归一化 → Markdown 渲染”的双形态输出。定向测试 `4 passed`，全量测试 `126 passed`。
- 2026-05-11 23:32 CST：推进 Phase 3 / Task 3.2。先在 `tests/test_paper_compare.py` 补单篇结构化抽取与 compare 前置 structured summaries 断言，再在 `app/schemas.py` 新增 `PaperStructuredSummary`，并在 `app/prompts/compare_prompt.py` 拆出 `EXTRACTION_PROMPT` / `build_extraction_prompt(...)`。`app/services/paper_compare.py` 新增 `extract_paper_summaries(...)`、单篇字段/evidence 归一化逻辑，以及 compare 阶段消费 structured summaries 的两步式 pipeline。定向测试 `6 passed`，全量测试 `128 passed`。
- 2026-05-12 00:05 CST：推进 Phase 3 / Task 3.3。先在 `tests/test_paper_compare.py` 补“compare aspect 未返回 evidence 时应自动回填”的失败基线，再在 `app/services/paper_compare.py` 新增 `COMPARE_ASPECT_TO_SUMMARY_FIELD` 与 `_infer_aspect_evidence(...)`，当 LLM 输出的 `CompareAspect.evidence` 为空时，自动从 per-paper structured summary 的同维度证据回填，保证 `method` / `dataset` / `metrics` 等核心维度具备最小 evidence grounding，并同步进入 Markdown“证据摘录”。定向测试 `7 passed`，全量测试 `128 passed, 1 skipped`。

## 已知问题

1. **`conda run` 退出的 pyarrow DLL 冲突**: 测试全部通过后 conda 进程退出时 crash，不影响结果
2. **Embedding 模型首次下载**: `bge-small-zh-v1.5` 首次使用需联网下载（约 130MB）
3. **笔记生成 Prompt 消耗**: 13 段模板 + 论文全文，需模型 context ≥ 8k tokens
4. **VectorStore 为轻量本地实现**: 当前为纯 Python 检索 + JSON 持久化，后续如需更强过滤/并发能力可替换为 ChromaDB 后端

## 下一步计划

- [ ] 把 `evaluate_comparison.py` 接到真实 compare service 的批量输出流程，形成“真实 compare 生成 → evaluator 消费 → report 落盘”的闭环
- [ ] 继续细化 aspect-level evidence quality 检查，区分“无 evidence”“证据存在但维度错配”“section 对齐不足”等不同失败类型
- [ ] ChromaDB 持久化后端替换（解决 conda 环境兼容性后）
- [ ] v0.2: SQLite 论文管理 + 标签分类
- [ ] v0.3: 实验日志分析模块
- [ ] v0.4: Agent 工具调用系统
- [ ] v0.5: 多模态论文理解（图表/公式）
