# Chroma + bge-m3 向量索引重建设计

## 1. 背景与当前状态

项目配置声明 `VECTOR_STORE=chroma`，依赖中也包含 Chroma，但 `app/services/vector_store.py` 当前仍是 JSON 文件持久化与 Python 线性余弦扫描，`settings.vector_store` 没有参与后端选择。

截至 2026-07-20，当前索引 `app/storage/vector_db/vector_store.json` 的实测状态为：

- 5,038 个 chunk，覆盖 48 篇论文，文件约 80.19 MB；
- 4,304 个 768 维向量、730 个 512 维向量、4 个 3 维测试向量；
- 各论文内部维度一致，但全库存在三种维度；
- JSON 实现使用 `zip()` 计算余弦相似度，维度不一致时会静默截断，而不是拒绝查询。

权威重建输入是 `app/storage/metadata/*_parsed.json`，目前共有 53 份。项目另有约 100 份 PDF，但本次不重新解析 PDF，避免把解析差异引入向量库迁移。

已确认的统一 embedding 配置为：

- provider：OpenAI-compatible API；
- model：`bge-m3`；
- Chroma：当前环境 `chromadb==1.5.9`；
- 距离空间：cosine。

## 2. 目标

1. 让 `VECTOR_STORE=chroma` 对应真实的 Chroma 持久化后端。
2. 使用 API `bge-m3` 对 53 份已解析论文重新分块并生成统一维度的向量。
3. 通过 staging collection 完成蓝绿重建，验证通过前不影响当前 JSON 查询路径。
4. 支持按论文断点续跑，避免 API 限流或进程中断造成重复费用。
5. 保留现有 `vector_store.json` 作为显式回退，不迁移其中的历史 embedding，不删除任何旧数据。
6. 保持现有 `VectorStore` import 和公开方法兼容，避免修改所有调用方。

## 3. 非目标

- 不重新解析现有 PDF。
- 不在本次工作中补齐尚未生成 parsed JSON 的 PDF。
- 不迁移 512、768 或 3 维历史 embedding。
- 不改变父子文档分块策略、BM25、hybrid rerank 或查询改写算法。
- 不引入 Chroma Server、Chroma Cloud 或多租户部署；本次使用本地 `PersistentClient`。
- 不自动删除旧 collection、JSON 索引、评测产物或其他存储文件。

## 4. 架构设计

保留 `app.services.vector_store.VectorStore` 作为门面，调用方继续通过现有类访问向量库。

```text
VectorStore facade
├── JsonVectorBackend
└── ChromaVectorBackend
```

建议文件边界：

- `app/services/vector_store.py`
  - 保留 `VectorStore` 类名和现有公开方法；
  - 按配置选择后端；
  - 保留 `HybridReranker` 公共后处理，确保两种后端的 hybrid 行为一致。
- `app/services/vector_backends/base.py`
  - 定义后端契约：`add_chunks`、`query_dense`、`delete_paper`、`delete_chunks`、`has_paper`、`metadata`、`count`、`list_chunks`。
- `app/services/vector_backends/json_backend.py`
  - 承接当前 JSON 加载、持久化和线性余弦检索逻辑；
  - 增加 embedding 数量与维度校验，消除静默截断。
- `app/services/vector_backends/chroma_backend.py`
  - 封装 `PersistentClient`、collection 配置、upsert、filter、query 和字段转换。
- `scripts/rebuild_chroma_index.py`
  - 从 parsed JSON 批量构建 staging collection；
  - 负责预检、断点续跑、回读校验和 manifest；
  - 不承载应用在线查询逻辑。

应用配置增加：

```text
VECTOR_STORE=chroma|json
CHROMA_PERSIST_DIR=app/storage/vector_db
CHROMA_COLLECTION_NAME=research_papers_bge_m3_v1
```

Chroma 是显式选择的后端。初始化失败、collection 未 ready、维度不匹配或数据损坏时应快速失败，不应静默切换到可能陈旧的 JSON 索引。回退由运维明确设置 `VECTOR_STORE=json` 并重启应用完成。

## 5. Chroma collection 设计

使用：

```python
client.get_or_create_collection(
    name=collection_name,
    configuration={"hnsw": {"space": "cosine"}},
)
```

不得依赖 Chroma 默认的 L2 空间。Chroma 返回 cosine distance 后，公共结果中的相似度分数定义为 `1.0 - distance`，与当前余弦分数语义保持一致。

collection metadata 使用标量值记录：

- `embedding_provider=api`
- `embedding_model=bge-m3`
- `embedding_dimension=<首批 API 响应的实际维度>`
- `chunk_strategy`
- `child_chunk_size`
- `child_chunk_overlap`
- `schema_version=1`
- `build_status=building|ready|failed`
- `source_count=53`
- `git_head=<构建时完整 HEAD>`

每个 chunk 的映射：

- Chroma ID：`chunk_id`
- document：`chunk.content`
- embedding：API 返回的 `bge-m3` 向量
- metadata：`paper_id`、`title`、`section`、`page_number`、`chunk_start`、`chunk_end`、`parent_id`、`section_path`、`page_range`、`element_type`

值为 `None` 的可选 metadata 不写入 Chroma，读取时恢复为 `None`。业务查询结果必须继续返回：

`chunk_id`、`content`、`paper_id`、`title`、`section`、`page_number`、`chunk_start`、`chunk_end`、`score`、`parent_id`、`section_path`、`page_range`、`element_type`。

## 6. 蓝绿重建流程

### 6.1 预检

1. 加载项目配置，确认 provider、model、base URL 与 API key 均已设置；日志只输出“是否配置”，不得输出 key。
2. 枚举并排序 53 份 `*_parsed.json`。
3. 对每个源文件计算 SHA-256。
4. 记录当前 Git HEAD、分块配置、目标 collection 和 schema version。
5. 若同名 collection 已存在，验证其模型、维度、分块配置和 schema version；任何不一致都停止，不自动覆盖或删除。

### 6.2 Canary

先选择一篇规模适中的论文执行真实 API canary：

1. 解析为 `PaperParseResult`；
2. 使用当前 `chunk_paper()` 生成 chunk；
3. 分批调用 `bge-m3`；
4. 从首批响应锁定实际向量维度；
5. 校验响应数量、向量非空、全部元素为有限数值且维度一致；
6. upsert 后按 `paper_id` 回读 ID 与数量；
7. 执行至少一个限定该论文的语义查询，检查字段和排序。

Canary 未通过时不继续全量构建。

### 6.3 全量构建

按源文件名稳定排序逐篇执行：

```text
parsed JSON
  -> Pydantic schema validation
  -> chunk_paper()
  -> batched bge-m3 embeddings
  -> count/dimension/value validation
  -> Chroma upsert
  -> read-back verification
  -> mark paper completed
```

一篇论文只有在全部 chunk 写入并回读一致后才算完成。脚本不得因为某篇已经存在就直接跳过，必须同时满足源哈希、manifest 状态与 Chroma 回读数量一致。

### 6.4 Manifest 与续跑

manifest 放在 Chroma 持久化目录中，文件名包含 collection 名，例如：

`rebuild_research_papers_bge_m3_v1_manifest.json`

manifest 不包含 API key 或完整认证头，记录：

- collection、provider、model、实际维度、schema version；
- Git HEAD 与分块配置；
- 53 份源文件的相对路径和 SHA-256；
- 每篇论文的 paper_id、chunk 数、状态、尝试次数、错误摘要和完成时间；
- 汇总状态与 chunk 总数。

续跑规则：

- 源哈希一致、状态 completed、Chroma 回读 ID/数量一致：跳过；
- 未完成或回读不一致：重新处理该论文并幂等 upsert；
- 源哈希变化：只重建对应论文；
- collection 契约不匹配：停止并要求使用新的版本化 collection 名。

## 7. 错误处理

- 对 HTTP 429、超时和可恢复 5xx 使用有限次数指数退避，并尊重 `Retry-After`。
- 达到重试上限后停止当前论文，记录脱敏错误并保留断点。
- API 返回向量数与文本数不一致、空向量、NaN、Infinity 或维度漂移时，在写入前失败。
- Chroma upsert 后回读失败时不标记完成。
- 查询向量维度与 collection 维度不一致时返回清晰错误，提示 embedding 配置与索引模型不一致。
- collection 不是 `ready` 时，应用默认拒绝使用；重建脚本可在 `building` 状态下继续写入。
- 所有日志与异常必须避免输出 API key、认证头和完整请求对象。

## 8. 测试设计

### 8.1 后端契约测试

同一组参数化测试运行 JSON 与 Chroma 后端：

- add/upsert 同 ID 不重复；
- 全局查询与 `paper_id` 过滤；
- cosine 排序和 score 语义；
- `delete_paper`、`delete_chunks`；
- `has_paper`、`count`、`list_chunks`、`metadata`；
- 业务查询字段完整恢复；
- 重建实例后持久化数据仍可读取；
- embeddings 数量或维度不一致时拒绝写入。

现有依赖 JSON 行为的测试应显式构造 JSON 后端；新增 Chroma 测试使用临时目录，不接触项目真实存储。

### 8.2 重建脚本测试

使用 fake embedding API 和临时 Chroma 验证：

- 首次完整构建；
- canary 失败时不进入全量；
- 中断后续跑；
- completed 论文正确跳过；
- 源哈希变化后只重建对应论文；
- collection 契约不匹配时拒绝覆盖；
- API 数量或维度异常时失败；
- manifest 与日志不包含密钥。

### 8.3 验证命令

先运行向量库与重建脚本的目标测试，再运行：

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests -v --ignore=tests/performance
```

性能目录不属于本次正确性验收范围。

## 9. 全量验收与切换

切换前必须同时满足：

1. collection `build_status=ready`；
2. 53 篇源文件全部 completed；
3. Chroma 总 chunk 数等于 manifest 汇总；
4. chunk ID 无重复；
5. 全 collection embedding 维度一致；
6. 抽样的 paper_id 过滤、语义排序和返回字段正确；
7. 后端契约测试、重建脚本测试和项目非性能测试通过。

切换步骤：

1. 设置 `VECTOR_STORE=chroma`；
2. 设置 `CHROMA_COLLECTION_NAME=research_papers_bge_m3_v1`；
3. 重启应用，避免复用旧的进程级单例；
4. 检查 health/system-status 中 backend、collection、chunk_count、paper_count 和 ready 状态；
5. 执行一组应用级 QA smoke test。

回退步骤：

1. 设置 `VECTOR_STORE=json`；
2. 重启应用；
3. 验证 health/system-status 与一组 QA smoke test。

回退不删除 Chroma collection，后续可检查并再次切换。

## 10. 依赖与兼容性

- 将 Chroma 锁定为 `chromadb==1.5.9`，使实现、测试与持久化格式可复现。
- 使用 1.5.9 的 `configuration={"hnsw": {"space": "cosine"}}`，不使用旧式 `metadata={"hnsw:space": "cosine"}`。
- 应用始终自行生成 embedding，并向 Chroma 传入 `embeddings`；不使用 Chroma 默认 embedding function。
- 查询必须使用与 collection 相同的 API endpoint/model 配置；实际维度仍需在运行时校验。

## 11. 风险与缓解

- API 限流或费用超预期：canary、分批、有限重试、按论文 checkpoint。
- API 服务同名模型发生版本变化：记录构建时间、endpoint 的非敏感标识、实际维度和 source hash；新模型重建使用新 collection 版本。
- parsed JSON 中存在损坏文件：单篇 schema 校验失败并保留断点，不把 collection 标为 ready。
- 分块代码在续跑期间变化：manifest 记录 Git HEAD 和分块参数；不匹配时拒绝续跑同一 collection。
- JSON 与 Chroma 结果存在 ANN 细微排序差异：契约测试验证分数语义，真实 canary 与 smoke test 验证可接受性，不要求逐项完全相同。
- Chroma 数据与 `vector_store.json` 位于同一持久化根目录：文件名和 collection 命名明确隔离；脚本不读取、覆盖或删除 JSON 文件。

## 12. 已确认决策

- 使用 API `bge-m3` 作为唯一 embedding 标准。
- 第一阶段只重建 53 份已有 parsed JSON，不重新解析 100 份 PDF。
- 使用版本化 staging collection 做蓝绿重建。
- 保留 JSON 后端作为显式回退，不做静默降级。
- 先 canary，再全量；支持按论文断点续跑。
- 旧向量不迁移、不覆盖、不删除。
