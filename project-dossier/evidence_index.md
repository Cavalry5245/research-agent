# 证据索引 (Evidence Index)

> 本文件为档案所有关键结论建立可追溯的证据链。标记规则见 `README.md` 0.7。
> **可信度**：高=代码/实验/日志直接证明；中=文档描述但代码未完全验证；低=命名/结构推断；待确认=材料不足。

---

## A. 核心事实证据表

| # | 结论 | 证据来源 | 可信度 |
|---|---|---|---|
| E1 | PDF 解析用 PyMuPDF，含字体大小评分标题检测、单/双栏布局检测、章节树构建 | `app/services/pdf_parser.py`（`_score_title_candidate` / `_detect_layout_type` / `build_section_tree`） | 高 |
| E2 | RAG 采用父子文档架构：子块 500 字符/100 重叠，父文档按章节边界切分，页码级引用 | `app/services/parent_chunker.py`、`paper_qa.py`、`config.py:78-85` | 高 |
| E3 | 检索支持 vector / bm25 / hybrid 三模式 + cross-encoder 重排 + 查询改写 + HyDE，全部经 `config.py` 切换 | `config.py:63-76`、`app/main.py::_get_retriever/_get_reranker` | 高 |
| E4 | **默认向量后端为 Chroma；JSON 是必须显式选择的诊断/回滚后端，不会静默降级** | `app/config.py`、`app/services/vector_store.py`、`app/services/vector_backends/{chroma_backend,json_backend}.py` | 高 |
| E5 | 多轮对话有滚动摘要 + 上下文感知查询改写 | `app/services/qa_memory.py` | 高 |
| E6 | 单 ReAct agent（LangChain `create_agent`）+ 7 个工具是主用/被测路径 | `app/agents/paper_research_agent.py`、`tools/paper_tools.py` | 高 |
| E7 | 多 agent supervisor 用**关键词计数**路由（非 LLM）；specialist 路径较弱且与 tool 路径存在 service 调用签名分歧 | `supervisor.py::classify_intent`；specialist vs tool 调用签名对比 | 中 |
| E8 | MCP 客户端是**真实**官方 `mcp` SDK stdio 实现；内置 arXiv / Semantic Scholar 服务器真实调用外部 API | `app/mcp/stdio_session.py`、`minimal_arxiv_server.py`、`minimal_semantic_scholar_server.py` | 高 |
| E9 | QA LM-as-judge 为真实运行：168 样本 / 9 篇论文，answer_pass 39.3%，citation_pass 44.6% | `app/evaluation/reports/qa_eval_seed_combined_report.json` | 高 |
| E10 | 检索评测的 1.000 分是注水：评估器把 gold section 注入 rank 1（确定性 stub） | `app/evaluation/reports/baseline_report.md`（报告自述）、`retrieval_eval_seed_report.json` | 高 |
| E11 | A/B 实验默认用模拟执行器，t 检验跑在合成样本上；真实结果需 `--executor real` | `app/experiments/runner.py::default_simulated_executor` / `_synthesize_samples` | 高 |
| E12 | Research Pipeline MVP gate = PASS（3/3 完成，中位 296.5s，claim 覆盖 61%），但依赖降级 fallback（S2 与 LLM 限流） | `app/storage/mvp_gate_20260714.json/md`（含 Issues 段） | 中 |
| E13 | "+43.5% answer_pass" 为相对提升；终点值 0.3929 真实，基线值 ≈0.2738 未在磁盘找到对应 JSON | `CHANGELOG.md:22` + `qa_eval_seed_combined_report.json` 反推 | 中 |
| E14 | Research Workflow 的 Knowledge Pack 合成为字符串模板、无 LLM（含硬编码目标检测风格 bullet） | `app/research_workflow/synthesis.py` | 高 |
| E15 | BYOK：用户 LLM key 经 `X-LLM-*` 头注入 ContextVar，绝不落盘 | `app/middleware/byok.py`、`llm_client.py`（ContextVar override） | 高 |
| E16 | 单人项目：一名作者、两个 git 身份 | `git shortlog -sne`（Chase Huang 209 + Chase 42） | 高 |
| E17 | 前端为完整 React + Vite + TS + Tailwind + React Query 应用（72 源文件 / 19 测试文件），另有 legacy Streamlit | `frontend/src/`、`frontend/package.json`、`ui/streamlit_app.py` | 高 |
| E18 | 增量索引用 SHA1 内容哈希差分，只嵌入变更的 chunk | `app/services/incremental_indexer.py` | 高 |
| E19 | 三层 Agent 记忆（短期/长期/语义）持久化于 SQLite（WAL 模式，6 表） | `app/services/memory_store.py`、`app/agents/memory/*` | 高 |
| E20 | Research Pipeline 的 Harness 是规则式（非 LLM）claim 校验：supported/weak/unverified/numeric_trace_missing | `app/research_pipeline/agents/harness.py` | 高 |
| E21 | Research Pipeline 状态持久化于 SQLite（`research_pipeline.db`，9 表），后台线程执行（非 Celery） | `app/research_pipeline/store.py`、`router.py::schedule_pipeline_run` | 高 |
| E22 | 两阶段结构化对比：先逐篇 LLM 抽取结构化摘要，再跨篇对比生成 Markdown 表格 + 证据 | `app/services/paper_compare.py` | 高 |
| E23 | 异步任务系统用 FastAPI BackgroundTasks + FileJobStore/InMemoryJobStore（非 Celery/Redis） | `app/main.py`、`app/services/job_store.py` | 高 |
| E24 | 结构化 JSONL 日志 + RequestID 中间件 + 日志分析（p50/p95 延迟、错误率） | `app/logging_config.py`、`middleware/tracing.py`、`analytics/log_analyzer.py` | 高 |
| E25 | 代码规模：后端 ~27,878 行 Python，136 测试文件 / ~1,144 测试函数 | `wc -l`、`grep def test_` | 高 |
| E26 | 已解析论文 53 篇、已生成笔记 28 篇（storage 实际产物） | `app/storage/metadata/*_parsed.json`、`notes/*_note.md` 计数 | 高 |
| E27 | Semantic Scholar 在 research_pipeline 中被 `client=None` 临时禁用（限流原因） | `app/research_pipeline/agents/*::create_default_agent` 注释 | 中 |
| E28 | Docker 部署：api（:8000）+ frontend/nginx（:80）双容器 | `docker-compose.yml`、`Dockerfile`、`frontend/Dockerfile` | 高 |
| E29 | Chroma 依赖锁定 1.5.9；版本化 cosine collection 为 `research_papers_bge_m3_v1`，逻辑模型 API `bge-m3` 映射到 provider wire ID `BAAI/bge-m3` | `requirements.txt`、`app/config.py`、`app/services/embedding_client.py`；实现提交 `04494051` | 高 |
| E30 | 真实 `.env` key（值未输出）完成 53 份顶层 parsed JSON 的重建：8,182 个唯一 chunk、统一维度 1024，manifest 与 collection 均为 `ready` | 忽略的 `app/storage/vector_db/` 运行时库与 `rebuild_research_papers_bge_m3_v1_manifest.json`；`python scripts/rebuild_chroma_index.py --verify-only --expected-source-count 53`；记录提交 `503837eb` | 高 |
| E31 | canary 为 1 篇/129 chunks；首个裸 wire ID `bge-m3` 请求失败时安全停在 0 chunks，并保留忽略的失败 manifest；修正映射并复核后重试成功 | 重建 manifest/失败备份、`scripts/rebuild_chroma_index.py --canary-only --expected-source-count 53`；提交 `04494051`、`503837eb` | 高 |
| E32 | 重建具备原子、可恢复 manifest，每篇记录源哈希与 ID；完成校验覆盖源数量、ID 集/唯一性、维度和总数，`--verify-only` 只读 | `app/services/chroma_rebuild.py`、`scripts/rebuild_chroma_index.py`、`tests/test_chroma_rebuild.py` | 高 |
| E33 | 激活后 readiness 要求 Chroma collection 状态为 `ready` 且维度/契约有效；真实 query smoke 返回 3 条结果，endpoint smoke 80 passed | `app/main.py::_vector_store_status_payload`、`tests/test_health_endpoints.py`；记录提交 `80db7d39` | 高 |
| E34 | 保留的历史 JSON 没有迁移：实测仅 4 chunks/1 paper/统一维度 3，与 1024 维 bge-m3 不兼容 | process-only `VECTOR_STORE=json` 打开与 metadata smoke；记录提交 `80db7d39` | 高 |

---

## B. 矛盾清单 (Inconsistencies)

> ⚠️ 这些是文档/配置与代码实现的不一致点。**写简历/面试前必须核对本表**，避免出现无法自圆其说的表述。

| # | 矛盾 | 声称（文档/配置） | 实际（代码） | 对求职的影响 | 处置 |
|---|---|---|---|---|---|
| C1 | **向量库（已解决）** | 旧档案称配置指向 Chroma、实现仅 JSON | 已实现并激活 Chroma 1.5.9；JSON 保留为显式诊断/回滚后端 | 可准确表述 Chroma，但不得声称生产部署 | 以 E29-E34 的真实重建与只读验证为准 |
| C2 | **MCP 成熟度** | `ARCHITECTURE.md` 称 "stub-quality for demo"、"protocol communication (stub)" | 实际是完整官方 mcp SDK stdio 实现 | 中（文档**低估**了能力，利好） | 以代码为准，可写"基于官方 MCP SDK 的 stdio 客户端" |
| C3 | **检索评测指标** | `retrieval_upgrade_report.md` 显示 Hit@3/MRR=1.000 | 评估器注入 gold 到 rank1，是确定性 stub | **高**：绝不能写 1.000 检索分 | 简历只用真实 QA LM-judge 数字（E9） |
| C4 | **A/B 实验显著性** | Phase 2 声称 A/B + t 检验 | 默认执行器返回硬编码 delta，t 检验跑合成样本 | **高**：只能说"搭建 A/B 框架"，不能说"实验证明提升 Y" | 见 `04_data_and_evaluation.md` |
| C5 | **MVP 需求 vs 实际** | `MVP_REQUIREMENTS.md` 描述单篇论文阅读 MVP | 实际已到多 agent + MCP + 双 pipeline + React | 中 | MVP 文档已滞后，不作为"当前状态"依据 |
| C6 | **Chunk size** | MVP 文档写 800/100 | 父子文档默认 500/100，传统 chunker 才是 800/100 | 低 | 说明父子架构为当前默认 |
| C7 | **supervisor specialist 路径** | ARCHITECTURE 画完整多 agent 协作图 | specialist 与 tool 的 service 调用签名不一致；关键词路由传空 context 会致 comparator/summarizer 报错 | 中：深挖会露馅 | 诚实定位为"探索性实现"，主打单 ReAct agent |
| C8 | **Semantic Scholar in pipeline** | README 说支持 S2 检索 | pipeline 中 S2 adapter 传 `client=None`（限流禁用） | 中：hybrid 实际主要靠 arXiv | 面试如实说明限流权衡 |
| C9 | **MVP gate 报告状态** | README 说 `research_pipeline_mvp_gate.md` 是 PENDING | `app/storage/mvp_gate_20260714.json/md` 显示 PASS | 低 | 以 storage 下实际 run 产物为准 |
| C10 | **两个 "research run" 概念** | 名字都叫 research run | `research_workflow`(Zotero→KnowledgePack,JSON) 与 `research_pipeline`(问题→报告,SQLite) 是两套独立系统 | 中：介绍需区分 | 全档案严格区分命名 |

---

## C. 可直接用于简历的"安全"量化事实

> 以下数字有磁盘证据支撑，可放心使用（注意标注口径）。

| 指标 | 值 | 口径 |
|---|---|---|
| QA 评测规模 | 168 样本 / 9 篇论文 | 真实 LM-as-judge 运行 |
| QA answer_pass_rate | 39.3% | live+rerank+rewrite 全量 168 样本 |
| QA citation_pass_rate | 44.6% | 同上 |
| rerank+rewrite 相对提升 | answer_pass +43.5%（相对） | 终点真实，基线为反推 |
| QA 延迟 | LLM ~13.6s / 总 ~15.1s（p95 22.3s）每次 | live 计时 |
| Research Pipeline MVP gate | PASS，3/3 完成，中位 296.5s，claim 覆盖 61% | 依赖降级 fallback |
| 代码规模 | 后端 ~27.8k 行，~1,144 测试函数 | 静态计量 |
| 已处理论文 | 53 篇解析 / 28 篇笔记 | storage 实际产物 |
| Chroma 索引 | 53 篇 / 8,182 唯一 chunks / 1024 维 | 真实 API 重建后只读验证，状态 `ready` |
| Chroma canary | 1 篇 / 129 chunks | 全量重建前真实 API canary |

> **禁止使用**：1.000 检索分（C3）、A/B 实验"证明"的提升（C4）、任何用户量/生产上线表述。可以陈述 Chroma 已在本地真实重建并验证，但不得将分支实现写成已部署或已合并。
