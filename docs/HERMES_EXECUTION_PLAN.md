# ResearchAgent 自动执行升级任务清单（Hermes Execution Plan）

> **For Hermes:** 按本文件从上到下执行；每个任务都应遵循 TDD（先写失败测试，再实现，再跑测试），并在每个阶段完成后更新文档与验证结果。若任务涉及真实外部依赖、凭据、人工标注或部署资源，必须先检查“人工前置条件”章节；缺失时暂停该任务并明确报告阻塞项。

**主目标：** 将 ResearchAgent 升级为适合写进大模型 / AI 应用开发岗位简历的高质量项目，重点补齐评估体系、RAG 深化、结构化多论文对比与工程化能力。

**执行原则：**
- 一次只推进一个小任务（2~15 分钟粒度）
- 每步必须可验证
- 每步尽量可由 Hermes 独立完成
- 涉及人工资源时必须显式阻塞，不得假设
- 每阶段完成后必须输出：改了什么、怎么验证、结果如何、下一步是什么

**项目根目录：** `/mnt/e/projects/ResearchAgent`

**默认执行环境：**
- 在 WSL 中执行
- 默认已进入项目所用的 conda 环境
- 默认在项目根目录运行命令
- 除非特别说明，不使用 Windows `venv\Scripts\python.exe` 路径风格命令

**推荐测试命令：**
```bash
python -m pytest tests -q
```

**补充说明：**
- 若全量测试耗时较长，可先跑目标测试文件，再在阶段结束时补跑全量测试
- 若某些测试依赖外部模型或网络，应在结果中标明“本地离线通过 / 真实链路待验证”

**阶段总览：**
1. Phase 0 — 执行前检查与基线冻结
2. Phase 1 — P0 评估体系（Benchmark / Dataset / Scripts / Reports）
3. Phase 2 — P1 检索质量升级（Reranker / Hybrid Retrieval / Citation Grounding）
4. Phase 3 — P1 多论文结构化 Synthesis 升级
5. Phase 4 — P2 工程化升级（Async Jobs / Storage / Observability）
6. Phase 5 — P3 交付增强（Docker / CI / README / Resume Assets）

---

# 0. 人工前置条件（必须先识别）

以下内容 Hermes **不能凭空制造**，如果缺失，必须先向用户索取、确认或调整方案。

注意：以下“人工前置条件”分为两类：
- `立即阻塞`：缺失后会阻止当前阶段继续推进
- `需要确认但可先降级推进`：缺失后可先用 mock / rule-based / 离线方案搭骨架

## 0.1 当前项目已具备、通常不构成立即阻塞的资源
基于项目当前状态，以下内容通常已经存在，可优先直接利用：
- 项目内已有 `.env` 与 `.env.example`
- 项目内已有样例 PDF 论文
- 项目内已有 parsed metadata JSON
- 项目内已有基础测试集、README、运行文档与开发日志

因此，以下任务通常可以先自动推进：
- Phase 0 全部
- Phase 1.1 ~ 1.4
- Phase 2 / 3 / 4 的接口层、脚手架、测试与文档骨架

## 0.2 需要人工提供或确认的事项

### A. 评测样本范围确认（需要确认但可先降级推进）
用于：
- benchmark 数据集的代表性
- 后续 README / 简历中的评估说服力

可选方案：
- 先直接使用项目内已有 PDF + metadata 自动生成 seed dataset
- 或由用户额外指定一批更有代表性的论文 PDF，作为正式 benchmark 基础库

如果用户暂未提供：
- Hermes 可先基于项目现有样本完成最小可行 benchmark
- 后续再增补更有代表性的评测集

### B. 真实 LLM / Embedding / Judge 验证能力（需要确认但可先降级推进）
用于：
- QA / comparison 的真实链路验证
- reranker / rerank benchmark（若使用真实模型）
- answer / citation 质量评估（若依赖 LLM judge）

当前原则：
- 若 `.env` 存在且关键字段完整，Hermes 可先按“可尝试真实链路”处理
- 若后续调用失败、额度不足或模型不稳定，则降级为：
  - rule-based evaluator
  - placeholder judge
  - offline benchmark 子集

需要用户确认的仅是：
- 是否希望直接使用当前 `.env` 配置跑真实评估
- 若真实链路失败，是否允许切换到本地模型 / Ollama / mock 方案

### C. 是否允许引入新增依赖（需要确认，默认可小幅新增）
例如：
- `rank-bm25`
- 新的 `sentence-transformers` reranker 模型
- `httpx` / `tenacity` / `prometheus-client`
- `sqlite` / `sqlmodel` / `sqlalchemy`

默认策略：
- 若用户未明确禁止，Hermes 可默认“小幅新增依赖允许，但必须记录原因、用途与替代方案”

若用户要求尽量零新增依赖：
- 则优先采用轻量替代实现
- 必要时把高依赖版本标记为下一迭代

### D. Phase 5 交付目标确认（部分任务会阻塞）
用于 Docker / CI / 演示交付增强：
- 是否只做本地 Docker 文件与说明
- 是否接 GitHub Actions
- 是否需要云部署目标

如果用户未明确：
- Hermes 可先生成 Docker / CI / README 相关文件骨架
- 真实部署验证、GitHub 连通与云端发布可标记为“待人工验证”

---

## 0.3 Hermes 可默认推进、无需人工等待的部分
以下内容可直接自动执行：
- 目录结构重构与新增模块
- 测试补齐
- evaluation 框架代码
- retrieval benchmark 脚本
- baseline report 模板
- reranker / hybrid / citation 的代码与测试脚手架
- async job / observability / docs / CI 基础实现
- 基于现有样本构建 seed dataset
- 基于当前 `.env` 进行“最佳努力”真实链路验证（失败则降级并如实记录）

---

# 1. 执行方式要求（给 Hermes）

每个任务都按以下顺序执行：

1. 阅读相关文件
2. 写 failing test
3. 跑单测确认失败
4. 写最小实现
5. 跑单测确认通过
6. 跑相关测试集或全量测试
7. 更新 README / DEVELOPMENT_LOG / 相关 docs
8. 汇报结果并推进下一个任务

如果某一步失败：
- 必须继续调试并修复
- 不得停在“我建议下次再做”
- 除非阻塞项属于“人工前置条件”

---

# 2. Phase 0 — 执行前检查与基线冻结

## Task 0.1：项目现状扫描
**目标：** 识别当前项目真实代码、测试、文档、依赖状态。

**Hermes actions**
- 读取：
  - `README.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/RUN_GUIDE.md`（若存在）
  - `app/main.py`
  - `app/schemas.py`
  - `app/services/`
  - `tests/`
- 统计：
  - 当前 endpoint 数量
  - 当前测试数量与通过情况
  - 当前 storage / evaluation / docs 结构
  - 当前环境配置方式（WSL + conda / `.env` / 本地模型依赖）

**验证**
- 跑一次全量测试或在必要时分批跑测试并汇总
- 输出当前 baseline 状态摘要

**完成标准**
- 形成一份“当前基线事实”摘要，供后续所有阶段引用

---

## Task 0.2：检查人工前置条件并分类
**目标：** 明确哪些阶段可立即自动推进，哪些需要用户补信息。

**Hermes actions**
- 检查 `.env.example` 与运行链路
- 检查是否存在可用 `.env`（只验证存在与字段，不泄露敏感值）
- 检查项目内是否已有样例 PDF / metadata 可用于评测集生成
- 根据现状生成“可立即执行 / 需人工确认 / 可先用 mock 替代”的分类表

**验证**
- 输出阻塞表

**完成标准**
- 明确：
  - Phase 1 是否可直接做
  - Phase 2 的真实评估是否需外部模型
  - Phase 5 是否需 GitHub / 部署目标

---

## Task 0.3：建立升级执行总 Todo 与阶段状态文档
**目标：** 为后续自动执行建立统一状态跟踪。

**Hermes actions**
- 创建：`docs/EXECUTION_STATUS.md`
- 内容包含：
  - 阶段列表
  - 每阶段任务清单
  - 状态：pending / in_progress / completed / blocked
  - 当前阻塞项
  - 最近测试结果
  - 当前执行环境说明（WSL + conda）

**验证**
- 文档创建成功

**完成标准**
- 后续每个阶段完成后都更新该文件

---

# 3. Phase 1 — P0 评估体系建设（最高优先级）

> 目标：先做出 benchmark 和 baseline，让项目具备“可评估、可优化”的骨架。

## Task 1.1：建立 evaluation 目录结构与 schema
**目标：** 创建评测模块基础结构。

**文件**
- 新建：
  - `app/evaluation/__init__.py`
  - `app/evaluation/schemas.py`
  - `app/evaluation/datasets/`
  - `app/evaluation/reports/`
  - `app/evaluation/scripts/`
- 新建测试：
  - `tests/test_evaluation_schemas.py`

**Hermes actions**
- 先写 schema 测试：
  - QA 样本 schema
  - Comparison 样本 schema
  - Retrieval eval result schema
- 跑失败测试
- 实现最小 schema
- 再跑通过

**完成标准**
- 有稳定可复用的评测数据结构定义

---

## Task 1.2：生成最小 benchmark 数据集（自动生成版）
**目标：** 构建可立即运行的最小评测集，不依赖大规模人工标注。

**策略**
优先自动生成一个“弱标注 baseline 数据集”：
- 从项目已有 metadata / parsed JSON 中抽样
- 生成：
  - section-based 问题
  - abstract-based 问题
  - multi-paper 对比问题
- 以程序规则生成初始 gold supporting sections

**文件**
- 新建：
  - `app/evaluation/scripts/build_seed_dataset.py`
  - `app/evaluation/datasets/qa_eval_seed.jsonl`
  - `app/evaluation/datasets/comparison_eval_seed.jsonl`
- 新建测试：
  - `tests/test_seed_dataset_builder.py`

**注意**
如果项目缺少可用样本论文：
- Hermes 必须报告阻塞：需要用户提供一批论文 PDF 或 metadata

若已有项目样本：
- 应默认直接基于现有样本生成 seed dataset
- 并在文档中说明样本规模与局限性

**完成标准**
- 至少能生成一份小规模 seed dataset

---

## Task 1.3：实现 retrieval evaluation 指标
**目标：** 先做最确定、最不依赖主观判断的部分。

**指标**
- Hit@k
- Recall@k
- MRR

**文件**
- 新建：
  - `app/evaluation/metrics.py`
  - `app/evaluation/scripts/evaluate_retrieval.py`
- 测试：
  - `tests/test_evaluation_metrics.py`
  - `tests/test_retrieval_evaluator.py`

**Hermes actions**
- 先写纯函数指标测试
- 再写 evaluator 测试
- 再实现 metrics 与 evaluator
- 用 seed dataset 跑一次 baseline

**完成标准**
- 能产出 retrieval baseline 数值

---

## Task 1.4：生成 baseline report
**目标：** 把评估结果沉淀成可读文档。

**文件**
- 新建：
  - `app/evaluation/reporting.py`
  - `app/evaluation/reports/baseline_report.md`
- 测试：
  - `tests/test_evaluation_reporting.py`

**输出内容建议**
- 数据集规模
- 检索配置
- Hit@k / Recall@k / MRR
- 失败案例样本
- 下一步优化建议
- 当前运行环境（WSL + conda）与验证说明（离线 / 真实链路）

**完成标准**
- 有首版 benchmark 报告可供 README 引用

---

## Task 1.5：实现 answer / citation evaluation 骨架
**目标：** 先做框架，支持后续真实 LLM judge 或规则评估接入。

**模式**
- 先实现 rule-based + placeholder judge
- 若存在可用 LLM，再补 LLM judge 模式

**文件**
- 新建：
  - `app/evaluation/judges.py`
  - `app/evaluation/scripts/evaluate_qa.py`
- 测试：
  - `tests/test_evaluation_judges.py`
  - `tests/test_qa_evaluator.py`

**完成标准**
- 能在无外部依赖时跑基础 answer/citation evaluator
- 有扩展点可接真实 judge

---

## Task 1.6：文档同步
**目标：** 让 Phase 1 成果形成“简历可讲述资产”。

**Hermes actions**
- 更新：
  - `README.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/EXECUTION_STATUS.md`
- 记录：
  - 评测数据结构
  - benchmark 脚本
  - baseline 报告路径
  - 当前指标结果
  - 运行环境与验证边界（WSL + conda / 离线 or 真实链路）

**完成标准**
- 项目已具备“有 benchmark”的公开叙事

---

# 4. Phase 2 — P1 检索质量升级

> 目标：让项目从基础版 RAG 升级为更像企业项目的高质量 RAG。

## Task 2.1：接入 reranker 接口层
**目标：** 不先绑定具体模型，先设计可插拔 reranker 接口。

**文件**
- 新建：
  - `app/services/reranker.py`
- 测试：
  - `tests/test_reranker.py`

**完成标准**
- 支持 mock reranker
- 支持后续 sentence-transformers cross-encoder 或 API reranker

---

## Task 2.2：RAG pipeline 增加 rerank 步骤
**目标：** 在检索后加入 reranking。

**文件**
- 修改：
  - `app/services/paper_qa.py`
  - 相关 schema / config
- 测试：
  - `tests/test_paper_qa.py`
  - 新增 rerank 相关测试

**验证**
- retrieval benchmark before/after

**完成标准**
- QA 链路支持 dense → rerank

---

## Task 2.3：实现 hybrid retrieval
**目标：** 支持 dense + sparse 组合检索。

**文件**
- 新建：
  - `app/services/sparse_retriever.py`
  - 或 `app/services/hybrid_retriever.py`
- 修改：
  - `vector_store.py` 或 retrieval 组装逻辑
- 测试：
  - `tests/test_hybrid_retrieval.py`

**默认策略**
- 若允许新增依赖，优先 `rank-bm25`
- 若不允许，可先实现轻量 token overlap baseline

**完成标准**
- benchmark 支持 dense / sparse / hybrid 对比

---

## Task 2.4：实现 citation grounding 所需 metadata 扩展
**目标：** 让 chunk / source 能携带更完整引用信息。

**可能需要扩展**
- page number
- section heading
- paper title
- chunk span / offsets（可选）

**文件**
- 修改：
  - `app/schemas.py`
  - `pdf_parser.py`
  - `chunker.py`
  - `paper_qa.py`
- 测试：
  - `tests/test_chunker.py`
  - `tests/test_pdf_parser.py`
  - `tests/test_paper_qa.py`

**注意**
如果当前 PDF parser 无法稳定提取页码，可先支持“section + chunk_id + snippet”版本，再标记页码为下一迭代。

**完成标准**
- QA 输出能明确展示 evidence 元信息

---

## Task 2.5：扩展 answer / citation evaluation 使用新链路
**目标：** 用 Phase 1 的评估框架验证 reranker / hybrid / citation 的收益。

**Hermes actions**
- 扩展 benchmark runner
- 产出对比报告：
  - baseline dense
  - dense + rerank
  - hybrid
  - hybrid + rerank

**输出**
- `app/evaluation/reports/retrieval_upgrade_report.md`

**完成标准**
- 至少一项指标可量化提升
- 若未提升，也必须记录实验结果与原因

---

# 5. Phase 3 — P1 多论文结构化 Synthesis 升级

> 目标：把“多论文对比”做成项目最有辨识度的亮点能力。

## Task 3.1：设计 comparison schema
**目标：** 让 comparison 不再只是自由文本，而是结构化输出。

**建议字段**
- research_problem
- method
- backbone
- dataset
- metrics
- strengths
- limitations
- scenarios
- key_differences
- evidence

**文件**
- 修改/新增：
  - `app/schemas.py`
  - `app/services/paper_compare.py`
- 测试：
  - `tests/test_paper_compare.py`（若不存在则新建）

**完成标准**
- comparison 能输出结构化 JSON / markdown 双形态

---

## Task 3.2：实现 per-paper structured extraction
**目标：** 先从单篇抽字段，再做跨论文对齐。

**文件**
- 新建：
  - `app/services/paper_extractor.py`
- 测试：
  - `tests/test_paper_extractor.py`

**完成标准**
- comparison 不再完全依赖一次性大 prompt

---

## Task 3.3：comparison 增加 evidence-aware 对齐
**目标：** 每个比较维度都尽量带 evidence。

**文件**
- 修改 `paper_compare.py`
- 更新 response schema
- 补测试

**完成标准**
- 比较结果中能定位证据来源

---

## Task 3.4：comparison evaluation 骨架实现
**目标：** 用评估框架衡量结构化 comparison 的覆盖度与完整度。

**指标建议**
- schema completeness
- evidence completeness
- paper coverage balance

**文件**
- 新建：
  - `app/evaluation/scripts/evaluate_comparison.py`
- 测试：
  - `tests/test_comparison_evaluator.py`

**完成标准**
- comparison 模块也进入 benchmark 闭环

---

# 6. Phase 4 — P2 工程化升级

## Task 4.1：设计索引异步任务 schema
**目标：** 为解析 / embedding / indexing 提供 job model。

**文件**
- 新建：
  - `app/jobs/schemas.py`
- 测试：
  - `tests/test_job_schemas.py`

---

## Task 4.2：实现最小本地 job runner
**目标：** 先实现无需外部队列的本地异步任务管理。

**文件**
- 新建：
  - `app/jobs/runner.py`
  - `app/jobs/store.py`
- 测试：
  - `tests/test_job_runner.py`

**策略**
- 先做进程内 / 本地文件型任务状态持久化
- 后续再扩展 Celery / RQ / Dramatiq（若有必要）

---

## Task 4.3：暴露 job API
**目标：** 让索引流程支持异步调用。

**建议接口**
- `POST /jobs/index`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/retry`

**文件**
- 修改 `app/main.py`
- 修改 schemas
- 补 API 测试

---

## Task 4.4：增加 observability 基础能力
**目标：** 支持请求/检索/回答链路的日志与简单指标。

**建议内容**
- structured logging
- retrieval trace
- latency 记录
- benchmark run metadata

**文件**
- 新建：
  - `app/observability/logging.py`
  - `app/observability/metrics.py`
- 测试：
  - `tests/test_observability.py`

---

## Task 4.5：存储层升级预留
**目标：** 不一定一步切库，但至少让架构可替换。

**建议实现**
- 为 metadata / jobs / evaluation report 提供统一 storage abstraction
- 先兼容本地 JSON / SQLite

**完成标准**
- 项目架构上不再强耦合单一 JSON 文件

---

# 7. Phase 5 — P3 交付增强

## Task 5.1：Docker 化
**目标：** 提供本地一键运行能力。

**文件**
- 新建：
  - `Dockerfile`
  - `docker-compose.yml`（可选）
  - `.dockerignore`
- 测试：
  - 至少验证 build 成功（如环境允许）

**人工前置条件**
- 若本机无 Docker，则只能生成文件与说明，不能完成真实运行验证

---

## Task 5.2：CI 工作流
**目标：** 自动运行测试，强化工程可信度。

**文件**
- 新建：
  - `.github/workflows/tests.yml`

**人工前置条件**
- 需要仓库最终托管到 GitHub / Git 平台，Hermes 本地只能生成 workflow 文件

---

## Task 5.3：README / docs / 演示资产升级
**目标：** 强化求职展示效果。

**建议补充**
- benchmark 指标表
- 检索架构图
- comparison 结构化输出示例
- citation grounding 示例
- 项目简历写法示例

**文件**
- 更新：
  - `README.md`
  - `docs/DEVELOPMENT_LOG.md`
  - `docs/RUN_GUIDE.md`
- 新建：
  - `docs/RESUME_BULLETS.md`
  - `docs/BENCHMARK_SUMMARY.md`

---

# 8. 阶段性阻塞策略

当 Hermes 自动执行时，若遇到以下情况，必须暂停并明确报告：

## Blocker A：没有任何可用于 benchmark 的论文样本
**需要人工提供**
- PDF 文件，或
- 已解析 metadata 样本

备注：如果项目内已有样本，则不应将此项视为当前阻塞。

## Blocker B：需要真实 LLM judge / reranker / comparison 验证，但当前模型链路不可用
**需要人工提供或确认**
- 可用 API Key / Base URL / Model，或
- 允许切换到本地模型，或
- 同意先使用 rule-based / mock / offline 方案继续推进

## Blocker C：需要真实部署验证，但本机缺 Docker / GitHub 连接
**处理方式**
- 继续生成配置文件
- 标记为“待人工验证”

## Blocker D：引入新依赖与现有环境冲突
**处理方式**
- 先尝试最小替代实现
- 若仍不可行，再向用户报告

## Blocker E：测试或评估耗时过长，无法在单轮内完成全量验证
**处理方式**
- 先跑目标测试或分批测试
- 汇总已验证范围与未验证范围
- 不得将“未完整跑完”伪装为“已完全验证”

---

# 9. Hermes 推荐的自动执行顺序

如果现在就开始自动推进，建议顺序如下：

1. **Phase 0 全部做完**
2. **Phase 1.1 ~ 1.4 先做完**（先拿到 retrieval benchmark baseline）
3. **再做 2.1 / 2.2 reranker 接口与接入**
4. **然后做 2.3 hybrid retrieval**
5. **再做 2.4 citation grounding**
6. **做 2.5 benchmark 对比报告**
7. **再做 Phase 3 多论文结构化升级**
8. **最后补 Phase 4 / 5 工程化与展示**

这条路径最容易尽快产出：
- 可量化 benchmark
- 可写进简历的技术亮点
- 可展示的优化前后对比

---

# 10. 第一轮自动执行的最小目标（建议立即开始）

第一轮 Hermes 自动执行建议只聚焦到以下可闭环目标：

## Sprint A（推荐立即执行）
- Task 0.1：项目现状扫描
- Task 0.2：人工前置条件检查
- Task 0.3：执行状态文档
- Task 1.1：evaluation schema
- Task 1.2：seed dataset builder
- Task 1.3：retrieval evaluation metrics
- Task 1.4：baseline report

**Sprint A 产出价值：**
- 从“没有 benchmark”升级为“有 benchmark 框架和 baseline”
- 这是后续所有优化的基础
- 也是最容易最先写进简历的硬证据

---

# 11. 每次执行完成后的标准汇报格式（Hermes 输出模板）

每次完成一个任务或一个小阶段，Hermes 应按以下格式汇报：

```markdown
## 已完成
- 做了什么
- 修改了哪些文件
- 新增了哪些测试

## 验证结果
- 跑了哪些命令
- 哪些测试通过
- 指标结果如何
- 是否在 WSL + conda 环境下验证

## 当前阻塞
- 是否需要人工提供资源
- 如果需要，具体缺什么

## 下一步
- 将继续执行哪个任务
```

---

# 12. 文档维护要求

每完成一个阶段，Hermes 必须同步更新：
- `docs/EXECUTION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`
- `README.md`（若用户可见能力有变化）

确保项目始终满足：
- 可运行
- 可验证
- 可讲述
- 可逐步自动执行
- 遇到阻塞时可清楚接力
