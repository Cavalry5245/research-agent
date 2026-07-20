# 05 · 技术选型与设计决策

> 记录项目中重要的技术决策、备选方案和权衡。区分"主动设计"与"受约束/临时妥协"。重要决策用 ADR（Architecture Decision Record）格式。

---

## 技术决策总表

| 决策点 | 选择 | 备选 | 主要理由 | 类型 |
|---|---|---|---|---|
| 后端框架 | FastAPI | Flask/Django | 异步、自动 OpenAPI 文档、Pydantic 集成 | 主动 |
| 前端（主）| React+Vite+TS | 继续用 Streamlit | 生产级 UI、可控交互、可部署 | 主动（后期迁移）|
| 前端（legacy）| Streamlit 保留 | 删除 | 快速调试入口，不删 | 主动 |
| PDF 解析 | PyMuPDF | GROBID/MinerU/Nougat | 轻量、纯 Python、无需额外服务 | 主动（MVP 约束）|
| 向量库 | **Chroma（默认）+ JSON（显式诊断/回滚）** | FAISS/仅 JSON | cosine、持久化、严格 readiness、无静默降级 | 主动（ADR-001 已决） |
| Embedding | API `bge-m3`（wire ID `BAAI/bge-m3`） | 本地 sentence-transformers | 统一 1024 维、真实 API 重建已验证 | 主动 |
| LLM 接入 | OpenAI 兼容 API | 绑定单一厂商 | 可切 DeepSeek/Qwen/Ollama | 主动 |
| RAG 切块 | 父子文档 | 固定切块 | 高精度检索 + 完整上下文回填 | 主动 |
| 检索 | vector/bm25/hybrid 可切 | 仅向量 | 中文场景 BM25 补充语义检索 | 主动 |
| 重排 | cross-encoder（可选）| 无 | 精排提升相关性；默认关（成本）| 主动 |
| Agent 框架 | LangChain+LangGraph | AutoGen/CrewAI/手写 | 生态一致、StateGraph 表达工作流 | 主动 |
| 多 agent 路由 | 关键词计数 | LLM 分类 | 零延迟、零成本、可解释 | 主动（也是局限）|
| 记忆/pipeline 存储 | SQLite（WAL）| Redis/Postgres | 单用户本地足够、WAL 支持并发读 | 主动 |
| 异步任务 | FastAPI BackgroundTasks | Celery/Redis | 单用户 MVP 够用 | 主动（约束）|
| 外部工具 | MCP（官方 SDK）| 自定义 HTTP 封装 | 标准协议、可复用生态服务器 | 主动 |
| 部署 | Docker Compose | k8s/单机脚本 | 一行启动、api+前端两容器 | 主动 |
| BYOK | X-LLM-* 头 + ContextVar | 服务端存 key | key 不落盘、多用户安全 | 主动 |

---

## ADR-001：默认 Chroma + API bge-m3，JSON 仅作显式回滚（已决）

**背景**：旧实现只有 JSON 线性扫描，但配置和架构文档指向 Chroma，形成事实与表述不一致。

**问题**：需要在不破坏可回滚性的前提下接入真实 Chroma，用一个统一 embedding 契约重建全部解析论文，并防止部分构建被应用误判为可用。

**候选方案**：A. 保持仅 JSON；B. Chroma 默认且保留显式 JSON 后端；C. Chroma 失败时自动降级 JSON。

**决定（2026-07-21）**：选择 B。锁定 `chromadb==1.5.9`，默认 cosine collection `research_papers_bge_m3_v1`；API 逻辑模型 `bge-m3` 确定性映射到 provider wire ID `BAAI/bge-m3`。JSON 只能显式选择，禁止静默降级。

**实施与证据**：
- 使用本地 `.env` 的实际 key（值从未输出/提交）先跑 canary，再断点续跑全量；最终 53 篇、8,182 唯一 chunks、统一维度 1024，manifest/collection 均为 `ready`。
- 首次使用裸 wire ID `bge-m3` 的 canary 被 provider 拒绝，流程安全停在 0 chunks 并保留忽略的失败 manifest；模型目录确认 `BAAI/bge-m3` 后修正映射（`04494051`）并复核，再成功重试（记录 `503837eb`）。
- `--verify-only` 只读检查源数量、每篇 hash/ID、全局 ID 唯一性、维度、总数和状态；应用 health/readiness 不接受 `building`/`failed` collection（激活 smoke 记录 `80db7d39`）。

**权衡/限制**：新增 Chroma 运行时依赖和重建运维复杂度，API embedding 有成本与限流风险，因此采用 canary、有限重试、逐篇原子 checkpoint 和蓝绿 collection。历史 JSON 未迁移；实测为 4 chunks/1 paper/统一维度 3，仅保留取证/显式回滚，不能用于 1024 维 bge-m3 查询。运行时数据库和 manifests 均忽略且未跟踪，本决策不等于已生产部署或已合并主分支。

---

## ADR-002：多 agent 路由用关键词而非 LLM

**背景**：Phase 5 引入 Supervisor 多 agent，需把用户请求路由到 4 个 specialist。

**问题**：路由用什么策略？

**决定**：`classify_intent` 用**关键词计数打分**，取最高分，默认 qa。

**理由**：零延迟、零 token 成本、决策可解释（rationale 记为 `keyword match → {type} (score N)`）。

**负面影响**（面试须诚实）：
- qa 关键词表含 `?`/`？`/`what`/`how` 等宽泛 token，模糊输入普遍偏向 QA。
- 关键词路由传空 context，导致 comparator/summarizer specialist 因缺 `paper_ids`/`paper_id` 报错。
- specialist 与 tool 的 service 调用签名不一致（见 [evidence_index.md](evidence_index.md) C7），说明 **tool 路径是主用/测试路径，specialist 路径偏探索性**。

**定位**：多 agent 是"可演示但脆弱"的探索实现，不应作为项目稳定能力主打。

---

## ADR-003：两套 research 子系统并存

**背景**：项目里有两个都叫 "research run" 的系统。

**决定**：保留两套：
- `research_workflow/`（旧）：Zotero collection → Knowledge Pack，JSON 存储，合成用**模板无 LLM**。
- `research_pipeline/`（新主线）：研究问题 → 校验报告，SQLite 存储，合成用 **LLM + 骨架回退**，含规则化 claim 校验。

**理由**：新 pipeline 设计更完善（问题驱动、引用校验），旧 workflow 不删作为 legacy。

**负面**：命名冲突，介绍时必须显式区分，否则自相矛盾（见 C10）。

---

## ADR-004：不引入 Celery/Redis，用 BackgroundTasks

**背景**：笔记生成、对比、索引是耗时操作（LLM 13.6s+）。

**决定**：Phase 3 用 FastAPI BackgroundTasks + FileJobStore（JSON 持久化），不引入 Celery/Redis。

**理由**：单用户本地 MVP，BackgroundTasks 足够；保留文件产物可读性。

**负面**：无分布式、无任务队列持久化保证、进程重启丢失内存任务（除非用 FileJobStore）。

**后续**：多用户需求明确后再评估 Celery。

---

## ADR-005：BYOK（Bring Your Own Key）

**背景**：Demo 若用固定 key 有成本和安全问题。

**决定**：前端 Settings 存 key 到浏览器 localStorage，按请求以 `X-LLM-*` 头发送；后端 `ByokMiddleware` 注入 `LLMClient`（ContextVar），**绝不落盘**。留空回退默认 LLM。

**理由**：多用户各用各的 key，服务端零密钥存储风险。

**正面**：安全叙事强（面试加分）；provider 无关。

**负面**：key 在浏览器 localStorage 有 XSS 暴露面（可作为面试深挖点讨论）。

---

## 交叉引用
- 决策对应的实现 → [03_core_modules.md](03_core_modules.md)
- 矛盾清单 → [evidence_index.md](evidence_index.md)
- 待补/待决 → [11_missing_information.md](11_missing_information.md)
