# API Reference

> 自动生成自 FastAPI OpenAPI schema — 36 endpoints / 28 paths

Base URL: `http://localhost:8000`

## 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |

## 论文管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/papers` | 列出所有论文 |
| POST | `/papers/upload` | 上传 PDF（multipart/form-data） |
| DELETE | `/papers/{paper_id}` | 删除论文及相关索引/笔记 |
| POST | `/papers/{paper_id}/parse` | 重新解析论文 |
| POST | `/papers/{paper_id}/index` | 切块入库（params: `force`） |
| GET | `/papers/{paper_id}/index-status` | 查看单篇索引状态 |
| GET | `/library/index-status` | 查看知识库索引汇总 |

## 笔记

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/papers/{paper_id}/note` | 生成 13 段结构化笔记 |
| GET | `/papers/{paper_id}/note` | 读取笔记内容 |
| GET | `/papers/{paper_id}/download` | 下载笔记 .md 文件 |

## RAG 问答与对比

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/qa` | RAG 问答（body: `question`, `paper_id?`, `top_k?`） |
| POST | `/papers/compare` | 多论文对比（body: `paper_ids`） |

## 知识库管理（Phase 4）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/kb` | 列出所有知识库 |
| POST | `/kb` | 创建知识库 |
| POST | `/kb/{kb_id}/papers` | 添加论文到知识库 |
| DELETE | `/kb/{kb_id}/papers/{paper_id}` | 从知识库移除论文 |

## 后台任务（Phase 3）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 列出后台任务 |
| POST | `/tasks/note/{paper_id}` | 提交笔记生成后台任务 |
| POST | `/tasks/compare` | 提交多论文对比后台任务 |
| GET | `/tasks/{job_id}` | 查询任务状态 |
| DELETE | `/tasks/{job_id}` | 取消任务 |
| GET | `/tasks/{job_id}/result` | 获取任务结果 |
| POST | `/tasks/{job_id}/retry` | 重试失败任务 |
| GET | `/jobs` | 列出 indexing jobs |
| GET | `/jobs/{job_id}` | 查询 indexing job 状态 |

## Agent（Phase 1 + 5）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/agent/execute` | Agent 执行（body: `task`, `mode`: react/supervisor） |

## 对话与追踪（Phase 5）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 对话历史列表（params: `limit`, `offset`） |
| GET | `/api/conversations/{id}` | 对话详情（含消息列表） |
| DELETE | `/api/conversations/{id}` | 删除对话 |
| GET | `/api/traces` | Agent 执行追踪（params: `conversation_id`, `agent_id`, `limit`） |
| GET | `/api/traces/stats` | 追踪统计（by_agent / by_action 聚合） |

## 请求示例

### 上传论文
```bash
curl -X POST http://localhost:8000/papers/upload -F "file=@paper.pdf"
```

### RAG 问答
```bash
curl -X POST http://localhost:8000/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "核心创新点是什么？", "top_k": 5}'
```

### Agent 执行（Supervisor 模式）
```bash
curl -X POST http://localhost:8000/agent/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "帮我分析这篇论文的方法", "mode": "supervisor"}'
```

### 查询执行追踪
```bash
curl "http://localhost:8000/api/traces?limit=20"
curl "http://localhost:8000/api/traces/stats"
```
