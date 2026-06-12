# ResearchAgent 运行与使用说明

本文档用于说明 ResearchAgent 项目的环境准备、启动方式、功能使用流程、常见问题和当前实现说明。适合项目初次运行、演示准备和后续维护时参考。

## 1. 项目简介

ResearchAgent 是一个面向研究生和科研人员的论文阅读与实验分析助手，支持以下核心能力：

- 上传并解析 PDF 论文
- 自动生成结构化中文 Markdown 论文笔记
- 构建本地论文知识库
- 基于论文内容进行 RAG 问答
- 对 2–5 篇论文进行多维度对比
- 导出 Markdown 结果
- 查看知识库索引状态
- 删除论文及其关联文件和索引

当前项目采用：

- FastAPI 作为后端接口层
- Streamlit 作为演示前端
- PyMuPDF 进行 PDF 文本解析
- OpenAI-compatible API 进行大模型调用
- sentence-transformers 进行文本向量化
- 本地 JSON 持久化 + 余弦相似度检索实现轻量向量库

## 2. 环境要求

推荐环境：

- 操作系统：Windows / macOS / Linux
- Python：3.11
- 环境管理：推荐使用 conda 环境 `research_agent`
- 网络：首次加载 embedding 模型时通常需要联网

## 3. 安装步骤

### 3.1 创建 conda 环境

在项目根目录外或任意终端中执行：

```powershell
conda create -n research_agent python=3.11 -y
conda activate research_agent
```

如果你已经创建过该环境，可直接执行：

```powershell
conda activate research_agent
```

### 3.2 安装依赖

进入项目根目录后执行：

```powershell
pip install -r requirements.txt
```

项目依赖主要包括：

- fastapi
- uvicorn[standard]
- streamlit
- pymupdf
- openai
- sentence-transformers
- torch
- chromadb
- pytest

说明：虽然 requirements.txt 中包含 chromadb，但当前项目主路径使用的是轻量本地持久化检索实现，而不是完整 ChromaDB 后端。

## 4. 环境变量配置

### 4.1 创建 `.env`

如果项目根目录存在 `.env.example`，可复制为 `.env`：

```powershell
Copy-Item .env.example .env
```

如果没有 `.env.example`，也可以手动新建 `.env` 文件。

### 4.2 最低必填配置

至少建议填写以下配置：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=deepseek-chat

EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=bge-small-zh-v1.5

VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=app/storage/vector_db

UPLOAD_DIR=app/storage/papers
NOTE_DIR=app/storage/notes
METADATA_DIR=app/storage/metadata
```

说明：

- `LLM_API_KEY` 为空时，笔记生成、论文问答、多论文对比会失败
- embedding 默认走本地模型，不需要额外 API key
- `VECTOR_STORE` 当前保留为 `chroma` 配置名，但项目实际主实现为本地 JSON 持久化向量检索

### 4.3 本地 Ollama 示例

如果你想使用本地 Ollama，可参考：

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen2.5:7b
```

## 5. 启动方式

项目支持两种常用运行方式。

### 5.1 方式一：启动 Streamlit 前端（推荐）

这是最适合演示和日常使用的方式。

```powershell
conda activate research_agent
streamlit run ui/streamlit_app.py
```

启动后在浏览器打开：

```text
http://localhost:8501
```

你可以在页面中完成：

- 上传论文
- 生成笔记
- 构建知识库
- 论文问答
- 多论文对比

### 5.2 方式二：启动 FastAPI 后端

如果你希望通过 API 调用项目，可启动后端服务：

```powershell
conda activate research_agent
uvicorn app.main:app --reload
```

## MCP Hub Demo Verification

Run all commands from `E:\projects\ResearchAgent`.

1. Verify Zotero local API:

```powershell
cmd /c "netstat -ano -p tcp | findstr :23119"
curl.exe -v "http://127.0.0.1:23119/api/users/0/items?limit=1"
```

Expected:

- `23119` is listening on `127.0.0.1`.
- `curl` returns `HTTP/1.0 200 OK` or another 2xx Zotero API response.

2. Verify Zotero MCP executable:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\Scripts\zotero-mcp.exe" version
```

Expected: prints `Zotero MCP v0.4.1` or a newer installed version.

3. Run MCP tests:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests\mcp tests\research_workflow\test_zotero_mcp_adapter.py tests\test_research_agent_mcp_server.py tests\test_research_run_router.py -q
```

Expected: all selected tests pass.

4. Start the API:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: `GET http://127.0.0.1:8000/health` returns `200 OK`.

5. Start Streamlit:

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m streamlit run ui/streamlit_app.py
```

Expected: the Research Workflow page shows MCP Hub status for Zotero, ResearchAgent, Semantic Scholar, arXiv, and Obsidian. The panel distinguishes running MCP servers, unavailable servers, discovered tool counts, and active fallbacks.

6. Run the flagship workflow:

- Open the Streamlit Research Workflow page.
- Use a known Zotero collection key.
- Set `Max papers` to `2`.
- Enable Semantic Scholar and arXiv only when network access is available.
- Leave Obsidian publishing disabled for the first run.
- Click `Process Local Collection`.

Expected:

- The run status becomes `completed`.
- The Knowledge Pack output directory exists.
- `assets/tool-calls.jsonl` records the Zotero provider and fallback state.
- The MCP Hub panel reports status honestly instead of claiming MCP availability when only a fallback is active.

启动后访问：

- 服务地址：http://localhost:8888
- API 文档：http://localhost:8888/docs

## 6. 推荐使用流程

推荐首次运行时按以下顺序操作：

### 第一步：上传 PDF 论文

在 Streamlit 页面中进入“论文上传”页：

- 选择一个 PDF 文件
- 系统自动保存原文件
- 自动解析 title / abstract / sections / full_text
- 自动生成 `paper_id`
- 自动把解析结果保存到 `app/storage/metadata/`

### 第二步：生成论文笔记

进入“笔记生成”页：

- 选择一篇已上传论文
- 可选重新解析 PDF
- 点击“生成笔记”
- 系统调用 LLM 按 13 段模板输出中文 Markdown
- 结果会保存到 `app/storage/notes/{paper_id}_note.md`

### 第三步：构建知识库

进入“知识库”页：

- 选择一篇已上传论文
- 点击“索引到向量库”
- 系统执行：切块 → embedding → 持久化索引

### 第四步：进行论文问答

进入“论文问答”页：

- 选择全库问答或单篇问答
- 输入问题
- 调用检索与 LLM 推理
- 返回答案及依据片段

### 第五步：进行多论文对比

进入“论文对比”页：

- 勾选 2–5 篇论文
- 生成多维度对比结果
- 支持导出 Markdown

## 7. API 接口概览

当前后端提供 13 个接口：

- `GET /health`：健康检查
- `GET /papers`：论文列表
- `POST /papers/upload`：上传 PDF 并自动解析
- `POST /papers/{id}/parse`：重新解析论文
- `POST /papers/{id}/note`：生成笔记
- `GET /papers/{id}/note`：读取笔记
- `GET /papers/{id}/download`：下载笔记
- `POST /papers/{id}/index`：写入知识库索引
- `GET /papers/{id}/index-status`：查看单篇论文索引状态
- `GET /library/index-status`：查看全库索引汇总
- `DELETE /papers/{id}`：删除论文及相关文件和索引
- `POST /qa`：论文问答
- `POST /papers/compare`：多论文对比

建议直接通过 `http://localhost:8888/docs` 查看 Swagger 文档并测试。

## 8. 数据存储说明

项目运行时会使用以下目录：

```text
app/storage/
├── papers/      # 上传的 PDF 原文件
├── metadata/    # 解析结果 JSON
├── notes/       # 生成的 Markdown 笔记 / 对比结果
└── vector_db/   # 向量索引持久化数据
```

典型数据包括：

- `metadata/{paper_id}_parsed.json`
- `notes/{paper_id}_note.md`
- `notes/compare_*.md`
- `vector_db/vector_store.json`

## 9. 测试与验证

在当前项目状态下，推荐使用以下命令运行测试：

```powershell
conda activate research_agent
python -m pytest tests -q
```

当前实测结果为：

```text
46 passed, 2 skipped
```

如果你只是想快速确认环境是否可用，建议至少验证两步：

1. 测试是否能通过
2. Streamlit 页面是否能正常打开

## 10. 常见问题

### 10.1 报错：LLM API Key 未配置

原因：`.env` 没有正确配置 `LLM_API_KEY`。

处理：

- 检查 `.env` 是否存在
- 检查 `LLM_BASE_URL`
- 检查 `LLM_API_KEY`
- 检查 `LLM_MODEL`

### 10.2 生成笔记或问答时报 LLM API 调用失败

可能原因：

- API key 不正确
- base_url 不正确
- 模型名不正确
- 网络不通
- 所用模型不兼容 OpenAI Chat Completions 接口

### 10.3 Embedding 模型首次加载很慢

原因：首次需要下载本地模型。

处理：等待首次加载完成即可，后续通常会使用本地缓存。

### 10.4 论文问答没有检索到内容

原因：尚未先把论文入库。

处理：先进入“知识库”页，执行“索引到向量库”。

### 10.5 为什么配置里写了 chroma，但代码里不是完整 ChromaDB？

这是当前项目设计上的历史兼容保留：

- 配置项沿用了 `VECTOR_STORE=chroma` 和 `CHROMA_PERSIST_DIR`
- 当前主实现是轻量本地 JSON 持久化检索
- 后续如果需要更强的过滤、并发和扩展能力，可再替换为真正的 ChromaDB 后端

## 11. 当前项目状态总结

当前版本已经完成：

- 论文上传与解析
- 结构化笔记生成
- 本地知识库构建
- RAG 问答
- 多论文对比
- 索引状态管理
- 论文删除与索引清理
- Streamlit 演示前端

因此它已经是一个可运行、可演示、可继续扩展的 MVP 项目。

## 12. 推荐启动命令速查

如果你只想最快把项目跑起来，按下面执行即可：

```powershell
conda activate research_agent
pip install -r requirements.txt
streamlit run ui/streamlit_app.py
```

如果你要跑后端接口：

```powershell
conda activate research_agent
uvicorn app.main:app --reload
```
