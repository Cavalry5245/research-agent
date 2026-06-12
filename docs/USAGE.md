# ResearchAgent 使用说明

## 1. 环境准备

### 1.1 系统要求

- Windows / macOS / Linux
- Python 3.11（推荐 conda）
- 网络连接（首次需下载 embedding 模型约 130MB）

### 1.2 安装步骤

```powershell
# 创建 conda 环境
conda create -n research_agent python=3.11 -y
conda activate research_agent

# 安装依赖
pip install -r requirements.txt
```

### 1.3 配置 LLM

复制并编辑配置文件：

```powershell
cp .env.example .env
```

打开 `.env`，填入你的 LLM 信息：

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=deepseek-chat
```

支持的 LLM 提供商（任一即可）：

| 提供商 | LLM_BASE_URL 示例 |
|--------|------------------|
| DeepSeek | `https://api.deepseek.com/v1` |
| Qwen (通义千问) | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Ollama (本地) | `http://localhost:11434/v1` |
| OpenAI | `https://api.openai.com/v1` |

> 如果只有 LLM 没有配置，笔记生成和问答功能会报错。Embedding 使用本地模型，无需额外配置。

### 1.4 启动

```powershell
# 方式一：Streamlit 前端（推荐，单命令运行所有功能）
streamlit run ui/streamlit_app.py

# 方式二：FastAPI 后端（提供 REST API + Swagger 文档）
uvicorn app.main:app --reload
# 浏览器打开 http://localhost:8888/docs 查看 API 文档
```

---

## 2. 功能使用

Streamlit 前端包含 5 个 Tab，按从左到右的顺序使用即可。

### 2.1 📤 上传论文

1. 点击「📤 论文上传」Tab
2. 拖拽或点击选择 `.pdf` 文件
3. 系统自动：
   - 保存 PDF 到 `app/storage/papers/`
   - 用 PyMuPDF 提取全文
   - 识别 title / abstract / sections
   - 保存解析结果到 `app/storage/metadata/{paper_id}_parsed.json`
4. 上传成功后显示 paper_id、标题、章节数、字符数

> 可重复上传多篇论文，paper_id 自动递增（`paper_20260505_001`, `_002`, ...）

### 2.2 📝 生成笔记

1. 切换到「📝 笔记生成」Tab
2. 下拉框选择论文
3. （可选）点击「📖 重新解析」重新提取文本
4. 点击「🤖 生成笔记」
5. 系统调用 LLM，按以下 13 段模板生成中文 Markdown：

```
# 论文阅读笔记：{title}
## 1. 基本信息
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

6. 生成后页面展示 Markdown 渲染结果
7. 点击「📥 下载 Markdown」保存为 `{paper_id}_note.md`

> 信息缺失时 LLM 会标注"原文未明确说明"，不会编造。

### 2.3 🗄️ 构建知识库

1. 切换到「🗄️ 知识库」Tab
2. 下拉框选择一篇已上传的论文
3. 点击「📥 索引到向量库」
4. 系统自动：
   - 切块（chunk_size=800, overlap=100）
   - 用 bge-small-zh-v1.5 将每个 chunk 转为 768 维向量
   - 写入向量库
5. 页面显示"已索引 N 个 chunks"

> 入库后才能进行 RAG 问答。可逐篇入库，也可批量。

### 2.4 💬 论文问答

1. 切换到「💬 论文问答」Tab
2. 选择检索范围：
   - 「全库问答」：在所有已入库论文中检索
   - 「单篇论文」：只在指定论文中检索
3. 输入问题（例如"这篇论文的核心创新点是什么？"）
4. 调整检索片段数（默认 5）
5. 点击「🔍 提问」
6. 系统执行：
   - 将问题转为向量 → 检索相关 chunk
   - 拼接上下文 → 调 LLM 生成回答
   - 展示回答 + 依据片段（可展开查看具体内容）

> 如果没有入库任何论文，会提示"当前知识库中没有检索到相关内容"。

### 2.5 📊 多论文对比

1. 切换到「📊 论文对比」Tab
2. 从多选框中勾选 2–5 篇要对比的论文
3. 点击「📊 生成对比表」
4. LLM 提取各论文信息，按以下维度生成 Markdown 表格：

| 维度 | 说明 |
|------|------|
| 论文标题 | — |
| 研究任务 | 检测 / 分类 / 生成 等 |
| 核心方法 | 方法概述 |
| 关键模块 | 模型关键组件 |
| 数据集 | 使用的数据集 |
| 评价指标 | 精度 / 召回 等 |
| 主要优势 | 相比其他方法的优势 |
| 局限性 | 方法局限 |
| 启发 | 对相关课题的参考价值 |

5. 生成后展示表格，支持下载 `.md` 文件

---

## 3. 数据存储说明

所有数据保存在项目根目录的 `app/storage/` 下：

```
app/storage/
├── papers/          # 上传的 PDF 原文件
├── metadata/        # 解析结果 JSON ({paper_id}_parsed.json)
├── notes/           # 生成的 Markdown 笔记
└── vector_db/       # 向量库持久化目录
```

> 启动时会自动创建缺失的目录。

---

## 4. API 调用（高级）

如果不使用 Streamlit，也可以通过 curl 调用 FastAPI：

### 健康检查

```powershell
curl http://localhost:8888/health
```

### 上传论文

```powershell
curl -X POST http://localhost:8888/papers/upload -F "file=@your_paper.pdf"
# → {"paper_id":"paper_20260505_001","status":"parsed",...}
```

### 生成笔记

```powershell
curl -X POST http://localhost:8888/papers/paper_20260505_001/note
# → 返回 JSON，content 字段包含完整 Markdown
```

### 论文问答

```powershell
curl -X POST http://localhost:8888/qa \
  -H "Content-Type: application/json" \
  -d '{"question":"核心创新点是什么？","paper_id":"paper_20260505_001","top_k":5}'
```

### 多论文对比

```powershell
curl -X POST http://localhost:8888/papers/compare \
  -H "Content-Type: application/json" \
  -d '{"paper_ids":["paper_20260505_001","paper_20260505_002"]}'
```

完整 API 文档：启动 FastAPI 后访问 `http://localhost:8888/docs`

---

## 5. 常见问题

### Q: 启动报错 "LLM API Key 未配置"

A: 检查 `.env` 文件中的 `LLM_API_KEY` 是否正确填写。

### Q: 笔记生成失败 "LLM API 调用失败"

A: 检查 `LLM_BASE_URL` 和 `LLM_MODEL` 是否正确，网络是否能连通。

### Q: Embedding 模型加载慢

A: 首次启动需从 HuggingFace 下载 `bge-small-zh-v1.5`（约 130MB），后续启动使用本地缓存。

### Q: 问答返回"没有检索到相关内容"

A: 需要先将论文入库（🗄️ 知识库 Tab），否则向量库为空。

### Q: 如何更换 Embedding 模型

A: 修改 `.env` 中的 `EMBEDDING_MODEL`，例如改为 `bge-m3` 或 `BAAI/bge-base-zh-v1.5`。

### Q: 如何接入本地 LLM（Ollama）

A: 在 `.env` 中设置：
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```
