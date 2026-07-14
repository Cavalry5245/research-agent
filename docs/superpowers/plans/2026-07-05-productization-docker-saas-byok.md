# 产品化执行文档：开源自部署 (Docker) + 托管 SaaS (BYOK)

> **状态**：A 轨道 + B 最小 demo 的代码已完成并合入 `main`（GitHub 已同步）。剩余收尾：CI 修绿、Railway 实际部署、README Demo 链接回填。
> **最后更新**：2026-07-05
> **权威计划**：本文件（进 git，可追溯）。会话临时计划 `~/.claude/plans/deep-prancing-sunset.md` 为 agent-local，非权威。

---

## 背景与目标

ResearchAgent 是功能完整的本地 AI 论文阅读助手（PDF → 中文笔记 → RAG QA → 多论文对比 → Markdown 导出，外加 LangGraph agent + research pipeline + paper-search MCP），此前只有本地开发形态。

**目标**：求职 / 作品集展示 —— 让技术面试官能看代码与架构，让非技术 HR 能点链接直接体验。预算 <¥100/月。

**收敛出的两条轨道**（代码重叠 >80%，A 是 B 的前置）：
- **A 开源自部署**：`git clone && docker compose up` 一条命令起完整应用，GitHub 可审阅。
- **B 托管 SaaS (BYOK)**：公开 URL，访客填自己的 LLM Key（Bring Your Own Key）即可体验，运营零 LLM 成本。

**范围决策**（已与用户确认）：
- 做 A 全部 + B 的 BYOK 最小 demo（单用户，无 auth）。
- **跳过** B1 用户系统 / B2 多租户隔离 / B5 长驻 worker —— 单用户 demo 足够求职展示，多用户特性留待有真实需求再做。
- 部署平台选 **Railway**。

---

## 已完成（代码已在 `main`，GitHub 已同步）

4 个产品化 commit 全部确认在 `origin/main` 上：

| Commit | 内容 |
|--------|------|
| `66c3b176` | **轨道 A**：LICENSE、requirements PyPI 化、Dockerfile CPU torch、nginx 安全头、tests.yml/release.yml、.gitignore 放开 .github、README/QUICKSTART |
| `29a888c0` | **轨道 B**：BYOK（contextvar + ByokMiddleware + 前端 Settings 卡片 + client.ts 头注入）+ `embedding_provider=api` 分支 + railway.toml |
| `d507619f` | BYOK UI 简化：去掉 provider 预设按钮，只留 OpenAI 兼容三输入框（Base URL / API Key / Model） |
| `750c3e4a` | QUICKSTART 克隆地址指向真实仓库 `Cavalry5245/research-agent` |

### 轨道 A 明细

- [x] **A1 许可与依赖卫生**
  - 新增 `LICENSE`（MIT，2026 Chase Huang）。
  - `requirements.txt`：`paper-search-mcp` 从裸 git commit pin 改为 PyPI `>=0.1.4`（PyPI 0.1.4 已含统一 `search_papers` / `download_with_fallback` 工具），消除再分发供应链风险。
- [x] **A2 Docker 全流程校验**
  - `Dockerfile` 先装 CPU-only torch（192MB，替代 1.5GB+ CUDA），避免 CI/构建拉巨型 wheel 超时，镜像瘦身。
  - `frontend/nginx.conf` 补安全头（CSP / X-Content-Type-Options / X-Frame-Options / Referrer-Policy / Permissions-Policy）。
  - 验证：`docker compose build`（api 3.84GB / frontend 93MB）→ `up -d` → `/health`、`/system/status`、frontend HTTP 200 → 上传+解析 PDF HTTP 200。
  - Streamlit 已确认仅 legacy/debug，不进 docker-compose。
- [x] **A3 文档与展示**
  - `README.md`：一句话定位、在线 Demo 占位、mermaid 架构图。
  - `QUICKSTART.md`：CPU torch 说明、embedding API 模式说明。
- [x] **A4 Release 流水线**
  - `.github/workflows/release.yml`：tag `v*` → GitHub Release + 推 api/frontend 镜像到 GHCR。
  - `.github/workflows/tests.yml`：CI 用 CPU torch + `--ignore=tests/performance`。

### 轨道 B 明细（最小 demo）

- [x] **B3 BYOK 核心**
  - `app/services/llm_client.py`：`UserLLMConfig` + `ContextVar` 注入，`LLMClient(user_override=)` 优先请求级 override，回退 `settings`。
  - `app/middleware/byok.py`：`ByokMiddleware` 读 `X-LLM-Base-URL` / `X-LLM-API-Key` / `X-LLM-Model` 头 → contextvar，请求结束复位。**Key 不落盘、不入日志**。
  - `frontend/src/api/client.ts`：`getLlmOverride/setLlmOverride`（localStorage 键 `ra.llmOverride`），`llmOverrideHeaders()` 注入所有 fetch。
  - `frontend/src/pages/settings/SettingsPage.tsx`：BYOK 卡片（Base URL / API Key / Model 三输入框 + Save/Clear）。
  - **验证铁证**：伪造 `X-LLM-API-Key: sk-bogus-byok-test` 调 `/papers/{id}/note` → HTTP 502，provider 明文返回 `Authentication Fails, Your api key: ****test is invalid` → 证明 override 确实打到 LLM。
- [x] **B4 Embedding 切 API**
  - `app/config.py`：新增 `embedding_base_url` / `embedding_api_key`。
  - `app/services/embedding_client.py`：`embedding_provider=="api"` 分支，调 OpenAI 兼容 `/v1/embeddings`（如 SiliconFlow bge-m3），按 batch 分块。
  - Docker 自部署默认 `local`；SaaS 建议 `api`（免本地模型冷启动）。仅 import 验证，未跑真实 SiliconFlow key 的端到端。

### 验证结果汇总

- 前端：`npm run lint`（tsc）✅ · `npm run build`（vite）✅ · `SettingsPage.test` ✅。
- 后端：app import ✅（`ByokMiddleware` 已注册）· `test_llm_client`/`test_embedding_client`/`test_tracing_middleware` 12 passed。
- Docker：重建 + `up` + `/health` ok + 上传解析 200 + BYOK 运行时铁证 ✅。

---

## 当前状态

- **代码交付层面：产品化基本完成**。A + B 全部代码已在 `origin/main`。
- **未完成的收尾**：
  1. GitHub Actions **CI 是红的**（见下方分类）。
  2. Railway **实际未部署**，还没有公开 Demo URL。
  3. README 顶部的"在线 Demo"仍是占位链接。
- **注意**：当前 git 工作分支是 `codex/qa-thread-memory`（后续会话开的无关新功能，QA 对话记忆），**不属产品化**。修 CI / 部署应基于 `main`。

---

## 剩余待办

### T1. 修绿 CI（提升作品集观感，优先）

`main` 上最近一次 CI（`750c3e4a`）失败。`--ignore=tests/performance` 已生效（不再是 12s 的 collection error，而是跑满约 3min 后测试失败）。失败分两类：

**类别一：CI 无 LLM key + 测试实例化真实客户端（非本会话回归，但需处理）**
- 现象：`openai.OpenAIError: Missing credentials` 或 `LLM API Key 未配置…（BYOK）`。
- 涉及：`tests/integration/test_multi_agent_e2e.py`（`TestMemoryIntegrationE2E` / `TestObservabilityWiring`）、`tests/test_paper_research_agent.py`（全部）、`tests/test_agent_tools.py`（note/compare）、`tests/test_async_compare_tasks.py`、`tests/test_paper_compare.py`。
- 根因：`app/agents/paper_research_agent.py:47-52` 在 `__init__` 里就 `_build_llm()`（`ChatOpenAI`）+ `create_agent()`；测试只 mock 了 `create_agent`，没拦住 `ChatOpenAI` 的凭据检查。文件顶注写"LLM calls are mocked"但实际没 mock 到构造层。
- **本会话关联**：报错文案的 BYOK 后缀是 B3 加的，但失败本身在无 key 环境必然发生（原文案也是"LLM API Key 未配置"），**不是 B3 引入的回归**。
- **修法建议**（择一或组合）：
  - [ ] 在 `tests.yml` 的测试步骤注入 dummy env：`LLM_API_KEY=sk-ci-dummy`、`OPENAI_API_KEY=sk-ci-dummy`，让 `ChatOpenAI` 构造通过（这些测试本就 mock 了实际调用，只是卡在构造）。
  - [ ] 或给真正需要真实 LLM 往返的测试加 `@pytest.mark.skipif(not os.getenv("LLM_API_KEY"), ...)`。
  - [ ] 或让 `PaperResearchAgent` 延迟构造 LLM（lazy），使 `create_agent` 的 mock 能覆盖。

**类别二：预存测试债（与产品化完全无关）**
- [ ] `tests/research_pipeline/test_zotero_source.py`：断言 Windows 路径 `E:\\...` / `C:\\...`，在 Linux CI 必挂 → 改用 `os.path` 或 `pathlib` 平台无关断言。
- [ ] `tests/research_pipeline/test_router.py` + `tests/test_research_run_router.py`：`'_IncludedRouter' object has no attribute 'path'` → FastAPI 版本漂移，路由自省方式变了。
- [ ] `tests/test_comparison_evaluator.py`：`Expected comparison seed dataset rows…assert []` → seed 数据集为空。
- [ ] `tests/test_retrieval.py::test_embedding_client_import`：断言 `bge-small-zh-v1.5` 但实际 default 是 `m3e-base` → 断言与配置漂移。
- [ ] `tests/research_pipeline/test_mvp_gate_report.py`：MVP gate 相关，与 PENDING 的 gate report 有关。

> 决策点：类别二是历史技术债，是否在本轮一并修，还是只 skip 让 CI 变绿、债务单独立项。求职观感角度，"CI 绿 + 少量 xfail/skip 并注明原因" 优于 "CI 全红"。

### T2. Railway 部署（达成"点链接试用"）

**平台**：Railway。项目 `research-agent`（project id `a6fd7781-4999-44be-a545-4dcce5c3c115`，account `Cavalry`）。策略：先部署 api 服务验证后端，frontend 后补。

**api 服务 ✅ 已部署上线**
- 公开 URL：`https://api-production-c986.up.railway.app`（`/health`、`/docs` 浏览器可正常访问）。
- 关键坑（已修）：Dockerfile 原 `CMD` 写死 `--port 8000`，Railway 注入自己的 `$PORT`（实际 8080）导致边缘代理连不上 → **502**。已改为 shell 形式 `uvicorn ... --port ${PORT:-8000}` + HEALTHCHECK 读 `$PORT`；本地 docker-compose 无 `$PORT` 时回退 8000，行为不变。日志确认 `Uvicorn running on http://0.0.0.0:8080`。
- 已配 env（Railway Variables，加密存储，不进 git）：`LLM_*`（兜底 `LLM_API_KEY=sk-visitor-byok-required` 占位，强制访客 BYOK，零成本）、`EMBEDDING_PROVIDER=api` + SiliconFlow key + `BAAI/bge-m3`、`VECTOR_STORE=chroma`、存储路径。
- 部署命令：`railway add --service api` → `railway variables --service api --set ...` → `railway up --service api` → `railway domain --service api`。

**剩余待办**
- [ ] **Dockerfile 端口修复未提交 git**：当前改动只在本地工作区（Railway 用 `railway up` 直接上传了本地代码，但 git 未 commit）。需提交推 main，否则 CI/其他 clone 不含此修复。
- [ ] **持久卷**：确认 `app/storage` 卷已挂载（railway.toml 声明了，需验证 Railway 面板生效），否则重部署丢用户数据。
- [ ] **api 端到端验证**：用公开 URL → 上传 PDF → BYOK 填 key → 生成笔记 → QA 跑通（之前本地 Docker 验过 BYOK 铁证，Railway 上需复验一次，尤其 embedding API 模式首次真机跑）。
- [ ] **frontend 服务**：nginx 写死 `proxy_pass http://api:8000`（docker-compose 内网名），Railway 服务间要用 `RAILWAY_PRIVATE_DOMAIN`。需改 nginx 支持环境变量注入 API 地址，再 `railway up` 部署 frontend 服务。这是"完整前端站点"的前置。

### T3. 回填 Demo 链接

- [ ] Railway 拿到 URL 后，替换 `README.md` 顶部"在线 Demo"占位（api Swagger `…/docs` 可先作为临时入口；frontend 上线后换成前端 URL）。

### T4（可选）镜像瘦身

- [ ] api 镜像 3.84GB 偏大（jupyter/scipy/sklearn/streamlit 等运行时非必需）。拆到 dev extras 后可降到 ~1.5GB，利于 Railway 免费 tier。

---

## 如何接上进度（新会话恢复上下文）

1. 读本文件（权威计划）+ `docs/PRODUCTION_READINESS.md`（诚实差距清单）。
2. 确认 git 位置：产品化基于 `main`；`codex/qa-thread-memory` 是无关分支，别在上面改 CI。
3. 查 CI 现状：`gh run list --branch main --limit 3`；看失败日志：`gh run view <id> --log-failed`。
4. 优先做 T1（修 CI 绿）→ T2（Railway 部署）→ T3（回填 Demo 链接）。
5. 验证纪律（见 `CLAUDE.md`）：测试用 `research_agent` conda 环境的 python，排除 `tests/performance`；每步跑验证命令 + 看 `git diff`。

---

## 关键文件索引

| 文件 | 作用 |
|------|------|
| `LICENSE` | MIT 许可 |
| `Dockerfile` / `frontend/Dockerfile` / `docker-compose.yml` | 双服务部署 |
| `frontend/nginx.conf` | 前端反代 + 安全头 |
| `railway.toml` | Railway 部署配置 + env 清单 |
| `.github/workflows/tests.yml` / `release.yml` | CI + 发布流水线 |
| `app/services/llm_client.py` | BYOK contextvar + `UserLLMConfig` |
| `app/middleware/byok.py` | BYOK 请求头 → contextvar 中间件 |
| `app/config.py` | `embedding_base_url` / `embedding_api_key` 等 env 开关 |
| `app/services/embedding_client.py` | `embedding_provider=api` 分支 |
| `frontend/src/api/client.ts` | BYOK 头注入 |
| `frontend/src/pages/settings/SettingsPage.tsx` | BYOK 设置 UI |
| `docs/PRODUCTIZATION_PLAN.md` | 早期双轨草案（被 .gitignore 排除，未进 git） |
| `docs/PRODUCTION_READINESS.md` | 差距清单（已进 git） |

---

## 风险与未决

- **CI 全红**：面试官点开 Actions 观感差，T1 优先。
- **MVP gate report 仍 PENDING**（`README:28`）：research_pipeline 评估未跑完，Demo 上勿宣传"研究流水线"评估能力，只展示 paper-tools 主链。
- **BYOK Key 安全**：localStorage 明文（浏览器本地，公共电脑勿留）；后端不落盘、不入日志；公开站必须 HTTPS（Railway 自带）。
- **BackgroundTasks 不持久**：进程重启丢运行中任务（B5 未做），demo 可接受，真多用户需换 RQ+Redis。
- **embedding API 模式未真机验证**：切换 embedding provider/model 会改向量维度，需清空 `vector_db` 重建索引。
- **镜像 3.84GB**：Railway 免费 tier 前建议 T4 瘦身。
