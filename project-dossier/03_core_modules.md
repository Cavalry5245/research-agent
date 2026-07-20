# 03 · 核心模块详解

> 本文档对每个核心模块使用统一模板：目标 / 输入输出 / 处理流程 / 关键实现 / 关键文件 / 第三方能力 / 设计选择 / 备选与权衡 / 测试 / 限制 / 个人贡献。
> 由于是个人独立项目，"个人贡献"一节主要区分**自研逻辑 vs 调用第三方框架**，而非区分人与人。

模块索引：
1. [PDF 解析](#61-pdf-解析-pdf_parser) · 2. [父子文档 RAG 与检索](#62-父子文档-rag-与检索) · 3. [RAG 问答与对话记忆](#63-rag-问答与对话记忆) · 4. [笔记生成](#64-笔记生成) · 5. [多论文对比](#65-多论文对比) · 6. [Agent 层](#66-agent-层) · 7. [Research Pipeline](#67-research-pipeline) · 8. [MCP 集成](#68-mcp-集成) · 9. [评测/分析/实验](#69-评测分析实验)

---

## 6.1 PDF 解析 (pdf_parser)

**6.1.1 目标**：从 PDF 提取结构化信息（标题、摘要、章节树、正文、页码），为笔记生成和 RAG 切块提供干净输入。

**6.1.2 输入/输出**：`(pdf_path, paper_id)` → `PaperParseResult`（title/abstract/sections/full_text/structured_elements/pdf_profile）+ 保存为 `metadata/{paper_id}_parsed.json`。

**6.1.3 核心处理流程**：
1. `fitz.open()` 逐页取文本块（含字体、坐标、页码）。
2. 布局检测：按块 x0 分布判断单栏/双栏，双栏按"先左后右"重排阅读顺序。
3. 标题检测：`_score_title_candidate` 综合字体大小、位置、元数据、聚类、文件名等打分，配合作者/元数据黑名单（正则+精确匹配）。
4. 块分类：`_classify_block_type` 用字体大小+关键词+数学符号+制表符启发式，分为 title/abstract/heading/paragraph/table/figure_caption/equation/reference。
5. 章节树：`build_section_tree` 用编号正则（`1.1.1`→L3）+ 关键词匹配构建 `section_path`（如 `Method/Loss`），标记 `in_references`。
6. 扫描件防护：`total_chars < page_count*100` 时判定为扫描件并报错。

**6.1.4 关键实现**：字体几何评分的标题检测、双栏阅读序重排、章节路径树——这些是 PyMuPDF 之上**自研的启发式逻辑**，超出 PDF 库本身能力。

**6.1.5 关键文件/函数**：
- `app/services/pdf_parser.py`：`parse_pdf`、`generate_paper_id`、`_detect_best_title`、`_score_title_candidate`、`_detect_layout_type`、`_classify_block_type`、`build_section_tree`、`save_parse_result`、`load_parsed_result`。

**6.1.6 第三方能力**：PyMuPDF (`fitz`) 提供文本/字体/坐标提取；**结构识别逻辑全部自研**。

**6.1.7 设计选择**：纯启发式规则解析，不用 GROBID/MinerU/Nougat 等重型工具。

**6.1.8 备选方案**：GROBID（出版级但需 Java 服务）、MinerU/Marker（重型、依赖多）、Nougat（多模态但慢）。

**6.1.9 权衡**：
| 维度 | 现方案（PyMuPDF+启发式）|
|---|---|
| 开发成本 | 低，纯 Python 无外部服务 |
| 精度 | 中，正文主干可用，复杂排版/公式/表格弱 |
| 部署 | 简单，无额外服务 |
| 扩展性 | 已预留 `pdf_parse_mode` 开关 |

**6.1.10 测试**：`tests/` 下有 PDF 解析测试（含 fixture PDF）。

**6.1.11 当前限制**：扫描件不支持；表格/公式/图像不做深度解析（属 MVP 文档 v0.5 计划范围）；部分源码中文注释存在 GBK 乱码。

**6.1.12 个人贡献**：标题评分、布局检测、章节树等全部自研启发式；PyMuPDF 仅提供底层文本抽取。

---

## 6.2 父子文档 RAG 与检索

**6.2.1 目标**：在"精准召回"与"完整上下文"之间取得平衡——子块用于检索，父文档用于回填。同时提供多种检索策略与重排的可插拔组合。

**6.2.2 输入/输出**：
- 索引侧：`PaperParseResult` → `ParentDocument[]`（不进索引）+ `Chunk[]`（进向量索引）。
- 检索侧：`query` → top-k 结果（含 score / parent_id / section_path / page_range）。

**6.2.3 核心处理流程**：
```
结构化元素 → build_parent_documents（按章节边界切父文档）
           → chunk_parent_documents（父内部滑窗切子块 500/100）
           → 子块加 context_header（title|section_path|页码）
           → API bge-m3 embedding → Chroma cosine collection
检索时: 命中子块 → 按 parent_id 分组 → 加载完整父文档 → 去重拼接上下文
```

**父文档边界规则**（`parent_chunker.py`）：Abstract 独立；每个 table 独立；L1 章节独立；L2 章节 >2000 字符才独立，否则并入父章节；L3+ 上并；references 跳过。

**6.2.4 关键算法/实现**：
- **Contextual Retrieval**：子块嵌入前拼上 `context_header`（标题|章节路径|页码范围），提升语义可辨识度。
- **向量库**：`vector_store.py` 按配置严格选择后端；默认 `ChromaVectorBackend` 使用 Chroma 1.5.9 `PersistentClient` 和 cosine collection `research_papers_bge_m3_v1`，不会静默回退。`JsonVectorBackend` 仅供显式诊断/回滚。
- **重建与校验**：`chroma_rebuild.py` + `scripts/rebuild_chroma_index.py` 先做 1 篇/129 chunks canary，再按论文断点续跑；原子 manifest 记录每篇源哈希与 ID，完成时校验 53 个源、8,182 个唯一 ID、总数和统一 1024 维。`--verify-only` 为只读路径。
- **生命周期/readiness**：collection 仅在全量验证完成后标记 `ready`；健康检查要求后端、schema、模型、build status 与正整数维度契约同时有效，否则报告未就绪。
- **BM25**：`bm25_retriever.py` 用 rank-bm25 `BM25Okapi` + jieba 中文分词。
- **Hybrid**：`hybrid_retriever.py` 对 dense/sparse 各自 min-max 归一化后 `alpha*dense + (1-alpha)*sparse` 线性融合。
- **重排**：`reranker.py` 含 `CrossEncoderReranker`（bge-reranker-v2-m3）、`HybridReranker`（token-overlap）、`IdentityReranker`。
- **查询优化**：`query_rewriter.py`（LLM 改写）、`hyde.py`（生成假设文档再嵌入检索）。
- **增量索引**：`incremental_indexer.py` 用 SHA1 内容哈希 diff，只嵌入变更块。

**6.2.5 关键文件**：`parent_chunker.py`、`parent_doc_store.py`、`vector_store.py`、`bm25_retriever.py`、`hybrid_retriever.py`、`reranker.py`、`query_rewriter.py`、`hyde.py`、`incremental_indexer.py`、`index_version.py`、`knowledge_base_manager.py`。

**6.2.6 第三方能力**：Chroma（持久化向量检索）、API `BAAI/bge-m3`（embedding）、sentence-transformers/torch（可选本地嵌入与 cross-encoder）、rank-bm25、jieba。后端契约、重建/续跑/验证、融合逻辑、父子架构与增量 diff 自研。

**6.2.7-6.2.9 设计/备选/权衡**：
- 父子文档 vs 朴素定长切块：父子解决"检索准但上下文碎"的矛盾，代价是存储和实现复杂度。
- Chroma vs JSON：Chroma 是默认可扩展检索路径；JSON 保留为显式、可检查的诊断/回滚路径，避免自动降级掩盖故障（见 [ADR-1](05_decisions_and_tradeoffs.md)）。
- hybrid alpha=0.5 默认，可调。

**6.2.10 测试**：检索、切块、混合检索、重排均有单测。

**6.2.11 当前限制**：当前是本地验证而非生产部署；历史 JSON store 仅 4 chunks/1 paper/统一维度 3，未迁移且与 1024 维 bge-m3 不兼容。检索评测的完美分仍是 stub（见 [C3](evidence_index.md)），真实检索质量需以 QA 端到端评测为准。

**6.2.12 个人贡献**：父子文档架构、上下文头、hybrid 融合、SHA1 增量索引、严格后端抽象、Chroma 生命周期与可恢复重建/验证流程均为项目实现；第三方提供 Chroma 引擎、嵌入模型、BM25 算法与分词。

---

## 6.3 RAG 问答与对话记忆

**6.3.1 目标**：基于检索到的论文片段生成防编造、带页码引用的回答，并支持多轮对话记忆。

**6.3.2 输入/输出**：`(question, paper_id?, top_k, conversation_id?)` → `{answer, sources[], rewritten_question?, conversation_id}`。

**6.3.3 核心流程**（`paper_qa.answer_question`）：
```
检索（自定义 retriever 或默认 vector）
  → 可选重排（校验重排后 chunk_id ⊆ 原始集）
  → 按 parent_id 分组
  → 加载完整父文档
  → 构建去重上下文 + 引用标签 [paper_id p.范围 section]
  → 上下文感知 or 普通 QA prompt（严格防编造/不足声明/列依据）
  → LLM → 答案 + sources（页码/章节/元素类型）+ 计时
```

**6.3.4 对话记忆**（`qa_memory.QAMemoryService`）：
- **上下文感知查询改写**：把会话摘要+近期轮次+上次改写喂给改写 prompt。
- **滚动摘要**：消息数≥阈值且新消息足够时触发会话摘要更新。
- 传改写后问题给检索，同时保留 `original_question`。

**6.3.5 关键文件**：`paper_qa.py`（`answer_question`、`_build_context`、`_apply_reranker`）、`qa_memory.py`、`memory_store.py`（SQLite 6 表）。

**6.3.6 第三方能力**：OpenAI SDK（LLM 调用，含指数退避重试）；prompt 工程、引用机制、记忆编排自研。

**6.3.10 测试**：QA 流程、记忆、改写有单测；端到端有 168 样本 LM-as-judge 评测。

**6.3.11 当前限制**：QA 真实评测 answer_pass≈39.3% / citation_pass≈44.6%（见 [04](04_data_and_evaluation.md)），仍有提升空间；空答案有时源于 LLM 客户端静默关闭（分析已发现）。

**6.3.12 个人贡献**：父文档回填、引用标签、上下文感知改写、滚动摘要全部自研。

---

## 6.4 笔记生成 (note_generator)

**6.4.1 目标**：把解析后的论文生成 13 段结构化中文精读笔记。

**6.4.3 流程**：`_build_paper_content` 截断到 8000 字符（超长时退化为摘要+章节）→ `build_note_prompt`（13 段模板 + 中文/学术/防编造约束）→ LLM → Markdown。

**6.4.5 关键文件**：`note_generator.py`、`prompts/paper_note_prompt.py`（及 compact 版）、`markdown_exporter.py`。

**6.4.11 限制**：超长论文用简单截断而非 MVP 文档设想的"分段摘要再汇总"（该策略文档有描述，代码未完整实现——见 [C6 相关](evidence_index.md)）。

**6.4.12 个人贡献**：prompt 模板设计、截断策略自研。

---

## 6.5 多论文对比 (paper_compare)

**6.5.1 目标**：对 2-5 篇论文生成结构化对比表（9 维度）。

**6.5.3 流程（两阶段 LLM）**：
1. `extract_paper_summaries`：每篇先抽结构化摘要（研究问题/方法/骨干/数据集/指标/优势/局限/场景 + 证据）。
2. `compare_papers_batch`：跨论文按固定维度顺序生成 Markdown 对比表，含证据摘录。

**6.5.5 关键文件**：`paper_compare.py`、`prompts/compare_prompt.py`。

**6.5.11 限制**：`comparison_eval_seed.jsonl` 只有 1 样本，对比质量评测样本极少（见 [C3](evidence_index.md)）。

**6.5.12 个人贡献**：两阶段抽取-对比 pipeline、证据回退逻辑自研。

---

## 6.6 Agent 层

**6.6.1 目标**：把论文工具封装为可被 LLM 编排的工具，并探索多 agent 协作。

**6.6.2 两条路径**：
- **单 ReAct Agent（主用，成熟）**：`paper_research_agent.py` 用 LangChain `create_agent` + 7 工具 + 对话记忆。
- **多 Agent Supervisor（探索性，较弱）**：`supervisor.py` 用 LangGraph StateGraph（route→execute→synthesize），**关键词计数路由**（非 LLM）。

**6.6.3 7 个工具**（`tools/paper_tools.py`，均调真实 service）：upload/list/note/index/qa/compare/export。QATool 最丰富（按 settings 组合重排+混合检索）。

**6.6.4 三层记忆**（`memory/`，SQLite 后端）：ShortTerm（对话窗口）/ LongTerm（偏好+阅读历史）/ Semantic（嵌入事实召回，暴力扫描）。

**6.6.5 可观测性**：`tracing.py`（AgentTracer，span 自动持久化）+ `decision_logger.py`（路由决策日志）+ `/api/traces` API。

**6.6.7 设计选择**：LangGraph 而非 AutoGen/CrewAI（与 LangChain 生态一致，无新依赖）；关键词路由而非 LLM 分类（零延迟/零成本/可解释）。

**6.6.11 当前限制**（诚实定位）：
- 多 agent supervisor 的 specialist 路径**较脆弱**：specialist 从 `context` 读 paper_id/paper_ids，但关键词路由传空 context，导致 comparator/summarizer 在纯自然语言输入下会报错（见 [C7](evidence_index.md)）。
- specialist 与 tool 的 service 调用签名存在不一致，说明 tool 路径是被测试/主用的，specialist 路径偏 demo。

**6.6.12 个人贡献**：工具封装层、LangChain 适配器（Pydantic 动态 args_schema）、三层记忆、可观测性自研；LangChain/LangGraph 提供 agent 引擎和图编排。

---

## 6.7 Research Pipeline（新主线）

**6.7.1 目标**：从研究问题端到端产出带引用校验的 Markdown 研究报告。

**6.7.3 五阶段**（`runner.py`，planner→retriever→planner→reader→synthesis→harness）：
1. **Planner**（`agents/planner.py`）：LLM 生成规范化问题/子问题/查询/相关性标准；再选候选论文。有确定性 fallback。
2. **Retriever**（`agents/retriever.py`）：按 source_mode（web_search/zotero_only/hybrid）路由，去重持久化，单源失败→degraded。
3. **Reader**（`agents/reader.py`）：abstract_only 或 pdf 模式抽 PaperCard，ThreadPool 并发+失败隔离，LLM 抽取有 fallback。
4. **Synthesis**（`agents/synthesis.py`）：LLM 生成固定 8 段报告（带 `[CITE:paper_id]`，强防编造），失败退化为确定性骨架（2 次重试）。
5. **Harness**（`agents/harness.py`）：**纯规则**校验，解析 CITE，打 supported/weak/unverified/numeric_trace_missing。

**6.7.5 关键文件**：`research_pipeline/runner.py`、`agents/*`、`sources/*`、`store.py`（SQLite 9 表）、`router.py`、`evaluation/run_mvp_gate.py`。

**6.7.11 限制**：
- Semantic Scholar 在 `create_default_agent` 中传 `client=None`（因限流临时禁用），实际主要靠 arXiv（见 [C8](evidence_index.md)）。
- MVP gate PASS 但依赖降级 fallback（见 [C9](evidence_index.md) 及 [04](04_data_and_evaluation.md)）。

**6.7.12 个人贡献**：五阶段编排、规则校验 Harness、降级 fallback 全部自研；LLM 提供 planner/reader/synthesis 生成能力。

---

## 6.8 MCP 集成

**6.8.1 目标**：以 MCP agent-client 模式接入外部学术工具（arXiv/Semantic Scholar/Zotero/paper-search），并把 ResearchAgent 自身也暴露为 MCP 服务器。

**6.8.2 关键事实**：MCP 客户端是**真实的官方 `mcp` Python SDK stdio 实现**——`stdio_session.py` 用 `mcp.ClientSession` + `stdio_client`，跑独立事件循环线程，做 `initialize/list_tools/call_tool`。⚠️ 见 [C2](evidence_index.md)：`docs/ARCHITECTURE.md` 说它"stub-quality"是**过时描述**。

**6.8.3 内置服务器**：`minimal_arxiv_server.py`（真实调 export.arxiv.org）、`minimal_semantic_scholar_server.py`（真实调 S2 API，客户端限流）、`paper_search_server.py`（包装第三方 paper-search-mcp）、`mock_server.py`（测试用）。

**6.8.5 关键文件**：`mcp/stdio_session.py`、`client_manager.py`、`tool_proxy.py`、`paper_normalizer.py`、`minimal_*_server.py`、`research_workflow/mcp_stdio_server.py`（暴露 7 个 ResearchAgent 工具）。

**6.8.11 限制**：`auto_restart`/health-check 字段标注"未来实现"，无实际自动重启；本地元数据 fallback adapter 是真 stub（仅在对应 MCP 关闭时激活）。

**6.8.12 个人贡献**：客户端生命周期管理、工具代理、论文归一化去重、内置服务器全部自研；mcp SDK 提供协议层。

---

## 6.9 评测/分析/实验

详见 [04_data_and_evaluation.md](04_data_and_evaluation.md)。此处仅列模块职责：
- **evaluation/**：`metrics.py`（Hit@k/Recall@k/MRR）、`judges.py`（answer+citation 双维度，rule/LLM 两模式）、seed 数据集（168 QA 样本/9 篇）。
- **analytics/**：埋点收集（JSONL）、失败检测/聚类、日志 p50/p95 分析、可视化。
- **experiments/**：A/B 框架（Welch t 检验），⚠️ 默认模拟执行器，真实需 `--executor real`（见 [C4](evidence_index.md)）。

---

## 交叉引用
- 评测数据与真实/模拟指标 → [04_data_and_evaluation.md](04_data_and_evaluation.md)
- 技术决策 ADR → [05_decisions_and_tradeoffs.md](05_decisions_and_tradeoffs.md)
- 所有矛盾标记 → [evidence_index.md](evidence_index.md)
