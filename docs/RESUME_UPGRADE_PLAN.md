# ResearchAgent 求职导向升级规划（LLM / AI 应用开发岗位）

> 目标：将当前 ResearchAgent 从“完整可运行的论文 RAG Demo”升级为“适合写进大模型 / AI 应用开发岗位简历、能体现评估能力、RAG 深度与工程化能力的项目”。

---

## 1. 当前项目基线

### 1.1 已具备能力

当前项目已经具备以下基础能力：

- PDF 上传与解析
- 结构化 Markdown 笔记生成
- 本地知识库构建
- 单篇 / 全库 RAG 问答
- 多论文对比
- 向量索引本地持久化
- 删除论文与索引清理
- 索引状态查询 API
- FastAPI 后端 + Streamlit 前端
- 自动化测试

### 1.2 当前项目优势

相较于普通的 LLM Demo（如纯聊天壳子、单接口调用类项目），ResearchAgent 已经具备：

1. **端到端闭环能力**：从 PDF ingestion → parsing → indexing → retrieval → generation → UI 展示
2. **明确场景聚焦**：论文研究助手 / 多论文比较，而不是泛化聊天机器人
3. **一定工程意识**：有 API、测试、删除清理、状态查询与持久化

### 1.3 当前短板

如果目标是用于投递 **大模型应用开发 / AI 应用工程 / LLM Engineer / RAG 工程师** 等岗位，目前仍存在以下不足：

- 缺少系统化评估（retrieval / answer / citation / comparison）
- 检索链路仍偏基础版 RAG，缺少 reranker / hybrid retrieval / metadata filtering
- 多论文对比能力尚未形成“结构化研究工作流”亮点
- 缺少异步任务、可观测性、部署与存储升级等工程化加强项
- 简历上可量化成果不足，尚不能很好证明优化能力

因此，后续升级重点不应是继续简单堆功能，而应转向：

- **补评估**
- **补检索优化**
- **补可信引用**
- **补工程成熟度**
- **补可量化成果**

---

## 2. 升级总目标

将项目升级为一个具备以下特征的求职型作品：

### 2.1 求职导向目标

该项目最终应该能在简历中体现出以下能力：

- 能独立搭建完整的 LLM 应用系统
- 理解 RAG 系统核心设计与优化方法
- 具备效果评估与指标驱动迭代能力
- 具备 Agent / workflow / tool-use 的扩展思维
- 具备一定工程化、可观测性、可部署意识

### 2.2 最终目标画像

升级后，ResearchAgent 不应只被描述为：

> 一个论文阅读和问答工具

而应能被描述为：

> 一个面向科研论文研究场景的多文档 RAG / Synthesis 系统，支持文档解析、结构化知识抽取、检索增强问答、跨论文对比、引用溯源、质量评估与工程化交付。

---

## 3. 升级优先级总览（P0 ~ P3）

| 优先级 | 模块 | 核心价值 | 对简历收益 |
|--------|------|----------|------------|
| P0 | 评估体系 | 从“能跑”升级为“可验证、可优化” | 极高 |
| P1 | RAG 深化（reranker / hybrid / citation） | 从基础版 RAG 升级为可信、高质量 RAG | 极高 |
| P1 | 结构化多论文对比 | 形成项目差异化亮点 | 极高 |
| P2 | 异步索引与任务编排 | 提升工程感与可扩展性 | 高 |
| P2 | 存储架构升级 | 提升项目可信度与系统性 | 高 |
| P2 | Observability | 体现真实 AI 系统调优能力 | 中高 |
| P3 | 成本 / 缓存 / 限流 / 模型路由 | 体现生产化思维 | 中 |
| P3 | 部署 / CI / 演示资产 | 提升交付与展示效果 | 中 |

---

## 4. 详细升级规划

---

# P0：评估体系建设（最高优先级）

## 4.1 目标

建立一套最小但完整的 **ResearchAgent RAG 评估闭环**，使项目具备：

- 检索质量可测
- 回答质量可测
- 引用正确性可测
- 多论文对比效果可测
- 后续优化具备量化依据

## 4.2 为什么要先做 P0

对于 AI 应用 / LLM 岗位，企业最关注的不只是“是否做了一个 RAG 系统”，而是：

- 你是否知道怎么判断系统效果好不好
- 你是否会基于指标做优化
- 你是否具备 AI 系统实验设计能力

没有评估，项目只能证明“你能做功能”；
有评估，项目才能证明“你能做优化”。

## 4.3 建议交付物

### 交付物 A：评测数据集

建议构建一个小规模但结构化的评测集，例如：

- 50~200 条单篇问答样本
- 20~50 条全库问答样本
- 20~50 条多论文比较样本

每条样本尽量包含：

- `question`
- `target_paper_ids`
- `gold_answer`
- `gold_supporting_chunks`
- `gold_sections`
- `task_type`（single_paper / multi_paper / comparison）

### 交付物 B：评估脚本

建议实现：

- `evaluate_retrieval.py`
- `evaluate_qa.py`
- `evaluate_comparison.py`
- `run_benchmark.py`

### 交付物 C：评估指标

#### Retrieval 指标
- Hit@k
- Recall@k
- MRR
- nDCG（可选）

#### Answer 指标
- Answer relevance
- Faithfulness
- Citation correctness
- Unsupported claim ratio（可选）

#### Comparison 指标
- Coverage
- Evidence completeness
- Schema completeness
- Cross-paper balance（可选）

## 4.4 实施建议

### 数据集落盘位置建议

```text
app/evaluation/
  datasets/
    qa_eval.jsonl
    comparison_eval.jsonl
  scripts/
    evaluate_retrieval.py
    evaluate_qa.py
    evaluate_comparison.py
  reports/
    baseline_report.md
```

### 最小闭环顺序

1. 先做 retrieval evaluation
2. 再做 answer evaluation
3. 最后做 comparison evaluation
4. 输出 baseline report

## 4.5 简历价值

做完后，简历中可以写：

- 构建论文 RAG 评测集与评估脚本，建立 hit@k、MRR、faithfulness、citation correctness 指标
- 基于 benchmark 驱动检索与生成链路优化，而非仅依赖主观体验

---

# P1：RAG 质量升级

---

## 5.1 Reranker（两阶段检索）

### 目标

将当前单阶段 dense retrieval 升级为：

1. 初筛：embedding 检索
2. 精排：cross-encoder reranker

### 价值

- 提升 top-k 结果质量
- 更适合长文档、专业术语、长尾问题场景
- 更容易在 benchmark 中体现优化效果

### 建议交付物

- `app/services/reranker.py`
- RAG pipeline 中增加 rerank 步骤
- benchmark 对比：with / without reranker

### 验证方式

- 统计 reranker 前后的 Hit@5 / MRR 提升
- 抽样检查 top-3 结果质量变化

### 简历价值

- 设计 dense retrieval + reranking 两阶段检索架构，提升论文问答场景下的召回与排序质量

---

## 5.2 Citation Grounding（引用溯源）

### 目标

让 QA / comparison 输出不仅有答案，还能明确指出：

- 来源论文
- section
- chunk_id
- 页码（若可获取）
- 原文证据片段

### 价值

- 提升可解释性
- 降低幻觉观感
- 非常适合演示和面试展示

### 建议升级

- PDF parsing 阶段补页码信息（若当前结构中缺失）
- chunk metadata 中保留页码字段
- QA response schema 增加 citation detail
- UI 支持展示 evidence 列表

### 简历价值

- 实现 citation grounding 与证据回溯机制，增强回答可信度与结果可验证性

---

## 5.3 Hybrid Retrieval

### 目标

从单一 dense retrieval 升级为 dense + sparse（如 BM25）混合检索。

### 价值

- 更适合处理术语精确匹配
- 弥补 embedding 对关键词召回不足的问题
- 更贴近企业级知识库系统常见做法

### 建议实现路线

- 首先引入一个轻量 BM25 检索模块
- 对 dense / sparse 分数做加权融合
- 支持 ablation：dense only / sparse only / hybrid

### 简历价值

- 引入 hybrid retrieval 优化专业术语与长尾查询召回效果

---

## 5.4 Metadata Filtering

### 目标

增强检索时的结构化过滤能力。

### 支持方向

- paper_id 过滤（已有）
- section 过滤
- 年份过滤（后续 metadata 扩展）
- 主题 / tag 过滤（后续扩展）
- comparison 时按 paper 平衡召回

### 价值

- 提升研究场景实用性
- 体现对知识库检索系统的理解

---

# P1：结构化多论文对比升级

## 6.1 目标

把当前“多论文对比”从简单 prompt 输出升级为 **结构化研究 synthesis 模块**。

## 6.2 建议输出 schema

每篇论文或每组对比应输出以下结构：

- 研究问题
- 核心方法
- 模型结构 / backbone
- 数据集
- 指标
- 优势
- 局限
- 适用场景
- 与其他论文的关键差异
- 证据引用

## 6.3 升级方向

### 方向 A：结构化抽取
先从每篇论文中抽取固定字段，再做多论文比较。

### 方向 B：Evidence-aware comparison
每个比较维度都要求绑定证据 chunk / citation。

### 方向 C：冲突与差异识别
自动指出：

- 方法差异
- 指标优劣
- 适用场景差异
- 潜在矛盾结论

## 6.4 价值

这是最容易形成项目差异化卖点的一块。做好后，项目就不再只是一个“论文问答器”，而更像“研究工作流 AI 工具”。

## 6.5 简历价值

- 构建多论文结构化比较与 synthesis 流程，支持研究问题、方法、指标、优劣势等多维度对齐分析与证据引用

---

# P2：工程化升级

---

## 7.1 异步索引与任务系统

### 目标

将当前同步解析 / 切块 / embedding / index 流程，升级为后台任务流水线。

### 建议能力

- 上传后异步处理
- job_id + status 查询
- 失败重试
- 任务错误原因记录
- 批量导入

### 建议 API

- `POST /jobs/index`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/retry`

### 价值

- 强化工程感
- 更适合后续接真实前端
- 适合展示任务编排能力

---

## 7.2 存储架构升级

### 当前问题

当前向量索引虽然已支持本地持久化，但仍偏轻量原型。

### 升级建议

最低成本方案：

- SQLite：存 metadata / jobs / evaluation records
- Chroma / FAISS：存向量

更强方案：

- PostgreSQL + pgvector
- Qdrant / Milvus（如果你想突出向量数据库经验）

### 价值

- 更接近真实项目
- 简历可信度更高

---

## 7.3 Observability

### 建议埋点内容

- 请求级日志
- retrieval latency
- answer latency
- token usage
- top-k retrieval trace
- rerank score
- error rate

### 输出形式建议

- 本地日志文件
- benchmark report
- 管理页 / debug 页（可选）

### 价值

体现你对 AI 系统可调试性、可维护性的理解。

---

# P3：产品化与交付能力补强

---

## 8.1 缓存 / 成本控制 / 模型路由

### 可选能力

- embedding cache
- query cache
- answer cache
- 模型路由（小模型处理简单任务，大模型处理复杂 synthesis）
- rate limit / timeout / fallback

### 价值

适合面试时讲“真实生产场景优化思路”，但求职优先级低于 P0 / P1。

---

## 8.2 部署 / CI / Demo 资产

### 建议补齐

- Docker / docker-compose
- GitHub Actions 自动跑测试
- demo 截图 / demo GIF / 架构图
- benchmark 结果图表
- README 中加入“效果对比”部分

### 价值

- 提高项目可展示性
- 增强交付与协作观感

---

## 9. 推荐落地顺序（按求职收益排序）

### 第一阶段：必须优先完成

1. 评测集与 benchmark 基线
2. retrieval evaluation
3. answer evaluation
4. reranker 接入
5. citation grounding

### 第二阶段：形成项目亮点

6. hybrid retrieval
7. metadata filtering
8. 结构化多论文 synthesis
9. comparison 证据绑定

### 第三阶段：补工程成熟度

10. 异步索引任务系统
11. 存储架构升级
12. observability

### 第四阶段：增强展示和交付

13. Docker / CI
14. benchmark 图表与 README 强化
15. 简历 bullets 与项目说明沉淀

---

## 10. 2 周版升级建议（适合尽快用于秋招 / 社招投递）

如果时间有限，建议优先做一个 **高 ROI 2 周版本**。

### Week 1

#### Day 1~2
- 设计评测集 schema
- 构建 30~50 条 QA 样本
- 构建 10~20 条 comparison 样本

#### Day 3
- 实现 retrieval evaluation 脚本
- 输出 baseline 指标

#### Day 4
- 实现 answer evaluation / citation evaluation 基础版

#### Day 5~6
- 接入 reranker
- 对比 before / after benchmark

#### Day 7
- 记录 benchmark 结果
- 更新 README / docs

### Week 2

#### Day 8~9
- 做 citation grounding
- 扩展 response schema 和 UI 展示

#### Day 10~11
- 实现 hybrid retrieval
- 增加 ablation 实验

#### Day 12~13
- 升级多论文对比为结构化 schema
- 给 comparison 增加 evidence

#### Day 14
- 汇总最终指标
- 编写简历项目描述和面试讲稿

---

## 11. 4 周版升级建议（适合做成高质量核心项目）

### 第 1 周
- 评测集
- retrieval / answer evaluation
- baseline 报告

### 第 2 周
- reranker
- citation grounding
- hybrid retrieval
- benchmark 对比

### 第 3 周
- 结构化多论文 synthesis
- metadata filtering
- comparison evidence

### 第 4 周
- 异步索引任务系统
- observability
- 存储升级
- Docker / CI / README 完善

---

## 12. 项目升级后的理想简历表述方向

项目完成上述升级后，简历中建议突出以下关键词：

- 多文档 RAG
- 检索优化
- hybrid retrieval
- reranking
- citation grounding
- benchmark / evaluation
- structured synthesis
- asynchronous ingestion
- observability
- provider-agnostic LLM application

### 示例表述方向

> 搭建面向科研论文场景的多文档 RAG / Synthesis 系统，支持 PDF 解析、结构化笔记、跨论文问答与多论文比较；构建检索与回答评测集，引入 hybrid retrieval、cross-encoder reranking 与 citation grounding，对 RAG 质量进行指标化评估与迭代优化。

---

## 13. 本项目最值得优先完成的四项升级

如果只能做最重要的部分，优先级如下：

1. **评测集 + Benchmark**
2. **Reranker + Citation Grounding**
3. **Hybrid Retrieval**
4. **结构化多论文对比**

这四项将直接决定该项目是否能从：

- “一个完整的个人 AI Demo”

升级为：

- “一个具备企业视角、可用于求职的大模型应用工程项目”

---

## 14. 下一步建议

建议从 **P0（评估体系）** 开始实施，并以“能产出 benchmark 数据和简历量化成果”为第一目标。

推荐最小执行顺序：

1. 先搭评测集 schema
2. 实现 retrieval evaluation
3. 输出 baseline 报告
4. 再引入 reranker 做第一轮优化
5. 最后把结果写进 README 和简历描述

---

## 15. 文档维护建议

后续每完成一个升级模块，建议同步更新：

- `README.md`
- `docs/DEVELOPMENT_LOG.md`
- `docs/RUN_GUIDE.md`
- benchmark 报告文档
- 简历版本项目说明文档

确保项目始终具备：

- 可运行
- 可演示
- 可评估
- 可讲述
- 可写进简历
