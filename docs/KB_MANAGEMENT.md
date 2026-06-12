# 知识库管理（Phase 4）

Phase 4 引入轻量级知识库管理功能：增量索引、版本元数据、多 KB 隔离。所有元数据均以 JSON 文件持久化，不引入数据库依赖。

## 增量索引

- 模块：`app/services/incremental_indexer.py::IncrementalIndexer`
- 算法：
  1. 拉取当前 `vector_store.list_chunks(paper_id)` 的 chunk_id 与 sha1(content)
  2. 与新的 chunks 求差集：
     - `to_add`：chunk_id 不存在 或 hash 已变
     - `to_remove`：chunk_id 已存在但新集合中不再出现
     - `unchanged`：其他
  3. 删除 `to_remove`（`vector_store.delete_chunks`），仅对 `to_add` 调用 embedding API
- 返回：`{paper_id, added, removed, unchanged}`

适用场景：论文重新解析后只动改动的章节，避免全量重嵌入。

## 索引版本管理

- 模块：`app/services/index_version.py::IndexVersionStore`
- 持久化：`app/storage/metadata/index_versions.json`
- 元数据 schema：
  ```json
  {
    "paper_id": "paper_001",
    "version": 1,
    "created_at": "2026-05-22T...",
    "chunk_count": 87,
    "embedding_model": "bge-small-zh-v1.5"
  }
  ```
- API：
  - `record_version(paper_id, chunk_count, embedding_model, extra=...)`
  - `list_versions(paper_id) → list[dict]`
  - `latest(paper_id) → dict | None`
  - `rollback_to(paper_id, version) → dict | None`（truncate 到该版本之前）

## 多知识库隔离

- 模块：`app/services/knowledge_base_manager.py::KnowledgeBaseManager`
- 持久化：`app/storage/metadata/knowledge_bases.json`
- 默认 KB：`"default"`（首次加载自动创建）
- 隔离方式：通过 `paper_ids` 列表关联；当前不复制 chunks，多 KB 共享 vector store，按 paper_id 过滤
- API：
  - `create_kb(kb_id, name, description="")`
  - `get_kb(kb_id) | list_kbs() | stats(kb_id)`
  - `add_paper_to_kb(kb_id, paper_id) | remove_paper_from_kb(kb_id, paper_id)`

## REST API

| Method | Path | 说明 |
|---|---|---|
| GET | `/kb` | 列出全部 KB |
| POST | `/kb` | 新建 KB（`kb_id`、`name`、`description`） |
| POST | `/kb/{kb_id}/papers` | 添加 paper（`paper_id`） |
| DELETE | `/kb/{kb_id}/papers/{paper_id}` | 移除 paper |

返回 schema：`KBResponse { id, name, description, paper_ids, created_at }`。

## 使用示例

```bash
# 新建知识库
curl -X POST http://localhost:8888/kb \
  -H "Content-Type: application/json" \
  -d '{"kb_id":"robotics","name":"机器人","description":"机器人相关论文"}'

# 添加论文
curl -X POST http://localhost:8888/kb/robotics/papers \
  -H "Content-Type: application/json" \
  -d '{"paper_id":"paper_20260101_001"}'

# 列出全部 KB
curl http://localhost:8888/kb
```

## 限制与后续

- 当前 KB 只做"组关联"，未对 vector store 做物理隔离；多租户场景建议在 vector store 层增加 `kb_id` 字段并在 retriever 处过滤
- 增量索引未与 `IndexVersionStore` 自动联动；如需"索引一次记一版"，在调用方完成
