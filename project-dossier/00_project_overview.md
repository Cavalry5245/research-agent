# 00 · 项目概览

> 标记规则见 `README.md`。本章所有结论可追溯至 `evidence_index.md`。

---

## 1.1 项目基本信息

| 项 | 内容 | 来源/备注 |
|---|---|---|
| 项目名称 | ResearchAgent（面向研究生的论文阅读与实验分析助手） | `docs/MVP_REQUIREMENTS.md` |
| 项目类型 | AI 应用 / 后端 / 全栈综合项目（LLM + RAG + Agent + 工程化） | 代码结构判断 |
| 开发时间 | 2026-05-11 ~ 2026-07-14（约 2 个月，以 git 为准） | `git log`；本地可能有更早工作【待确认】 |
| 项目状态 | 活跃开发中；Research Pipeline MVP 六个 slice 已完成 | `README.md` |
| 项目角色 | **个人独立开发者**（设计 + 实现 + 测试 + 文档全栈） | 作者确认 + `git shortlog`(E16) |
| 团队规模 | 1 人 | 作者确认 |
| 使用场景 | 论文精读、RAG 问答、多论文对比、研究选题调研、related work 写作准备 | `docs/MVP_REQUIREMENTS.md` |
| 目标用户 | 研究生 / 博士生 / 算法工程师 / AI 从业者 | `docs/MVP_REQUIREMENTS.md` |
| 部署状态 | **仅本地 / Demo 运行**，无真实上线、无真实用户 | 作者确认 |
| 代码仓库 | 本地 git 仓库（`E:\projects\ResearchAgent`） | — |
| 数据规模 | 已解析 53 篇论文、28 篇笔记；Chroma 8,182 个唯一验证 chunks；QA 评测 168 样本 / 9 篇 | E9, E26, E30 |
| 当前完成度 | 见 1.4 | — |

## 技术栈速览

- **后端**：Python 3.11, FastAPI, Pydantic, Uvicorn
- **前端**：React + Vite + TypeScript + TailwindCSS + React Query（主）；Streamlit（legacy）
- **LLM**：OpenAI 兼容 API（默认 deepseek-chat），支持 BYOK
- **RAG**：Chroma 1.5.9（默认、cosine、版本化 collection）+ 显式 JSON 诊断/回滚后端、BM25(jieba)、混合检索、cross-encoder 重排(bge-reranker-v2-m3)、HyDE、查询改写、父子文档架构
- **Embedding**：OpenAI 兼容 API `bge-m3`（provider wire ID `BAAI/bge-m3`），当前索引统一 1024 维
- **Agent**：LangChain + LangGraph（单 ReAct agent + 多 agent supervisor）
- **外部工具**：MCP（官方 SDK，stdio）接入 arXiv / Semantic Scholar / Zotero / paper-search-mcp
- **持久化**：SQLite（WAL）+ Chroma PersistentClient + JSON 文件
- **部署**：Docker + docker-compose（api + nginx 前端）
- **CI**：GitHub Actions

> 技术栈边界：可表述“本地完成 Chroma + API bge-m3 的 53 篇/8,182 chunks 重建与校验”；不得声称生产部署。历史 JSON 仅 4 chunks/1 paper/统一维度 3，未迁移且不能承接 1024 维 bge-m3 查询。

---

## 1.2 项目介绍（多版本）

### 一句话版
一个本地优先的 AI 科研助手：上传论文 PDF 即可生成中文精读笔记、做全文 RAG 问答与多论文对比，也支持输入研究问题自动检索文献并产出带引用校验的调研报告。

### 50 字版
ResearchAgent 是本地优先的 AI 科研阅读与调研助手。基于 FastAPI + React 构建，集成 PDF 解析、父子文档 RAG 问答、多论文对比，以及从研究问题到带引用校验报告的自动调研流水线。

### 100 字版
ResearchAgent 是一个面向研究生和算法工程师的本地优先 AI 科研助手，包含两条主线：一是论文精读工具链（PDF 解析 → 13 段中文笔记 → 父子文档 RAG 问答 → 多论文对比 → Markdown 导出）；二是研究调研流水线（研究问题 → Planner/Retriever/Reader/Synthesis/Harness 五阶段 → 带引用校验状态的 Markdown 报告）。技术上覆盖混合检索、cross-encoder 重排、LangGraph 多 agent、MCP 外部工具接入，并配有 LLM-as-judge 评测与分析体系。后端约 2.8 万行 Python，含约 1,100 个测试。

### 200 字版
ResearchAgent 是一个个人独立开发的、本地优先的 AI 科研阅读与调研助手，定位为"面向科研工作流的轻量 Agent 系统"而非简单 ChatPDF。它有两条并重的主线：

**论文精读线**（较成熟）：PDF 上传后经 PyMuPDF 结构化解析（字体评分标题检测、布局检测、章节树），生成 13 段结构化中文笔记；采用父子文档 RAG 架构（子块检索、父文档回填、页码级引用），检索层支持向量/BM25/混合三模式并可叠加 cross-encoder 重排、查询改写与 HyDE；支持 2-5 篇论文的两阶段结构化对比。

**研究调研线**（当前主线）：输入研究问题后，Planner → Retriever（arXiv/Semantic Scholar/Zotero）→ Reader → Synthesis → Harness 五阶段流水线自动产出 8 段研究报告，并用规则式 Harness 对每条 claim 标注 supported/weak/unverified 等校验状态。

工程侧具备异步任务、结构化日志、错误中间件、Docker 部署、BYOK、SQLite 记忆、MCP 工具接入，以及基于 168 样本的 LLM-as-judge 评测体系。后端约 2.8 万行 Python、约 1,100 个测试，前端为完整 React 应用。

### 非技术人员版
这是一个"论文阅读助理"软件。研究生读论文很费时间，这个工具能自动把一篇英文论文读成一份结构清晰的中文笔记，还能像和人聊天一样就论文内容提问、让多篇论文并排对比。更进一步，你只要提一个研究问题，它就能自己去网上文献库找相关论文、读完、写一份带出处标注的调研小报告，并标明哪些结论证据充分、哪些还需存疑。全部可以在自己电脑上运行，不依赖任何外部服务器。

### 技术面试版
ResearchAgent 是我个人开发的一个 LLM 应用项目，核心是把"科研阅读工作流"拆成可组合的服务和 agent。技术亮点集中在三块：(1) **RAG 工程**——我实现了父子文档检索架构（子块负责精准召回、父文档负责完整上下文回填、页码级引用），并把向量/BM25/混合检索、cross-encoder 重排、HyDE、查询改写都做成 config 可切换的插拔式组件；(2) **Agent 编排**——用 LangGraph 做了确定性工作流和一个五阶段研究流水线（含规则式 claim 校验的 Harness），并通过官方 MCP SDK 接入 arXiv/Zotero 等外部工具；(3) **可观测与评测**——搭了 168 样本的 LLM-as-judge 评测、埋点分析和失败聚类。全栈上后端 FastAPI + 前端 React，配 Docker 部署和 BYOK。我也很清楚项目里哪些是真实验证过的、哪些还是 stub 或需要坐实的地方。

### 项目答辩版
（背景）研究生读论文、做选题调研的资料整理成本很高，普通 ChatPDF 只能一问一答、无法沉淀结构化科研材料。（目标）我想做一个面向科研工作流的本地 AI 助手，覆盖"读论文—问论文—比论文—做调研"。（方案）系统分两条主线：论文精读线用父子文档 RAG 保证答案有出处、可溯源到页码；研究调研线用五阶段 agent 流水线把"研究问题"变成"带引用校验的报告"，其中 Harness 阶段会逐条校验报告里的论断是否有文献支撑。（工程）后端 FastAPI、前端 React、SQLite/JSON 持久化、Docker 部署，并且我为它建了评测体系来量化效果、暴露问题。（诚实边界）目前是本地 Demo，检索评测有一部分是占位实现、A/B 实验默认是模拟执行器，这些我在文档里都明确标注了，正在逐步用真实 pipeline 替换。

---

## 1.3 项目价值

| 维度 | 说明 | 是否被数据验证 |
|---|---|---|
| 解决什么问题 | 科研文献阅读/调研的信息整理成本高；ChatPDF 无法沉淀结构化材料、答案难溯源 | 问题定义来自需求文档，非用户调研【合理推断】 |
| 为什么需要 | 把"读论文—问论文—比论文—做调研"整合进一个可溯源、可导出的本地工作流 | — |
| 相比原有方式的改进 | (1) 答案带页码级引用可溯源；(2) 笔记结构化可直接进 Obsidian；(3) 调研报告带逐条 claim 校验，区分"证据充分/存疑/未验证" | 引用与校验能力有代码支撑(E2,E20)；"效率提升"未做用户实验【缺少证据】 |
| 工程价值 | 完整覆盖 LLM 应用工程化：插拔式 RAG、异步任务、可观测、评测、Docker、BYOK | 代码支撑充分 |
| 用户/业务价值 | **仅本地 Demo，无真实用户，不可量化用户价值** | 作者确认 |

> **价值表述红线**：不得声称任何用户量、效率提升百分比、上线成果。可量化的只有系统内部评测指标（见 `04_data_and_evaluation.md`）。

---

## 1.4 当前完成度

| 子系统 | 完成度 | 依据 |
|---|---|---|
| PDF 解析 | ✅ 完成且真实使用（53 篇已解析） | E1, E26 |
| 13 段笔记生成 | ✅ 完成（28 篇已生成） | E26 |
| 父子文档 RAG 问答 | ✅ 完成，有真实评测 | E2, E9 |
| 多论文对比 | ✅ 完成（两阶段结构化） | E22 |
| 混合检索/重排/HyDE/改写 | ✅ 代码完成，config 可切换 | E3 |
| 异步任务/日志/错误处理 | ✅ 完成 | E23, E24 |
| 单 ReAct Agent + 7 工具 | ✅ 完成（主用路径） | E6 |
| 多 Agent Supervisor | ⚠️ 可演示但脆弱（关键词路由、签名不一致） | E7, C7 |
| MCP 工具接入 | ✅ 客户端真实实现；部分源默认关闭 | E8, C8 |
| Research Pipeline（问题→报告） | ✅ 六 slice 完成，MVP gate PASS（依赖 fallback） | E12, E20, E21 |
| Research Workflow（Zotero→KnowledgePack） | ✅ 完成，但合成为模板无 LLM | E14 |
| React 前端 | ✅ 完整多页面应用 | E17 |
| 检索评测 | ⚠️ 部分为注入 gold 的 stub | C3 |
| A/B 实验 | ⚠️ 默认模拟执行器 | C4 |
| 真实部署上线 | ❌ 仅本地/Demo | 作者确认 |

图例：✅ 已完成且验证 · ⚠️ 完成但有重要限制 · ❌ 未做
