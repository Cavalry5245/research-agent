# ResearchAgent：科研 Agent / 论文实验助手开发需求文档

## 0. 文档说明

本文档用于指导 `ResearchAgent` 项目的第一版 MVP 开发，并作为后续功能升级的路线依据。项目目标不是一次性实现完整科研平台，而是优先构建一个可运行、可演示、可写入简历的 AI 应用开发项目。

第一版核心链路为：

```text
上传论文 PDF
↓
解析论文文本
↓
生成结构化 Markdown 论文笔记
↓
构建本地知识库
↓
基于论文内容进行问答
↓
导出 Markdown 笔记
```

---

## 1. 项目名称

**ResearchAgent：面向研究生的论文阅读与实验分析助手**

英文名：

**ResearchAgent: An AI Research Assistant for Paper Reading and Experiment Analysis**

---

## 2. 项目定位

ResearchAgent 是一个面向科研人员、研究生和算法工程师的 AI 论文阅读与实验辅助系统。系统支持论文 PDF 解析、结构化信息抽取、Markdown 笔记生成、本地知识库问答、多论文对比与实验日志分析，帮助用户提升文献阅读、实验复盘和论文写作准备效率。

本项目不是一个简单的 ChatPDF 工具，而是面向科研工作流的轻量级 Agent 系统。第一版重点解决“读论文、整理笔记、问论文、导出材料”四个核心问题，后续逐步扩展到实验分析、论文综述、工具调用和多模态论文理解。

---

## 3. 目标用户

### 3.1 核心用户

- 研究生
- 博士生
- 科研助理
- 计算机视觉 / 自然语言处理 / 大模型方向研究人员
- 算法工程师
- 需要快速阅读论文和整理技术资料的 AI 从业者

### 3.2 典型使用场景

#### 场景一：单篇论文快速阅读

用户上传一篇 PDF 论文，系统自动生成结构化中文阅读笔记，包括研究背景、核心问题、方法概述、实验设置、数据集、评价指标、创新点、局限性和对用户课题的启发。

#### 场景二：基于论文内容进行问答

用户上传论文后，可以询问：

- 这篇论文解决了什么问题？
- 核心创新点是什么？
- 使用了哪些数据集？
- 实验指标有哪些？
- 方法有什么局限？
- 这篇论文对红外小目标检测有什么启发？

系统基于论文内容检索相关片段，并调用大语言模型生成回答。

#### 场景三：多篇论文对比

用户选择多篇论文，系统自动生成对比表，从研究任务、核心方法、关键模块、数据集、评价指标、优势和局限等维度进行比较。

#### 场景四：论文笔记沉淀

用户将生成的结构化笔记导出为 Markdown 文件，保存到本地知识库、Obsidian、Typora、Notion 或其他知识管理工具中。

#### 场景五：实验日志分析，后续版本实现

用户上传训练日志、评测结果或实验记录，系统提取关键指标、最佳 checkpoint、性能变化趋势和可能的失败原因，并生成实验复盘报告。

---

## 4. 项目目标

### 4.1 MVP 目标

构建一个可运行的科研论文阅读助手 MVP，支持以下能力：

1. 上传单篇或多篇 PDF 论文。
2. 解析 PDF 文本内容。
3. 自动生成结构化 Markdown 论文笔记。
4. 将论文内容切块并写入本地向量库。
5. 支持基于论文内容的 RAG 问答。
6. 支持多篇论文对比。
7. 支持 Markdown 文件导出。
8. 提供一个简单 Web 页面用于演示。

### 4.2 求职展示目标

项目完成后，应能够体现以下能力：

- AI 应用开发能力
- Python 后端开发能力
- LLM API 接入能力
- RAG 检索增强生成能力
- Prompt 设计能力
- 轻量 Agent 工具编排能力
- 文件解析和本地知识库构建能力
- 面向科研场景的产品理解能力

---

## 5. 第一版 MVP 功能需求

## 5.1 功能模块总览

| 模块 | 功能 | MVP 是否实现 | 优先级 |
|---|---|---:|---:|
| PDF 上传 | 上传论文 PDF | 是 | P0 |
| PDF 解析 | 提取标题、摘要、章节和正文 | 是 | P0 |
| 论文笔记生成 | 生成结构化 Markdown 笔记 | 是 | P0 |
| Markdown 导出 | 导出论文笔记 | 是 | P0 |
| 文本切块 | 对论文正文进行 chunk 切分 | 是 | P0 |
| 向量库 | 构建本地 Chroma 向量库 | 是 | P0 |
| RAG 问答 | 基于论文内容回答问题 | 是 | P0 |
| 多论文对比 | 生成多论文对比表 | 是 | P1 |
| 实验日志分析 | 分析训练日志和评测结果 | 否，后续 | P2 |
| 用户登录 | 多用户账号系统 | 否 | P3 |
| 联网论文检索 | arXiv / Semantic Scholar 检索 | 否 | P3 |
| 高精度图表公式解析 | 表格、公式、图像理解 | 否 | P3 |

---

## 5.2 PDF 上传模块

### 5.2.1 功能描述

用户可以通过 Web 页面上传一篇或多篇 PDF 论文，系统将文件保存到本地存储目录，并为每篇论文生成唯一 `paper_id`。

### 5.2.2 输入

- PDF 文件
- 可选：论文标签，如 `infrared small target detection`、`VLM`、`RAG`

### 5.2.3 输出

```json
{
  "paper_id": "paper_20260505_001",
  "filename": "example.pdf",
  "status": "uploaded",
  "storage_path": "app/storage/papers/example.pdf"
}
```

### 5.2.4 验收标准

- 支持上传 `.pdf` 文件。
- 非 PDF 文件需要返回明确错误。
- 文件上传后保存到 `app/storage/papers/`。
- 每篇论文需要生成唯一 `paper_id`。
- 上传记录写入 metadata 文件。

---

## 5.3 PDF 解析模块

### 5.3.1 功能描述

系统使用 PyMuPDF 解析 PDF 文本，并尝试识别论文标题、摘要、章节结构和正文内容。

### 5.3.2 推荐实现

第一版优先使用：

```text
PyMuPDF / pymupdf
```

解析结果不要求达到出版级精度，但需要保证正文主干可用。

### 5.3.3 输出数据结构

```json
{
  "paper_id": "paper_20260505_001",
  "title": "Paper Title",
  "abstract": "Abstract text...",
  "sections": [
    {
      "heading": "Introduction",
      "content": "..."
    },
    {
      "heading": "Method",
      "content": "..."
    }
  ],
  "full_text": "..."
}
```

### 5.3.4 章节识别规则

第一版可使用规则匹配：

- Abstract
- Introduction
- Related Work
- Method
- Methodology
- Experiments
- Results
- Discussion
- Conclusion
- References

### 5.3.5 验收标准

- 能够从 PDF 中提取全文文本。
- 能够提取或近似识别标题。
- 能够提取摘要，无法识别时返回空字符串或“未识别”。
- 能够按常见章节标题进行初步切分。
- 解析结果保存为 JSON 文件。

---

## 5.4 论文笔记生成模块

### 5.4.1 功能描述

系统调用 LLM，根据论文解析内容生成结构化中文 Markdown 阅读笔记。

### 5.4.2 笔记模板

生成结果必须遵循以下 Markdown 模板：

```markdown
# 论文阅读笔记：{title}

## 1. 基本信息

- 论文标题：
- 作者：
- 发表年份：
- 会议/期刊：
- 研究任务：
- 方法类别：
- 应用场景：
- 关键词：

## 2. 研究背景

## 3. 核心问题

## 4. 方法概述

## 5. 模型结构 / 技术路线

## 6. 实验设置

## 7. 数据集与评价指标

## 8. 主要实验结果

## 9. 创新点总结

## 10. 局限性分析

## 11. 对相关课题的启发

## 12. 可引用表述

## 13. BibTeX
```

### 5.4.3 Prompt 要求

Prompt 需要约束模型：

1. 使用中文输出。
2. 保持学术、客观、简洁。
3. 不要编造原文未出现的信息。
4. 信息缺失时写“原文未明确说明”。
5. 输出严格遵循 Markdown 模板。
6. 面向计算机视觉、AI、大模型、科研写作场景。

### 5.4.4 输入过长处理策略

如果论文全文超过模型上下文长度，采用分阶段处理：

1. 按章节或 chunk 对论文进行局部摘要。
2. 汇总局部摘要。
3. 基于汇总内容生成最终论文笔记。

### 5.4.5 验收标准

- 能生成完整 Markdown 格式论文笔记。
- 生成内容包含方法、实验、指标、创新点和局限性。
- 输出文件保存到 `app/storage/notes/`。
- 文件名包含 `paper_id` 或论文标题。
- 模型调用失败时有明确错误提示。

---

## 5.5 Markdown 导出模块

### 5.5.1 功能描述

将系统生成的论文笔记保存为 `.md` 文件，并支持用户下载。

### 5.5.2 输出路径

```text
app/storage/notes/{paper_id}_note.md
```

### 5.5.3 验收标准

- 能够生成 `.md` 文件。
- 文件内容格式正确。
- 支持从 Web 页面下载。
- 如果文件已存在，可以选择覆盖或生成新版本。

---

## 5.6 文本切块模块

### 5.6.1 功能描述

将论文文本切分为适合向量检索的文本块。

### 5.6.2 推荐参数

```python
chunk_size = 800
chunk_overlap = 100
```

### 5.6.3 Chunk 数据结构

```json
{
  "chunk_id": "paper_001_chunk_0001",
  "paper_id": "paper_001",
  "title": "Paper Title",
  "section": "Method",
  "content": "chunk text..."
}
```

### 5.6.4 验收标准

- 能够将论文正文切分为多个 chunk。
- 每个 chunk 包含 metadata。
- chunk 之间有适度重叠。
- 空文本、过短文本需要跳过。

---

## 5.7 向量库模块

### 5.7.1 功能描述

将论文 chunk 通过 embedding 模型转为向量，并写入本地向量库，用于后续 RAG 问答。

### 5.7.2 推荐向量库

MVP 推荐：

```text
Chroma
```

后续可扩展：

```text
FAISS
Milvus
Elasticsearch
```

### 5.7.3 Embedding 模型

第一版可支持以下任一种：

- bge-small-zh-v1.5
- bge-base-zh-v1.5
- bge-m3
- OpenAI-compatible embedding API

### 5.7.4 验收标准

- 能够将论文 chunk 写入 Chroma。
- 能够根据 query 返回 top_k 个相关 chunk。
- 检索结果包含 paper_id、title、section、chunk_id。
- 向量库支持本地持久化。

---

## 5.8 RAG 论文问答模块

### 5.8.1 功能描述

用户输入问题，系统从向量库检索相关论文片段，将片段作为上下文传给 LLM，并生成基于论文内容的回答。

### 5.8.2 输入示例

```json
{
  "question": "这篇论文的核心创新点是什么？",
  "paper_id": "paper_001",
  "top_k": 5
}
```

### 5.8.3 输出格式

```markdown
## 回答

...

## 依据片段

1. Paper: xxx, Section: Method, Chunk: xxx
2. Paper: xxx, Section: Experiments, Chunk: xxx
```

### 5.8.4 Prompt 要求

1. 只根据检索到的上下文回答。
2. 不允许编造论文中没有的信息。
3. 如果上下文不足，需要明确说明。
4. 回答应结构清晰，适合科研人员阅读。
5. 涉及方法、实验、指标时尽量具体。

### 5.8.5 验收标准

- 能基于单篇论文回答问题。
- 能基于所有已入库论文回答问题。
- 回答中附带依据片段。
- 检索不到结果时返回明确提示。
- 不允许模型无依据胡编。

---

## 5.9 多论文对比模块

### 5.9.1 功能描述

用户选择多篇论文，系统生成多论文对比表。

### 5.9.2 对比维度

- 论文标题
- 研究任务
- 核心方法
- 关键模块
- 使用数据集
- 评价指标
- 主要优势
- 局限性
- 对用户课题的启发

### 5.9.3 输出格式

```markdown
| 论文 | 研究任务 | 核心方法 | 数据集 | 指标 | 优势 | 局限 |
|---|---|---|---|---|---|---|
| Paper A | ... | ... | ... | ... | ... | ... |
| Paper B | ... | ... | ... | ... | ... | ... |
```

### 5.9.4 验收标准

- 支持选择 2–5 篇论文。
- 能生成 Markdown 对比表。
- 信息缺失时写“未明确说明”。
- 对比结果可保存为 Markdown。

---

## 5.10 Streamlit 前端模块

### 5.10.1 功能描述

使用 Streamlit 构建一个简单的 Web 演示界面。

### 5.10.2 页面设计

建议包含 4 个页面：

```text
1. 论文上传
2. 论文笔记生成
3. 论文问答
4. 多论文对比
```

### 5.10.3 页面功能

#### 页面一：论文上传

- 上传 PDF
- 显示上传状态
- 显示 paper_id
- 显示已上传论文列表

#### 页面二：论文笔记生成

- 选择论文
- 点击生成笔记
- 展示 Markdown 笔记
- 下载 Markdown 文件

#### 页面三：论文问答

- 选择单篇论文或全库问答
- 输入问题
- 展示回答
- 展示依据片段

#### 页面四：多论文对比

- 多选论文
- 点击生成对比表
- 展示 Markdown 表格
- 下载对比结果

### 5.10.4 验收标准

- Web 页面可以正常启动。
- 用户可以完成从上传到导出的完整流程。
- 页面不要求复杂美观，但逻辑清晰。
- 错误提示明确。

---

## 6. 非功能需求

## 6.1 配置管理

系统需要支持 `.env` 配置。

`.env.example` 示例：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat

EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=bge-small-zh-v1.5

VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=app/storage/vector_db

UPLOAD_DIR=app/storage/papers
NOTE_DIR=app/storage/notes
METADATA_DIR=app/storage/metadata
```

## 6.2 错误处理

需要处理以下错误：

- 文件格式错误
- PDF 解析失败
- LLM API 调用失败
- API key 未配置
- 向量库写入失败
- 检索无结果
- Markdown 文件保存失败

错误信息需要清晰，不能直接暴露底层堆栈给前端用户。

## 6.3 日志记录

建议使用 Python logging，至少记录：

- 文件上传日志
- PDF 解析日志
- LLM 调用日志
- 向量库写入日志
- RAG 查询日志
- 错误日志

## 6.4 可扩展性

代码结构需要支持后续扩展：

- 替换 LLM 模型
- 替换 embedding 模型
- 替换向量数据库
- 增加 Agent 工具
- 增加实验日志分析模块
- 增加论文联网检索模块

---

## 7. 推荐技术栈

## 7.1 后端

```text
Python
FastAPI
Pydantic
Uvicorn
python-dotenv
```

## 7.2 前端

```text
Streamlit
```

## 7.3 PDF 解析

```text
PyMuPDF
```

后续可扩展：

```text
GROBID
MinerU
Marker
unstructured
Nougat
```

## 7.4 LLM

```text
OpenAI-compatible API
DeepSeek
Qwen
本地 vLLM
Ollama
```

## 7.5 向量库

```text
Chroma
```

后续可扩展：

```text
FAISS
Milvus
Elasticsearch
```

## 7.6 Embedding

```text
bge-small-zh-v1.5
bge-base-zh-v1.5
bge-m3
OpenAI-compatible embedding API
```

---

## 8. 推荐项目目录结构

```text
research-agent/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── MVP_REQUIREMENTS.md
│   └── UPGRADE_PLAN.md
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   │
│   ├── services/
│   │   ├── pdf_parser.py
│   │   ├── chunker.py
│   │   ├── llm_client.py
│   │   ├── embedding_client.py
│   │   ├── vector_store.py
│   │   ├── note_generator.py
│   │   ├── paper_qa.py
│   │   ├── paper_compare.py
│   │   └── markdown_exporter.py
│   │
│   ├── agents/
│   │   ├── tools.py
│   │   └── research_agent.py
│   │
│   ├── prompts/
│   │   ├── paper_note_prompt.py
│   │   ├── qa_prompt.py
│   │   ├── compare_prompt.py
│   │   └── experiment_log_prompt.py
│   │
│   └── storage/
│       ├── papers/
│       ├── notes/
│       ├── vector_db/
│       └── metadata/
│
├── ui/
│   └── streamlit_app.py
│
├── examples/
│   ├── sample_papers/
│   └── sample_outputs/
│
└── tests/
    ├── test_pdf_parser.py
    ├── test_note_generator.py
    └── test_retrieval.py
```

---

## 9. FastAPI 接口设计

## 9.1 接口列表

```text
POST /papers/upload
POST /papers/{paper_id}/parse
POST /papers/{paper_id}/note
POST /papers/{paper_id}/index
POST /qa
POST /papers/compare
GET  /papers
GET  /papers/{paper_id}
GET  /papers/{paper_id}/note
GET  /papers/{paper_id}/download
```

## 9.2 上传论文

```http
POST /papers/upload
```

请求：

```text
multipart/form-data
file: PDF
```

响应：

```json
{
  "paper_id": "paper_001",
  "filename": "example.pdf",
  "status": "uploaded"
}
```

## 9.3 生成论文笔记

```http
POST /papers/{paper_id}/note
```

响应：

```json
{
  "paper_id": "paper_001",
  "note_path": "app/storage/notes/paper_001_note.md",
  "status": "success"
}
```

## 9.4 论文问答

```http
POST /qa
```

请求：

```json
{
  "question": "这篇论文的核心创新点是什么？",
  "paper_id": "paper_001",
  "top_k": 5
}
```

响应：

```json
{
  "answer": "...",
  "sources": [
    {
      "paper_id": "paper_001",
      "section": "Method",
      "chunk_id": "chunk_001"
    }
  ]
}
```

---

## 10. Prompt 模板

## 10.1 论文笔记生成 Prompt

```text
你是一名计算机视觉与人工智能方向的科研助手。请根据给定论文内容，生成结构化中文 Markdown 阅读笔记。

要求：
1. 使用中文输出。
2. 保持学术、客观、简洁。
3. 不要编造论文中没有的信息。
4. 如果信息缺失，请写“原文未明确说明”。
5. 输出必须严格遵循给定 Markdown 模板。
6. 涉及方法、实验、指标时尽量具体。
7. 对“对相关课题的启发”部分，可以结合计算机视觉、红外小目标检测、多模态模型、Agent 或 AI 应用开发进行分析，但必须基于原文内容，不得无依据扩展。

Markdown 模板：
# 论文阅读笔记：{title}

## 1. 基本信息
- 论文标题：
- 作者：
- 发表年份：
- 会议/期刊：
- 研究任务：
- 方法类别：
- 应用场景：
- 关键词：

## 2. 研究背景

## 3. 核心问题

## 4. 方法概述

## 5. 模型结构 / 技术路线

## 6. 实验设置

## 7. 数据集与评价指标

## 8. 主要实验结果

## 9. 创新点总结

## 10. 局限性分析

## 11. 对相关课题的启发

## 12. 可引用表述

## 13. BibTeX

论文内容：
{paper_content}
```

## 10.2 RAG 问答 Prompt

```text
你是一个严谨的科研论文问答助手。请只根据给定上下文回答用户问题。

要求：
1. 不要使用上下文之外的知识编造答案。
2. 如果上下文不足，请明确说明“根据当前论文片段无法判断”。
3. 回答应结构清晰，适合科研人员阅读。
4. 涉及方法、实验、指标时要尽量具体。
5. 回答后列出依据片段编号。

用户问题：
{question}

检索到的论文片段：
{context}
```

## 10.3 多论文对比 Prompt

```text
你是一名科研综述助手。请根据多篇论文的结构化信息，生成对比分析。

要求：
1. 输出 Markdown 表格。
2. 对比维度包括：研究任务、核心方法、关键模块、数据集、评价指标、优势、局限性、对相关课题的启发。
3. 不要夸大论文贡献。
4. 如果某项信息缺失，写“未明确说明”。

论文信息：
{papers}
```

---

## 11. 第一阶段开发计划

## 11.1 阶段一：项目初始化

目标：

- 创建项目仓库。
- 建立目录结构。
- 配置虚拟环境。
- 编写 `.env.example`。
- 编写 README 初稿。
- 配置 FastAPI 和 Streamlit 启动方式。

验收：

- `uvicorn app.main:app --reload` 可启动。
- `streamlit run ui/streamlit_app.py` 可启动。

---

## 11.2 阶段二：PDF 解析

目标：

- 实现 PDF 文本提取。
- 实现标题、摘要和章节的粗粒度识别。
- 保存解析结果。

核心文件：

```text
app/services/pdf_parser.py
app/schemas.py
```

验收：

- 输入一篇 PDF，能输出 JSON 解析结果。
- 至少包含 `title`、`abstract`、`sections`、`full_text` 字段。

---

## 11.3 阶段三：LLM Client 与笔记生成

目标：

- 实现 OpenAI-compatible LLM 调用。
- 实现论文笔记生成。
- 实现 Markdown 保存。

核心文件：

```text
app/services/llm_client.py
app/services/note_generator.py
app/services/markdown_exporter.py
app/prompts/paper_note_prompt.py
```

验收：

- 输入解析后的论文文本，生成 Markdown 笔记。
- 笔记保存到本地。

---

## 11.4 阶段四：RAG 检索问答（✅ 完成 - 父子文档架构）

### 当前状态
已完成父子文档架构升级，实现高精度检索和完整上下文回填。

### 架构特性
- **父文档**: 保存完整章节上下文（不进入向量索引）
- **子块**: 滑动窗口切分（500 字符，100 重叠）
- **检索**: Dense + BM25 hybrid search
- **回填**: 自动加载父文档提供完整上下文
- **引用**: 页码级别准确引用

### 关键组件
- `parent_doc_store.py` - 父文档存储（JSON）
- `parent_chunker.py` - 父文档构建和子块切分
- `paper_qa.py` - 检索回填逻辑
- `vector_store.py` - Hybrid search 实现
- `embedding_client.py` - 向量化服务

### 验收
- ✅ 可以将论文加入知识库（父子文档索引）
- ✅ 可以基于论文内容回答问题（完整上下文）
- ✅ 回答包含准确引用（页码范围）

详见 `docs/RAG_ARCHITECTURE.md`

---

## 11.5 阶段五：多论文对比与前端演示

目标：

- 实现多论文对比。
- 使用 Streamlit 串联完整流程。
- 优化 README 和示例输出。

核心文件：

```text
app/services/paper_compare.py
ui/streamlit_app.py
README.md
```

验收：

- 支持上传论文。
- 支持生成笔记。
- 支持论文问答。
- 支持多论文对比。
- 支持 Markdown 下载。

---

## 12. MVP 验收标准

第一版完成时，需要满足以下标准：

1. 可以通过 Streamlit 上传 PDF。
2. 可以解析 PDF 文本。
3. 可以生成结构化 Markdown 论文笔记。
4. 可以保存和下载 Markdown 文件。
5. 可以将论文写入本地向量库。
6. 可以基于论文内容进行问答。
7. 可以展示检索依据片段。
8. 可以选择 2–5 篇论文生成对比表。
9. README 中包含项目介绍、技术栈、启动方式和示例截图。
10. 代码结构清晰，便于后续扩展。

---

# 后续升级方案

---

## 13. 版本路线总览

| 版本 | 目标 | 核心能力 |
|---|---|---|
| v0.1 | 论文阅读助手 MVP | PDF 解析、笔记生成、RAG 问答、Markdown 导出 |
| v0.2 | 科研知识库增强 | 多论文管理、标签、检索过滤、引用追踪 |
| v0.3 | 实验日志分析助手 | 训练日志解析、指标抽取、实验复盘报告 |
| v0.4 | Agent 工具调用系统 | 工具注册、任务规划、自动执行多步科研任务 |
| v0.5 | 多模态论文理解 | 表格、图像、公式、模型结构图解析 |
| v1.0 | 科研工作流平台 | 论文阅读、知识库、实验分析、综述生成、写作辅助 |

---

## 14. v0.2：科研知识库增强

### 14.1 升级目标

把项目从“单篇论文阅读工具”升级为“本地科研知识库”。

### 14.2 新增功能

#### 论文管理

- 支持论文列表管理。
- 支持按标签分类。
- 支持按研究方向筛选。
- 支持按年份、会议、任务检索。

#### 元数据增强

为每篇论文保存：

```json
{
  "title": "...",
  "authors": ["..."],
  "year": "2024",
  "venue": "CVPR",
  "task": "Infrared Small Target Detection",
  "keywords": ["VLM", "Detection", "Infrared"],
  "tags": ["ISTD", "VLM", "Grounding DINO"]
}
```

#### 检索增强

- 支持按单篇论文检索。
- 支持按标签检索。
- 支持按任务检索。
- 支持全库问答。
- 支持返回引用来源。

### 14.3 技术改进

- 增加 SQLite 存储论文 metadata。
- 增加检索过滤条件。
- 优化 chunk metadata。
- 增加 rerank 模块，可选用 bge-reranker。

### 14.4 简历价值

该版本能体现：

- 本地知识库构建能力。
- RAG 系统工程能力。
- 结构化数据管理能力。
- 面向科研场景的信息组织能力。

---

## 15. v0.3：实验日志分析助手

### 15.1 升级目标

从“论文阅读助手”扩展到“实验复盘助手”，让系统能分析训练日志、评测结果和实验记录。

### 15.2 输入类型

支持上传：

- `.log`
- `.txt`
- `.json`
- `.csv`
- 训练输出目录
- COCO eval 结果
- TensorBoard 导出的标量数据

### 15.3 核心功能

#### 指标抽取

从日志中提取：

- loss
- AP
- AP50
- AP75
- Recall
- False Alarm Rate
- best epoch
- best checkpoint
- learning rate
- batch size

#### 异常分析

识别：

- loss 不下降
- 过拟合
- 指标震荡
- 验证集性能下降
- 训练提前崩溃
- 显存不足
- NaN loss

#### 实验报告生成

自动生成 Markdown 实验复盘：

```markdown
# 实验复盘报告

## 1. 实验配置

## 2. 指标变化

## 3. 最佳结果

## 4. 异常现象

## 5. 可能原因

## 6. 下一步建议
```

### 15.4 和用户研究方向的结合

该模块可以重点适配红外小目标检测实验：

- 解析检测指标。
- 分析误检和漏检。
- 归因复杂背景场景。
- 生成小论文实验结果分析草稿。
- 对比 baseline、baseline + A、baseline + B、baseline + A + B。

### 15.5 技术改进

- 增加日志解析器。
- 增加指标可视化。
- 增加实验记录数据库。
- 增加实验版本对比。
- 可选接入 matplotlib 绘图。

### 15.6 简历价值

该版本能体现：

- AI + 科研工作流结合能力。
- 数据分析能力。
- 实验自动化能力。
- 面向算法研发场景的工程落地能力。

---

## 16. v0.4：Agent 工具调用系统

### 16.1 升级目标

把项目从“功能集合”升级为“轻量级科研 Agent”。

### 16.2 工具注册机制

将系统功能封装为工具：

```python
read_pdf_tool
parse_paper_tool
generate_note_tool
retrieve_knowledge_tool
compare_papers_tool
analyze_experiment_log_tool
export_markdown_tool
```

### 16.3 Agent 执行流程

用户输入任务：

```text
帮我分析这三篇论文的共同创新点，并生成一个综述笔记。
```

Agent 自动执行：

```text
识别任务意图
↓
选择相关论文
↓
调用检索工具
↓
调用对比分析工具
↓
生成综述笔记
↓
导出 Markdown
```

### 16.4 功能要求

- 支持工具注册。
- 支持任务拆解。
- 支持多步调用。
- 支持中间结果保存。
- 支持失败重试。
- 支持执行日志展示。

### 16.5 技术路线

第一阶段不强依赖框架，可手写轻量工具调用机制。

后续可接入：

- LangChain
- LlamaIndex
- AutoGen
- CrewAI
- OpenAI function calling / tool calling

### 16.6 简历价值

该版本能体现：

- Agent 架构理解。
- 工具调用系统设计能力。
- 任务规划和执行链路设计能力。
- 工程可扩展性设计能力。

---

## 17. v0.5：多模态论文理解

### 17.1 升级目标

增强系统对论文中表格、图片、公式和模型结构图的理解能力。

### 17.2 新增能力

#### 表格解析

- 提取实验表格。
- 识别数据集、指标和结果。
- 自动总结 SOTA 对比结果。

#### 图像解析

- 提取论文中的模型结构图。
- 生成图像说明。
- 识别模块名称和流程。

#### 公式解析

- 提取公式区域。
- 将公式转为 LaTeX 或文本说明。
- 解释核心公式含义。

### 17.3 技术路线

可尝试：

- MinerU
- Marker
- Nougat
- PaddleOCR
- LayoutParser
- 多模态大模型 API
- Qwen-VL
- InternVL
- GPT-4o / Gemini 类多模态模型

### 17.4 简历价值

该版本能体现：

- 多模态 AI 应用开发能力。
- 文档智能解析能力。
- 科研场景复杂信息抽取能力。
- 与用户计算机视觉背景高度一致。

---

## 18. v1.0：科研工作流平台

### 18.1 升级目标

将系统升级为完整科研工作流平台。

### 18.2 核心模块

| 模块 | 功能 |
|---|---|
| 论文库 | 论文上传、解析、标签、检索 |
| 阅读助手 | 论文笔记、问答、对比 |
| 实验助手 | 日志分析、指标对比、实验报告 |
| 综述助手 | 多论文归纳、研究脉络分析 |
| 写作助手 | 章节草稿、相关工作整理 |
| Agent 工作流 | 多工具调用、任务规划、自动执行 |
| 导出系统 | Markdown、Docx、BibTeX、表格 |

### 18.3 高级功能

- 自动生成 Related Work 初稿。
- 自动整理 BibTeX。
- 自动生成论文方法对比表。
- 自动生成实验结果分析段落。
- 支持本地模型部署。
- 支持私有化科研知识库。
- 支持项目级知识管理。

### 18.4 求职定位

v1.0 完成后，该项目可以作为以下岗位的核心作品：

- AI 应用开发工程师
- Agent 开发工程师
- 大模型应用开发工程师
- RAG 工程师
- 多模态应用开发工程师
- AI 工具链开发工程师
- 算法平台开发工程师

---

## 19. 推荐开发优先级

### 第一优先级：必须先完成

```text
PDF 解析
论文笔记生成
Markdown 导出
RAG 问答
Streamlit 演示页面
```

### 第二优先级：完成后增强

```text
多论文对比
论文标签管理
SQLite metadata
Rerank
README 截图和示例
```

### 第三优先级：体现差异化

```text
实验日志分析
实验报告生成
Agent 工具调用
多步科研任务执行
```

### 第四优先级：高级能力

```text
表格解析
图像理解
公式解析
联网论文检索
综述自动生成
```

---

## 20. 项目里程碑

## Milestone 1：MVP 可运行

目标：

- 单篇 PDF 上传。
- 解析论文。
- 生成论文笔记。
- 导出 Markdown。

验收：

- 能完整跑通 PDF → Markdown。

---

## Milestone 2：RAG 问答可用

目标：

- 论文切块。
- 写入向量库。
- 支持论文问答。

验收：

- 能基于论文内容回答问题，并返回依据片段。

---

## Milestone 3：前端演示完整

目标：

- Streamlit 页面完成。
- 支持上传、笔记、问答、对比和下载。

验收：

- 可以录制项目演示视频。
- 可以截图写入 README。

---

## Milestone 4：实验日志分析

目标：

- 支持上传训练日志。
- 提取实验指标。
- 生成实验复盘报告。

验收：

- 能分析一次真实训练日志。
- 能输出 Markdown 实验报告。

---

## Milestone 5：Agent 化

目标：

- 将各模块封装为工具。
- 实现轻量任务规划与工具调用。

验收：

- 用户输入复杂任务后，系统能自动调用多个工具完成任务。

---

## 21. 简历描述示例

### 21.1 MVP 版本简历描述

**ResearchAgent：面向科研场景的论文阅读与知识库问答助手**

基于 FastAPI、Streamlit、PyMuPDF、Chroma 和 OpenAI-compatible LLM API 构建科研论文阅读助手，支持论文 PDF 解析、结构化 Markdown 笔记生成、本地知识库构建、RAG 问答、多论文对比和 Markdown 导出。设计论文切块、向量检索、Prompt 模板和来源引用机制，提升文献阅读和科研资料整理效率。

### 21.2 Agent 版本简历描述

**ResearchAgent：面向科研工作流的轻量级 Agent 系统**

设计并实现面向研究生科研场景的 Agent 系统，将 PDF 解析、论文笔记生成、知识库检索、多论文对比、实验日志分析和 Markdown 导出封装为可组合工具，支持用户通过自然语言完成论文阅读、实验复盘和综述整理任务。系统采用 FastAPI + Streamlit 架构，支持 OpenAI-compatible 模型接口、本地向量库和模块化工具扩展。

---

## 22. 面试讲解主线

面试介绍该项目时，建议按以下逻辑讲：

```text
背景：研究生读论文和做实验时，资料整理成本高。
问题：普通 ChatPDF 只能问答，不能沉淀结构化科研材料。
目标：做一个面向科研工作流的 AI Agent。
方案：PDF 解析 + LLM 笔记生成 + RAG 问答 + 多论文对比 + Markdown 导出。
工程：FastAPI 后端、Streamlit 前端、Chroma 向量库、OpenAI-compatible LLM 接口。
亮点：不是简单聊天机器人，而是将科研任务拆成可复用工具。
后续：扩展实验日志分析、Agent 工具调用和多模态论文理解。
```

---

## 23. 第一版交付物清单

MVP 完成后，项目至少应包含：

- GitHub 仓库
- README.md
- MVP_REQUIREMENTS.md
- requirements.txt
- .env.example
- FastAPI 后端
- Streamlit 前端
- 示例论文
- 示例 Markdown 笔记
- 示例问答结果
- 示例多论文对比结果
- 项目截图
- 一段 1–3 分钟演示视频，后续可选

---

## 24. 当前立即执行建议

当前最优先的第一步是：

1. 创建项目仓库 `research-agent`。
2. 新建 `docs/MVP_REQUIREMENTS.md`，放入本文档。
3. 按推荐目录结构创建文件夹。
4. 先实现 `pdf_parser.py`。
5. 再实现 `llm_client.py` 和 `note_generator.py`。
6. 跑通第一条主链路：`PDF → 文本 → Markdown 笔记`。

在第一条主链路跑通前，不建议优先做复杂 Agent 框架、复杂前端、联网检索或多用户系统。

