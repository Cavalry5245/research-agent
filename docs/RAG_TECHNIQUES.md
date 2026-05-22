# RAG 技术（Phase 4）

本项目在 Phase 4 引入了若干高级 RAG 技术，覆盖：检索（vector / BM25 / hybrid）、精排（cross-encoder rerank）、查询优化（LLM rewrite / HyDE）、多 embedding 模型切换、增量索引与知识库管理。

## 调用链总览

```
query
  ├─ (可选) QueryRewriter.rewrite() 或 HyDE.generate_hypothetical_doc()
  │
  ▼
retriever
  ├─ vector            → VectorStore.query(top_k=recall_top_k)
  ├─ bm25              → BM25Retriever.search(top_k=recall_top_k)
  └─ hybrid (默认 α=0.5)
        ├─ VectorStore.query(top_k=recall_top_k)
        ├─ BM25Retriever.search(top_k=recall_top_k)
        └─ min-max 归一化 → α·dense + (1-α)·sparse
  │
  ▼
(可选) CrossEncoderReranker.rerank(top_k=rerank_top_k=5)
  │
  ▼
build_qa_prompt → LLM → answer + sources
```

所有阶段都通过 `.env` 配置切换（详见 `app/config.py`）。

## Cross-encoder Rerank

- 默认模型：`BAAI/bge-reranker-v2-m3`（多语种，约 568MB）
- 实现：`app/services/reranker.py::CrossEncoderReranker`
  - 懒加载，注入式 model 便于测试
  - `batch_size=16`
  - 输出按 rerank_score 降序，并以原 score / chunk_id 作为稳定排序键
- 推荐二阶段：召回 top_k=20 → 精排 top_k=5（`rerank_recall_top_k` / `rerank_top_k`）

## BM25 + Hybrid Retriever

- BM25：`app/services/bm25_retriever.py`
  - `rank_bm25.BM25Okapi`
  - `jieba.lcut` 分词（中文友好）
  - 索引懒构建：首次 `search` 时拉 `vector_store.list_chunks(paper_id=...)` 构建
- Hybrid：`app/services/hybrid_retriever.py`
  - min-max 归一化 dense / sparse 分数
  - `score = α·dense + (1-α)·sparse`
  - 同 chunk_id 去重融合；输出保留 dense_score / sparse_score 便于调试
- 默认 α=0.5；通过 `HYBRID_ALPHA` 调整

## 查询优化

- `QueryRewriter`：调用 LLM 把口语 / 模糊查询改写为学术检索友好版本；失败回退原查询
- `HyDE`：让 LLM 生成 150-300 字的"假设论文段落"，对该段落做 embedding，再走向量检索
- Prompt 位于 `app/prompts/query_rewrite_prompt.py` / `app/prompts/hyde_prompt.py`

## 多 Embedding 模型

- `EmbeddingClient` 支持 alias 切换：bge-{small,base,large}-zh-v1.5、bge-m3、m3e-{small,base,large}
- 评测脚本：`python -m app.experiments.evaluate_embeddings --models <m1> <m2> ... [--live N]`
  - `--live N`：实际加载模型并对 N 条样本测真实嵌入耗时

## 增量索引与知识库

- `IncrementalIndexer`：按 chunk content 的 sha1 hash 做 diff，仅嵌入新增 / 改动的 chunk，删除消失 chunk
- `IndexVersionStore`：JSON 文件记录每篇论文的索引版本（chunk_count、embedding_model、created_at）；支持回滚到任意历史版本
- `KnowledgeBaseManager`：JSON registry 支持创建、列出、增删论文，默认 KB 名为 `"default"`
- KB API：`GET /kb`、`POST /kb`、`POST /kb/{kb_id}/papers`、`DELETE /kb/{kb_id}/papers/{paper_id}`

## 配置开关一览

| Env / Setting | 类型 | 默认 | 说明 |
|---|---|---|---|
| `ENABLE_RERANK` | bool | false | 启用 cross-encoder rerank |
| `RERANK_MODEL` | str | `BAAI/bge-reranker-v2-m3` | rerank 模型名 |
| `RERANK_TOP_K` | int | 5 | rerank 输出条数 |
| `RERANK_RECALL_TOP_K` | int | 20 | rerank 之前的召回条数 |
| `RETRIEVER` | str | `vector` | `vector` / `bm25` / `hybrid` |
| `HYBRID_ALPHA` | float | 0.5 | hybrid dense 权重（0-1） |
| `HYBRID_RECALL_TOP_K` | int | 20 | hybrid recall 阶段条数 |
| `QUERY_REWRITE` | str | `off` | `off` / `llm` |
| `HYDE` | str | `off` | `off` / `on` |
