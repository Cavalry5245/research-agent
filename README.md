# ResearchAgent

> 📋 **当前执行计划**：[JD_ALIGNED_ROADMAP.md](docs/JD_ALIGNED_ROADMAP.md)  
> 🎯 **目标**：打造符合「大语言模型与 Agent 应用开发实习生」岗位要求的完整 Agent 应用案例

面向研究生的论文阅读与实验分析 AI 助手。支持 PDF 解析、结构化 Markdown 笔记生成、本地知识库构建、RAG 问答、多论文对比和 Markdown 导出。

相关文档：
- 运行与使用说明：`docs/RUN_GUIDE.md`
- 使用说明：`docs/USAGE.md`
- 系统架构：`docs/ARCHITECTURE.md`
- MVP 需求文档：`docs/MVP_REQUIREMENTS.md`
- 开发日志：`docs/DEVELOPMENT_LOG.md`

## 功能

| 功能 | 说明 |
|------|------|
| 📤 PDF 上传与解析 | PyMuPDF 提取 title / abstract / sections / full_text |
| 📝 笔记生成 | LLM 生成 13 段结构化中文 Markdown 论文笔记 |
| 🔍 RAG 问答 | 向量检索 + LLM，支持单篇/全库，附带依据片段 |
| 📊 多论文对比 | 2–5 篇论文自动生成结构化 Markdown 对比表（含固定核心维度与关键差异） |
| 🗄️ 知识库 | 文本切块 + sentence-transformers 嵌入 + 向量检索；支持多 KB 隔离与增量索引 |
| 🎯 高级 RAG | Cross-encoder Rerank（bge-reranker-v2-m3）+ BM25/Hybrid 检索 + 查询改写 / HyDE |
| 📥 Markdown 导出 | 笔记/对比结果保存为 .md 并支持下载 |
| 🤖 **Agent 助手** | 自然语言驱动：自动拆解任务、调用工具链、工作流编排 |
| 📊 **数据分析 & A/B 测试** | analytics 收集器、3 个实验场景、失败 case 分析、Jupyter Notebook 可视化 |
| ⚙️ **工程化任务与日志** | 后台任务状态追踪、统一错误响应、request_id、JSONL 日志分析 |
| 🧠 **多 Agent 协作** | Supervisor 路由 + 4 个 Specialist Agent + 三层记忆系统 + 执行追踪 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11, FastAPI, Pydantic |
| 前端 | Streamlit |
| PDF 解析 | PyMuPDF |
| LLM | OpenAI-compatible API (DeepSeek / Qwen / Ollama) |
| Embedding | sentence-transformers (bge-small-zh-v1.5) + 多模型切换 (bge-large / m3e / bge-m3) |
| 向量检索 | 余弦相似度（接口兼容 Chroma） |
| **Agent** | **LangChain + LangGraph（工具调用 + 工作流编排 + Supervisor 多 Agent）** |
| **Multi-Agent** | **LangGraph Supervisor + 4 Specialist Agents + SQLite Memory** |
| **Analytics (Phase 2)** | **pandas + matplotlib + seaborn + scipy（指标 / 可视化 / 显著性检验）** |
| **Production readiness (Phase 3)** | **FastAPI BackgroundTasks + FileJobStore + JSONL logging + request tracing** |
| 评测 | `app/evaluation` schemas + seed dataset builder + retrieval / QA benchmark scripts |
| 配置 | .env (pydantic-settings) |

## Phase 1 Benchmark & Evaluation

Phase 1 已补齐一套可离线运行的 benchmark 骨架，用于把项目从“能跑”升级为“可评估、可讲述”。当前重点是验证评测数据流、脚本通路和报告产物，而不是宣称真实线上 RAG 效果。

### 评测数据结构

`app/evaluation/schemas.py` 当前定义了三类核心结构：
- `QAEvalSample`：单论文问答样本，字段包含 `sample_id`、`question`、`expected_answer`、`paper_id`、`paper_title`、`supporting_sections`、`difficulty`、`metadata`
- `ComparisonEvalSample`：多论文对比样本，字段包含 `paper_ids`、`paper_titles`、`expected_summary`、`comparison_aspects`、`supporting_sections`
- `RetrievalEvalResult` / `RetrievalMatch`：检索评测结果，记录 `hit_at_k`、`recall_at_k`、`mrr` 及每个候选 chunk 的 `rank`、`section`、`score`

### Benchmark 脚本与产物

- Seed dataset 构建：`app/evaluation/scripts/build_seed_dataset.py`
- Retrieval benchmark：`app/evaluation/scripts/evaluate_retrieval.py`
- QA answer/citation benchmark 骨架：`app/evaluation/scripts/evaluate_qa.py`
- QA seed dataset：`app/evaluation/datasets/qa_eval_seed.jsonl`
- Comparison seed dataset：`app/evaluation/datasets/comparison_eval_seed.jsonl`
- Baseline Markdown 报告：`app/evaluation/reports/baseline_report.md`
- Retrieval JSON 报告：`app/evaluation/reports/retrieval_eval_seed_report.json`
- QA JSON 报告：`app/evaluation/reports/qa_eval_seed_report.json`

### 当前基线结果

基于当前仓库内 parsed metadata 自动生成的 seed dataset：
- QA samples: 11
- Papers covered: 4
- Supporting-section labels: 6

当前 `baseline_report.md` 记录的 retrieval baseline 为：
- Hit@3 = 1.000
- Recall@3 = 1.000
- MRR = 1.000

当前 `qa_eval_seed_report.json` 记录的 rule-based QA scaffold 结果为：
- answer_pass_rate = 1.000
- citation_pass_rate = 1.000
- mean_answer_score = 1.000
- mean_citation_score = 1.000

注意：这些数值来自离线 deterministic seed baseline。`evaluate_retrieval.py` 会把 gold supporting section 注入 rank 1，`evaluate_qa.py` 也直接使用 seed expected answer 作为预测值，因此这些结果只能证明评测框架、报告生成和数据结构已经打通，不能代表真实向量检索或真实 LLM 问答质量。

### 运行环境与验证边界

- 默认验证环境：WSL + 已激活 conda 环境
- 当前 benchmark 结论：离线可复现、无需真实外部模型
- 尚未覆盖：真实 embedding 检索链路、真实 LLM 回答链路、线上 API 波动、跨环境性能差异
- 因此当前公开叙事应表述为：“项目已具备 benchmark 与 baseline report 骨架，可继续接入真实检索链路验证优化收益”，而不是“检索效果已达 100%”。

### Benchmark 命令

```bash
python app/evaluation/scripts/build_seed_dataset.py
python app/evaluation/scripts/evaluate_retrieval.py --top-k 3
python app/evaluation/scripts/evaluate_qa.py --mode rule_based
```


## 快速启动

```powershell
# 1. 创建并激活 conda 环境
conda create -n research_agent python=3.11 -y
conda activate research_agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env: 填入 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 4. 启动 Streamlit（推荐，单命令运行）
streamlit run ui/streamlit_app.py
# → 浏览器打开 http://localhost:8501

# 或启动 FastAPI 后端
uvicorn app.main:app --reload
# → http://localhost:8000
# → API 文档: http://localhost:8000/docs
```

## 使用流程

### 1. 上传论文
- 打开 Streamlit，在「📤 论文上传」Tab 选择 PDF
- 系统自动解析并分配 paper_id
- 在列表中可查看已上传论文

### 2. 生成笔记
- 切换到「📝 笔记生成」Tab
- 选择论文，点击「🤖 生成笔记」
- 系统调用 LLM 生成 13 段结构化中文 Markdown
- 支持预览和下载 .md 文件

### 3. 构建知识库
- 切换到「🗄️ 知识库」Tab
- 选择论文，点击「📥 索引到向量库」
- 论文被切块（chunk_size=800）、向量化、写入向量库

### 4. 论文问答
- 切换到「💬 论文问答」Tab
- 选择全库或单篇，输入问题
- 系统检索相关片段，LLM 基于上下文生成回答
- 底部展示检索依据片段

### 5. 多论文对比
- 切换到「📊 论文对比」Tab
- 选择 2–5 篇论文，点击「📊 生成对比表」
- LLM 生成结构化 Markdown 对比表，并汇总关键差异与证据摘录

## 系统架构

```
Streamlit UI (5 Tabs)
  ↓ 直接调用
Service Layer
  ├── pdf_parser (PyMuPDF)
  ├── note_generator → LLM
  ├── paper_qa → VectorStore + Embedding + LLM
  ├── paper_compare → LLM
  └── chunker / markdown_exporter
  ↓
Background Tasks + JobStore + JSONL Logs
  ↓
Storage: papers/ | notes/ | metadata/ | vector_db/ | logs/
```

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/papers` | 列出所有论文 |
| `POST` | `/papers/upload` | 上传 PDF（自动解析） |
| `POST` | `/papers/{id}/parse` | 重新解析 |
| `POST` | `/papers/{id}/note` | 生成笔记 |
| `GET` | `/papers/{id}/note` | 读取笔记 |
| `GET` | `/papers/{id}/download` | 下载笔记 |
| `POST` | `/papers/{id}/index` | 切块入库 |
| `GET` | `/papers/{id}/index-status` | 查看单篇论文索引状态 |
| `GET` | `/library/index-status` | 查看知识库索引汇总 |
| `DELETE` | `/papers/{id}` | 删除论文及相关索引/笔记 |
| `POST` | `/qa` | RAG 问答 |
| `POST` | `/papers/compare` | 多论文对比 |
| `GET` | `/tasks` | 列出后台任务 |
| `POST` | `/tasks/note/{id}` | 提交笔记生成后台任务 |
| `POST` | `/tasks/compare` | 提交多论文对比后台任务 |
| `GET` | `/tasks/{job_id}` | 查询任务状态 |
| `GET` | `/tasks/{job_id}/result` | 获取任务结果 |
| `DELETE` | `/tasks/{job_id}` | 取消任务 |
| `POST` | `/tasks/{job_id}/retry` | 重试失败任务 |
| `POST` | `/agent/execute` | Agent 执行（mode: react/supervisor） |
| `GET` | `/api/conversations` | 对话历史列表 |
| `GET` | `/api/conversations/{id}` | 对话详情 |
| `GET` | `/api/traces` | Agent 执行追踪 |
| `GET` | `/api/traces/stats` | 追踪统计 |

### cURL 示例

```powershell
# 上传 PDF
curl -X POST http://localhost:8000/papers/upload -F "file=@paper.pdf"

# 生成笔记
curl -X POST http://localhost:8000/papers/paper_20260505_001/note

# 论文问答
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"question":"核心创新点是什么？","top_k":5}'

# 查看单篇索引状态
curl http://localhost:8000/papers/paper_20260505_001/index-status

# 查看知识库索引汇总
curl http://localhost:8000/library/index-status

# 多论文对比
curl -X POST http://localhost:8000/papers/compare \
  -H "Content-Type: application/json" \
  -d '{"paper_ids":["paper_20260505_001","paper_20260505_002"]}'
```

## 项目结构

```
research-agent/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── MVP_REQUIREMENTS.md    # 完整需求文档
│   ├── DEVELOPMENT_LOG.md     # 开发日志
│   └── ARCHITECTURE.md        # 系统架构
├── app/
│   ├── main.py                # FastAPI (13 endpoints)
│   ├── config.py              # 配置管理
│   ├── schemas.py             # Pydantic 模型
│   ├── services/              # 核心模块
│   │   ├── pdf_parser.py
│   │   ├── llm_client.py
│   │   ├── embedding_client.py
│   │   ├── vector_store.py
│   │   ├── chunker.py
│   │   ├── note_generator.py
│   │   ├── paper_qa.py
│   │   ├── paper_compare.py
│   │   ├── paper_status.py
│   │   ├── paper_manager.py
│   │   └── markdown_exporter.py
│   ├── prompts/               # Prompt 模板
│   │   ├── paper_note_prompt.py
│   │   ├── qa_prompt.py
│   │   └── compare_prompt.py
│   ├── agents/                # Agent 系统（Phase 1）
│   │   ├── tools/             # 工具封装层
│   │   ├── workflows/         # LangGraph 工作流
│   │   ├── prompts/           # Agent prompt 模板
│   │   ├── langchain_adapter.py  # BaseTool → LangChain 适配
│   │   └── paper_research_agent.py  # Agent 主体
│   ├── storage/               # 本地数据
├── ui/
│   └── streamlit_app.py       # 5 Tab 前端
├── examples/
│   ├── sample_papers/
│   └── sample_outputs/
│       └── sample_note.md
└── tests/                     # 202 passed, 1 skipped（当前最新本地全量测试基线）
    ├── test_paper_status.py
    ├── test_paper_manager.py
    ├── test_pdf_parser.py
    ├── test_note_generator.py
    ├── test_chunker.py
    ├── test_retrieval.py
    └── test_paper_qa.py
```

## 开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 项目初始化 | FastAPI + Streamlit 骨架 | ✅ |
| PDF 解析 | PyMuPDF → title/abstract/sections | ✅ |
| 笔记生成 | LLM 13段 Markdown 模板 | ✅ |
| 文本切块 | chunk_size=800, overlap=100 | ✅ |
| Embedding + 向量库 | sentence-transformers + 本地持久化检索 | ✅ |
| RAG 问答 | 检索 + LLM 生成 + sources | ✅ |
| 多论文对比 | 2-5 篇结构化对比表 | ✅ |
| Streamlit 前端 | 6 Tab 完整串联（含 Agent 助手） | ✅ |
| **Agent 系统** | LangChain + LangGraph 工作流编排（6 工具 + 2 工作流） | ✅ |
| **数据分析与效果评估** | Phase 2 analytics + experiments + 4 个 Jupyter Notebook + 失败分析 | ✅ |
| **工程化与生产就绪** | 异步任务、结构化日志、错误处理、健康检查、日志分析 | ✅ |
| **高级 RAG（Phase 4）** | Cross-encoder Rerank + BM25/Hybrid + QueryRewrite/HyDE + 多 KB | ✅ |
| **多 Agent 协作（Phase 5）** | Supervisor 路由 + Specialist Agents + 三层记忆 + 执行追踪 | ✅ |
| 测试基线 | 202 → 401 passed | ✅ |

## 运行测试

```bash
conda activate research_agent
python -m pytest tests -q
# 202 passed, 1 skipped
```

## 后续升级

> 📋 **详细升级路线图**：[JD_ALIGNED_ROADMAP.md](docs/JD_ALIGNED_ROADMAP.md)  
> 🎯 **执行周期**：12 周（6 个 Phase）  
> 🚀 **当前阶段**：Phase 2 已完成（2026-05-20）→ Phase 3 准备启动

| Phase | 目标 | 周期 |
|-------|------|------|
| Phase 1 | Agent 工作流基础（工具封装、LangChain 集成、工作流编排） | Week 1-2 |
| Phase 2 | 数据分析与效果评估（Pandas/Matplotlib、A/B 测试、失败分析） | Week 3-4 |
| Phase 3 | 工程化与生产就绪（异步任务、结构化日志、数据库、缓存） | Week 5-6 |
| Phase 4 | 高级 RAG 与检索增强（Rerank、Hybrid Search、HyDE、查询改写） | Week 7-8 |
| Phase 5 | 多 Agent 协作与记忆管理（专业化 Agent、AutoGen/CrewAI、记忆系统） | Week 9-10 |
| Phase 6 | 项目收尾与展示准备（文档完善、代码质量、Demo 视频、面试材料） | Week 11-12 |

## 简历描述

**ResearchAgent：面向科研场景的论文阅读与知识库问答 Agent**

基于 FastAPI、Streamlit、PyMuPDF 和 OpenAI-compatible LLM API 构建科研论文阅读助手，支持论文 PDF 解析、13 段结构化 Markdown 笔记生成、sentence-transformers 向量嵌入、本地持久化向量检索、RAG 问答（附来源引用）、多论文结构化对比和 Markdown 导出。设计文本切块滑动窗口、Prompt 模板约束机制和模块化 service 架构，具备 Agent 工具化扩展能力。

**技术亮点**: Python / FastAPI / Streamlit / PyMuPDF / sentence-transformers / Embedding / RAG / Prompt Engineering / 向量检索
