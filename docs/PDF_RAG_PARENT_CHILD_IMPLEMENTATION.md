# PDF RAG 父子文档实施方案

## 目标

将当前论文 PDF RAG 链路升级为“结构化解析 + 父子文档 + 滑动窗口子块 + 双索引检索 + Agent 回填回答”的完整方案。

核心原则：

- 父文档保存完整章节上下文，不进入向量索引。
- 子块由父文档内部滑动窗口切分，进入向量索引和关键词索引。
- 检索阶段只召回子块；命中子块后通过 `parent_id` 拉取完整父文档给大模型。
- 全链路保留 `paper_id`、`parent_id`、`chunk_id`、章节路径、页码范围和引用信息。

项目场景限定为数字文本型论文 PDF，不处理扫描版 OCR。单栏、双栏、图文混排、表格混排都属于需要支持的常见输入。

## 当前问题

当前实现主要是：

- `app/services/pdf_parser.py` 使用 PyMuPDF 抽取全文文本，再通过关键词正则识别章节。
- `app/services/chunker.py` 对章节文本做固定长度滑动窗口切片。
- `app/services/vector_store.py` 存储 chunk 和 embedding。
- `app/services/bm25_retriever.py` 从 vector store 的 chunk 列表临时构建 BM25。
- `app/services/paper_qa.py` 直接把检索命中的 chunk 拼入 prompt。
- `app/agents/tools/paper_tools.py` 的 QA tool 返回 sources 时只保留了 paper/title/section，丢失页码、chunk、父文档等证据信息。

主要不足：

- PDF 版式、双栏阅读顺序、表格、图注没有结构化建模。
- chunk 只有章节级上下文，缺少父文档回填能力。
- 页码只在 section/chunk 上弱保留，缺少稳定的 page range 和引用标签。
- 检索命中内容直接进入 LLM，上下文完整性受 chunk 大小限制。
- 评测没有明确区分 child hit、parent hit、页码引用准确性和答案质量。

## 目标架构

完整链路：

1. 识别 PDF 类型和版式。
2. 多模态结构化解析正文、标题、表格文本、图题图注和页码位置。
3. 还原论文 section tree。
4. 按论文结构生成父文档。
5. 在父文档内部执行滑动窗口切分，生成子块。
6. 子块进入向量索引和 BM25 关键词索引。
7. Agent 工具链按需检索子块。
8. 检索命中子块后，通过 `parent_id` 拉取完整父文档。
9. LLM 基于父文档上下文生成答案。
10. 输出带页码、章节、chunk、parent 的引用。
11. 通过评测闭环持续优化解析、切分和检索策略。

## 核心概念

### 滑动窗口切分

将文本按固定长度分段，相邻块保留部分重叠内容，避免关键语句被截断，保障检索时上下文不丢失。

默认策略：

- 只在同一个父文档内部滑动。
- 不跨父文档边界。
- 默认 `chunk_size = 500 tokens`。
- 默认 `chunk_overlap = 100 tokens`。
- 短父文档生成一个子块。
- 长父文档生成多个有 overlap 的子块。

### 父子文档分块

双层分块架构：

- 父文档：大块上下文，保存完整章节、表格或图注上下文，不向量检索。
- 子块：从父文档拆出的细粒度文本块，进入向量库和关键词索引用于匹配。

检索流程：

```text
query
  -> 检索子块
  -> rerank 子块
  -> 读取子块 parent_id
  -> 拉取完整父文档
  -> 将父文档作为上下文交给 LLM
  -> 输出答案和引用
```

这样可以兼顾：

- 子块粒度小，匹配精度更高。
- 父文档上下文完整，回答质量更稳定。
- 页码和章节信息可追踪。

## 数据模型

### PdfProfile

用于记录 PDF 类型和版式识别结果。

建议字段：

- `paper_id`
- `page_count`
- `is_text_pdf`
- `layout_type`: `single_column | double_column | mixed | unknown`
- `text_density`
- `has_tables`
- `has_figures`
- `reference_page_start`
- `warnings`

### DocumentElement

结构化解析的最小元素。

建议字段：

- `element_id`
- `paper_id`
- `type`: `title | abstract | heading | paragraph | table | figure_caption | equation | reference`
- `text`
- `page_number`
- `bbox`
- `section_path`
- `order_index`
- `metadata`

### ParentDocument

父文档保存完整上下文，不进入向量索引。

建议字段：

- `parent_id`
- `paper_id`
- `title`
- `section_path`
- `content`
- `page_range`
- `element_type`
- `element_ids`
- `bbox_refs`
- `metadata`

父文档边界：

- Abstract 可以成为独立父文档。
- 一级或二级章节可以成为父文档。
- 重要表格可以成为独立父文档，或归属到所在章节父文档。
- 图题图注可以成为独立父文档，或归属到所在章节父文档。
- References 默认不进入主 QA 父文档。

### Child Chunk

子块进入向量索引和关键词索引。

在现有 `Chunk` 基础上建议新增字段：

- `parent_id`
- `section_path`
- `page_range`
- `element_type`
- `content_for_embedding`
- `context_header`
- `bbox_refs`

字段语义：

- `content`: 子块原文，用于展示和引用。
- `content_for_embedding`: `context_header + content`，用于 embedding。
- `context_header`: 论文标题、章节路径、页码范围、父文档摘要或局部上下文。
- `parent_id`: 检索命中子块后回填父文档的关键关联字段。

### SourceItem

答案引用来源。

建议扩展字段：

- `parent_id`
- `page_range`
- `section_path`
- `element_type`
- `citation_label`

引用标签示例：

```text
[paper_20260509_004 p.4 Method]
```

## 实施步骤

### 1. PDF 类型与版式识别

新增 PDF profile 生成逻辑：

- 使用 PyMuPDF 检查每页文本块数量、文本密度和可抽取字符数。
- 若全文可抽取字符过少，判定为扫描版或图片型 PDF，返回明确错误。
- 根据 block 的 x 坐标分布判断单栏、双栏或混合版式。
- 粗略识别图片、表格、参考文献起始页。

验收标准：

- 数字文本 PDF 可以继续解析。
- 扫描版 PDF 不进入后续 RAG 链路。
- profile 写入 metadata，便于调试和评测归因。

### 2. 多模态结构化解析

升级 `parse_pdf()` 内部实现：

- 使用 `page.get_text("dict")` 获取 block、line、span、bbox、font size。
- 按坐标重排双栏阅读顺序。
- 识别标题、正文段落、表格文本、图题图注、公式和参考文献。
- 每个元素保留页码、bbox、阅读顺序和 section path。

实现要求：

- 对外保持当前 `PaperParseResult` 兼容。
- metadata JSON 中新增 `pdf_profile`、`elements`、`parse_warnings`。
- `full_text` 仍保留，用于兼容旧功能。

### 3. 论文结构还原

新增 section tree 构建逻辑：

- 综合字体大小、编号格式、标题关键词、位置和上下文判断 heading。
- 支持常见标题：Abstract、Introduction、Related Work、Method、Experiments、Results、Discussion、Conclusion、References。
- 支持二级和三级标题。
- 将正文、表格、图注归属到最近的 section path。

验收标准：

- 单栏和双栏论文的阅读顺序正确。
- section path 稳定写入元素和父文档。
- References 之后的内容默认不进入主 QA 父文档。

### 4. 父文档构建

新增 `build_parent_documents()`：

- 输入 structured elements。
- 按 section path 聚合正文、表格、图注。
- 每个父文档保留完整内容、页码范围、元素 ID 和 bbox refs。
- 父文档写入普通 doc store，不写入向量索引。

建议新增 `ParentDocumentStore`：

- `add_parents(paper_id, parents)`
- `get_parent(parent_id)`
- `get_parents(parent_ids)`
- `delete_paper(paper_id)`
- `metadata()`

存储方式：

- v1 可以使用 JSON 文件存储，延续当前 `VectorStore` 的本地优先风格。
- 后续可以替换为 SQLite，不影响检索接口。

### 5. 滑动窗口子块生成

新增 `chunk_parent_documents()`：

- 对每个父文档独立滑动窗口切分。
- 子块不跨父文档边界。
- 每个子块必须包含 `parent_id`。
- 每个子块保留 `page_range`、`section_path`、`element_type`。
- 每个子块生成 `context_header` 和 `content_for_embedding`。

默认参数：

```text
chunk_size = 500 tokens
chunk_overlap = 100 tokens
min_chunk_chars = 20
```

验收标准：

- 长章节生成多个重叠子块。
- overlap 只发生在同一父文档内部。
- 子块能通过 `parent_id` 找回完整父文档。

### 6. 双索引建设

索引原则：

- 向量索引只写入子块。
- BM25 关键词索引只写入子块。
- 父文档不进入向量索引。

改造 `IndexPaperTool` 和后台索引流程：

```text
parse PDF
  -> build structured elements
  -> build parent documents
  -> store parent documents
  -> sliding-window child chunks
  -> embed child chunks
  -> write child chunks to vector store
  -> BM25 uses child chunks from vector store
```

embedding 文本：

```text
content_for_embedding = context_header + "\n\n" + content
```

展示和引用仍使用 `content`。

### 7. 检索与父文档回填

改造 `answer_question()` 检索流程：

```text
query
  -> dense + BM25 hybrid search child chunks
  -> optional cross-encoder rerank child chunks
  -> group by parent_id
  -> select top parent documents
  -> load full parent documents
  -> build prompt context from parents
  -> generate answer
```

上下文构造要求：

- prompt 中包含父文档 citation label。
- 保留命中子块作为 evidence trace。
- 同一父文档多个子块命中时只回填一次父文档。
- 父文档过长时，可以优先放入完整父文档；若超过上下文预算，再使用命中子块附近窗口和父文档标题/摘要压缩。

### 8. Agent 工具链改造

建议拆分或增强工具：

- `search_paper_chunks`: 检索子块。
- `get_parent_document`: 根据 `parent_id` 拉取父文档。
- `answer_question`: 完整 QA 编排。

`QATool` 输出 sources 时必须保留：

- `paper_id`
- `parent_id`
- `chunk_id`
- `section_path`
- `page_range`
- `citation_label`

不再只返回 paper/title/section。

### 9. 页码引用与回答约束

更新 QA prompt：

- 每段上下文前加 citation label。
- 要求答案中的关键论点引用对应 label。
- 如果父文档不能支持问题，必须明确说明当前论文片段无法判断。

示例上下文：

```text
[paper_001 p.3-4 Method]
...
```

示例回答：

```text
该论文的方法核心是多阶段特征提取与注意力融合，主要在 Method 部分展开说明 [paper_001 p.3-4 Method]。
```

## 评测闭环

新增或重建一份干净论文 QA 评测集。

每条样本包含：

- `sample_id`
- `question`
- `expected_answer`
- `paper_id`
- `gold_parent_id`
- `gold_section_path`
- `gold_page_range`
- `answer_type`: `abstract | method | result | table | figure | cross_section | out_of_scope`

核心指标：

- `child_hit@k`: 检索子块是否命中相关证据。
- `parent_hit@k`: 子块回溯的父文档是否命中 gold parent。
- `citation_page_accuracy`: 引用页码是否覆盖 gold page。
- `answer_pass_rate`: 答案是否语义正确。
- `abstain_accuracy`: 无证据问题是否正确拒答。

失败归因：

- `parse_error`
- `structure_error`
- `child_retrieval_miss`
- `parent_retrieval_miss`
- `citation_miss`
- `answer_miss`
- `judge_error`

## 测试计划

### 单元测试

- PDF profile 能识别文本 PDF 和扫描版 PDF。
- 双栏 block 排序符合阅读顺序。
- section tree 能识别一级、二级标题。
- parent documents 不跨主章节。
- child chunks 只在父文档内部滑窗。
- 每个 child chunk 都有 `parent_id`。
- parent store 能增删查。
- vector store 只存 child chunks。

### 集成测试

- 上传 PDF 后能生成 profile、elements、parents、child chunks。
- 索引完成后，vector store 中存在 child chunks，parent store 中存在父文档。
- QA 检索命中 child chunk 后能拉取 parent document。
- sources 返回 parent、chunk、section 和页码信息。
- 删除论文时同时删除 PDF、metadata、note、parent documents 和 child chunks。

### 评测测试

- 干净 QA 集输出 child hit、parent hit、citation page accuracy、answer pass rate。
- 失败报告能按失败原因聚合。
- 对比旧链路和新链路，至少报告端到端 answer pass rate 和 citation page accuracy。

## 默认配置

建议新增配置：

```env
PDF_PARSE_MODE=structured
CHUNK_STRATEGY=parent_child_sliding_window
PARENT_DOC_STORE=json
CHILD_CHUNK_SIZE=500
CHILD_CHUNK_OVERLAP=100
RETRIEVER=hybrid
ENABLE_RERANK=true
PRESERVE_PAGE_CITATIONS=true
```

## 分阶段落地

### Phase 1：数据结构与兼容改造

- 新增 `ParentDocument`、`PdfProfile`、`DocumentElement` schema。
- 扩展 `Chunk` 和 `SourceItem`。
- 新增 `ParentDocumentStore`。
- 保持旧 API 可用。

### Phase 2：父子分块和索引

- 实现父文档构建。
- 实现父文档内滑动窗口子块切分。
- 改造索引流程，只索引子块。
- 确保 BM25 和 vector search 都基于子块。

### Phase 3：检索回填与 Agent QA

- 改造 `answer_question()`，命中子块后回填父文档。
- 改造 QA prompt 和 source 输出。
- 改造 Agent `QATool`，保留完整引用字段。

### Phase 4：结构化 PDF 解析增强

- 增强双栏排序。
- 增强标题层级识别。
- 增强表格、图注、References 处理。
- 写入 parse warnings。

### Phase 5：评测闭环

- 构建人工校验 QA 集。
- 新增 child hit、parent hit、页码引用准确率。
- 输出失败归因报告。

## 实施注意事项

- 不要把父文档写入向量索引。
- 不要让子块跨父文档边界。
- 不要在 Agent sources 中丢弃页码和 chunk 信息。
- 不要用扫描版 OCR 作为 v1 范围。
- 不要把 References 默认纳入主 QA 索引，除非问题明确要求引用文献相关内容。
- 父文档过长时，应先做上下文预算控制，再考虑摘要压缩；不能静默截断导致引用失真。

## 验收标准

完成后应满足：

- 一篇数字文本论文可以被解析为 profile、elements、parents、child chunks。
- vector store 中只存在 child chunks。
- child chunk 全部带 `parent_id`。
- 检索命中 child chunk 后可以稳定拉取完整 parent document。
- QA 答案 sources 包含页码、section、parent_id、chunk_id。
- 评测报告能同时展示 child hit@k、parent hit@k、citation page accuracy 和 answer pass rate。
