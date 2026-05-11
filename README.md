# ResearchAgent

面向研究生的论文阅读与实验分析 AI 助手。支持 PDF 解析、结构化 Markdown 笔记生成、本地知识库构建、RAG 问答、多论文对比和 Markdown 导出。

相关文档：
- 运行与使用说明：`docs/RUN_GUIDE.md`
- 使用说明：`docs/USAGE.md`
- 系统架构：`docs/ARCHITECTURE.md`
- MVP 需求文档：`docs/MVP_REQUIREMENTS.md`
- 开发日志：`docs/DEVELOPMENT_LOG.md`

## 功能

| 功能 | 说明 |
|------|------|
| 📤 PDF 上传与解析 | PyMuPDF 提取 title / abstract / sections / full_text |
| 📝 笔记生成 | LLM 生成 13 段结构化中文 Markdown 论文笔记 |
| 🔍 RAG 问答 | 向量检索 + LLM，支持单篇/全库，附带依据片段 |
| 📊 多论文对比 | 2–5 篇论文自动生成 9 维度 Markdown 对比表 |
| 🗄️ 知识库 | 文本切块 + sentence-transformers 嵌入 + 向量检索 |
| 📥 Markdown 导出 | 笔记/对比结果保存为 .md 并支持下载 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11, FastAPI, Pydantic |
| 前端 | Streamlit |
| PDF 解析 | PyMuPDF |
| LLM | OpenAI-compatible API (DeepSeek / Qwen / Ollama) |
| Embedding | sentence-transformers (bge-small-zh-v1.5) |
| 向量检索 | 余弦相似度（接口兼容 Chroma） |
| 配置 | .env (pydantic-settings) |

## 快速启动

```powershell
# 1. 创建并激活 conda 环境
conda create -n research_agent python=3.11 -y
conda activate research_agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
cp .env.example .env
# 编辑 .env: 填入 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 4. 启动 Streamlit（推荐，单命令运行）
streamlit run ui/streamlit_app.py
# → 浏览器打开 http://localhost:8501

# 或启动 FastAPI 后端
uvicorn app.main:app --reload
# → http://localhost:8000
# → API 文档: http://localhost:8000/docs
```

## 使用流程

### 1. 上传论文
- 打开 Streamlit，在「📤 论文上传」Tab 选择 PDF
- 系统自动解析并分配 paper_id
- 在列表中可查看已上传论文

### 2. 生成笔记
- 切换到「📝 笔记生成」Tab
- 选择论文，点击「🤖 生成笔记」
- 系统调用 LLM 生成 13 段结构化中文 Markdown
- 支持预览和下载 .md 文件

### 3. 构建知识库
- 切换到「🗄️ 知识库」Tab
- 选择论文，点击「📥 索引到向量库」
- 论文被切块（chunk_size=800）、向量化、写入向量库

### 4. 论文问答
- 切换到「💬 论文问答」Tab
- 选择全库或单篇，输入问题
- 系统检索相关片段，LLM 基于上下文生成回答
- 底部展示检索依据片段

### 5. 多论文对比
- 切换到「📊 论文对比」Tab
- 选择 2–5 篇论文，点击「📊 生成对比表」
- LLM 生成 9 维度 Markdown 对比表

## 系统架构

```
Streamlit UI (5 Tabs)
  ↓ 直接调用
Service Layer
  ├── pdf_parser (PyMuPDF)
  ├── note_generator → LLM
  ├── paper_qa → VectorStore + Embedding + LLM
  ├── paper_compare → LLM
  └── chunker / markdown_exporter
  ↓
Storage: papers/ | notes/ | metadata/ | vector_db/
```

详见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/papers` | 列出所有论文 |
| `POST` | `/papers/upload` | 上传 PDF（自动解析） |
| `POST` | `/papers/{id}/parse` | 重新解析 |
| `POST` | `/papers/{id}/note` | 生成笔记 |
| `GET` | `/papers/{id}/note` | 读取笔记 |
| `GET` | `/papers/{id}/download` | 下载笔记 |
| `POST` | `/papers/{id}/index` | 切块入库 |
| `GET` | `/papers/{id}/index-status` | 查看单篇论文索引状态 |
| `GET` | `/library/index-status` | 查看知识库索引汇总 |
| `DELETE` | `/papers/{id}` | 删除论文及相关索引/笔记 |
| `POST` | `/qa` | RAG 问答 |
| `POST` | `/papers/compare` | 多论文对比 |

### cURL 示例

```powershell
# 上传 PDF
curl -X POST http://localhost:8000/papers/upload -F "file=@paper.pdf"

# 生成笔记
curl -X POST http://localhost:8000/papers/paper_20260505_001/note

# 论文问答
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"question":"核心创新点是什么？","top_k":5}'

# 查看单篇索引状态
curl http://localhost:8000/papers/paper_20260505_001/index-status

# 查看知识库索引汇总
curl http://localhost:8000/library/index-status

# 多论文对比
curl -X POST http://localhost:8000/papers/compare \
  -H "Content-Type: application/json" \
  -d '{"paper_ids":["paper_20260505_001","paper_20260505_002"]}'
```

## 项目结构

```
research-agent/
├── README.md
├── requirements.txt
├── .env.example
├── docs/
│   ├── MVP_REQUIREMENTS.md    # 完整需求文档
│   ├── DEVELOPMENT_LOG.md     # 开发日志
│   └── ARCHITECTURE.md        # 系统架构
├── app/
│   ├── main.py                # FastAPI (13 endpoints)
│   ├── config.py              # 配置管理
│   ├── schemas.py             # Pydantic 模型
│   ├── services/              # 核心模块
│   │   ├── pdf_parser.py
│   │   ├── llm_client.py
│   │   ├── embedding_client.py
│   │   ├── vector_store.py
│   │   ├── chunker.py
│   │   ├── note_generator.py
│   │   ├── paper_qa.py
│   │   ├── paper_compare.py
│   │   ├── paper_status.py
│   │   ├── paper_manager.py
│   │   └── markdown_exporter.py
│   ├── prompts/               # Prompt 模板
│   │   ├── paper_note_prompt.py
│   │   ├── qa_prompt.py
│   │   └── compare_prompt.py
│   ├── agents/                # 预留 Agent 扩展
│   └── storage/               # 本地数据
├── ui/
│   └── streamlit_app.py       # 5 Tab 前端
├── examples/
│   ├── sample_papers/
│   └── sample_outputs/
│       └── sample_note.md
└── tests/                     # 48 项测试（46 passed, 2 skipped）
    ├── test_paper_status.py
    ├── test_paper_manager.py
    ├── test_pdf_parser.py
    ├── test_note_generator.py
    ├── test_chunker.py
    ├── test_retrieval.py
    └── test_paper_qa.py
```

## 开发进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 项目初始化 | FastAPI + Streamlit 骨架 | ✅ |
| PDF 解析 | PyMuPDF → title/abstract/sections | ✅ |
| 笔记生成 | LLM 13段 Markdown 模板 | ✅ |
| 文本切块 | chunk_size=800, overlap=100 | ✅ |
| Embedding + 向量库 | sentence-transformers + 本地持久化检索 | ✅ |
| RAG 问答 | 检索 + LLM 生成 + sources | ✅ |
| 多论文对比 | 2-5 篇 9 维度表格 | ✅ |
| Streamlit 前端 | 5 Tab 完整串联 | ✅ |

## 运行测试

```powershell
conda activate research_agent
python -m pytest tests\ -v
# 46 passed, 2 skipped
```

## 后续升级

| 版本 | 目标 |
|------|------|
| v0.2 | SQLite 论文管理 + 标签分类 + 检索过滤 |
| v0.3 | 实验日志分析（训练日志 → 指标提取 → 复盘报告） |
| v0.4 | Agent 工具调用（工具注册 → 任务规划 → 多步执行） |
| v0.5 | 多模态论文理解（图表/公式/模型结构图） |
| v1.0 | 科研工作流平台 |

## 简历描述

**ResearchAgent：面向科研场景的论文阅读与知识库问答 Agent**

基于 FastAPI、Streamlit、PyMuPDF 和 OpenAI-compatible LLM API 构建科研论文阅读助手，支持论文 PDF 解析、13 段结构化 Markdown 笔记生成、sentence-transformers 向量嵌入、本地持久化向量检索、RAG 问答（附来源引用）、多论文 9 维度对比和 Markdown 导出。设计文本切块滑动窗口、Prompt 模板约束机制和模块化 service 架构，具备 Agent 工具化扩展能力。

**技术亮点**: Python / FastAPI / Streamlit / PyMuPDF / sentence-transformers / Embedding / RAG / Prompt Engineering / 向量检索
