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

**总计: 48 项，其中 46 passed、2 skipped。**

## 已知问题

1. **`conda run` 退出的 pyarrow DLL 冲突**: 测试全部通过后 conda 进程退出时 crash，不影响结果
2. **Embedding 模型首次下载**: `bge-small-zh-v1.5` 首次使用需联网下载（约 130MB）
3. **笔记生成 Prompt 消耗**: 13 段模板 + 论文全文，需模型 context ≥ 8k tokens
4. **VectorStore 为轻量本地实现**: 当前为纯 Python 检索 + JSON 持久化，后续如需更强过滤/并发能力可替换为 ChromaDB 后端

## 下一步计划

- [ ] ChromaDB 持久化后端替换（解决 conda 环境兼容性后）
- [ ] v0.2: SQLite 论文管理 + 标签分类
- [ ] v0.3: 实验日志分析模块
- [ ] v0.4: Agent 工具调用系统
- [ ] v0.5: 多模态论文理解（图表/公式）
