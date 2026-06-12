# 开发问题记录

> 维护目的：记录 ResearchAgent 开发和调试过程中遇到的真实问题、影响、解决方式和后续预防措施，避免同类问题反复出现。
> 最近更新：2026-06-12

## 记录规范

- 新问题追加到本文顶部，保留时间、状态和验证证据。
- 只记录已经验证过的问题；不要仅凭终端乱码或猜测下结论。
- 如果问题依赖本机环境、外部账号、token 或第三方服务，需要明确标注“本地已处理”和“外部待处理”的边界。
- 本项目禁止批量删除文件或目录；清理临时文件时只能一次处理一个明确文件路径，目录清理交给用户确认后手动执行。

## 2026-06-12：Zotero API 端口没通时，ResearchAgent 读不到 collection

- 状态：本地已处理，今天验证通过。
- 现象：ResearchAgent 的 Zotero collection intake 看起来像是“拿不到文献”或者“Zotero 这一步没反应”，但代码本身不一定坏。它默认是去连本机 Zotero Desktop 暴露出来的 HTTP API，也就是 `http://127.0.0.1:23119/api`。
- 真正的问题：如果 Zotero 没开、Zotero 本地 API 没起来，或者 `23119` 这个端口没在监听，ResearchAgent 就没法从 Zotero 里拉 collection/items。这个问题很容易被误判成 MCP、Python 或 intake 代码的问题。
- 怎么查：先看端口有没有起来：

```powershell
cmd /c "netstat -ano -p tcp | findstr :23119"
```

  正常情况应该能看到 `127.0.0.1:23119 LISTENING`。

- 再直接打 Zotero local API：

```powershell
curl.exe -v "http://127.0.0.1:23119/api/users/0/items?limit=1"
```

  正常情况应该返回 `HTTP 200`。今天本机验证结果是：`netstat` 能看到 `127.0.0.1:23119 LISTENING`，`curl` 返回 `200`。
- 解决方式：先保证 Zotero Desktop 正常启动，再确认 `23119` 端口能访问。ResearchAgent 这边暂时不用改端口，因为当前 `ZoteroLocalHttpClient` 默认就是连 `http://127.0.0.1:23119/api`。
- 以后遇到类似问题：不要一上来就改 MCP 或 workflow 代码，先跑上面两条命令。只要 `23119` 不通，优先处理 Zotero 本地服务；端口通了再继续查 collection id、PDF attachment 或 workflow 逻辑。

## 2026-06-11：Research Run Major 问题修复

### 1. `/research-runs/tools/call` 只暴露工具名，没有接入真实后端

- 状态：已解决。
- 现象：`research_agent.search_chunks` 默认返回空列表，`research_agent.answer_question` 和 `research_agent.compare_papers` 返回静态 fallback 文案；API 表面看起来可用，但没有真正调用检索、QA、论文对比后端。
- 影响：MCP façade 无法作为真实 ResearchAgent 工具入口，前端或外部 agent 调用时会得到假成功或低价值结果。
- 解决方式：在 `app/routers/research_runs.py` 增加向量库、Embedding、LLM、reranker、retriever 的依赖注入，并把 `app.services.paper_qa.answer_question` 与 `app.services.paper_compare.compare_papers` 接入 `ResearchAgentMCPServer`。
- 关键点：`run_id` 只作为运行上下文，不能当成 `paper_id` 使用；检索和 QA 支持显式 `paper_id` 参数。
- 验证：新增 router 测试覆盖 search / QA / compare 后端注入；相关测试集 `84 passed`。

### 2. `execute_local_run()` 中 synthesis / Obsidian publish 异常会冒泡成 500

- 状态：已解决。
- 现象：`KnowledgePackSynthesisService().generate()`、`write_synthesis_files()` 或 Obsidian Markdown 发布失败时，异常直接向上抛出，run 状态没有可靠落盘。
- 影响：用户看到 500，但 `research_runs.json`、run summary、trace 和 step error 可能停留在过时状态，后续排查困难。
- 解决方式：将 synthesis 和 Obsidian publish 包装为 registry tool dispatch；失败时统一调用 `_fail_run()`，持久化 run `status=failed`、`completed_at`、run error、对应 step error 和 tool-call error。
- 关键点：paper processing 的单篇失败仍然不中断整轮 run；只有 synthesis / publish 这种 run 级步骤失败才标记整轮 run failed。
- 验证：新增测试分别模拟 synthesis 失败和 Obsidian publish 失败，断言 run、step、trace、tool-calls 都记录错误。

### 3. Tool Registry 集成不完整

- 状态：已解决。
- 现象：`ToolRegistry` 只有 `research_agent.echo`，`execute_local_run()` 手写 tool-call JSONL，没有通过统一 registry dispatch。
- 影响：工具健康检查和实际执行链路脱节，后续接入 MCP、观测、fallback、错误归一化时会重复造逻辑。
- 解决方式：`execute_local_run()` 为本次 run 注册 `zotero.list_collection_items`、`research_agent.process_paper`、`research_agent.generate_knowledge_pack`、`obsidian.publish_knowledge_pack`，并通过 `ToolRegistry.dispatch()` 执行和记录。
- 关键点：默认 registry 只提供占位工具定义和 health 信息；真实 handler 由 run 执行时按依赖注入注册，避免默认 handler 在缺少运行期依赖时误执行。
- 验证：新增 registry dispatch 顺序测试，确认上述四个工具都被调用并写入标准 tool-call 字段。

### 4. 本地 Codex 配置中存在敏感 token 风险

- 状态：本地防误提交已处理；外部 token 轮换待用户在对应服务完成。
- 现象：本地 `.codex/config.toml` 可能包含 Anthropic 或 relay token。
- 影响：如果被纳入 Git，会造成密钥泄漏。
- 解决方式：`.gitignore` 忽略 `.codex/` 本地工具目录，防止 Codex 本地配置进入仓库。
- 边界：本地仓库无法完成上游 provider / relay 管理端的 token revoke 和 re-issue；真正轮换需要登录对应控制台生成新 token 并替换本机配置。
- 验证：`git status --short --untracked-files=all` 不再列出 `.codex/config.toml`。

## Windows 迁移与本地运行问题

### 5. WSL 环境无法可靠访问 Windows 下的 Zotero

- 状态：已通过迁移到 Windows 本地开发解决；原始错误栈和具体失败点未完整保留。
- 现象：项目早期在 WSL 上开发，但 Zotero 安装和数据主要在 Windows 用户环境中。尝试在 WSL 侧做本地修改和绕行适配后，仍然无法让 ResearchAgent 稳定访问 Windows 下的 Zotero。
- 影响：Zotero Collection Intake 是主工作流入口；如果 WSL 无法可靠读取 Zotero 数据或调用本机 Zotero 服务，后续论文理解、综合和 Obsidian 输出都无法形成端到端闭环。
- 解决方式：将 ResearchAgent 的主要开发和调试环境迁移到 Windows，让 Python 服务、Zotero、Obsidian 和本地文件系统处在同一用户环境中，减少跨 WSL/Windows 边界带来的路径、权限、进程和本机服务访问问题。
- 边界：当前记录只确认“WSL 访问 Windows Zotero 不可靠”这一结论；不要在没有重新复现的情况下补写具体协议、端口或权限原因。
- 预防：后续凡是涉及 Zotero、Obsidian、桌面应用或 Windows 用户目录的集成，默认优先在 Windows 原生环境验证；如果重新考虑 WSL，需要先做最小 Zotero smoke test，再投入大规模代码改造。

### 6. Windows 下使用错误 Python 环境导致导入或测试异常

- 状态：已形成固定处理方式。
- 现象：直接使用系统 Python、base Anaconda Python 或 `conda run` 时，可能出现依赖缺失、导入失败或 `UnicodeEncodeError`。
- 影响：容易把环境问题误判为产品代码问题。
- 解决方式：本仓库测试和导入检查优先使用固定解释器 `D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe`。
- 验证方式：使用该解释器执行 `python -m pytest ...`，避免通过 `conda run` 包一层。
- 预防：文档、脚本和后续调试记录中统一写明该解释器路径。

### 7. PowerShell 输出乱码容易误导文件编码判断

- 状态：已形成排查原则。
- 现象：PowerShell 中读取部分中文 Markdown 或 Python 文件时，控制台输出可能显示乱码。
- 影响：可能误判文件已经损坏，从而进行不必要的重写或修复。
- 解决方式：不要只看终端渲染结果；需要用 UTF-8 aware 的文件读取或编辑器直接确认文件内容。
- 预防：遇到“乱码”先验证文件真实字节和编码，再决定是否修复。

### 8. HuggingFace 本地模型缓存迁移后需要验证离线加载

- 状态：已验证过，后续仍需按环境复查。
- 现象：WSL 到 Windows 迁移后，Embedding / Reranker 模型缓存路径可能与 `.env` 或默认配置不一致。
- 影响：运行时可能下载失败、模型加载失败，或使用错误模型维度。
- 解决方式：优先验证当前 `.env` 是否已经指向本地缓存；不要主动修改 `.env`，除非用户明确要求。
- 验证方式：用项目解释器调用 `EmbeddingClient().embed_query("test")`，确认返回维度符合当前模型预期。

## 产品与集成方向问题

### 9. 功能列表分散，项目故事不够聚焦

- 状态：方向已收敛，仍需持续执行。
- 现象：项目容易被描述成普通 RAG、PDF 解析、对比和笔记导出的功能集合。
- 影响：作为简历项目或演示项目时，亮点不够集中，Agent / MCP 价值不明显。
- 解决方式：主线收敛为 `Zotero Collection -> Collection Intake -> Paper Understanding -> Literature Synthesis -> Experiment Planning -> Obsidian Publishing -> Knowledge Pack`。
- 预防：新增功能时优先服务这条 flagship workflow，避免扩散成泛化工具箱。

### 10. Obsidian 输出如果只有单页笔记，承载不了研究工作流结果

- 状态：已采用多页 Knowledge Pack 方向。
- 现象：单个 Markdown note 难以同时承载文献综述、方法矩阵、研究空白、实验计划和阅读路线。
- 影响：输出不利于复用，也不利于展示 agent 工作流的阶段产物。
- 解决方式：采用多页 Knowledge Pack，核心页面包括 Literature Review、Method Matrix、Research Gaps、Experiment Plan、Reading Roadmap。
- 预防：后续 Obsidian 发布逻辑应继续围绕多页结构，而不是退回单页摘要。

## 测试与验证问题

### 11. 先写实现再补测试容易漏掉真实失败路径

- 状态：已在本轮修复中采用红灯测试补强。
- 现象：旧测试只检查 route 存在、字段存在或调用成功，没有断言真实后端被调用，也没有覆盖 synthesis / publish 异常。
- 影响：接口可能“看起来可用”，但真实集成路径无效。
- 解决方式：先增加能失败的行为测试，再实现最小代码通过测试。
- 验证：本轮先看到新增测试失败，再修复到 `49 passed` 和相关测试集 `84 passed`。
- 预防：新增工具、endpoint 或 workflow step 时，测试至少覆盖成功路径、依赖注入路径和关键失败落盘路径。

## 后续维护清单

- 新增外部工具集成时，先定义 tool name、required args、health 语义，再接真实 handler。
- 对 run 级步骤，异常必须持久化到 run、step、trace 和 tool-calls，不能只依赖 HTTP status。
- 对本地敏感配置，只做 Git 防误提交不等于完成 token 轮换；外部 token 仍需在 provider / relay 控制台处理。
- 对 Windows 环境问题，先确认解释器、编码、路径和缓存，再判断产品代码是否有 bug。
