# QUICKSTART — Docker

使用 Docker 一键启动 ResearchAgent，无需安装 Python、配置环境。

## 前置条件

- [Docker](https://docs.docker.com/engine/install/)（推荐 Docker Desktop 或 Docker Engine 24+）
- 至少 4GB 可用内存
- 一个 LLM API Key（如 DeepSeek、SiliconFlow、OpenAI 等）

## 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/your-username/ResearchAgent.git
cd ResearchAgent
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少配置 LLM：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=deepseek-chat
```

也支持 SiliconFlow、OpenAI 等兼容 API：

```env
# SiliconFlow
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_MODEL=deepseek-llm-chat

# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### 3. 启动

```bash
docker compose up -d
```

### 4. 打开

| 服务 | 地址 | 说明 |
|------|------|------|
| React 前端 | http://localhost | Research Pipeline 主界面 |
| API 文档 | http://localhost:8000/docs | FastAPI Swagger 文档 |
| 健康检查 | http://localhost:8000/health | 服务状态 |

## 使用流程

1. 打开 http://localhost
2. 进入 Workflow 页面创建 Research Run
3. 输入研究问题，选择来源模式，配置参数
4. 查看 Agent Timeline、Candidate Papers、PaperCards
5. 生成带引用校验的 Markdown 研究报告

更多功能请查看主 README。

## 常见问题

### 首次构建需要多久？

取决于网络。首次 `docker compose up` 需要下载 Python 基础镜像和安装依赖，通常 3-10 分钟。后续启动秒级完成。

### 数据存在哪里？

`app/storage/` 目录挂载为 Docker volume，容器删除后数据不会丢失：
- `papers/` — 上传的 PDF
- `notes/` — 生成的笔记
- `vector_db/` — Chroma 向量数据库
- `metadata/` — 论文解析结果

### 如何更新？

```bash
git pull
docker compose build
docker compose up -d
```

### 如何停止？

```bash
docker compose down
```

### 如何查看日志？

```bash
docker compose logs -f api         # 后端日志
docker compose logs -f frontend    # 前端日志
```

### 提示 `torch` 在 CPU 上运行？

正常。Docker 镜像默认使用 CPU 版 torch。sentence-transformers 模型推理在 CPU 上运行，性能足够个人使用。

### Embedding 模型下载慢？

首次启动时 API 服务会自动下载本地 embedding 模型（~33MB，bge-small-zh-v1.5）。如果下载失败，可设置 HTTP 代理，或等待后续 `EMBEDDING_PROVIDER=api` 模式（计划中，将支持 SiliconFlow / OpenAI 兼容的 `/v1/embeddings`，免本地下载冷启动）。
