# Changelog

## Phase 5 — 多 Agent 协作与记忆管理 (2026-05-25)

- LangGraph Supervisor StateGraph：route → execute → synthesize 三节点流水线
- 4 个 Specialist Agent：Extractor / Summarizer / QA（含 Rerank）/ Comparator
- 三层记忆系统：ShortTerm（对话历史）/ LongTerm（偏好）/ Semantic（向量事实），SQLite 持久化
- AgentTracer 执行追踪 + DecisionLogger 路由决策日志
- `run_traced()` 将 routing_decision / delegation_result 写入 MemoryStore
- Streamlit Agent 助手支持 supervisor / react 模式切换
- `/api/traces` + `/api/traces/stats` 可观测性 API
- Streamlit Agent 监控页（执行时间线 / 路由决策 / 工具统计）
- 493 tests passing（含 44 个 multi-agent 集成测试）

## Phase 4 — 高级 RAG 与检索增强 (2026-05-22)

- Cross-encoder Rerank（bge-reranker-v2-m3）
- BM25 + 向量混合检索（HybridRetriever，alpha 可调）
- 查询改写（QueryRewriter）+ HyDE 假设文档嵌入
- 多知识库管理（KBManager：创建 / 切换 / 删除 / 列表）
- 168 样本真实评测替换全部模拟基线
- Rerank+Rewrite 组合基线：answer_pass_rate +43.5%
- Abstract section 切块修复 + 检索 A/B 重跑

## Phase 3 — 工程化与生产就绪 (2026-05-20)

- FastAPI BackgroundTasks + FileJobStore 异步任务系统
- 结构化 JSONL 日志（request_id 追踪）
- 统一错误响应中间件
- 任务 CRUD API（提交 / 查询 / 取消 / 重试）
- 健康检查 endpoint

## Phase 2 — 数据分析与效果评估 (2026-05-20)

- AnalyticsCollector 数据收集器
- 检索 / QA / 对比三维度分析脚本
- A/B 测试框架（ExperimentRunner + t 检验 + Markdown 报告）
- FailureAnalyzer 失败案例聚类与根因分析
- 4 个 Jupyter Notebook（检索分析 / QA 质量 / 实验对比 / 失败案例）
- LLM-as-Judge 评测（answer + citation 双维度）
- Seed dataset 扩展至 168 样本 / 9 篇论文

## Phase 1 — Agent 工作流基础 (2026-05-18)

- 工具封装层：6 个 BaseTool（Upload / Note / Index / QA / Compare / Export）
- ToolRegistry 工具注册中心
- LangChain 适配器：BaseTool → LangChain Tool 自动转换
- PaperResearchAgent：create_react_agent + 对话历史
- LangGraph 工作流：ResearchWorkflow / ComparisonWorkflow
- Streamlit Agent 助手 Tab
- `POST /agent/execute` API

## MVP — 基础功能 (2026-05-15)

- PDF 解析（PyMuPDF → title / abstract / sections / full_text）
- 13 段结构化中文 Markdown 笔记生成
- 文本切块（chunk_size=800, overlap=100）+ sentence-transformers 嵌入
- 向量检索 + RAG 问答（附来源引用）
- 多论文结构化对比（2-5 篇）
- Streamlit 5-Tab UI + FastAPI 13 endpoints
- Evaluation 骨架（seed dataset + baseline report）
